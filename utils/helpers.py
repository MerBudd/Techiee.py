"""
Utility functions for message handling and URL processing.
"""
import re


async def split_and_send_messages(message, text, max_length, user_id=None):
    """Split long messages and send them sequentially, using reply for first message.
    
    Features:
    - Does not cut words in the middle
    - Preserves markdown formatting by cutting before markdown elements
    - Adds "... [m/n]" indicators (no "..." on final message)
    - Mentions the user in 2nd and later split messages for notification visibility
    
    Args:
        message: The Discord message to reply to
        text: The text content to send
        max_length: Maximum length per message
        user_id: Optional user ID to mention in continuation messages
    """
    if not text:
        return
    
    # If text fits in one message, just send it
    if len(text) <= max_length:
        await message.reply(text, mention_author=True)
        return
    
    # Reserve space for indicator " ... [XX/XX]" (max 13 chars) + mention " <@USER_ID>" (max ~25 chars)
    mention_reserve = 25 if user_id else 0
    indicator_reserve = 15 + mention_reserve
    effective_max = max_length - indicator_reserve
    
    # Markdown patterns that should not be split in the middle
    # Paired markers: **, *, ~~, __, _, ```, `
    paired_markers = ['```', '**', '__', '~~', '*', '_', '`']
    # Block markers at start of line: >, #, -, numbered lists
    block_markers = ['>', '#', '-', '*']
    
    def count_unclosed_markers(text_chunk):
        """Count unclosed paired markdown markers in a text chunk."""
        unclosed = {}
        for marker in paired_markers:
            # Count occurrences
            count = text_chunk.count(marker)
            # Special handling for triple backticks vs single backticks
            if marker == '`' and '```' in text_chunk:
                # Subtract triple backticks from single backtick count
                count -= text_chunk.count('```') * 3
            if count % 2 != 0:
                unclosed[marker] = True
        return unclosed
    
    def find_safe_cut_point(text, max_pos):
        """Find a safe position to cut the text, respecting word and markdown boundaries."""
        if max_pos >= len(text):
            return len(text)
        
        # Start from max_pos and work backwards to find a space or newline
        cut_pos = max_pos
        
        # First, try to find a newline (best cut point)
        newline_pos = text.rfind('\n', 0, max_pos)
        if newline_pos > max_pos * 0.5:  # Only use if it's not too far back
            # Check if the next line starts with a block marker
            next_line_start = newline_pos + 1
            for marker in block_markers:
                if next_line_start < len(text) and text[next_line_start:].startswith(marker):
                    return newline_pos + 1  # Cut right before the block marker line
            return newline_pos + 1
        
        # Find the last space before max_pos
        space_pos = text.rfind(' ', 0, max_pos)
        if space_pos > max_pos * 0.3:  # Only use if it's not too far back
            cut_pos = space_pos + 1
        else:
            # If no good space found, just cut at max_pos
            cut_pos = max_pos
        
        # Check for unclosed markdown markers
        chunk = text[:cut_pos]
        unclosed = count_unclosed_markers(chunk)
        
        if unclosed:
            # Find the last occurrence of any unclosed marker and cut before it
            for marker in unclosed:
                # Find the last opening of this marker
                last_marker_pos = chunk.rfind(marker)
                if last_marker_pos > 0:
                    # Cut before the word containing this marker
                    # Find the start of the word
                    word_start = chunk.rfind(' ', 0, last_marker_pos)
                    if word_start == -1:
                        word_start = chunk.rfind('\n', 0, last_marker_pos)
                    if word_start == -1:
                        word_start = 0
                    else:
                        word_start += 1
                    
                    if word_start > 0:
                        cut_pos = min(cut_pos, word_start)
        
        # Make sure we don't cut in the middle of a word
        # If cut_pos is not at a space/newline, move back to the last space
        if cut_pos < len(text) and cut_pos > 0:
            if text[cut_pos - 1] not in ' \n' and (cut_pos >= len(text) or text[cut_pos] not in ' \n'):
                # We're in the middle of a word, find the last space
                last_space = text.rfind(' ', 0, cut_pos)
                if last_space > 0:
                    cut_pos = last_space + 1
                else:
                    # Check for newline
                    last_newline = text.rfind('\n', 0, cut_pos)
                    if last_newline > 0:
                        cut_pos = last_newline + 1
        
        return max(1, cut_pos)  # Ensure we always make progress
    
    # Split the text into chunks
    chunks = []
    remaining = text
    
    while remaining:
        if len(remaining) <= effective_max:
            chunks.append(remaining)
            break
        
        cut_pos = find_safe_cut_point(remaining, effective_max)
        chunk = remaining[:cut_pos].rstrip()
        chunks.append(chunk)
        remaining = remaining[cut_pos:].lstrip()
    
    # Add indicators to each chunk
    # For continuation messages (2nd and later), add user mention after indicator
    user_mention = f" <@{user_id}>" if user_id else ""
    total = len(chunks)
    for i in range(len(chunks)):
        if i == 0:
            # First message - no mention needed (it's a reply with mention_author=True)
            if total > 1:
                chunks[i] = f"{chunks[i]}... [{i+1}/{total}]"
            # If only one chunk, it was already handled above, but just in case
        elif i < total - 1:
            # Middle messages - add "... [m/n]" and user mention
            chunks[i] = f"{chunks[i]}... [{i+1}/{total}]{user_mention}"
        else:
            # Last message - just add "[m/n]" without dots, but with user mention
            chunks[i] = f"{chunks[i]} [{i+1}/{total}]{user_mention}"
    
    # Send the messages
    for idx, chunk in enumerate(chunks):
        if idx == 0:
            await message.reply(chunk, mention_author=True)
        else:
            await message.channel.send(chunk)


def clean_discord_message(input_string):
    """Clean Discord message of any <@!123456789> tags."""
    bracket_pattern = re.compile(r'<[^>]+>')
    cleaned_content = bracket_pattern.sub('', input_string)
    return cleaned_content.strip()


def extract_url(string):
    """Extract URL from a string."""
    url_regex = re.compile(
        r'(?:(?:https?|ftp)://)?'
        r'(?:\S+(?::\S*)?@)?'
        r'(?:'
        r'(?!(?:10|127)(?:\.\d{1,3}){3})'
        r'(?!(?:169\.254|192\.168)(?:\.\d{1,3}){2})'
        r'(?!172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})'
        r'(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])'
        r'(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){2}'
        r'(?:\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-4]))'
        r'|'
        r'(?:www.)?'
        r'(?:[a-z\u00a1-\uffff0-9]-?)*[a-z\u00a1-\uffff0-9]+'
        r'(?:\.(?:[a-z\u00a1-\uffff]{2,}))+'
        r'(?:\.(?:[a-z\u00a1-\uffff]{2,})+)*'
        r')'
        r'(?::\d{2,5})?'
        r'(?:[/?#]\S*)?',
        re.IGNORECASE
    )
    match = re.search(url_regex, string)
    return match.group(0) if match else None


def is_youtube_url(url):
    """Check if URL is a YouTube URL."""
    if url is None:
        return False
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    return re.match(youtube_regex, url) is not None
