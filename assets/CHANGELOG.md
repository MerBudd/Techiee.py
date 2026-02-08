# Changelog

## [2.6.2-exp] - 2026-02-08 (Experimental)

### Fixed
- **Message History Sync**: Fixed an issue where deleting or regenerating a response (via reactions) wouldn't update the bot's memory. The bot now correctly forgets deleted messages and remembers regenerated ones.
- **Typing Indicator**: Fixed the typing indicator stopping too early or persisting incorrectly. It now uses reference counting to stay active exactly as long as needed, even when multiple people are chatting at once.
- **Settings Visibility**: Settings changes made via `/settings` in tracked channels are now visible to everyone in the channel, similar to how they work in threads.

## [2.6.1-exp] - 2026-02-08 (Experimental)

### Fixed
- **Context Isolation & Scoping**: Resolved "context slipping" issues where context from one conversation (e.g., a DM) would bleed into others. Implemented distinct `context_key` tuples for DMs, tracked channels, threads, and @mentions.
- **Interactive `/settings` Improvements**: 
  - Added user mentions to scope messages in non-shared contexts for better clarity.
  - Settings changes in tracked threads are now public (non-ephemeral), allowing all thread participants to see configuration changes.
- **Context Loading UI**: Replaced fixed defaults in the `/settings` context button with an interactive `ContextModal`, allowing users to choose exactly how many messages to load and for how long the context persists.
- **`/help` Command Stability**: Converted the long help text into a Discord Embed, fixing errors caused by exceeding Discord's 2000-character message limit.
- **Deprecation Fixes**: Resolved `DeprecationWarning` related to `interaction.message` and `message.interaction` by migrating to modern Discord.py metadata fields.
- **Processor Sync**: Updated all multimodal processors (images, videos, YouTube, websites, files) to correctly utilize the new context scoping logic.

## [2.6.0-exp] - 2026-02-07 (Experimental)
 
