from __future__ import annotations

from unittest.mock import Mock

from core.target_resolver import TargetResolver


def test_target_resolver_prefers_exact_longest_fragment():
    aliases = Mock()
    aliases.resolve_any.return_value = {"status": "none"}
    aliases.suggest_any.return_value = []

    index = Mock()
    index.resolve.side_effect = lambda query, categories, alias_manager, fuzzy: (
        (Mock(path="/workspace/Google Chrome.lnk", category="applications"), [])
        if query == "Google Chrome"
        else (None, [])
    )

    resolver = TargetResolver(aliases, lambda: index)

    target, error = resolver.resolve(
        "мой Google Chrome",
        ("applications",),
        use_workspace_index=True,
    )

    assert target == "/workspace/Google Chrome.lnk"
    assert error is None


def test_target_resolver_reports_ambiguous_workspace_match():
    aliases = Mock()
    aliases.resolve_any.return_value = {"status": "none"}
    aliases.suggest_any.return_value = []

    index = Mock()
    index.resolve.return_value = (
        None,
        [
            Mock(path="/workspace/one.exe", category="applications"),
            Mock(path="/workspace/two.exe", category="applications"),
        ],
    )

    resolver = TargetResolver(aliases, lambda: index)

    target, error = resolver.resolve(
        "Steam",
        ("applications",),
        use_workspace_index=True,
    )

    assert target is None
    assert error is not None
    assert "однозначно" in error


def test_target_resolver_accepts_fuzzy_suggestion_only_after_confirmation():
    aliases = Mock()
    aliases.resolve_any.return_value = {"status": "none"}
    aliases.suggest_any.return_value = [
        {"score": 0.91, "target": "Steam.lnk", "category": "applications"}
    ]

    resolver = TargetResolver(aliases)

    target, error = resolver.resolve(
        "открой стим",
        ("applications",),
        alias_confirmation_callback=lambda query, target, category: True,
    )

    assert target == "Steam.lnk"
    assert error is None
    aliases.add_alias.assert_called_once_with("applications", "Steam.lnk", "открой стим")


def test_target_resolver_declines_fuzzy_alias_without_confirmation():
    aliases = Mock()
    aliases.resolve_any.return_value = {"status": "none"}
    aliases.suggest_any.return_value = [
        {"score": 0.91, "target": "Steam.lnk", "category": "applications"}
    ]

    resolver = TargetResolver(aliases)

    target, error = resolver.resolve(
        "открой стим",
        ("applications",),
        alias_confirmation_callback=lambda *_args: False,
    )

    assert target == "открой стим"
    assert error is None
    aliases.add_alias.assert_not_called()


def test_target_resolver_rejects_close_fuzzy_suggestions_as_ambiguous():
    aliases = Mock()
    aliases.resolve_any.return_value = {"status": "none"}
    aliases.suggest_any.return_value = [
        {"score": 0.91, "target": "Steam.lnk", "category": "applications"},
        {"score": 0.86, "target": "Steam Beta.lnk", "category": "applications"},
    ]

    resolver = TargetResolver(aliases)

    target, error = resolver.resolve("стим", ("applications",))

    assert target is None
    assert error is not None
    assert "Варианты" in error
    aliases.add_alias.assert_not_called()
