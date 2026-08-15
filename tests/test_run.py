from compas_benchmarks.serialization import run


def test_run_reports_each_batch_on_stderr(capsys):
    rows = run.run(["mesh"], "quick", ["json"], repeat=1, seed=42)

    captured = capsys.readouterr()
    assert len(rows) == 2
    # Results are returned, never printed by run() itself — stdout stays free for the table.
    assert captured.out == ""
    assert "[1/2] mesh @ 1,000" in captured.err
    assert "[2/2] mesh @ 10,000" in captured.err
    assert "json" in captured.err
    assert "Done: 2 rows" in captured.err


def test_run_is_silent_when_progress_is_off(capsys):
    run.run(["mesh"], "quick", ["json"], repeat=1, seed=42, progress=False)

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


def test_human_time_scales_by_magnitude():
    assert run._human_time(0.0123) == "12ms"
    assert run._human_time(5.5) == "5.5s"
    assert run._human_time(125) == "2m05s"
