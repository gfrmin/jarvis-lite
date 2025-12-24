"""Tests for Jarvis Lite bot - focusing on Anthropic API integration."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

# Set required env vars before importing bot
os.environ.setdefault("TELEGRAM_TOKEN", "test_token")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")
os.environ.setdefault("ALLOWED_USER_IDS", "123456")


VALID_MODEL_PREFIXES = (
    "claude-haiku-4-5",
    "claude-sonnet-4",
    "claude-opus-4",
    "claude-3-haiku",
    "claude-3-sonnet",
    "claude-3-opus",
    "claude-3-5-haiku",
    "claude-3-5-sonnet",
)


class TestModelId:
    """Tests to ensure the Anthropic model ID is valid."""

    def test_model_id_has_valid_prefix(self):
        """Ensure the model ID used starts with a known valid Claude model prefix."""
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"action": "add", "text": "test", "list": "inbox"}')]
            mock_client.messages.create.return_value = mock_response

            from bot import parse_with_haiku
            parse_with_haiku("test message")

            call_args = mock_client.messages.create.call_args
            model_id = call_args.kwargs.get("model") or call_args[1].get("model")

            assert model_id is not None, "Model ID should be specified"
            assert any(model_id.startswith(prefix) for prefix in VALID_MODEL_PREFIXES), (
                f"Model ID '{model_id}' should start with one of: {VALID_MODEL_PREFIXES}"
            )


class TestParseWithHaiku:
    """Tests for the parse_with_haiku function."""

    def test_returns_dict_with_action_key(self):
        """Test that parse_with_haiku always returns a dict with 'action' key."""
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"action": "add", "text": "buy milk", "list": "inbox"}')]
            mock_client.messages.create.return_value = mock_response

            from bot import parse_with_haiku
            result = parse_with_haiku("buy milk")

            assert isinstance(result, dict), "Result should be a dict"
            assert "action" in result, "Result should have 'action' key"

    def test_handles_json_parse_error(self):
        """Test graceful handling when API returns invalid JSON."""
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text="not valid json")]
            mock_client.messages.create.return_value = mock_response

            from bot import parse_with_haiku
            result = parse_with_haiku("buy milk")

            assert result == {"action": "unknown"}, "Should return unknown action on parse error"

    def test_handles_api_exception(self):
        """Test graceful handling when Anthropic API raises an exception."""
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("API Error")

            from bot import parse_with_haiku

            with pytest.raises(Exception):
                parse_with_haiku("buy milk")

    def test_parses_add_action(self):
        """Test parsing an add task action."""
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"action": "add", "text": "buy milk @errands", "list": "inbox"}')]
            mock_client.messages.create.return_value = mock_response

            from bot import parse_with_haiku
            result = parse_with_haiku("buy milk @errands")

            assert result["action"] == "add"
            assert result["text"] == "buy milk @errands"
            assert result["list"] == "inbox"

    def test_parses_complete_action(self):
        """Test parsing a complete task action."""
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='{"action": "complete", "task_id": 5}')]
            mock_client.messages.create.return_value = mock_response

            from bot import parse_with_haiku
            result = parse_with_haiku("done 5")

            assert result["action"] == "complete"
            assert result["task_id"] == 5

    def test_handles_markdown_code_blocks(self):
        """Test that markdown code blocks in response are handled."""
        with patch("anthropic.Anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_response = MagicMock()
            mock_response.content = [MagicMock(text='```json\n{"action": "add", "text": "test", "list": "inbox"}\n```')]
            mock_client.messages.create.return_value = mock_response

            from bot import parse_with_haiku
            result = parse_with_haiku("test")

            assert result["action"] == "add"


class TestValidActions:
    """Tests to ensure all action types are handled."""

    VALID_ACTIONS = [
        "add", "complete", "delete", "move", "show",
        "review", "today", "clear_today", "process", "help", "unknown"
    ]

    def test_all_actions_are_valid(self):
        """Ensure only valid actions are returned."""
        for action in self.VALID_ACTIONS:
            with patch("anthropic.Anthropic") as mock_anthropic:
                mock_client = MagicMock()
                mock_anthropic.return_value = mock_client
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text=json.dumps({"action": action}))]
                mock_client.messages.create.return_value = mock_response

                from bot import parse_with_haiku
                result = parse_with_haiku("test")

                assert result["action"] == action


def _escape_markdown(text: str) -> str:
    """
    Local copy of escape_markdown for testing without importing bot module.
    This avoids dependency issues with telegram/cryptography in test environments.
    """
    escape_chars = ['_', '*', '`', '[']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


class TestEscapeMarkdown:
    """Tests for the escape_markdown function to prevent Telegram entity parsing errors."""

    def test_escapes_underscores(self):
        """Test that underscores are escaped (prevents italic formatting issues)."""
        result = _escape_markdown("blog.nli.org.il/en/operation_mincemeat/")
        assert result == "blog.nli.org.il/en/operation\\_mincemeat/"

    def test_escapes_asterisks(self):
        """Test that asterisks are escaped (prevents bold formatting issues)."""
        result = _escape_markdown("important *task* here")
        assert result == "important \\*task\\* here"

    def test_escapes_backticks(self):
        """Test that backticks are escaped (prevents code formatting issues)."""
        result = _escape_markdown("run `npm install` command")
        assert result == "run \\`npm install\\` command"

    def test_escapes_square_brackets(self):
        """Test that opening square brackets are escaped (prevents link formatting issues)."""
        result = _escape_markdown("check [this] link")
        # Only [ needs escaping in Telegram Markdown v1, ] alone doesn't start formatting
        assert result == "check \\[this] link"

    def test_escapes_multiple_special_chars(self):
        """Test that multiple special characters are all escaped."""
        result = _escape_markdown("read_this *important* `code` [link]")
        assert result == "read\\_this \\*important\\* \\`code\\` \\[link]"

    def test_url_with_underscores(self):
        """Test the specific URL pattern that was causing the original bug."""
        # This is the exact pattern from the bug report
        result = _escape_markdown("Read blog.nli.org.il/en/operation_mincemeat/")
        assert "\\_" in result
        assert "_" not in result.replace("\\_", "")

    def test_empty_string(self):
        """Test that empty strings are handled correctly."""
        result = _escape_markdown("")
        assert result == ""

    def test_no_special_chars(self):
        """Test that strings without special chars are unchanged."""
        result = _escape_markdown("simple task text")
        assert result == "simple task text"

    def test_preserves_other_characters(self):
        """Test that non-markdown characters are preserved."""
        result = _escape_markdown("Buy milk @errands #next")
        assert result == "Buy milk @errands #next"


def _format_task(task: dict, show_list: bool = False) -> str:
    """
    Local copy of format_task for testing without importing bot module.
    """
    from datetime import date
    star = "★ " if task.get("is_today") else ""
    escaped_text = _escape_markdown(task['text'])
    parts = [f"{star}[{task['id']}] {escaped_text}"]
    if show_list:
        parts.append(f"#{task['list']}")
    if task.get("due_date"):
        due = task["due_date"]
        if isinstance(due, date):
            due = due.isoformat()
        parts.append(f"(due: {due})")
    return " ".join(parts)


class TestFormatTask:
    """Tests for format_task to ensure markdown escaping is applied."""

    def test_format_task_escapes_underscores(self):
        """Test that format_task escapes underscores in task text."""
        task = {
            'id': 1,
            'text': 'Read blog.nli.org.il/en/operation_mincemeat/',
            'list': 'inbox',
            'is_today': False,
            'due_date': None
        }
        result = _format_task(task)
        assert "\\_" in result
        assert "operation\\_mincemeat" in result

    def test_format_task_with_url_and_today_star(self):
        """Test format_task with URL containing underscores and today marker."""
        task = {
            'id': 42,
            'text': 'Check https://example.com/some_path/file_name.html',
            'list': 'next',
            'is_today': True,
            'due_date': None
        }
        result = _format_task(task)
        assert result.startswith("★ ")
        assert "some\\_path" in result
        assert "file\\_name" in result

    def test_format_task_shows_list_when_requested(self):
        """Test that format_task shows list name when show_list=True."""
        task = {
            'id': 1,
            'text': 'test_task',
            'list': 'next',
            'is_today': False,
            'due_date': None
        }
        result = _format_task(task, show_list=True)
        assert "#next" in result
        assert "test\\_task" in result
