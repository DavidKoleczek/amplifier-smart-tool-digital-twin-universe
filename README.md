# Digital Twin Universe Smart Tool

A [Smart Tool](https://github.com/microsoft/amplifier-smart-tools) that stands up
isolated, realistic environments from a declarative profile, so software can be tested
as though actually deployed. Every capability lives in the `amplifier_digital_twin_universe`
library; the CLI is a thin wrapper over it and adds nothing of its own.

## Installation

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/), and
[Incus](docs/installing-incus.md) to launch anything.

```bash
# as a CLI
uv tool install git+https://github.com/DavidKoleczek/amplifier-smart-tool-digital-twin-universe

# as a library
uv add "amplifier-digital-twin-universe @ git+https://github.com/DavidKoleczek/amplifier-smart-tool-digital-twin-universe"

# as a skill, for a coding agent
npx skills add DavidKoleczek/amplifier-smart-tool-digital-twin-universe
```

Verify with `amplifier-digital-twin-universe manifest`, which needs no prerequisites
and no credentials. To upgrade, run `uv tool upgrade amplifier-digital-twin-universe`.

## Interface

```bash
# what this host can do, and ordered steps to fix what it cannot
amplifier-digital-twin-universe check
amplifier-digital-twin-universe install --goal "test a web service"

# author a profile from a description, and check one you already have
amplifier-digital-twin-universe create-profile --description "a FastAPI app on port 8000" --out profile.yaml
amplifier-digital-twin-universe validate-profile --file profile.yaml

# the environment lifecycle
amplifier-digital-twin-universe launch --profile profile.yaml
amplifier-digital-twin-universe list
amplifier-digital-twin-universe status --id dtu-1a2b3c4d
amplifier-digital-twin-universe check-readiness --id dtu-1a2b3c4d
amplifier-digital-twin-universe exec --id dtu-1a2b3c4d --command "curl -sf localhost:8000/health"
amplifier-digital-twin-universe file-push --id dtu-1a2b3c4d --source ./src --destination /workspace --recursive
amplifier-digital-twin-universe file-pull --id dtu-1a2b3c4d --source /var/log/app.log --destination ./
amplifier-digital-twin-universe update --id dtu-1a2b3c4d
amplifier-digital-twin-universe destroy --id dtu-1a2b3c4d

# work out what is wrong, and drive the lifecycle from a request in words
amplifier-digital-twin-universe doctor --symptom "the container has no outbound network"
amplifier-digital-twin-universe manage --request "tear down every stopped environment" --confirmed
```

Every result is one JSON document on stdout. `-h` is the terse summary for a person;
`--help` is the complete listing for an agent. See the
[CLI reference](docs/03-cli.md) for every flag, and the
[library reference](docs/01-library.md) for the same capabilities as Python.

## Configuration

`create-profile`, `install`, `doctor`, and `manage` are model-backed and need a model
provider configured in the environment, such as `ANTHROPIC_API_KEY`. Everything else is
deterministic and needs nothing. See
[docs/02-configuration.md](docs/02-configuration.md) for provider and model selection
and the environment variables this tool reads.

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).
