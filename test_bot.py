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
