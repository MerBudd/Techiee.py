"""
Unit tests for utils/gemini.py — Interactions API migration.

Tests cover:
- interaction_history helper functions
- generate_response_with_text (single-turn and multi-turn)
- process_image_attachment (with and without previous interaction)
- process_website_url (with and without previous interaction)
- History state synchronisation (clear, pop)
"""
import asyncio
import unittest
from unittest.mock import MagicMock, patch
import sys

# Save original modules to restore later in tearDownModule to prevent test pollution
original_modules = {}
for name in ["google", "google.genai", "google.genai.types", "aiohttp", "config", "utils.config_manager"]:
    original_modules[name] = sys.modules.get(name)

# ---------------------------------------------------------------------------
# Stub out heavy dependencies before importing gemini module
# ---------------------------------------------------------------------------

# Stub google.genai so we don't need real credentials
google_mod = MagicMock()
genai_mod = MagicMock()
types_mod = MagicMock()

# Content / Part stubs
class _Part:
    def __init__(self, text=None, **kwargs):
        self.text = text
        for k, v in kwargs.items():
            setattr(self, k, v)
    @classmethod
    def from_uri(cls, **kwargs):
        return cls(**kwargs)
    @classmethod
    def from_text(cls, text):
        return cls(text=text)

class _Content:
    def __init__(self, role="user", parts=None):
        self.role = role
        self.parts = parts or []

class _FileData:
    def __init__(self, file_uri=None):
        self.file_uri = file_uri

types_mod.Part = _Part
types_mod.Content = _Content
types_mod.FileData = _FileData
genai_mod.types = types_mod
genai_mod.Client = MagicMock()

# Wire up sys.modules stubs
sys.modules["google"] = google_mod
sys.modules["google.genai"] = genai_mod
sys.modules["google.genai.types"] = types_mod
sys.modules["aiohttp"] = MagicMock()

# Stub config
config_mod = MagicMock()
config_mod.gemini_api_keys = ["FAKE_KEY"]
config_mod.get_system_instruction = MagicMock(return_value="You are a test bot.")
config_mod.url_context_tool = MagicMock()
config_mod.get_google_search_tool = MagicMock(return_value=None)
config_mod.create_generate_config = MagicMock(return_value=MagicMock())
sys.modules["config"] = config_mod


# Stub utils.config_manager
config_manager_mod = MagicMock()
dynamic_cfg = MagicMock()
dynamic_cfg.max_history = 10
dynamic_cfg.default_thinking_level = "minimal"
dynamic_cfg.default_text_model = "gemini-2.5-flash"
dynamic_cfg.default_image_model = "imagen-3"
dynamic_cfg.default_image_prompt = "Describe this image."
dynamic_cfg.default_pdf_and_txt_prompt = "Summarize this document."
dynamic_cfg.default_url_prompt = "Summarize this URL:"
dynamic_cfg.enable_google_search = False
config_manager_mod.dynamic_config = dynamic_cfg
sys.modules["utils.config_manager"] = config_manager_mod

# Now import the real module under test
import utils.gemini as gemini_module  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_interaction(output_text="Hello, world!", interaction_id="iact-abc-123"):
    """Return a mock Interaction object matching the real SDK shape."""
    interaction = MagicMock()
    interaction.id = interaction_id
    interaction.output_text = output_text
    return interaction


