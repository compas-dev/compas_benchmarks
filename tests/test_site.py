import csv
import os

from compas_benchmarks import site
from compas_benchmarks.serialization import report

ROWS = [
    {
        "subject": "mesh",
        "size": "1000",
        "format": "json",
        "size_bytes": "1000",
        "roundtrip_median_s": "0.2",
        "lossless": "True",
    },
    {
        "subject": "mesh",
        "size": "1000",
        "format": "compas_pb",
        "size_bytes": "500",
        "roundtrip_median_s": "0.1",
        "lossless": "True",
    },
]


def _write_results(results_dir):
    os.makedirs(os.path.join(results_dir, "samples"))
    with open(os.path.join(results_dir, "baseline_quick.csv"), "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(ROWS[0]))
        writer.writeheader()
        writer.writerows(ROWS)
    with open(os.path.join(results_dir, "baseline_quick.html"), "w") as html_file:
        html_file.write("<html><body><p class='meta'>generated 2026-01-01 00:00 &middot; preset quick</p></body></html>")
    with open(os.path.join(results_dir, "samples", "mesh.json"), "w") as sample_file:
        sample_file.write("{}")


def test_build_site_copies_results_and_writes_an_index(tmp_path):
    results_dir = str(tmp_path / "results")
    out_dir = str(tmp_path / "site")
    _write_results(results_dir)

    index_path = site.build_site(results_dir, out_dir, source_url="https://example.test/repo", run_url="https://example.test/run/1")

    assert index_path == os.path.join(out_dir, "index.html")
    # The report, its CSV, and the samples are published alongside the index.
    for relative in ["baseline_quick.html", "baseline_quick.csv", os.path.join("samples", "mesh.json")]:
        assert os.path.exists(os.path.join(out_dir, relative))

    with open(index_path) as index_file:
        index = index_file.read()
    assert 'href="baseline_quick.html"' in index
    assert 'href="baseline_quick.csv"' in index
    assert 'href="samples/mesh.json"' in index
    assert "https://example.test/run/1" in index
    # The run metadata is recovered from the report itself.
    assert "generated 2026-01-01 00:00" in index
    # ... and the headline is the same one the Markdown summary states.
    assert "2.00× smaller" in index


def test_headline_states_the_same_figures_in_every_markup():
    summary = report.summarize(ROWS)

    plain = report.headline(summary)
    markdown = report.headline(summary, code=("`", "`"), emphasis=("**", "**"))
    for figure in ["2.00× smaller", "2.00× faster", "1/1"]:
        assert figure in plain
        assert "**{}**".format(figure) in markdown
    assert "`compas_pb`" in markdown


def test_build_site_without_reports(tmp_path):
    results_dir = str(tmp_path / "results")
    os.makedirs(results_dir)

    index_path = site.build_site(results_dir, str(tmp_path / "site"))

    with open(index_path) as index_file:
        assert "No reports in this build." in index_file.read()
