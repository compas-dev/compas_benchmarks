"""Measure formats against other versions of compas, in the same report.

compas is imported once per process, so a second version of it cannot be measured in the
process that already holds the first. Each variant therefore gets its own throwaway virtual
environment (created with uv) holding this project and the requested compas, and the runner
itself is executed there as a worker. Its rows come back through a CSV and are merged into
the main results with the format renamed to ``<format>@<variant>`` (e.g. ``json@py3``), so
the report shows them next to the formats measured against the locked compas.

One worker per variant, not per measurement: the timed regions are confined to
:func:`metrics.measure` inside each process, so process boundaries do not affect them, and
every variant still runs on the same machine within the same run as the baseline.

A branch under test may need fixes that have not landed on it yet. Patches in
``patches/compas/<ref>/*.patch`` are applied, in name order, to a ``git:<ref>`` variant before
it is installed; a patch the branch already contains is skipped, so it can stay until the
branch catches up and be deleted afterwards.
"""

import contextlib
import csv
import glob
import os
import shutil
import subprocess
import sys
import tempfile

COMPAS_REPOSITORY = "https://github.com/compas-dev/compas.git"

# The repository root (src/compas_benchmarks/serialization/ -> three levels up): a worker
# environment installs this project from source, so variants need a source checkout.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PATCHES_DIR = os.path.join(PROJECT_ROOT, "patches", "compas")

_TEXT_COLUMNS = {"subject", "format", "note"}
_INT_COLUMNS = {"size", "size_bytes", "peak_mem_bytes"}
_BOOL_COLUMNS = {"lossless", "data_equal", "canonical_hash_equal"}


class Variant(object):
    """Another compas to measure: a ``git:<ref>`` of compas-dev/compas, or any requirement.

    Parameters
    ----------
    name : str
        Suffix of the variant's formats in the report (``json@<name>``).
    requirement : str
        What ``uv pip install`` installs when no patches apply.
    ref : str, optional
        The git ref, for a ``git:<ref>`` variant; its patches are looked up by it.
    """

    def __init__(self, name, requirement, ref=None):
        self.name = name
        self.requirement = requirement
        self.ref = ref

    def __repr__(self):
        return "Variant({!r}, {!r}, ref={!r})".format(self.name, self.requirement, self.ref)


class Environment(object):
    """A variant's prepared worker environment: its interpreter and what compas it holds."""

    def __init__(self, name, python, description):
        self.name = name
        self.python = python
        self.description = description


def parse(spec):
    """Parse a ``NAME=SOURCE`` variant spec into a :class:`Variant`.

    ``SOURCE`` is either ``git:<branch|tag|sha>`` of compas-dev/compas, or any requirement
    ``uv pip install`` accepts (``compas==2.14.0``, ``compas @ git+...``, ``/path/to/compas``).

    Examples
    --------
    >>> parse("py3=git:remove-future")
    Variant('py3', 'compas @ git+https://github.com/compas-dev/compas.git@remove-future', ref='remove-future')
    >>> parse("old=compas==2.12.0")
    Variant('old', 'compas==2.12.0', ref=None)
    """
    name, separator, source = spec.partition("=")
    name = name.strip()
    source = source.strip()
    if not separator or not name or not source:
        raise ValueError("Expected a variant as NAME=SOURCE, got {!r}".format(spec))
    if "@" in name:
        raise ValueError("A variant name cannot contain '@' (it separates format and variant): {!r}".format(name))
    if source.startswith("git:"):
        ref = source[len("git:") :]
        return Variant(name, "compas @ git+{}@{}".format(COMPAS_REPOSITORY, ref), ref=ref)
    return Variant(name, source)


def patches_for(ref, patches_dir=None):
    """Return the patches to apply to ``git:<ref>``, in the order they are applied."""
    return sorted(glob.glob(os.path.join(patches_dir or PATCHES_DIR, ref, "*.patch")))


def _coerce(row):
    """Restore the types of a row read back from a CSV, as :func:`run.run` produces them."""
    result = {}
    for key, value in row.items():
        if key in _TEXT_COLUMNS:
            result[key] = value
        elif key in _BOOL_COLUMNS:
            result[key] = value == "True"
        elif value in ("", "None"):
            result[key] = None
        elif key in _INT_COLUMNS:
            result[key] = int(value)
        else:
            result[key] = float(value)
    return result


def relabel(variant_rows, name, baseline_rows):
    """Rename a variant's formats to ``<format>@<name>`` and rebase them on the main ``json``.

    ``compression_vs_json`` is recomputed against the ``json`` row of the main results, so
    every ratio in the report shares one baseline.

    Returns
    -------
    list[dict]
    """
    json_sizes = {(row["subject"], int(row["size"])): row["size_bytes"] for row in baseline_rows if row["format"] == "json"}
    relabeled = []
    for row in variant_rows:
        row = dict(row)
        json_size = json_sizes.get((row["subject"], int(row["size"])))
        row["format"] = "{}@{}".format(row["format"], name)
        row["compression_vs_json"] = round(json_size / row["size_bytes"], 3) if json_size else float("nan")
        row["note"] = "{} (compas variant {!r})".format(row["note"], name) if row["note"] else "compas variant {!r}".format(name)
        relabeled.append(row)
    return relabeled


