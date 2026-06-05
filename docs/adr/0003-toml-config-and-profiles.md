# ADR 0003: TOML Config And Profiles

## Status

Accepted.

## Context

The CLI needs reusable local settings without hiding which values are used.

## Decision

Profiles live in `~/.apiclient.toml` under `[profiles.NAME]`.

Precedence:

1. CLI flags
2. Environment variables
3. TOML profile values
4. Defaults

## Alternatives considered

- **JSON config.** TOML's section headers map more cleanly onto AWS-CLI-style
  named profiles, and Python's stdlib `tomllib` removes the dependency cost.
- **`.env` file.** Encourages a single global namespace; loses named profiles.
- **No config file, env-only.** Operationally fine for one machine; awkward
  when users want to keep several stable profiles (dev, staging, prod).
- **An external TOML writer (`tomli-w` / `tomlkit`).** Would buy formatting
  fidelity, but trades a stdlib-only build for a dependency. The hand-written
  dumper is intentionally tiny and only emits scalars + named tables.

## Consequences

The config model stays simple and scriptable. The project avoids adding a TOML
writer dependency by writing simple profile files itself. The cost: any TOML
feature outside `[profiles.NAME]` scalars (arrays of tables, inline arrays,
non-scalar values) is rejected at write-time rather than silently rewritten.
