"""Assemble a results directory into a static site for GitHub Pages.

The benchmark's real output is an interactive HTML report, so CI publishes that report
itself rather than transcribing a flattened copy of it into a job summary. This module
takes a results directory (as written by ``compas_benchmarks.serialization.run``), copies
it verbatim, and adds an ``index.html`` landing page: one card per report, each with the
run's metadata, its headline result, and links to the report, its CSV, and the encoded
samples.

Usage::

    python -m compas_benchmarks.site results --out site
"""

import argparse
import csv
import datetime
import html
import os
import re
import shutil

from compas_benchmarks.serialization import report

_META_PATTERN = re.compile(r"<p class='meta'>(.*?)</p>", re.DOTALL)

_INDEX_CSS = """
.cards { display: grid; gap: 16px; margin: 24px 0 0; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px 22px; }
.card h2 { font-size: 17px; margin: 0 0 4px; border: 0; padding: 0; }
.card h2 a { color: inherit; text-decoration: none; }
.card h2 a:hover { text-decoration: underline; }
.card .lead { font-size: 14px; line-height: 1.55; margin: 12px 0 0; color: var(--text-primary); }
.links { display: flex; flex-wrap: wrap; gap: 8px; margin: 16px 0 0; }
.links a { font-size: 13px; text-decoration: none; color: var(--text-primary);
  background: var(--track); border: 1px solid var(--border); border-radius: 8px; padding: 5px 12px; }
.links a:hover { border-color: var(--text-secondary); }
.links a.primary { background: var(--text-primary); color: var(--page); border-color: var(--text-primary); }
.intro { font-size: 14px; line-height: 1.6; color: var(--text-secondary); margin: 12px 0 0; max-width: 70ch; }
.intro a, .meta a { color: inherit; }
.empty { color: var(--muted); font-size: 14px; margin: 24px 0 0; }
.samples { font-size: 12px; color: var(--muted); margin: 14px 0 0; }
.samples code { font-size: 12px; }
"""


def _read_rows(csv_path):
    with open(csv_path, newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def _meta_line(html_path):
    """Recover the run metadata line (generated / preset / repeat / seed / compas) from a report."""
    try:
        with open(html_path) as html_file:
            match = _META_PATTERN.search(html_file.read())
    except OSError:
        return ""
    return html.unescape(match.group(1)) if match else ""


def _discover(results_dir):
    """Return one entry per report found in ``results_dir``, newest first."""
    entries = []
    for name in sorted(os.listdir(results_dir)):
        if not name.endswith(".html"):
            continue
        stem = name[: -len(".html")]
        csv_name = stem + ".csv"
        csv_path = os.path.join(results_dir, csv_name)
        html_path = os.path.join(results_dir, name)
        entries.append(
            {
                "stem": stem,
                "html": name,
                "csv": csv_name if os.path.exists(csv_path) else None,
                "meta": _meta_line(html_path),
                "rows": _read_rows(csv_path) if os.path.exists(csv_path) else [],
                "mtime": os.path.getmtime(html_path),
            }
        )
    entries.sort(key=lambda entry: entry["mtime"], reverse=True)
    return entries


def _sample_links(results_dir):
    sample_dir = os.path.join(results_dir, "samples")
    if not os.path.isdir(sample_dir):
        return []
    return sorted(name for name in os.listdir(sample_dir) if not name.startswith("."))


def _card(entry, sample_names):
    rows = entry["rows"]
    title = entry["stem"].replace("_", " ")

    parts = ['<div class="card">']
    parts.append('<h2><a href="{href}">{title}</a></h2>'.format(href=html.escape(entry["html"]), title=html.escape(title)))
    if entry["meta"]:
        parts.append('<p class="meta">{}</p>'.format(html.escape(entry["meta"])))

    if rows:
        summary = report.summarize(rows)
        sentence = report.headline(summary, code=("<code>", "</code>"), emphasis=("<b>", "</b>"))
        if sentence:
            parts.append('<p class="lead">{}</p>'.format(sentence))

    parts.append('<div class="links">')
    parts.append('<a class="primary" href="{}">Open the report</a>'.format(html.escape(entry["html"])))
    if entry["csv"]:
        parts.append('<a href="{}">Download the CSV</a>'.format(html.escape(entry["csv"])))
    parts.append("</div>")

    if sample_names:
        links = ", ".join('<a href="samples/{0}">{0}</a>'.format(html.escape(name)) for name in sample_names)
        parts.append('<p class="samples">Encoded samples: {}</p>'.format(links))

    parts.append("</div>")
    return "".join(parts)


def build_index(entries, sample_names=(), source_url=None, run_url=None):
    """Return the landing page listing every published report.

    Parameters
    ----------
    entries : list[dict]
        As returned by :func:`_discover`.
    sample_names : list[str], optional
        Files in ``samples/``, linked from the newest card so the encodings stay browsable.
    source_url : str, optional
        Link back to the repository.
    run_url : str, optional
        Link to the CI run that produced these results.

    Returns
    -------
    str
    """
    entries = list(entries)
    published = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    provenance = ["published {}".format(published)]
    if run_url:
        provenance.append('<a href="{}">CI run</a>'.format(html.escape(run_url)))
    if source_url:
        provenance.append('<a href="{}">source</a>'.format(html.escape(source_url)))

    body = [
        "<h1>COMPAS benchmarks</h1>",
        '<p class="meta">{}</p>'.format(" · ".join(provenance)),
        '<p class="intro">Serialization benchmarks for the COMPAS core ecosystem: wire size, serialize and '
        "deserialize time, peak memory, and round-trip fidelity across JSON, protobuf, and MessagePack. "
        "Each report below is interactive — filter by compressed or uncompressed formats and read the "
        "per-subject detail. Sizes and losslessness are deterministic; timings from a shared CI runner are "
        "indicative only.</p>",
    ]

    if not entries:
        body.append('<p class="empty">No reports in this build.</p>')
    else:
        cards = [_card(entry, sample_names if index == 0 else []) for index, entry in enumerate(entries)]
        body.append('<div class="cards">{}</div>'.format("".join(cards)))

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>COMPAS benchmarks</title><style>{css}</style></head>"
        "<body><div class='wrap'>{body}</div></body></html>"
    ).format(css=report.stylesheet() + _INDEX_CSS, body="".join(body))


def build_site(results_dir, out_dir, source_url=None, run_url=None):
    """Copy ``results_dir`` to ``out_dir`` and write the index page into it.

    Returns
    -------
    str
        The path of the generated index page.
    """
    if not os.path.isdir(results_dir):
        raise SystemExit("No results directory at {}".format(results_dir))

    entries = _discover(results_dir)
    shutil.copytree(results_dir, out_dir, dirs_exist_ok=True)

    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, "w") as index_file:
        index_file.write(build_index(entries, _sample_links(results_dir), source_url=source_url, run_url=run_url))
    return index_path


def main():
    parser = argparse.ArgumentParser(description="Build the GitHub Pages site from a benchmark results directory.")
    parser.add_argument("results_dir", help="Directory holding the report HTML, CSV, and samples")
    parser.add_argument("--out", default="site", help="Directory to write the site into (default: site)")
    parser.add_argument("--source-url", help="Link back to the repository")
    parser.add_argument("--run-url", help="Link to the CI run that produced the results")
    args = parser.parse_args()

    index_path = build_site(args.results_dir, args.out, source_url=args.source_url, run_url=args.run_url)
    print("Wrote {}".format(index_path))


if __name__ == "__main__":
    main()
