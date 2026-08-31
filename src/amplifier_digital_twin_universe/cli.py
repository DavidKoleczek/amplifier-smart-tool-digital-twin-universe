"""Thin CLI over the library.

Argument parsing, I/O conventions, and structured output live here. Domain logic
does not: anything the CLI can do, the library can do. Results go to stdout as
JSON; failures go to stdout as a JSON error envelope with a non-zero exit code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import textwrap
from typing import Any, NamedTuple, NoReturn

from amplifier_digital_twin_universe import MODEL_BACKED_CAPABILITIES
from amplifier_digital_twin_universe.create import DEFAULT_MAX_ATTEMPTS, create_profile
from amplifier_digital_twin_universe.errors import (
    GenerationFailedError,
    MissingPrerequisiteError,
    NoProviderError,
    SmartToolError,
)
from amplifier_digital_twin_universe.manifest import ManifestError, load_manifest
from amplifier_digital_twin_universe.profiles import validate_profile

PROG = "amplifier-digital-twin-universe"

EXIT_OK = 0
EXIT_BAD_INVOCATION = 2
EXIT_NO_PROVIDER = 3
EXIT_MISSING_PREREQUISITE = 4
EXIT_FAILED = 5

_EXIT_FOR_ERROR = {
    NoProviderError: EXIT_NO_PROVIDER,
    MissingPrerequisiteError: EXIT_MISSING_PREREQUISITE,
}


def _emit(document: dict[str, Any]) -> None:
    """Write exactly one JSON document to stdout, newline-terminated."""
    json.dump(document, sys.stdout, sort_keys=True, default=str)
    sys.stdout.write("\n")


def _emit_error(code: str, message: str, remedy: str, exit_code: int, **extra: Any) -> int:
    _emit({"error": {"code": code, "message": message, "remedy": remedy, **extra}})
    return exit_code


class _EnvelopeParser(argparse.ArgumentParser):
    """argparse parser that reports bad invocations as JSON envelopes on stdout.

    argparse's own handling prints a usage dump and exits 2. The exit code is the
    part a caller can rely on, so it is kept; the dump is replaced with the same
    envelope every other failure emits, carrying a code to branch on and a remedy
    to act on.
    """

    def error(self, message: str) -> NoReturn:
        _emit_error(
            "bad_invocation",
            message,
            f"Run '{PROG} --help' for the full list of capabilities and their arguments.",
            EXIT_BAD_INVOCATION,
        )
        raise SystemExit(EXIT_BAD_INVOCATION)


def cmd_manifest(_args: argparse.Namespace) -> int:
    """[deterministic] Emit this tool's manifest as structured data."""
    try:
        manifest = load_manifest()
    except ManifestError as exc:
        return _emit_error(
            "manifest_unreadable",
            str(exc),
            "Reinstall the tool so its manifest ships with the package.",
            EXIT_FAILED,
        )
    _emit({"result": manifest.to_dict()})
    return EXIT_OK


def cmd_validate_profile(args: argparse.Namespace) -> int:
    """[deterministic] Check whether a profile document is launchable."""
    try:
        yaml_text = _read_source(args.file)
    except OSError as exc:
        return _emit_error(
            "unreadable_input",
            str(exc),
            "Pass a readable path to --file, or '-' to read the profile from stdin.",
            EXIT_BAD_INVOCATION,
        )
    # Sources resolve against the profile's own directory, as they do at launch.
    base_dir = None if args.file == "-" else Path(args.file).resolve().parent
    report = validate_profile(yaml_text, _parse_vars(args.var), base_dir=base_dir)
    _emit({"result": report.to_dict()})
    return EXIT_OK if report.valid else EXIT_FAILED


