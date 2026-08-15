# compas_benchmarks

Benchmarks for the [COMPAS](https://github.com/compas-dev/compas) core ecosystem.

This repository has one job: produce reproducible numbers about COMPAS, so design decisions
in the core libraries are made on measurements rather than on argument. It measures COMPAS
from the outside and never modifies it — anything a benchmark needs beyond the public API
(such as a format-independent content hash) is implemented here.

What it measures is up to you: `uv.lock` pins released versions so runs are comparable by
default, and any branch, tag, or commit can be installed over the top — locally or on CI —
when the point is to measure unreleased work.

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

### Benchmarking a branch

Any branch, tag, or commit of a subject under test can be installed over the synced
environment — measuring unreleased work is the normal case, not an exception:

```bash
uv pip install "compas @ git+https://github.com/compas-dev/compas.git@some-branch"
uv pip install "compas_pb @ git+https://github.com/gramaziokohler/compas_pb.git@some-branch"

# ... and for an unpushed local checkout:
uv pip install /path/to/compas
```

Two things to know about the override. First, **use `uv run --no-sync` afterwards** (or export
`UV_NO_SYNC=1`): a plain `uv run` re-syncs to `uv.lock` and would silently restore the
released version, leaving you benchmarking something other than what you asked for. Second,
`uv pip install` targets `$VIRTUAL_ENV` when one is active, unlike `uv sync` and `uv run`,
which always find this project's `.venv` — so deactivate any unrelated environment first, or
you will install into it by mistake.

`uv sync --all-extras --locked` puts everything back to the locked versions.

On CI, the same thing is a workflow input: `compas_ref` / `compas_pb_ref` accept a PyPI
specifier (`==2.15.1`) or a git ref (`git:some-branch`).

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

A run reports each batch on **stderr** as it completes, so a long run shows its progress:

```
Benchmarking 3 formats over 4 batches (2 timed runs each): json, compas_pb, compas_pb_zstd
[2/4] mesh @ 10,000
         json                     864.1KB     34ms
         compas_pb                320.3KB     27ms
         compas_pb_zstd           168.6KB     29ms
```

Progress goes to stderr and the results table to stdout, so redirecting the table keeps the
progress on screen. Every line is printed between measurements, never inside one — the timed
regions are confined to `metrics.measure` — so this cannot influence the numbers. `--quiet`
turns it off.

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
