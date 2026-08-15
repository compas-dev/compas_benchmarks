# compas_benchmarks

Benchmarks for the [COMPAS](https://github.com/compas-dev/compas) core ecosystem.

This repository has one job: produce reproducible numbers about COMPAS, so design decisions
in the core libraries are made on measurements rather than on argument. It depends on
released COMPAS packages and never modifies them — anything a benchmark needs beyond the
public API (such as a format-independent content hash) is implemented here.

## Suites

| Suite | What it measures |
|---|---|
| [`serialization`](docs/serialization.md) | wire size, serialize/deserialize time, peak memory, and round-trip fidelity across JSON, protobuf (`compas_pb`), and MessagePack — the measurement instrument for [`docs/PRD-serialization.md`](docs/PRD-serialization.md) |

## Install

The project is managed with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --all-extras
```

`--all-extras` adds the optional binary formats (`compas_pb`, `msgspec`, `zstandard`); a plain
`uv sync` gives you COMPAS, JSON, and the tooling, and any format whose dependency is missing
is skipped rather than failing the run. `uv.lock` pins the exact versions every measurement
was taken against — CI syncs with `--locked`, so a run's numbers always name a known
environment.

To measure a specific version of a subject under test, install it over the synced
environment:

```bash
uv pip install "compas @ git+https://github.com/compas-dev/compas.git@main"
uv pip install "compas_pb @ git+https://github.com/gramaziokohler/compas_pb.git@main"
```

Then use `uv run --no-sync` for the commands below, so the next `uv run` does not restore the
locked versions underneath you.

## Run

```bash
# Quick baseline — writes results/baseline_quick.{csv,html} + results/samples/
uv run python -m compas_benchmarks.serialization.run

# Full corpus (large; slow and memory-hungry)
uv run python -m compas_benchmarks.serialization.run --preset full --out results/baseline_full.csv

# Tests and style
uv run pytest
uv run ruff check . && uv run ruff format .
```

Run from the repository root: results land in `results/`, relative to the working directory.
Every run writes a CSV (the machine record) and a self-contained HTML report next to it (the
human one). `results/` is git-ignored — benchmark output is reproduced, not committed.

See [`docs/serialization.md`](docs/serialization.md) for the corpus, the formats under test,
and the findings so far.

## On CI

The [`serialization-benchmark`](.github/workflows/benchmark.yml) workflow runs the `quick`
preset on every push to `main` and every pull request. The output is an interactive HTML
report, so it is **published to GitHub Pages** rather than transcribed into a job summary:
pushes to `main` and manual runs deploy the site (index + report + CSV + encoded samples),
while pull requests upload the same site as a downloadable artifact and leave the published
site showing `main`.

Use **Actions → serialization-benchmark → Run workflow** to choose the preset, repeat count,
formats, and the `compas` / `compas_pb` versions to benchmark. Treat CI *timings* as
indicative only — size and losslessness numbers are deterministic, timings on a shared runner
are not.

Publishing needs Pages enabled once, in **Settings → Pages → Build and deployment → Source:
GitHub Actions**. Each deploy replaces the site with that run's results; earlier runs stay
available as workflow artifacts.

Build the same site locally with:

```bash
uv run python -m compas_benchmarks.site results --out site
```

## Adding a benchmark suite

Add a subpackage under `src/compas_benchmarks/`, runnable as
`uv run python -m compas_benchmarks.<suite>.run`, with its notes in `docs/<suite>.md`.

## License

MIT — see [LICENSE](LICENSE).
