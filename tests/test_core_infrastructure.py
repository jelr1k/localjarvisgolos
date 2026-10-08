    assert manager.ensure_whisper_model("tiny") == "tiny"
    assert manager.whisper_download_size("tiny") == 0
    assert manager.whisper_status("tiny") == "unknown"


def test_workspace_index_refresh_and_category_search(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "readme.txt").write_text("x", encoding="utf-8")
    (tmp_path / "Steam.lnk").write_text("x", encoding="utf-8")
    (tmp_path / "folder").mkdir()

    index = WorkspaceIndex(tmp_path)

    assert len(index.entries()) == 4
    assert [entry.name for entry in index.search("readme.txt", ("files",), fuzzy=False)] == ["readme.txt"]
    assert [entry.name for entry in index.search("Steam", ("applications",), fuzzy=False)] == ["Steam.lnk"]
    assert [entry.name for entry in index.entries(("folders",))] == ["folder", "notes"]