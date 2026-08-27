"""The bottled DTU profile authoring expertise.

The guide ships inside the package and is read through this accessor rather than
by locating a file, for the same reason the manifest is: install layouts differ
by ecosystem and no filesystem path is portable across them.
"""

from __future__ import annotations

from functools import lru_cache
import importlib.resources as resources

GUIDE_FILENAME = "profile-authoring.md"


@lru_cache(maxsize=1)
def authoring_guide() -> str:
    """The profile authoring guide, as prompt material.

    Deterministic. Requires no model provider.
    """
    return (
        resources.files("amplifier_digital_twin_universe.knowledge")
        .joinpath(GUIDE_FILENAME)
        .read_text(encoding="utf-8")
    )
