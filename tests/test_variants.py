import math

import pytest

from compas_benchmarks.serialization import run
from compas_benchmarks.serialization import variants


def _row(subject, size, fmt, size_bytes, note=""):
    return {"subject": subject, "size": size, "format": fmt, "size_bytes": size_bytes, "compression_vs_json": 1.0, "note": note}


def test_parse_expands_git_refs_of_compas():
    variant = variants.parse("py3=git:remove-future")
    assert (variant.name, variant.requirement, variant.ref) == ("py3", "compas @ git+https://github.com/compas-dev/compas.git@remove-future", "remove-future")


def test_parse_passes_other_requirements_through():
    for spec, requirement in [("old=compas==2.12.0", "compas==2.12.0"), ("local=/path/to/compas", "/path/to/compas")]:
        variant = variants.parse(spec)
        assert (variant.requirement, variant.ref) == (requirement, None)


def test_patches_for_finds_a_refs_patches_in_order(tmp_path):
    for name in ["0002-b.patch", "0001-a.patch", "notes.md"]:
        (tmp_path / "some" / "branch").mkdir(parents=True, exist_ok=True)
        (tmp_path / "some" / "branch" / name).write_text("")

    assert [p.split("/")[-1] for p in variants.patches_for("some/branch", str(tmp_path))] == ["0001-a.patch", "0002-b.patch"]
    assert variants.patches_for("other", str(tmp_path)) == []


def test_the_remove_future_branch_carries_its_fix():
    assert [p.split("/")[-1] for p in variants.patches_for("remove-future")] == ["0001-accept-frame-components.patch"]


@pytest.mark.parametrize("spec", ["py3", "=git:main", "py3=", "a@b=git:main"])
def test_parse_rejects_malformed_specs(spec):
    with pytest.raises(ValueError):
        variants.parse(spec)


def test_coerce_restores_the_types_run_produces():
    row = variants._coerce(
        {"subject": "mesh", "size": "1000", "format": "json", "size_bytes": "512", "dump_median_s": "0.25", "lossless": "False", "max_abs_error": "", "note": "x"}
    )
    assert row == {"subject": "mesh", "size": 1000, "format": "json", "size_bytes": 512, "dump_median_s": 0.25, "lossless": False, "max_abs_error": None, "note": "x"}


def test_relabel_renames_formats_and_rebases_on_the_main_json():
    baseline = [_row("mesh", 1000, "json", 1000), _row("mesh", 1000, "compas_pb", 400)]
    relabeled = variants.relabel([_row("mesh", 1000, "json", 800, note="compact text"), _row("graph", 10, "json", 50)], "py3", baseline)

    assert [row["format"] for row in relabeled] == ["json@py3", "json@py3"]
    assert relabeled[0]["compression_vs_json"] == 1.25
    assert relabeled[0]["note"] == "compact text (compas variant 'py3')"
    # No main json for that batch: no ratio, rather than a ratio against the wrong thing.
    assert math.isnan(relabeled[1]["compression_vs_json"])


def test_add_variants_slots_variant_rows_after_their_batch(monkeypatch):
    rows = [_row("mesh", 1000, "json", 1000), _row("mesh", 10000, "json", 10000), _row("points", 1000, "json", 100)]

    def fake_measure(environment, subjects, preset, format_names, repeat, seed, progress=True):
        return [_row(row["subject"], row["size"], "json", row["size_bytes"]) for row in rows]

    monkeypatch.setattr(variants, "measure", fake_measure)
    environment = variants.Environment("py3", "python", "compas 2.15.0")
    merged = run.add_variants(rows, [environment], ["mesh", "points"], "quick", ["json"], 1, 42)

    assert [(row["subject"], row["size"], row["format"]) for row in merged] == [
        ("mesh", 1000, "json"),
        ("mesh", 1000, "json@py3"),
        ("mesh", 10000, "json"),
        ("mesh", 10000, "json@py3"),
        ("points", 1000, "json"),
        ("points", 1000, "json@py3"),
    ]
