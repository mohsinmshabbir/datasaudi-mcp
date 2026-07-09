# Contributing to datasaudi-mcp

Thanks for your interest — contributions are welcome.

## Setup

You'll need [`uv`](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/mohsinmshabbir/datasaudi-mcp
cd datasaudi-mcp
uv sync --all-extras
```

> **Important:** run tests through `uv run` (or an activated project venv), not a system
> Python. The async tests need the project's `pytest-asyncio`; running `pytest` with the
> wrong interpreter produces confusing async failures that are an environment issue, not a
> real bug.

## Tests

```bash
uv run pytest -m "not live"    # offline suite — no network; this is what CI runs
uv run pytest -m live          # optional: hits the real api.datasaudi.sa (needs network)
uv run ruff check src tests    # lint
```

- The **offline** suite is the source of truth and must stay green (it runs in CI on 3.12 and 3.13).
- **Live** tests are opt-in and validate behavior against the real API — run them when you
  touch the client or change how queries are built.

## Design principles

This project holds one bar above all: **never silently mislead.** For a data tool, a
plausible-but-wrong answer is worse than an error. Concretely, that means:

- Validate inputs the API silently accepts or drops (e.g. unknown measures), and **fail loud**
  with the valid options so the model can self-correct.
- Return **honest envelopes** — tell the caller when a result is complete vs. a page, and never
  let a truncated result look complete.
- Be explicit about what the data does **not** cover, rather than guessing.

If you're extending a tool, keep results comfortably under the client's result-size limit and
preserve the completeness/paging signals. See [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)
for the verified DataSaudi API grammar and its gotchas, and
[`docs/FURTHER_READING.md`](docs/FURTHER_READING.md) for the design sources.

## Pull requests

- Keep the offline suite green and ruff clean.
- Add a test for new behavior (a rule without a test isn't done).
- One focused change per PR where you can.

By contributing, you agree your contributions are licensed under the project's
[MIT License](LICENSE).