### Added
- **Multi-Attachment Support**: Techiee can now process all attachments in a message simultaneously (up to Discord's limit), including mixed types like multiple images, videos, and documents.
- **Reaction-Based Actions**: Interactive reactions on bot responses:
  - 🗑️: Delete the bot's response (Author only).
  - 🔄: Regenerate the response (Author only).
- **Reply Chain Context**: Automatically fetches up to 10 previous messages in a reply chain to maintain context when you reply to an older message.
- **Interactive `/settings` Menu**: A comprehensive, GUI-based settings menu using Discord's dropdowns and buttons for managing thinking levels and personas.
- **`/conversation-summary` Command**: Generatesa concise summary of your current conversation history.
 
### Changed
- **Processor Architecture**: Updated all processor cogs to handle lists of attachments and reply chain context fragments.
- **Response Tracking**: Implemented an LRU-cached Response Tracker for reaction processing.

## [2.5.0] - 2026-02-07

### Added
- **Dynamic Date/Time Awareness**: Techiee now knows the current date and time in every conversation.
- **User Identification**: System prompt now includes the user's display name and @username.
- **System Prompt Paid Feature Notes**: System prompt now informs Techiee that image generation and Google Search grounding require a paid API key.
- **`/context` Command**: New slash command to load recent channel messages as context.
  - `count` parameter: Number of messages to load (1-50, default: 10).
  - `lasts_for` parameter: Context persists for multiple messages (1-20, default: 5).
  - **Channel-aware filtering**: Includes your own messages in non-tracked channels, excludes them in tracked channels/threads.
  - **Auto-response**: In non-tracked channels, Techiee responds to your next messages without needing @mention.
  - Works with all content types: text, images, videos, files, YouTube URLs, and website URLs.

### Changed
- **System Prompt Architecture**: Converted static `system_instruction` to a dynamic `get_system_instruction()` function that generates context-aware prompts.
- **System Prompt update**: Updated system prompt slightly to clarify humor and sass.
- **Configs Reorganization**: Reorganized `config.py` for better organization.
- **Google Search Grounding**: Changed Google search grounding tool on/off switching from being manual code un-commenting to a toggle in `config.py`

### Fixed
- **Discord-friendly Math Rendering**: Automatically converts LaTeX math notation (e.g., `$\frac{a}{b}$`, `$\alpha$`, `$x^2$`) into readable Unicode text wrapped in code blocks for better Discord display.

## [2.4.0] - 2026-01-28

### Added
- **503 Error Retry Button**: Implemented a retry mechanism for "Server Overloaded" (503) errors.
  - Interactive retry button with a countdown (3s).
  - Only the original message author can use it.
  - Automatic error handling: button updates to reflect retry status and failure counts.
  - Error message is automatically deleted and replaced with the actual response upon successful retry.

## [2.3.0] - 2026-01-27

### Added
- **Image Generation**: Added `/image` command to generate or edit images using Nano Banana. Note: Requires a paid API key, will return error 429 with a free key.
- **Modular Cog Architecture**: Completely reorganized codebase into Discord.py cogs for better maintainability.
  - **Processors** (`cogs/processors/`): Separate cogs for each content type (text, images, videos, files, YouTube, websites).
  - **Commands** (`cogs/commands/`): Logically grouped slash commands (admin, general, settings, image_gen).
  - **Router** (`cogs/router.py`): Central message dispatcher that routes to appropriate processors.
  - **Utils** (`utils/`): Shared utilities for Gemini API calls and helper functions.
- **Multimodal Chat History**: Implemented support for multimodal chat history. Images, videos, files, etc. are now included in the chat history.
- **API Key Rotation**: Implemented automatic API key rotation for extended usage.

### Changed
- **Main File**: Reduced from ~880 lines to ~75 lines, now just loads cogs.
- **Code Organization**: AI generation logic in `utils/gemini.py`, routing logic in cogs.

### Fixed
- **Bot Mention Support**: Bot now responds when @ mentioned in any channel, as intended.
- **Public Thread Creation**: Threads are now created as public instead of private, as intended.

## [2.2.0] - 2026-01-26

### Added
- **`/forget` Command**: New slash command to clear message history, replacing the old keyword-based method.
- **Discord Reply Feature**: Bot now uses Discord's native reply feature when responding to messages, making it easier to track conversations.
- **Video Processing Logic**: Added a separate function for video attachments to wait for them to finish processing on Google's side, so the bot can reply to them. Times out after 120 seconds.

### Changed
- **History Reset**: Replaced keyword-based history reset ("CLEAR HISTORY", etc.) with the cleaner `/forget` slash command.
- **Help Text**: Improved formatting and clarity, corrected default thinking level to `minimal`.

### Fixed
- **Typing Indicator**: Improved management of the Discord typing indicator to ensure it remains active during long response generations and cancels correctly upon message delivery.

## [2.1.0] - 2026-01-26

### Added
- **Centralized Configuration**: Moved Gemini generation settings to `config.py` for easier management.
- **Experimental Grounding**: Added integration for Google Search grounding tool (currently commented out due to API tier requirements).

### Changed
- **Thinking Defaults**: Updated the default thinking level for the AI.
- **Command Management**: Enhanced global command synchronization logic for better reliability.
- **Clarified docs**: Updated the README, SETUP and CHANGELOG files, and updated a few comments in `config.py` and `Techiee.py`

## [2.0.0] - 2026-01-21

### Added
- **Slash Commands**:
  - `/thinking`: Adjustable reasoning depth (minimal, low, medium, high).
  - `/persona`: Custom AI personality persistence across sessions.
- **Contextual Settings**: Implemented per-user and per-thread memory for persona and thinking level settings.
- **Files API Integration**: Enhanced handling of large attachments using Google's Gemini Files API.
- **Improved Tool Support**: Integrated `UrlContext` tool for enhanced processing of website links.

### Changed
- **SDK Migration**: Switched to the new `google-genai` SDK for modern feature support.
- **Model Upgrade**: Updated model to `gemini-3-flash-preview`.
- **Dependencies**: The Google GenAI SDK and Files API now handle most file and URL processing, which allowed for 5 dependencies to be removed while still keeping the same capabilities.