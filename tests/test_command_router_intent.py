from core.alias_manager import AliasManager
from services.command_router import CommandRouter


def make_router(tmp_path):
    aliases = AliasManager(tmp_path / "aliases.json")
    return CommandRouter({}, None, aliases)


def test_where_question_is_not_file_search(tmp_path):
    router = make_router(tmp_path)
    assert router._resolve_action("Где находится Москва?") is None
    assert router._resolve_action("Где находится, что делать, текстей?") is None


def test_where_file_is_file_search(tmp_path):
    router = make_router(tmp_path)
    action = router._resolve_action("Где находится файл tool_test.txt?")
    assert action == ("search", "файл tool_test.txt?")


def test_show_is_contextual(tmp_path):
    router = make_router(tmp_path)
    assert router._resolve_action("Покажи мне пример") is None
    assert router._resolve_action("Покажи файл tool_test.txt") == ("search", "файл tool_test.txt")


def test_compound_file_command_still_detects_multiple_actions(tmp_path):
    router = make_router(tmp_path)
    assert router._has_multiple_actions("Найди файл tool_test.txt, прочитай его и перескажи")


def test_tools_for_message_is_owned_by_router(tmp_path):
    router = make_router(tmp_path)
    assert "launch_application" in router.tools_for_message("запусти Steam")
    assert "get_process_status" in router.tools_for_message("закрой Steam")
    assert router.tools_for_message("расскажи анекдот") == set()
