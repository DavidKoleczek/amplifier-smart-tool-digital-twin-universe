"""Amplifier Digital Twin Universe -- a smart tool.

The library is the tool. Every capability lives here; the CLI and any other
surface are thin adapters over this package and add nothing of their own.

Nothing in this module requires a model provider at import time. Model-backed
capabilities fail loudly, naming the remedy, only when actually invoked.
"""

from amplifier_digital_twin_universe.create import ProfileDraft, create_profile, create_profile_async
from amplifier_digital_twin_universe.errors import (
    GenerationFailedError,
    MissingPrerequisiteError,
    NoProviderError,
    ProfileInvalidError,
    SmartToolError,
)
from amplifier_digital_twin_universe.manifest import Manifest, Requirement, load_manifest
from amplifier_digital_twin_universe.profiles import ValidationReport, validate_profile

__all__ = [
    "MODEL_BACKED_CAPABILITIES",
    "GenerationFailedError",
    "Manifest",
    "MissingPrerequisiteError",
    "NoProviderError",
    "ProfileDraft",
    "ProfileInvalidError",
    "Requirement",
    "SmartToolError",
    "ValidationReport",
    "create_profile",
    "create_profile_async",
    "load_manifest",
    "validate_profile",
]

# Which capabilities consult a model. Declared here so a caller can read it
# programmatically and make cost / determinism decisions before invoking.
# Everything not listed is deterministic and runs with no provider configured.
MODEL_BACKED_CAPABILITIES: tuple[str, ...] = ("create_profile",)
