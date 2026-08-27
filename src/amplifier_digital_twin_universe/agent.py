"""The model-backed path, on top of the amplifier-agent engine.

Everything here is confined to this module so the rest of the library stays
importable, and runnable, with no model provider configured.

`import amplifier_agent_lib` overwrites `os.environ["AMPLIFIER_HOME"]` at import
time. Every import of it is therefore deferred into a function body, so merely
importing this package cannot disturb a host that uses that variable.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import os
import sys
from typing import Any
import uuid

from amplifier_digital_twin_universe.errors import MissingPrerequisiteError, NoProviderError

WORKSPACE = "amplifier-digital-twin-universe"


@dataclass(frozen=True)
class TurnResult:
    """One completed model turn."""

    reply: str
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal | None

    def usage(self) -> dict[str, Any]:
        return {
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": None if self.cost_usd is None else str(self.cost_usd),
        }


def available_providers() -> list[str]:
    """Providers whose credentials resolve in this environment.

    Deterministic. Reads credentials but calls no model.
    """
    from amplifier_agent_cli.provider_sources import enumerate_resolvable_providers

    return list(enumerate_resolvable_providers())


def require_provider(preferred: str | None = None) -> str:
    """Pick a usable provider, or fail naming what to configure.

    The check happens before any model call so a caller with no credentials gets
    a precise failure rather than an authentication error from deep inside a
    provider module.
    """
    resolvable = available_providers()
    if preferred:
        if preferred not in resolvable:
            raise NoProviderError(
                f"Model provider {preferred!r} has no resolvable credentials.",
                f"Set the credential environment variable for {preferred!r}, "
                f"or choose one of: {', '.join(resolvable) or 'none available'}.",
            )
        return preferred
    if not resolvable:
        raise NoProviderError(
            "This capability is model-backed and no model provider is configured.",
            "Set ANTHROPIC_API_KEY (or OPENAI_API_KEY, GOOGLE_API_KEY, AZURE_OPENAI_API_KEY) and run again.",
        )
    return resolvable[0]


async def run_turn(
    prompt: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> TurnResult:
    """Run one single-shot model turn and return its reply.

    Model-backed. Consumes tokens and may return a different answer on a second
    run. Each call is a fresh engine with an ephemeral session, so turns carry no
    state between them and identical input produces an identical request.
    """
    _require_git()
    provider_name = require_provider(provider)

    from amplifier_agent_cli.provider_sources import inject_provider, inject_routing_matrix
    from amplifier_agent_lib import __version__
    from amplifier_agent_lib._runtime import make_turn_handler
    from amplifier_agent_lib.bundle.cache import load_and_prepare_cached
    from amplifier_agent_lib.engine import Engine
    from amplifier_agent_lib.protocol import PROTOCOL_VERSION, server_default_capabilities
    from amplifier_agent_lib.protocol_points.defaults_cli import ApprovalOverride, CliApprovalSystem, CliDisplaySystem

    prepared = await load_and_prepare_cached(aaa_version=__version__)

    # The vendored bundle declares provider stubs, and injection is a no-op while
    # any provider is mounted. Without this clear the injection is discarded.
    prepared.mount_plan["providers"] = []
    inject_provider(prepared, provider_name, model_override=model)
    inject_routing_matrix(prepared, provider_name)

    handler = make_turn_handler(prepared, cwd=None, is_resumed=False, workspace=WORKSPACE)
    engine = Engine(
        turn_handler=handler,
        protocol_points={
            # `mode="yes"` is stored but never read by the shipped approval
            # system, so it declines everything. `override` is the parameter that
            # actually decides.
            "approval": CliApprovalSystem(override=ApprovalOverride.YES),
            "display": CliDisplaySystem(stream=sys.stderr, verbosity="quiet"),
        },
    )
    await engine.boot(
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": dict(server_default_capabilities()),
            "sessionId": "",
            "resume": False,
        },
        bundle_override=prepared,
    )
    try:
        result = await engine.submit_turn({"sessionId": "", "turnId": f"turn-{uuid.uuid4().hex}", "prompt": prompt})
    finally:
        await engine.shutdown()

    return TurnResult(
        reply=result.get("reply") or "",
        tokens_in=int(result.get("tokensIn") or 0),
        tokens_out=int(result.get("tokensOut") or 0),
        cost_usd=result.get("costUsd"),
    )


def _require_git() -> None:
    """The engine fetches its modules by cloning, so git must be on PATH."""
    from shutil import which

    if which("git") is None:
        raise MissingPrerequisiteError(
            "git was not found on PATH.",
            "Install git. The agent engine fetches its modules by cloning repositories.",
        )


def preferred_model() -> str | None:
    """An explicit model override, when the caller set one in the environment."""
    return os.environ.get("AMPLIFIER_DTU_MODEL") or None
