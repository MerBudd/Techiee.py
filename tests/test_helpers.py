import unittest
from utils.helpers import (
    extract_custom_emojis,
    get_emoji_cdn_url,
    clean_discord_message,
    extract_url,
    is_youtube_url,
    convert_latex_to_discord,
)


class TestHelpers(unittest.TestCase):
    """Test case for utils/helpers.py utilities."""

    def test_extract_custom_emojis(self):
        # AAA Pattern: Arrange, Act, Assert
        
        # Test static emoji
        text_static = "Hello <:smile:1234567890> world!"
        res_static = extract_custom_emojis(text_static)
        self.assertEqual(res_static, [("smile", "1234567890", False)])

        # Test animated emoji
        text_animated = "Look at this <a:dance:9876543210>!"
        res_animated = extract_custom_emojis(text_animated)
        self.assertEqual(res_animated, [("dance", "9876543210", True)])

        # Test multiple emojis
        text_multiple = "Some <:one:111> and <a:two:222> emojis"
        res_multiple = extract_custom_emojis(text_multiple)
        self.assertEqual(res_multiple, [("one", "111", False), ("two", "222", True)])

        # Test empty input
        self.assertEqual(extract_custom_emojis(""), [])
        self.assertEqual(extract_custom_emojis(None), [])

    def test_get_emoji_cdn_url(self):
        # Arrange & Act & Assert
        self.assertEqual(
            get_emoji_cdn_url("12345"),
            "https://cdn.discordapp.com/emojis/12345.png?size=128"
        )
        self.assertEqual(
            get_emoji_cdn_url("67890", animated=True),
            "https://cdn.discordapp.com/emojis/67890.gif?size=128"
        )

    def test_clean_discord_message(self):
        # Arrange & Act & Assert
        raw_msg = "Hello <:smile:12345> and <a:dance:67890>!"
        cleaned = clean_discord_message(raw_msg)
        self.assertEqual(cleaned, "Hello [Emoji: smile] and [Animated Emoji: dance]!")

    def test_extract_url(self):
        # Arrange & Act & Assert
        self.assertEqual(extract_url("Check http://example.com/test out"), "http://example.com/test")
        self.assertEqual(extract_url("No URL here"), None)

    def test_is_youtube_url(self):
        # Arrange & Act & Assert
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertTrue(is_youtube_url("https://youtu.be/dQw4w9WgXcQ"))
        self.assertFalse(is_youtube_url("https://google.com"))
        self.assertFalse(is_youtube_url(None))

    def test_convert_latex_to_discord(self):
        # Arrange & Act & Assert
        
        # Test inline latex
        text_inline = "The formula is $E=mc^2$."
        converted_inline = convert_latex_to_discord(text_inline)
        self.assertEqual(converted_inline, "The formula is `E=mc²`.")

        # Test display latex
        text_display = "Math:\n$$\\frac{a}{b}$$"
        converted_display = convert_latex_to_discord(text_display)
        self.assertEqual(converted_display, "Math:\n```\n(a)/(b)\n```")


if __name__ == "__main__":
    unittest.main()
