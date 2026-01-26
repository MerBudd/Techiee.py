# Changelog

## [2.2.0] - 2026-01-26

### Added
- **`/forget` Command**: New slash command to clear message history, replacing the old keyword-based method.
- **Discord Reply Feature**: Bot now uses Discord's native reply feature when responding to messages, making it easier to track conversations.

### Changed
- **History Reset**: Replaced keyword-based history reset ("CLEAR HISTORY", etc.) with the cleaner `/forget` slash command.
- **Help Text**: Improved formatting and clarity, corrected default thinking level to `minimal`.

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

### Fixed
- **Typing Indicator**: Improved management of the Discord typing indicator to ensure it remains active during long response generations and cancels correctly upon message delivery.