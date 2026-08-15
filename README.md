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

```bash
pip install -e ".[formats,dev]"
```

`formats` pulls in the optional binary formats (`compas_pb`, `msgspec`, `zstandard`). Without
it the benchmarks still run, skipping any format whose dependency is missing.

To measure a specific version of a subject under test, install it over the top:

```bash
pip install "compas @ git+https://github.com/compas-dev/compas.git@main"
pip install "compas_pb @ git+https://github.com/gramaziokohler/compas_pb.git@main"
```

## Run

```bash
# Quick baseline — writes results/baseline_quick.{csv,html} + results/samples/
python -m compas_benchmarks.serialization.run

# Full corpus (large; slow and memory-hungry)
python -m compas_benchmarks.serialization.run --preset full --out results/baseline_full.csv
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
python -m compas_benchmarks.site results --out site
```

## Adding a benchmark suite

Add a subpackage under `src/compas_benchmarks/`, runnable as
`python -m compas_benchmarks.<suite>.run`, with its notes in `docs/<suite>.md`.

## License

MIT — see [LICENSE](LICENSE).
