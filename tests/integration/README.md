# Integration Tests

This folder contains integration tests that validate repo wiring across modules and scripts.

Execution model:
- Local default (`pytest`) excludes integration tests.
- Explicit run: `pytest tests/integration -m integration --runintegration`
- CI runs these tests in a dedicated `integration-scaffold` job.

Guidelines:
- Keep tests deterministic and side-effect free by default.
- Mock network and external APIs unless a dedicated environment is provided.
- Prefer validating boundaries (config, orchestration, scripts) over internals.