def _run_checked(command, what):
    try:
        return subprocess.run(command, check=True, stdout=subprocess.PIPE, text=True).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit("Could not {}: {}".format(what, error))


def _progress(enabled, message):
    if enabled:
        print(message, file=sys.stderr, flush=True)


def _checkout(ref, patches, dest, progress):
    """Check out compas at ``ref`` into ``dest`` and apply ``patches``.

    Returns
    -------
    str
        The checked-out commit and the patches applied, for the report header.
    """
    git = shutil.which("git")
    if not git:
        raise SystemExit("Patching a compas variant needs git on PATH.")
    _run_checked([git, "init", "--quiet", dest], "create a checkout of compas")
    _run_checked([git, "-C", dest, "fetch", "--quiet", "--depth", "1", COMPAS_REPOSITORY, ref], "fetch compas {!r}".format(ref))
    _run_checked([git, "-C", dest, "checkout", "--quiet", "FETCH_HEAD"], "check out compas {!r}".format(ref))
    commit = _run_checked([git, "-C", dest, "rev-parse", "--short", "HEAD"], "read the commit of compas {!r}".format(ref)).strip()

    applied = []
    for patch in patches:
        patch_name = os.path.basename(patch)
        # Applies in reverse: the branch already contains it, so there is nothing to do.
        if subprocess.run([git, "-C", dest, "apply", "--check", "--reverse", patch], capture_output=True).returncode == 0:
            _progress(progress, "  {} is already in {}; skipped (it can be deleted)".format(patch_name, ref))
            continue
        _run_checked([git, "-C", dest, "apply", patch], "apply {} to compas {!r} ({}); update or remove it".format(patch_name, ref, commit))
        _progress(progress, "  applied {}".format(patch_name))
        applied.append(patch_name)

    return "{} @ {}{}".format(ref, commit, "".join(" + " + name for name in applied))


@contextlib.contextmanager
def prepared(variant, progress=True, patches_dir=None):
    """Create a throwaway environment holding this project and the variant's compas.

    Yields
    ------
    :class:`Environment`
        Valid until the context exits, when the environment is deleted.
    """
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("Benchmarking a compas variant needs uv on PATH: https://docs.astral.sh/uv/")
    if not os.path.exists(os.path.join(PROJECT_ROOT, "pyproject.toml")):
        raise SystemExit("Benchmarking a compas variant needs a source checkout of compas_benchmarks (no pyproject.toml at {}).".format(PROJECT_ROOT))

    with tempfile.TemporaryDirectory(prefix="compas-benchmark-{}-".format(variant.name)) as workdir:
        patches = patches_for(variant.ref, patches_dir) if variant.ref else []
        requirement = variant.requirement
        source = None
        if patches:
            _progress(progress, "Variant {!r}: checking out compas {} and applying {} patch(es)".format(variant.name, variant.ref, len(patches)))
            requirement = os.path.join(workdir, "compas")
            source = _checkout(variant.ref, patches, requirement, progress)
        _progress(progress, "Variant {!r}: installing {}".format(variant.name, requirement))

        env_dir = os.path.join(workdir, "venv")
        python = os.path.join(env_dir, "Scripts" if os.name == "nt" else "bin", "python")
        _run_checked([uv, "venv", "--quiet", "--python", sys.executable, env_dir], "create the environment for variant {!r}".format(variant.name))
        # --refresh-package: a branch name must be re-resolved to its current commit, and a
        # local checkout rebuilt, rather than served from uv's cache.
        _run_checked(
            [uv, "pip", "install", "--quiet", "--python", python, "--refresh-package", "compas", "{}[formats]".format(PROJECT_ROOT), requirement],
            "install {!r} for variant {!r}".format(requirement, variant.name),
        )
        version = _run_checked([python, "-c", "import compas; print(compas.__version__)"], "import compas in variant {!r}".format(variant.name)).strip()
        if source is None:
            frozen = _run_checked([uv, "pip", "freeze", "--quiet", "--python", python], "list the packages of variant {!r}".format(variant.name))
            line = next((line.strip() for line in frozen.splitlines() if line.startswith("compas @ ")), None)
            source = line[len("compas @ ") :] if line else None
        description = "compas {} ({})".format(version, source) if source else "compas {}".format(version)

        yield Environment(variant.name, python, description)


def measure(environment, subjects, preset, format_names, repeat, seed, progress=True):
    """Run the benchmark for ``format_names`` in a prepared environment.

    Returns
    -------
    list[dict]
        The worker's rows, formats not yet relabeled.
    """
    with tempfile.TemporaryDirectory(prefix="compas-benchmark-{}-rows-".format(environment.name)) as workdir:
        out = os.path.join(workdir, "rows.csv")
        command = [environment.python, "-m", "compas_benchmarks.serialization.run", "--preset", preset, "--repeat", str(repeat), "--seed", str(seed), "--out", out, "--no-samples"]
        command += ["--subjects"] + list(subjects) + ["--formats"] + list(format_names)
        if not progress:
            command.append("--quiet")
        _progress(progress, "Variant {!r}: {}".format(environment.name, environment.description))
        # The worker's progress goes straight to our stderr; its stdout (the table) is dropped.
        _run_checked(command, "benchmark variant {!r}".format(environment.name))

        with open(out, newline="") as csv_file:
            return [_coerce(row) for row in csv.DictReader(csv_file)]
