---
name: amplifier-digital-twin-universe
description: >-
  Stand up isolated, realistic environments from a declarative profile so
  software can be tested as though actually deployed. Use when (1) "the tests
  pass on my machine" is not enough evidence and code must be exercised the way
  a real deployment would exercise it, (2) verifying a CLI or service installs
  and runs cleanly from scratch, (3) exercising code against mocked third-party
  services without changing its configuration, (4) driving the
  amplifier-digital-twin-universe smart tool from a library, a CLI, or an agent.
  Triggers on "digital twin", "DTU", "digital twin universe", "isolated
  environment", "incus container", "test as if deployed", "amplifier-digital-twin-universe".
license: MIT
metadata:
  author: DavidKoleczek
  version: "0.1.0"
  repository: https://github.com/DavidKoleczek/amplifier-smart-tool-digital-twin-universe
---

# Using amplifier-digital-twin-universe

A Digital Twin Universe (DTU) is a complete, isolated environment stood up on demand
from a declarative profile. It closes the gap between "the tests pass on my machine"
and "this works where it will actually run."

**The library is the tool.** `amplifier_digital_twin_universe` holds every capability.
The CLI is a thin wrapper over it and adds nothing of its own, so anything you can do
from the shell you can also do from Python.

## Before writing code

Confirm every capability, argument, and field name against `--help` or the library's
own signatures before you write it. Do not fill gaps from memory.

```bash
amplifier-digital-twin-universe --help
```

`--help` is the complete, agent-facing listing: every capability, its arguments, what
it returns, and which capabilities are model-backed. `-h` is a short summary for a
person and is deliberately not the same output. If you cannot confirm something from
`--help` or the source, say so rather than guessing.

| Need | Source |
|---|---|
| What the tool is for and what it needs | <https://github.com/DavidKoleczek/amplifier-smart-tool-digital-twin-universe/blob/main/SMART_TOOL.md> |
| Installing the required prerequisite | <https://github.com/DavidKoleczek/amplifier-smart-tool-digital-twin-universe/blob/main/docs/installing-incus.md> |
| Installing the optional prerequisite | <https://github.com/DavidKoleczek/amplifier-smart-tool-digital-twin-universe/blob/main/docs/installing-docker.md> |

## Install

As a CLI:

```bash
uv tool install git+https://github.com/DavidKoleczek/amplifier-smart-tool-digital-twin-universe
```

As a library:

```bash
uv add "amplifier-digital-twin-universe @ git+https://github.com/DavidKoleczek/amplifier-smart-tool-digital-twin-universe"
```

## Prerequisites

`incus` is required and runs the environments. Without it nothing can launch, and the
tool fails naming the remedy rather than guessing.

`docker` is optional and runs mock service sidecars. Without it, everything works
except profiles that declare sidecars.

Linux only. The tool does not claim platforms it has not been run on.

## Reading the manifest

The manifest says what the tool is for and what it needs, so a caller can decide
whether to reach for it before invoking anything. It is reachable two ways.

```bash
amplifier-digital-twin-universe manifest
```

```python
from amplifier_digital_twin_universe import load_manifest

manifest = load_manifest()
manifest.name, manifest.version, manifest.platforms
manifest.to_dict()  # plain data, JSON-serializable
```

Read it through the library rather than by locating a file. Install layouts differ by
ecosystem and no filesystem path is portable across them.

## Output and failure contract

Every CLI capability writes exactly one JSON document to stdout.

A failure writes a structured envelope and exits non-zero. Never parse prose out of it,
and never treat an empty result as success.

```json
{"error": {"code": "no_provider", "message": "...", "remedy": "..."}}
```

```
0  success
2  bad invocation
3  a model-backed capability was called with no provider configured
4  a required prerequisite is missing
5  the capability ran and failed
```

A model-backed capability with no provider configured fails saying exactly that and
names what to configure. It never falls back to a degraded deterministic answer, so a
result you receive is always the result you asked for.

## Choosing a surface

Import the library from Python. Shell out to the CLI from anything that cannot import
Python in-process: a shell script, a CI job, or an agent that can run commands but not
load a Python object. Both reach the same capabilities.
