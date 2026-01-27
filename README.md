<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="/assets/Techiee-light.png">
    <source media="(prefers-color-scheme: light)" srcset="/assets/Techiee-dark.png">
    <img
    alt="Techiee logo showing a star with 8 sides and rounded corners, with a gradient color going from blue to purple to orange. To the right of the star is the text 'Techiee.py' written in a semibold and rounded font."
    src="/assets/Techiee-light.png"
    style="width: 75%; height: auto;"
    >
  </picture>
</div>

## <img src="/assets/Techiee-star.png" width="30" height="30" align=top> What is Techiee? <img src="/assets/Techiee-star.png" width="30" height="30" align=top>

Techiee is an advanced Discord chatbot built on Google's Gemini models. It is multimodal; which means it can understand text, images, videos, documents, websites, and even YouTube videos, together, directly within your Discord server.

This is the Python version of Techiee. It has been completely rewritten to support the latest Gemini 3 models and multimodal capabilities.

## Key Features

- **🖼️ Multimodal Support**: Send images, videos, documents, PDFs, or text files and Techiee will analyze them.
- **🌐 Web & YouTube Integration**: Paste a website URL or a YouTube link, and Techiee can summarize or discuss the content.
- **🧠 Advanced Reasoning**: Use the `/thinking` command to adjust the AI's reasoning depth (Minimal to High).
- **🎭 Persistent Personas**: Set a custom personality with `/persona` that stays active even after history resets.
- **💬 Memory**: Maintains per-user and per-thread message history and personas for natural conversations.
- **🧵 Threads**: Create dedicated chat spaces with `/createthread`.
- **🎨 Image Generation**: Generate or edit images with `/image`, using Nano Banana (requires paid API key).
- **🔍 Google Search Grounding**: Support for real-time web search (requires paid plan, disabled by default).

>[!NOTE]
> Personas and Thinking levels only apply to the user who used the command in DMs, @mentions, and tracked channels. In threads created with `/createthread`, they apply to everyone.

## Configuration

You can tweak all bot settings, including safety filters, model parameters, and tracked channels, inside the [config.py](config.py) file.

## Commands

- `/help`: Shows available commands and bot information.
- `/createthread <name>`: Starts a new thread where Techiee will respond to every message.
- `/thinking <level>`: Sets the AI's reasoning level (minimal, low, medium, high).
- `/persona <description>`: Sets a custom personality. Use `/persona default` to reset.
- `/forget`: Clears your message history with Techiee.
- `/image`: Generates or edits an image using Nano Banana (requires paid API key).
- `/sync`: Syncs slash commands globally (Owner only).

---

<div align="center">

<table>
  <tr>
    <td align="center">
      <a href="/assets/SETUP.md">
        <picture>
          <source media="(prefers-color-scheme: dark)" srcset="/assets/Setup-light.png">
          <source media="(prefers-color-scheme: light)" srcset="/assets/Setup-dark.png">
          <img
            alt="Paper icon with gradient colors, to the right of it is the text 'Setup'"
            src="/assets/Setup-light.png"
            style="max-height: 90px; width: auto; max-width: 100%;"
          >
        </picture>
        <br>
        <strong>Detailed installation instructions</strong>
      </a>
    </td>
    <td align="center">
      <a href="/assets/CHANGELOG.md">
        <picture>
          <source media="(prefers-color-scheme: dark)" srcset="/assets/Changelogs-light.png">
          <source media="(prefers-color-scheme: light)" srcset="/assets/Changelogs-dark.png">
          <img
            alt="Paper icon with gradient colors, to the right of it is the text 'Changelogs'"
            src="/assets/Changelogs-light.png"
            style="max-height: 90px; width: auto; max-width: 100%;"
          >
        </picture>
        <br>
        <strong>List of changes</strong>
      </a>
    </td>
  </tr>
</table>

</div>


---

*Developed by Budd (@merbudd) and Tech (@techgamerexpert).*
