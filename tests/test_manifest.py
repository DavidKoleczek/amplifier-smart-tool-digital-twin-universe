"""The manifest is a contract, so it gets tested like one."""

import json
import subprocess
import sys

from amplifier_digital_twin_universe import MODEL_BACKED_CAPABILITIES
from amplifier_digital_twin_universe.cli import main
from amplifier_digital_twin_universe.manifest import load_manifest, package_version


def test_manifest_loads_through_the_library() -> None:
    manifest = load_manifest()
    assert manifest.smart_tool_format == 1
    assert manifest.name == "amplifier-digital-twin-universe"
    assert manifest.description
    assert manifest.use_cases
    assert manifest.platforms


def test_manifest_version_matches_the_package_definition() -> None:
    assert load_manifest().version == package_version()


def test_required_prerequisite_is_declared_with_a_doc_reference() -> None:
    incus = next(r for r in load_manifest().requires if r.name == "incus")
    assert incus.optional is False
    assert incus.install.endswith(".md")


def test_optional_prerequisite_states_what_is_lost() -> None:
    docker = next(r for r in load_manifest().requires if r.name == "docker")
    assert docker.optional is True
    assert "without it" in docker.purpose.lower()


def test_cli_manifest_capability_emits_structured_output(capsys) -> None:
    assert main(["manifest"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["result"]["name"] == "amplifier-digital-twin-universe"


def test_bad_invocation_emits_an_error_envelope_naming_a_remedy(capsys) -> None:
    assert main([]) == 2
    error = json.loads(capsys.readouterr().out)["error"]
    assert error["code"] == "no_capability"
    assert error["remedy"]


def test_full_help_discloses_model_backed_capabilities() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "amplifier_digital_twin_universe.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "model-backed" in completed.stdout.lower()


def test_terse_and_full_help_are_not_aliases() -> None:
    argv = [sys.executable, "-m", "amplifier_digital_twin_universe.cli"]
    terse = subprocess.run([*argv, "-h"], capture_output=True, text=True, check=False)
    full = subprocess.run([*argv, "--help"], capture_output=True, text=True, check=False)
    assert terse.stdout != full.stdout
    assert len(full.stdout) > len(terse.stdout)


def test_help_disclosure_matches_the_declared_model_backed_capabilities() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "amplifier_digital_twin_universe.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    for capability in MODEL_BACKED_CAPABILITIES:
        assert capability in completed.stdout
