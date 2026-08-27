---
smart_tool_format: 1
name: amplifier-digital-twin-universe
version: 0.1.0
description: >
  Stands up isolated, realistic environments from a declarative profile so software
  can be tested as though actually deployed. Use when "tests pass locally" is not
  enough evidence and you need to exercise code the way a real deployment would.
use_cases:
  - Turn a description of what you want to test into a launchable environment profile
  - Test a web app in a container that mirrors its real deployment
  - Simulate an end-user environment without touching production
  - Verify a CLI tool installs and runs cleanly from scratch
  - Exercise code against mocked third-party services without changing its configuration
platforms:
  - linux
requires:
  - name: incus
    purpose: Runs the isolated environments.
    install: docs/installing-incus.md
  - name: git
    purpose: Fetches the agent engine's modules. Profile authoring cannot run without it.
    install: https://git-scm.com/downloads
  - name: docker
    purpose: Runs mock service sidecars. Without it, profiles declaring sidecars cannot launch.
    optional: true
    install: docs/installing-docker.md
---

# amplifier-digital-twin-universe

A Digital Twin Universe (DTU) is a complete, isolated environment stood up on demand
from a declarative profile. It closes the gap between "the tests pass on my machine"
and "this works where it will actually run."

## When this is the right choice

Reach for this when the thing you want to verify depends on its environment: a service
that must resolve real hostnames, a CLI that must install from scratch, a web app whose
behavior differs behind a proxy. A unit test cannot tell you any of that.

Do not reach for it for pure logic you can test in-process. Standing up an environment
costs seconds to minutes; a function call costs microseconds.

## Sharp edges

- Environments are ephemeral. Anything you want to keep must be pulled out before teardown.
- `incus` is a hard prerequisite. The tool detects its absence and fails naming the remedy
  rather than guessing.
- Without `docker`, profiles that declare sidecars cannot launch. Everything else still works.