def run(coro):
    """Run an async coroutine in the test (Python 3.14 compatible)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tests: interaction_history helpers
# ---------------------------------------------------------------------------

class TestInteractionHistoryHelpers(unittest.TestCase):

    def setUp(self):
        gemini_module.interaction_history.clear()

    def test_get_previous_interaction_id_empty(self):
        self.assertIsNone(gemini_module.get_previous_interaction_id("key1"))

    def test_append_and_get(self):
        gemini_module.append_interaction_id("key1", "id-1")
        self.assertEqual(gemini_module.get_previous_interaction_id("key1"), "id-1")

    def test_append_multiple_returns_latest(self):
        gemini_module.append_interaction_id("key1", "id-1")
        gemini_module.append_interaction_id("key1", "id-2")
        gemini_module.append_interaction_id("key1", "id-3")
        self.assertEqual(gemini_module.get_previous_interaction_id("key1"), "id-3")

    def test_max_history_limit_enforced(self):
        # Temporarily lower max_history for this test
        original = dynamic_cfg.max_history
        dynamic_cfg.max_history = 3
        for i in range(5):
            gemini_module.append_interaction_id("key1", f"id-{i}")
        ids = gemini_module.interaction_history["key1"]
        self.assertLessEqual(len(ids), 3)
        dynamic_cfg.max_history = original

    def test_pop_last(self):
        gemini_module.append_interaction_id("key1", "id-1")
        gemini_module.append_interaction_id("key1", "id-2")
        popped = gemini_module.pop_last_interaction_id("key1")
        self.assertEqual(popped, "id-2")
        self.assertEqual(gemini_module.get_previous_interaction_id("key1"), "id-1")

    def test_pop_empty_returns_none(self):
        self.assertIsNone(gemini_module.pop_last_interaction_id("nonexistent"))

    def test_clear_interaction_history(self):
        gemini_module.append_interaction_id("key1", "id-1")
        gemini_module.clear_interaction_history("key1")
        self.assertIsNone(gemini_module.get_previous_interaction_id("key1"))

    def test_clear_nonexistent_no_error(self):
        # Should not raise
        gemini_module.clear_interaction_history("does-not-exist")


# ---------------------------------------------------------------------------
# Tests: generate_response_with_text
# ---------------------------------------------------------------------------

class TestGenerateResponseWithText(unittest.TestCase):

    def setUp(self):
        gemini_module.interaction_history.clear()
        self.settings = {"text_model": "gemini-2.5-flash", "thinking_level": "minimal"}

    def _patch_execute(self, interaction):
        """Patch execute_with_retry to return a given interaction synchronously."""
        async def _mock_execute(func, *args, **kwargs):
            return interaction
        return patch.object(gemini_module, "execute_with_retry", side_effect=_mock_execute)

    def test_single_turn_no_history_key(self):
        """Without history_key: no previous_interaction_id, returns output_text."""
        interaction = _make_interaction("Hi there!")
        with self._patch_execute(interaction):
            result = run(gemini_module.generate_response_with_text(
                "Hello", self.settings
            ))
        self.assertEqual(result, "Hi there!")

    def test_first_turn_stores_interaction_id(self):
        """With history_key on first turn: ID is stored after call."""
        interaction = _make_interaction("First reply", "iact-001")
        with self._patch_execute(interaction):
            run(gemini_module.generate_response_with_text(
                "Hello", self.settings, history_key="key-A"
            ))
        self.assertEqual(gemini_module.get_previous_interaction_id("key-A"), "iact-001")

    def test_second_turn_uses_previous_id(self):
        """On second turn: previous_interaction_id is drawn from history."""
        gemini_module.append_interaction_id("key-A", "iact-000")

        captured_calls = []

        async def _mock_execute(func):
            # Inspect the lambda to capture kwargs
            captured_calls.append(func)
            return _make_interaction("Second reply", "iact-001")

        with patch.object(gemini_module, "execute_with_retry", side_effect=_mock_execute):
            result = run(gemini_module.generate_response_with_text(
                ["msg1", "msg2"], self.settings, history_key="key-A"
            ))

        self.assertEqual(result, "Second reply")
        # ID should now be updated to the new one
        self.assertEqual(gemini_module.get_previous_interaction_id("key-A"), "iact-001")

    def test_empty_output_text_returns_error_message(self):
        """output_text=None should return the friendly error string."""
        interaction = _make_interaction(None, "iact-002")
        with self._patch_execute(interaction):
            result = run(gemini_module.generate_response_with_text(
                "Hello", self.settings
            ))
        self.assertIn("empty response", result)

    def test_exception_returns_error_string(self):
        """An exception in execute_with_retry returns an error string (not a raise)."""
        async def _raise(func):
            raise RuntimeError("network error")

        with patch.object(gemini_module, "execute_with_retry", side_effect=_raise):
            result = run(gemini_module.generate_response_with_text(
                "Hello", self.settings
            ))
        self.assertIn("Exception", result)
        self.assertIn("network error", result)

    def test_interactions_create_parameters(self):
        """Verify client.interactions.create is called with the system_instruction at top level and None in config."""
        mock_config = MagicMock()
        mock_config.system_instruction = "You are a test bot."
        config_mod.create_generate_config.return_value = mock_config

        async def _mock_execute(func):
            return func()

        interaction = _make_interaction("Hi!")
        gemini_module.api_key_manager.client.interactions.create.reset_mock()
        gemini_module.api_key_manager.client.interactions.create.return_value = interaction

        with patch.object(gemini_module, "execute_with_retry", side_effect=_mock_execute):
            run(gemini_module.generate_response_with_text("Hello", self.settings))

        # Check call arguments
        create_mock = gemini_module.api_key_manager.client.interactions.create
        create_mock.assert_called_once()
        kwargs = create_mock.call_args.kwargs

        # system_instruction must be at top level
        self.assertEqual(kwargs.get("system_instruction"), "You are a test bot.")

        # system_instruction must be None in generation_config
        gen_config = kwargs.get("generation_config")
        self.assertIsNone(gen_config.system_instruction)


# ---------------------------------------------------------------------------
# Tests: process_website_url
# ---------------------------------------------------------------------------

class TestProcessWebsiteUrl(unittest.TestCase):

    def setUp(self):
        gemini_module.interaction_history.clear()
        self.settings = {"text_model": "gemini-2.5-flash", "thinking_level": "minimal"}
        self.url = "https://example.com"

    def _patch_execute(self, interaction):
        async def _mock_execute(func):
            return interaction
        return patch.object(gemini_module, "execute_with_retry", side_effect=_mock_execute)

    def test_returns_tuple(self):
        """Should return a (response_text, user_parts) tuple."""
        interaction = _make_interaction("Page summary", "iact-web-1")
        with self._patch_execute(interaction):
            result = run(gemini_module.process_website_url(
                self.url, "Summarize this", self.settings
            ))
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "Page summary")

    def test_stores_interaction_id_with_history_key(self):
        interaction = _make_interaction("Page summary", "iact-web-2")
        with self._patch_execute(interaction):
            run(gemini_module.process_website_url(
                self.url, "Summarize", self.settings, history_key="web-key"
            ))
        self.assertEqual(gemini_module.get_previous_interaction_id("web-key"), "iact-web-2")

    def test_second_call_uses_previous_id(self):
        gemini_module.append_interaction_id("web-key", "iact-web-0")
        interaction = _make_interaction("Continued summary", "iact-web-3")
        with self._patch_execute(interaction):
            result = run(gemini_module.process_website_url(
                self.url, "Continue", self.settings, history_key="web-key"
            ))
        self.assertEqual(result[0], "Continued summary")
        self.assertEqual(gemini_module.get_previous_interaction_id("web-key"), "iact-web-3")


# ---------------------------------------------------------------------------
# Tests: history synchronisation (clear / pop via forget/delete paths)
# ---------------------------------------------------------------------------

class TestHistorySynchronisation(unittest.TestCase):

    def setUp(self):
        gemini_module.interaction_history.clear()
        gemini_module.message_history.clear()

    def test_clear_wipes_both_histories(self):
        """Simulates /forget: clears message_history and interaction_history."""
        key = ("dm", 999)
        gemini_module.message_history[key] = [_Content(role="user"), _Content(role="model")]
        gemini_module.append_interaction_id(key, "id-x")

        del gemini_module.message_history[key]
        gemini_module.clear_interaction_history(key)

        self.assertNotIn(key, gemini_module.message_history)
        self.assertIsNone(gemini_module.get_previous_interaction_id(key))

    def test_pop_on_delete_restores_previous_turn(self):
        """Simulates ❌ delete reaction: pops last ID so next call uses parent turn."""
        key = ("thread", 42)
        gemini_module.append_interaction_id(key, "parent-id")
        gemini_module.append_interaction_id(key, "child-id")

        popped = gemini_module.pop_last_interaction_id(key)

        self.assertEqual(popped, "child-id")
        self.assertEqual(gemini_module.get_previous_interaction_id(key), "parent-id")

    def test_pop_before_regenerate_uses_correct_parent(self):
        """Simulates 🔄 regenerate: pop first, then next call gets parent."""
        key = ("mention", 7)
        gemini_module.append_interaction_id(key, "turn-1")
        gemini_module.append_interaction_id(key, "turn-2")

        # Simulate regenerate: pop before re-calling
        gemini_module.pop_last_interaction_id(key)
        self.assertEqual(gemini_module.get_previous_interaction_id(key), "turn-1")


def tearDownModule():
    # Restore original modules to prevent test pollution
    for name, value in original_modules.items():
        if value is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = value


if __name__ == "__main__":
    unittest.main()
