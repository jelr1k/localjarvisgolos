from tools import paths


def test_fuzzy_filename_search_matches_whispered_run(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / "run_test.bat"
    target.write_text("@echo off\n", encoding="utf-8")

    monkeypatch.setattr(paths, "TOOL_WORKSPACE", workspace)
    monkeypatch.setattr(paths, "APP_ROOT", workspace)
    monkeypatch.setattr(paths, "prepare_tool_workspace", lambda: workspace)
    monkeypatch.setattr(paths, "is_path_allowed", lambda path: True)

    matches = paths.find_by_name("ран тест.bat", fuzzy=True)

    assert matches == [target.resolve()]


def test_fuzzy_filename_search_keeps_close_candidates_ambiguous(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    first = workspace / "run_test.bat"
    second = workspace / "run-test.bat"
    first.write_text("", encoding="utf-8")
    second.write_text("", encoding="utf-8")

    monkeypatch.setattr(paths, "TOOL_WORKSPACE", workspace)
    monkeypatch.setattr(paths, "APP_ROOT", workspace)
    monkeypatch.setattr(paths, "prepare_tool_workspace", lambda: workspace)
    monkeypatch.setattr(paths, "is_path_allowed", lambda path: True)

    matches = paths.find_by_name("ран тест.bat", fuzzy=True)

    assert set(matches) == {first.resolve(), second.resolve()}