def cmd_create_profile(args: argparse.Namespace) -> int:
    """[model-backed] Draft a launchable profile from a description."""
    context = None
    if args.context_file:
        try:
            context = _read_source(args.context_file)
        except OSError as exc:
            return _emit_error(
                "unreadable_input",
                str(exc),
                "Pass a readable path to --context-file.",
                EXIT_BAD_INVOCATION,
            )
    try:
        draft = create_profile(
            args.description,
            context=context,
            variables=_parse_vars(args.var),
            max_attempts=args.max_attempts,
            provider=args.provider,
            model=args.model,
        )
    except GenerationFailedError as exc:
        return _emit_error(exc.code, exc.message, exc.remedy, EXIT_FAILED, attempts=exc.attempts)
    except SmartToolError as exc:
        return _emit_error(exc.code, exc.message, exc.remedy, _EXIT_FOR_ERROR.get(type(exc), EXIT_FAILED))

    result = draft.to_dict()
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(draft.yaml_text, encoding="utf-8")
        # A capability that produces an artifact identifies it rather than
        # embedding it in a message.
        result["path"] = str(out)
    _emit({"result": result})
    return EXIT_OK


def _read_source(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def _parse_vars(pairs: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs or []:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise SystemExit(
                _emit_error(
                    "bad_invocation",
                    f"--var expects KEY=VALUE, got {pair!r}.",
                    "Pass each variable as --var NAME=value.",
                    EXIT_BAD_INVOCATION,
                )
            )
        out[key] = value
    return out


_TERSE = "Stand up isolated, realistic environments from a declarative profile."

_MODEL_BACKED_LINE = (
    "Model-backed capabilities: "
    + ", ".join(MODEL_BACKED_CAPABILITIES)
    + ". These consume tokens and\nmay return a different answer on a second run. They fail rather than degrade\n"
    "when no provider is configured. Every other capability is deterministic and\n"
    "runs with no model provider configured.\n"
    if MODEL_BACKED_CAPABILITIES
    else "No capability is model-backed. Every capability listed above is deterministic\n"
    "and runs with no model provider configured.\n"
)

_OUTPUT_NOTE = (
    'Output: one JSON document on stdout. Failures emit\n{"error": {"code", "message", "remedy"}} and exit non-zero.\n'
)

_MODEL_BACKED_NOTE = (
    "This capability is model-backed: it consumes tokens and may return a different\n"
    "answer on a second run. It fails rather than degrades when no model provider is\n"
    "configured.\n"
)

_DETERMINISTIC_NOTE = (
    "This capability is deterministic: it returns the same answer every time and\n"
    "runs with no model provider configured.\n"
)

_HELP_WIDTH = 78

# Column layout for the compact per-capability blocks in the top-level listing.
_NAME_COLUMN = 18
_KIND_COLUMN = 17
_FIELD_INDENT = " " * (2 + _NAME_COLUMN)


class _Capability(NamedTuple):
    """What a caller needs to know to invoke one capability.

    One record feeds both readers: the top-level `--help` listing renders it
    compactly alongside its siblings, and the capability's own `--help` renders
    it in full. Neither restates the other's text.
    """

    name: str
    summary: str
    args: tuple[str, ...]
    returns: str
    exits: tuple[str, ...]
    notes: tuple[str, ...] = ()

    @property
    def model_backed(self) -> bool:
        # The declaration is made against the library's names, so the CLI asks
        # in those terms rather than keeping a second list of its own.
        return self.name.replace("-", "_") in MODEL_BACKED_CAPABILITIES

    @property
    def kind(self) -> str:
        return "model-backed" if self.model_backed else "deterministic"

    @property
    def usage_parts(self) -> list[str]:
        """The usage line as tokens, so wrapping never splits one apart."""
        parts = [f"{PROG} {self.name}"]
        for arg in self.args:
            spec, _, qualifier = arg.partition(" (")
            qualifier = qualifier.rstrip(")")
            if qualifier == "required":
                parts.append(spec)
            elif qualifier == "repeatable":
                parts.append(f"[{spec} ...]")
            else:
                parts.append(f"[{spec}]")
        return parts


_CAPABILITIES = (
    _Capability(
        name="manifest",
        summary="Emit this tool's manifest as structured data.",
        args=(),
        returns=('{"result": {smart_tool_format, name, version, description, use_cases[], platforms[], requires[]}}'),
        exits=(
            "0 the manifest was emitted",
            "2 the invocation was bad",
            "5 the manifest could not be read",
        ),
    ),
    _Capability(
        name="validate-profile",
        summary="Check whether a profile document is launchable.",
        args=("--file PATH|- (required)", "--var KEY=VALUE (repeatable)"),
        returns=('{"result": {valid: bool, name, description, errors[], warnings[], unresolved_variables[]}}'),
        exits=(
            "0 the profile is launchable",
            "2 the invocation was bad or the profile could not be read",
            "5 the profile is not launchable",
        ),
    ),
    _Capability(
        name="create-profile",
        summary="Draft a launchable profile from a description.",
        args=(
            "--description TEXT (required)",
            "--context-file PATH",
            "--var KEY=VALUE (repeatable)",
            "--out PATH",
            f"--max-attempts N (default {DEFAULT_MAX_ATTEMPTS})",
            "--provider NAME",
            "--model NAME",
        ),
        returns=('{"result": {yaml, name, description, attempts, warnings[], unresolved_variables[], usage{}, path?}}'),
        exits=(
            "0 a profile was drafted",
            "2 the invocation was bad or the context file could not be read",
            "3 no model provider is configured",
            "4 a prerequisite is missing",
            "5 the draft budget was spent without a clean parse",
        ),
        notes=(
            (
                "Each draft is validated by the engine's own profile loader and repaired "
                "until it parses cleanly or the budget is spent."
            ),
        ),
    ),
)

_BY_NAME = {capability.name: capability for capability in _CAPABILITIES}


def _wrap(text: str, indent: str = "", continuation: str | None = None) -> list[str]:
    return textwrap.wrap(
        text,
        width=_HELP_WIDTH,
        initial_indent=indent,
        subsequent_indent=indent if continuation is None else continuation,
        break_long_words=False,
        break_on_hyphens=False,
    )


def _pack(tokens: list[str], indent: str, continuation: str) -> list[str]:
    """Fill lines with whole tokens. Tokens carry spaces, so wrapping cannot split one."""
    lines: list[str] = []
    current = indent
    for token in tokens:
        if current in (indent, continuation):
            current += token
        elif len(current) + 1 + len(token) <= _HELP_WIDTH:
            current += f" {token}"
        else:
            lines.append(current)
            current = continuation + token
    lines.append(current)
    return lines


def _tokens(items: tuple[str, ...], separator: str) -> list[str]:
    """Items as wrap tokens, each carrying the separator that follows it."""
    return [f"{item}{separator}" for item in items[:-1]] + list(items[-1:])


def _field(label: str, tokens: list[str]) -> list[str]:
    """A labelled field in the top-level listing, wrapped under its own label."""
    first, *rest = tokens
    return _pack([f"{label}: {first}", *rest], _FIELD_INDENT, _FIELD_INDENT + " " * (len(label) + 2))


def _compact_block(capability: _Capability) -> str:
    """One capability as it appears in the top-level `--help` listing."""
    kind = f"[{capability.kind}]"
    lines = [f"  {capability.name:<{_NAME_COLUMN}}{kind:<{_KIND_COLUMN}}{capability.summary}"]
    lines += _field("args", _tokens(capability.args, ",") or ["none"])
    lines += _field("returns", capability.returns.split(" "))
    lines += _field("exit", _tokens(capability.exits, ";"))
    for note in capability.notes:
        lines += _wrap(note, _FIELD_INDENT)
    return "\n".join(lines) + "\n"


def _capability_help(capability: _Capability) -> str:
    """One capability in full, for an agent deciding how to call it."""
    lines = [f"{PROG} {capability.name} -- [{capability.kind}] {capability.summary}", ""]
    lines += _pack(capability.usage_parts, "usage: ", " " * 7)
    lines += ["", "Arguments:"]
    lines += [f"  {arg}" for arg in capability.args] or ["  none"]
    lines += ["", "Returns:"]
    lines += _wrap(capability.returns, "  ", "    ")
    lines += ["", "Exit codes:"]
    lines += [f"  {code}" for code in capability.exits]
    for note in capability.notes:
        lines += ["", *_wrap(note)]
    disclosure = _MODEL_BACKED_NOTE if capability.model_backed else _DETERMINISTIC_NOTE
    lines += ["", *disclosure.rstrip("\n").split("\n")]
    lines += ["", *_OUTPUT_NOTE.rstrip("\n").split("\n")]
    return "\n".join(lines) + "\n"


# `--help` is the complete, agent-facing listing. `-h` is the terse user summary.
# They are not aliases, at either level.
_FULL_HELP = (
    "Capabilities:\n"
    + "\n".join(_compact_block(capability) for capability in _CAPABILITIES)
    + "\n"
    + _MODEL_BACKED_LINE
    + "\n"
    + _OUTPUT_NOTE
    + "\n"
    + "Exit codes: 0 success, 2 bad invocation, 3 no model provider configured,\n"
    + "4 missing prerequisite, 5 the capability ran and failed.\n"
)


class _TerseHelpAction(argparse.Action):
    """`-h` prints the short summary; `--help` prints the complete listing."""

    def __init__(self, option_strings: list[str], dest: str, **kwargs: Any) -> None:
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser: argparse.ArgumentParser, *_rest: Any) -> NoReturn:
        capabilities = "".join(f"  {capability.name:<19}{capability.summary}\n" for capability in _CAPABILITIES)
        sys.stdout.write(
            f"{PROG} -- {_TERSE}\n\nCapabilities:\n{capabilities}\nRun '{PROG} --help' for the complete listing.\n"
        )
        raise SystemExit(EXIT_OK)


class _CapabilityHelpAction(argparse.Action):
    """`--help` on a capability: everything needed to call that capability."""

    def __init__(self, option_strings: list[str], dest: str, capability: _Capability, **kwargs: Any) -> None:
        super().__init__(option_strings, dest, nargs=0, **kwargs)
        self.capability = capability

    def __call__(self, parser: argparse.ArgumentParser, *_rest: Any) -> NoReturn:
        sys.stdout.write(_capability_help(self.capability))
        raise SystemExit(EXIT_OK)


def _add_capability_parser(sub: argparse._SubParsersAction, name: str) -> argparse.ArgumentParser:
    """Register one capability with the same two-level help the top level has."""
    capability = _BY_NAME[name]
    label = f"[{capability.kind}] {capability.summary}"
    parser = sub.add_parser(name, help=label, description=label, add_help=False)
    parser.add_argument("-h", action="help", help="Terse summary for a person.")
    parser.add_argument(
        "--help",
        action=_CapabilityHelpAction,
        capability=capability,
        help="Everything an agent needs to call this capability.",
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = _EnvelopeParser(
        prog=PROG,
        description=_TERSE,
        epilog=_FULL_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument("-h", action=_TerseHelpAction, help="Terse summary for a person.")
    parser.add_argument(
        "--help",
        action="help",
        help="Complete capability listing for an agent deciding how to call this tool.",
    )

    sub = parser.add_subparsers(dest="capability")

    p_manifest = _add_capability_parser(sub, "manifest")
    p_manifest.set_defaults(func=cmd_manifest)

    p_validate = _add_capability_parser(sub, "validate-profile")
    p_validate.add_argument(
        "--file", metavar="PATH|-", required=True, help="Path to the profile YAML, or '-' for stdin."
    )
    p_validate.add_argument("--var", action="append", metavar="KEY=VALUE", help="Launch variable. Repeatable.")
    p_validate.set_defaults(func=cmd_validate_profile)

    p_create = _add_capability_parser(sub, "create-profile")
    p_create.add_argument("--description", metavar="TEXT", required=True, help="What you want to stand up and test.")
    p_create.add_argument(
        "--context-file", metavar="PATH", help="Path to extra material for the model, read into the payload."
    )
    p_create.add_argument("--var", action="append", metavar="KEY=VALUE", help="Launch variable. Repeatable.")
    p_create.add_argument("--out", metavar="PATH", help="Write the profile YAML here and report the path.")
    p_create.add_argument(
        "--max-attempts",
        metavar="N",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=f"Draft-and-repair budget (default {DEFAULT_MAX_ATTEMPTS}).",
    )
    p_create.add_argument("--provider", metavar="NAME", help="Model provider to use.")
    p_create.add_argument("--model", metavar="NAME", help="Model to use.")
    p_create.set_defaults(func=cmd_create_profile)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "capability", None):
        return _emit_error(
            "no_capability",
            "No capability was named.",
            f"Run '{PROG} --help' to see the available capabilities.",
            EXIT_BAD_INVOCATION,
        )
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
