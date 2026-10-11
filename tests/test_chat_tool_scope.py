from core.alias_manager import AliasManager
from services.chat_service import ChatService


def make_service(tmp_path, enabled=None):
    enabled = enabled or {
        "search_files": True,
        "read_file": True,
        "delete_file": True,
        "launch_application": True,
        "close_application": True,
        "get_process_status": True,
    }
    config = {
        "model": "test-model",
        "thinking": False,
        "temperature": 0.7,
        "context_length": 4096,
        "max_tokens": 512,
        "tools": enabled,
    }
    aliases = AliasManager(tmp_path / "aliases.json")
    return ChatService(provider=None, config=config, ollama_manager=None, alias_manager=aliases)


def test_normal_chat_has_no_tools(tmp_path):
    service = make_service(tmp_path)
    assert service.router.tools_for_message("Расскажи анекдот") == set()


def test_question_with_where_phrase_has_no_tools(tmp_path):
    service = make_service(tmp_path)
    assert service.router.tools_for_message("Где находится Москва?") == set()
    assert service.router.tools_for_message("Где находится, что делать, текстей?") == set()


def test_where_file_is_means_search_tool(tmp_path):
    service = make_service(tmp_path)
    assert service.router.tools_for_message("Где находится файл tool_test.txt?") == {"search_files"}
    assert service.router.tools_for_message("Где лежит папка Downloads") == {"search_files"}


def test_show_file_is_search_but_show_general_text_is_chat(tmp_path):
    service = make_service(tmp_path)
    assert service.router.tools_for_message("Покажи файл tool_test.txt") == {"search_files"}
    assert service.router.tools_for_message("Покажи мне пример") == set()


def test_search_command_gets_only_search_tool(tmp_path):
    service = make_service(tmp_path)
    assert service.router.tools_for_message("Найди файл tool_test.txt") == {"search_files"}


def test_read_command_gets_only_read_tool(tmp_path):
    service = make_service(tmp_path)
    assert service.router.tools_for_message("Прочитай файл tool_test.txt") == {"read_file"}


def test_compound_search_and_read_gets_both_tools(tmp_path):
    service = make_service(tmp_path)
    assert service.router.tools_for_message("Найди файл tool_test.txt, прочитай его и перескажи") == {
        "search_files",
        "read_file",
    }


def test_delete_command_gets_delete_and_search(tmp_path):
    service = make_service(tmp_path)
    assert service.router.tools_for_message("Удали файл tool_test.txt") == {
        "delete_file",
        "search_files",
    }


def test_disabled_tools_are_filtered(tmp_path):
    service = make_service(tmp_path, {"search_files": True, "read_file": False})
    assert service.router.tools_for_message("Найди файл tool_test.txt, прочитай его") == {"search_files"}
