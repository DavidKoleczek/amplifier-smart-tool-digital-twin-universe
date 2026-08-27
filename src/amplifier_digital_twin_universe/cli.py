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
from typing import Any, NoReturn

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

    Failures must be structured and must name a remedy, never a bare usage dump
    on stderr, never a stack trace.
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

# `--help` is the complete, agent-facing listing. `-h` is the terse user summary.
# They are not aliases.
_FULL_HELP = (
    "Capabilities:\n"
    "  manifest          [deterministic]  Emit this tool's manifest as structured data.\n"
    "                    args: none\n"
    '                    returns: {"result": {smart_tool_format, name, version,\n'
    "                             description, use_cases[], platforms[], requires[]}}\n"
    "\n"
    "  validate-profile  [deterministic]  Check whether a profile document is launchable.\n"
    "                    args: --file PATH|- (required), --var KEY=VALUE (repeatable)\n"
    '                    returns: {"result": {valid: bool, name, description,\n'
    "                             errors[], warnings[], unresolved_variables[]}}\n"
    "                    exit: 0 when valid, 5 when not\n"
    "\n"
    "  create-profile    [model-backed]   Draft a launchable profile from a description.\n"
    "                    args: --description TEXT (required), --context-file PATH,\n"
    "                          --var KEY=VALUE (repeatable), --out PATH,\n"
    f"                          --max-attempts N (default {DEFAULT_MAX_ATTEMPTS}), "
    "--provider NAME, --model NAME\n"
    '                    returns: {"result": {yaml, name, description, attempts,\n'
    "                             warnings[], unresolved_variables[], usage{}, path?}}\n"
    "                    Each draft is validated by the engine's own profile loader\n"
    "                    and repaired until it parses cleanly or the budget is spent.\n"
    "\n"
    f"{_MODEL_BACKED_LINE}"
    "\n"
    "Output: one JSON document on stdout. Failures emit\n"
    '{"error": {"code", "message", "remedy"}} and exit non-zero.\n'
    "\n"
    "Exit codes: 0 success, 2 bad invocation, 3 no model provider configured,\n"
    "4 missing prerequisite, 5 the capability ran and failed.\n"
)


class _TerseHelpAction(argparse.Action):
    """`-h` prints the short summary; `--help` prints the complete listing."""

    def __init__(self, option_strings: list[str], dest: str, **kwargs: Any) -> None:
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser: argparse.ArgumentParser, *_rest: Any) -> NoReturn:
        sys.stdout.write(
            f"{PROG} -- {_TERSE}\n"
            "\nCapabilities:\n"
            "  manifest           Emit this tool's manifest.\n"
            "  validate-profile   Check whether a profile is launchable.\n"
            "  create-profile     Draft a launchable profile from a description.\n"
            f"\nRun '{PROG} --help' for the complete listing.\n"
        )
        raise SystemExit(EXIT_OK)


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

    p_manifest = sub.add_parser("manifest", help="[deterministic] Emit this tool's manifest as structured data.")
    p_manifest.set_defaults(func=cmd_manifest)

    p_validate = sub.add_parser(
        "validate-profile",
        help="[deterministic] Check whether a profile document is launchable.",
    )
    p_validate.add_argument("--file", required=True, help="Path to the profile YAML, or '-' for stdin.")
    p_validate.add_argument("--var", action="append", metavar="KEY=VALUE", help="Launch variable. Repeatable.")
    p_validate.set_defaults(func=cmd_validate_profile)

    p_create = sub.add_parser(
        "create-profile",
        help="[model-backed] Draft a launchable profile from a description.",
    )
    p_create.add_argument("--description", required=True, help="What you want to stand up and test.")
    p_create.add_argument("--context-file", help="Path to extra material for the model, read into the payload.")
    p_create.add_argument("--var", action="append", metavar="KEY=VALUE", help="Launch variable. Repeatable.")
    p_create.add_argument("--out", help="Write the profile YAML here and report the path.")
    p_create.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=f"Draft-and-repair budget (default {DEFAULT_MAX_ATTEMPTS}).",
    )
    p_create.add_argument("--provider", help="Model provider to use.")
    p_create.add_argument("--model", help="Model to use.")
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
