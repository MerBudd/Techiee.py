"""
Settings commands cog - AI settings commands with Discord UI.
"""
import discord
from discord import app_commands, ui
from discord.ext import commands

from config import tracked_channels, max_history, cooldowns, help_text
from utils.gemini import (
    tracked_threads,
    context_settings,
    default_settings,
    set_settings_for_context,
    get_message_history_contents,
    get_history_key,
    message_history,
    generate_response_with_text,
    pending_context,
    set_pending_context,
    get_pending_context,
)



def get_settings_key_from_interaction(interaction: discord.Interaction):
    """Get the appropriate settings key from an interaction (slash command context)."""
    channel_id = interaction.channel.id
    user_id = interaction.user.id
    user_mention = interaction.user.mention
    
    # Thread context (shared by everyone in thread)
    if channel_id in tracked_threads:
        return (("thread", channel_id), "this thread", True)  # is_shared=True
    
    # DM context
    if isinstance(interaction.channel, discord.DMChannel):
        return (("dm", user_id), "your DMs", False)
    
    # Tracked channel context (per-user in tracked channel)
    if channel_id in tracked_channels:
        return (("tracked", user_id), f"{user_mention} in this tracked channel", False)
    
    # @mention context
    return (("mention", user_id), f"{user_mention} for @mentions", False)


class ThinkingSelect(ui.Select):
    """Dropdown for selecting AI thinking level."""
    
    def __init__(self, current_level: str):
        options = [
            discord.SelectOption(
                label="Minimal", value="minimal",
                description="Fastest, less reasoning (default)",
                default=(current_level == "minimal"),
                emoji="⚡"
            ),
            discord.SelectOption(
                label="Low", value="low",
                description="Fast, simple reasoning",
                default=(current_level == "low"),
                emoji="🏃"
            ),
            discord.SelectOption(
                label="Medium", value="medium",
                description="Balanced thinking",
                default=(current_level == "medium"),
                emoji="⚖️"
            ),
            discord.SelectOption(
                label="High", value="high",
                description="Deep reasoning",
                default=(current_level == "high"),
                emoji="🧠"
            ),
        ]
        super().__init__(placeholder="Select thinking level...", options=options, custom_id="thinking_select")
    
    async def callback(self, interaction: discord.Interaction):
        settings_key, scope_msg, _ = get_settings_key_from_interaction(interaction)
        current_settings = context_settings.get(settings_key, default_settings.copy())
        current_settings["thinking_level"] = self.values[0]
        set_settings_for_context(settings_key, current_settings)
        
        # Acknowledge the interaction silently (don't edit the ephemeral settings menu)
        await interaction.response.defer()
        
        # Always send a public message for the change
        await interaction.channel.send(f"🧠 Thinking level set to **{self.values[0]}** for {scope_msg}.")


class PersonaModal(ui.Modal, title="Set Custom Persona"):
    """Modal for setting a custom persona."""
    
    persona_input = ui.TextInput(
        label="Persona Description",
        style=discord.TextStyle.paragraph,
        placeholder="Describe the persona you want the AI to adopt...\nLeave empty to reset to default.",
        required=False,
        max_length=2000
    )
    
    def __init__(self, settings_key, scope_msg):
        super().__init__()
        self.settings_key = settings_key
        self.scope_msg = scope_msg
    
    async def on_submit(self, interaction: discord.Interaction):
        current_settings = context_settings.get(self.settings_key, default_settings.copy())
        
        # Acknowledge silently and send public message
        await interaction.response.defer()
        
        if not self.persona_input.value or self.persona_input.value.lower() == "default":
            current_settings["persona"] = None
            set_settings_for_context(self.settings_key, current_settings)
            await interaction.channel.send(f"🎭 Persona reset to default for {self.scope_msg}.")
        else:
            current_settings["persona"] = self.persona_input.value
            set_settings_for_context(self.settings_key, current_settings)
            persona_preview = self.persona_input.value[:100] + "..." if len(self.persona_input.value) > 100 else self.persona_input.value
            await interaction.channel.send(f"🎭 Persona set for {self.scope_msg}:\n> {persona_preview}")


class PersonaButton(ui.Button):
    """Button to open persona modal."""
    
    def __init__(self, settings_key, scope_msg):
        super().__init__(label="Set Persona", style=discord.ButtonStyle.primary, emoji="🎭", custom_id="persona_button")
        self.settings_key = settings_key
        self.scope_msg = scope_msg
    
    async def callback(self, interaction: discord.Interaction):
        modal = PersonaModal(self.settings_key, self.scope_msg)
        await interaction.response.send_modal(modal)

class ContextModal(ui.Modal, title="Load Context"):
    """Modal for customizing context loading."""
    
    count = ui.TextInput(
        label="Number of messages to load (1-50)",
        default="10",
        min_length=1,
        max_length=2,
        placeholder="10"
    )
    lasts_for = ui.TextInput(
        label="Context lasts for X messages (1-20)",
        default="5",
        min_length=1,
        max_length=2,
        placeholder="5"
    )
    
    def __init__(self, context_key, channel):
        super().__init__()
        self.context_key = context_key
        self.channel = channel
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse and validate inputs
        try:
            count = max(1, min(50, int(self.count.value)))
        except ValueError:
            count = 10
        try:
            duration = max(1, min(20, int(self.lasts_for.value)))
        except ValueError:
            duration = 5
        
        bot = interaction.client
        user_id = interaction.user.id
        channel_id = self.channel.id
        await interaction.response.defer()
        
        # Determine if this is a tracked context
        is_tracked = channel_id in tracked_channels or channel_id in tracked_threads
        is_dm = isinstance(self.channel, discord.DMChannel)
        
        try:
            # Fetch messages from channel history (matching /context filtering)
            messages = []
            async for msg in self.channel.history(limit=count * 3):
                # In tracked channels/threads: skip user's own messages
                if is_tracked and msg.author.id == user_id:
                    continue
                
                # Skip bot's messages that are replies to the user
                if msg.author.id == bot.user.id:
                    if msg.reference and msg.reference.resolved:
                        if hasattr(msg.reference.resolved, 'author') and msg.reference.resolved.author.id == user_id:
                            continue
                    if interaction.user in msg.mentions:
                        continue
                    continue  # Skip all bot messages in context modal
                
                messages.append(msg)
                if len(messages) >= count:
                    break
            
            if not messages:
                filter_note = " (your messages and my replies to you are excluded)" if is_tracked else " (my replies to you are excluded)"
                await interaction.channel.send(f"❌ No messages found to load as context{filter_note}.")
                return
            
            messages.reverse()
            
            import aiohttp
            from google.genai.types import Part, Content
            context_contents = []
            for msg in messages:
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
                text = f"[CONTEXT MESSAGE from {msg.author.display_name} (@{msg.author.name}) at {timestamp}]:\n{msg.content}"
                parts = [Part(text=text)]
                
                # Download and include image attachments
                if msg.attachments:
                    async with aiohttp.ClientSession() as session:
                        for attachment in msg.attachments:
                            if attachment.content_type and attachment.content_type.startswith('image/'):
                                try:
                                    async with session.get(attachment.url) as resp:
                                        if resp.status == 200:
                                            image_bytes = await resp.read()
                                            parts.append(Part(inline_data={
                                                "mime_type": attachment.content_type,
                                                "data": image_bytes
                                            }))
                                except Exception:
                                    parts.append(Part(text=f"[Failed to load image: {attachment.filename}]"))
                            else:
                                parts.append(Part(text=f"[Attachment: {attachment.filename}]"))
                
                # Download sticker images
                if msg.stickers:
                    async with aiohttp.ClientSession() as session:
                        for sticker in msg.stickers:
                            sticker_text = f"[Sticker: {sticker.name}]"
                            if hasattr(sticker, 'url') and sticker.url:
                                try:
                                    async with session.get(str(sticker.url)) as resp:
                                        if resp.status == 200:
                                            image_bytes = await resp.read()
                                            content_type = resp.headers.get('Content-Type', 'image/png')
                                            if 'json' not in content_type and 'lottie' not in content_type:
                                                parts.append(Part(text=sticker_text))
                                                parts.append(Part(inline_data={
                                                    "mime_type": content_type.split(';')[0],
                                                    "data": image_bytes
                                                }))
                                                continue
                                except Exception:
                                    pass
                                sticker_text += f" (URL: {sticker.url})"
                            parts.append(Part(text=sticker_text))
                
                # Download GIF thumbnails and include embed content
                if msg.embeds:
                    async with aiohttp.ClientSession() as session:
                        for embed in msg.embeds:
                            if embed.type == "gifv" or (embed.provider and embed.provider.name and embed.provider.name.lower() in ("tenor", "giphy")):
                                gif_url = None
                                if embed.thumbnail and embed.thumbnail.url:
                                    gif_url = embed.thumbnail.url
                                elif embed.url:
                                    gif_url = embed.url
                                if gif_url:
                                    provider = embed.provider.name if embed.provider and embed.provider.name else "unknown"
                                    try:
                                        async with session.get(str(gif_url)) as resp:
                                            if resp.status == 200:
                                                image_bytes = await resp.read()
                                                content_type = resp.headers.get('Content-Type', 'image/gif')
                                                if content_type.startswith('image/') or content_type.startswith('video/'):
                                                    parts.append(Part(text=f"[GIF from {provider}]"))
                                                    parts.append(Part(inline_data={
                                                        "mime_type": content_type.split(';')[0],
                                                        "data": image_bytes
                                                    }))
                                                    continue
                                    except Exception:
                                        pass
                                    parts.append(Part(text=f"[GIF: {gif_url}]"))
                            else:
                                embed_lines = []
                                if embed.title:
                                    embed_lines.append(f"Title: {embed.title}")
                                if embed.author and embed.author.name:
                                    embed_lines.append(f"Author: {embed.author.name}")
                                if embed.description:
                                    embed_lines.append(f"Description: {embed.description}")
                                if embed.fields:
                                    for field in embed.fields:
                                        embed_lines.append(f"{field.name}: {field.value}")
                                if embed.footer and embed.footer.text:
                                    embed_lines.append(f"Footer: {embed.footer.text}")
                                if embed.url:
                                    embed_lines.append(f"URL: {embed.url}")
                                if embed_lines:
                                    parts.append(Part(text=f"[Embed]\n" + "\n".join(embed_lines) + "\n[/Embed]"))
                
                context_contents.append(Content(role="user", parts=parts))
            
            # Set listen_channel_id for auto-respond in non-tracked channels (matching /context)
            listen_channel = None if (is_tracked or is_dm) else channel_id
            set_pending_context(self.context_key, context_contents, remaining_uses=duration, listen_channel_id=listen_channel)
            
            # Build response message matching /context format
            include_note = ""
            if not is_tracked:
                include_note = " (including your own)"
            
            # Determine scope message
            if channel_id in tracked_threads:
                scope_msg = "this thread"
            elif is_dm:
                scope_msg = "your DMs"
            elif channel_id in tracked_channels:
                scope_msg = f"{interaction.user.mention} in this tracked channel"
            else:
                scope_msg = f"{interaction.user.mention} for @mentions"
            
            auto_respond_note = ""
            if listen_channel:
                auto_respond_note = "\n🎯 **I'll respond to your next messages here without needing @mention!**"
            
            await interaction.channel.send(
                f"✅ **Context loaded for {interaction.user.mention}!** {len(messages)} message(s){include_note} from this channel are now cached for **{scope_msg}**.\n\n"
                f"📝 **Send your prompts** - the context will be used for your next **{duration}** message(s).{auto_respond_note}"
            )
        except Exception as e:
            await interaction.channel.send(f"❌ Error loading context: {str(e)}")


class ContextButton(ui.Button):
    """Button to load context from channel history."""
    
    def __init__(self, context_key, channel, has_context=False):
        label = "📖 Refresh Context" if has_context else "📖 Load Context"
        super().__init__(label=label, style=discord.ButtonStyle.secondary, custom_id="context_button")
        self.context_key = context_key
        self.channel = channel
    
    async def callback(self, interaction: discord.Interaction):
        # Bug 2: Show modal to let user choose count and duration
        modal = ContextModal(self.context_key, self.channel)
        await interaction.response.send_modal(modal)

class ResetButton(ui.Button):
    """Button to reset all settings to default."""
    
    def __init__(self, settings_key, scope_msg):
        super().__init__(label="Reset All", style=discord.ButtonStyle.danger, emoji="🔄", custom_id="reset_button")
        self.settings_key = settings_key
        self.scope_msg = scope_msg
    
    async def callback(self, interaction: discord.Interaction):
        # Reset settings to defaults
        set_settings_for_context(self.settings_key, default_settings.copy())
        
        # Clear any pending context (matching /reset-settings behavior)
        if self.settings_key in pending_context:
            del pending_context[self.settings_key]
        
        # Acknowledge silently and send a new public message (matching /reset-settings)
        await interaction.response.defer()
        await interaction.channel.send(
            f"🔄 All settings reset to default for {self.scope_msg}.\n"
            f"• Thinking level: minimal\n"
            f"• Persona: default\n"
            f"• Loaded context: cleared"
        )


class HelpButton(ui.Button):
    """Button to show the help message."""
    
    def __init__(self):
        super().__init__(label="Help", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="help_button")
    
    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            description=help_text,
            color=discord.Color.dark_green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CreateThreadModal(ui.Modal, title="Create Thread"):
    """Modal for entering thread name."""
    
    thread_name = ui.TextInput(
        label="Thread Name",
        placeholder="Enter a name for the new thread...",
        min_length=1,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            thread = await interaction.channel.create_thread(
                name=self.thread_name.value,
                type=discord.ChannelType.public_thread
            )
            tracked_threads.add(thread.id)
            await interaction.response.send_message(
                f"✅ Thread **{self.thread_name.value}** created! Head over to {thread.mention} to start chatting.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to create threads here.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to create thread: {e}", ephemeral=True)


class CreateThreadButton(ui.Button):
    """Button to create a new tracked thread."""
    
    def __init__(self):
        super().__init__(label="Create Thread", style=discord.ButtonStyle.secondary, emoji="🧵", custom_id="create_thread_button")
    
    async def callback(self, interaction: discord.Interaction):
        # Can't create threads in DMs
        if isinstance(interaction.channel, discord.DMChannel):
            await interaction.response.send_message("❌ Can't create threads in DMs.", ephemeral=True)
            return
        modal = CreateThreadModal()
        await interaction.response.send_modal(modal)


class ForgetButton(ui.Button):
    """Button to clear conversation history for the current context."""
    
    def __init__(self, settings_key, scope_msg):
        super().__init__(label="Forget", style=discord.ButtonStyle.secondary, emoji="🧼", custom_id="forget_button")
        self.settings_key = settings_key
        self.scope_msg = scope_msg
    
    async def callback(self, interaction: discord.Interaction):
        cleared = False
        if self.settings_key in message_history:
            del message_history[self.settings_key]
            cleared = True
        if self.settings_key in pending_context:
            del pending_context[self.settings_key]
            cleared = True
        
        if cleared:
            await interaction.response.send_message(f"🧼 History cleared for {self.scope_msg}!", ephemeral=True)
        else:
            await interaction.response.send_message("📭 No history to clear in this context.", ephemeral=True)


class SettingsView(ui.View):
    """View containing all settings controls."""
    
    def __init__(self, settings_key, scope_msg, user_id=None, channel=None, timeout=180):
        super().__init__(timeout=timeout)
        
        current_settings = context_settings.get(settings_key, default_settings.copy())
        current_thinking = current_settings.get("thinking_level", "minimal")
        
        # Add the thinking dropdown
        self.add_item(ThinkingSelect(current_thinking))
        
        # Add buttons (row 1: core settings)
        self.add_item(PersonaButton(settings_key, scope_msg))
        # Add context button if we have channel (settings_key serves as context_key)
        if channel:
            has_context = settings_key in pending_context
            self.add_item(ContextButton(settings_key, channel, has_context))
        
        # Row 2: utility buttons
        self.add_item(HelpButton())
        self.add_item(CreateThreadButton())
        self.add_item(ForgetButton(settings_key, scope_msg))
        self.add_item(ResetButton(settings_key, scope_msg))




class Settings(commands.Cog):
    """Cog for AI settings commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.checks.cooldown(1, cooldowns.get("settings", 5))
    @app_commands.command(name='settings', description='Open the settings panel to customize thinking depth, persona, and load conversation context.')
    async def settings(self, interaction: discord.Interaction):
        """Open the interactive settings menu."""
        settings_key, scope_msg, is_shared = get_settings_key_from_interaction(interaction)
        current_settings = context_settings.get(settings_key, default_settings.copy())
        user_id = interaction.user.id
        
        # Build current settings summary
        thinking = current_settings.get("thinking_level", "minimal")
        persona = current_settings.get("persona")
        persona_display = f'"{persona[:50]}..."' if persona and len(persona) > 50 else (f'"{persona}"' if persona else "Default")
        
        # Get context status (use settings_key as context_key)
        ctx = pending_context.get(settings_key)
        if ctx:
            ctx_count = len(ctx.get("contents", []))
            ctx_remaining = ctx.get("remaining_uses", 0)
            context_display = f"{ctx_count} msgs loaded, expires in {ctx_remaining} msg(s)"
        else:
            context_display = "None"
        
        embed = discord.Embed(
            title="⚙️ AI Settings",
            description=f"Settings for **{scope_msg}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="🧠 Thinking Level", value=thinking.capitalize(), inline=True)
        embed.add_field(name="🎭 Persona", value=persona_display, inline=True)
        embed.add_field(name="📖 Loaded Context", value=context_display, inline=True)
        embed.add_field(name="📊 History Limit", value=f"{max_history} messages", inline=True)
        embed.set_footer(text="Use the controls below to adjust settings")
        
        view = SettingsView(settings_key, scope_msg, user_id, interaction.channel)
        # Settings menu is always ephemeral, but changes (thinking, persona, context) send public messages
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    
    @app_commands.command(name='thinking', description='Set the AI thinking level for reasoning depth.')
    @app_commands.choices(level=[
        app_commands.Choice(name='minimal - Fastest, less reasoning', value='minimal'),
        app_commands.Choice(name='low - Fast, simple reasoning', value='low'),
        app_commands.Choice(name='medium - Balanced thinking', value='medium'),
        app_commands.Choice(name='high - Deep reasoning', value='high'),
    ])
    async def thinking(self, interaction: discord.Interaction, level: app_commands.Choice[str]):
        """Set the AI thinking/reasoning level."""
        await interaction.response.defer()
        
        settings_key, scope_msg, _ = get_settings_key_from_interaction(interaction)
        current_settings = context_settings.get(settings_key, default_settings.copy())
        current_settings["thinking_level"] = level.value
        set_settings_for_context(settings_key, current_settings)
        
        await interaction.followup.send(f"🧠 Thinking level set to **{level.value}** for {scope_msg}.")
        
        # Broadcast change if in tracked channel or thread (followup.send is already visible if not ephemeral, but wait... thinking command is public by default?)
        # thinking command doesn't have ephemeral=True in defer, so it's public.
        # But wait, get_settings_key_from_interaction doesn't determine ephemerality for thinking command.
        # The user said "/settings menu ephemeral". thinking command is separate.
        # Assuming thinking command should be public anyway.
        # No change needed here for existing public commands.
    
    @app_commands.command(name='persona', description='Set a custom persona for the AI.')
    @app_commands.describe(description='The persona description (leave empty or use "default" to reset)')
    async def persona(self, interaction: discord.Interaction, description: str = None):
        """Set a custom persona for the AI."""
        settings_key, scope_msg, _ = get_settings_key_from_interaction(interaction)
        current_settings = context_settings.get(settings_key, default_settings.copy())
        
        if description is None or description.lower() == "default":
            current_settings["persona"] = None
            set_settings_for_context(settings_key, current_settings)
            await interaction.response.send_message(f"🎭 Persona reset to default for {scope_msg}.")
        else:
            current_settings["persona"] = description
            set_settings_for_context(settings_key, current_settings)
            await interaction.response.send_message(f"🎭 Persona set for {scope_msg}:\n> {description}")
    
    @app_commands.command(name='reset-settings', description='Reset all AI settings (persona, thinking level, context) to defaults.')
    async def reset_settings(self, interaction: discord.Interaction):
        """Reset all AI settings to defaults for this context."""
        settings_key, scope_msg, _ = get_settings_key_from_interaction(interaction)
        
        # Reset settings to defaults
        set_settings_for_context(settings_key, default_settings.copy())
        
        # Clear any pending context
        if settings_key in pending_context:
            del pending_context[settings_key]
        
        await interaction.response.send_message(
            f"🔄 All settings reset to default for {scope_msg}.\n"
            f"• Thinking level: minimal\n"
            f"• Persona: default\n"
            f"• Loaded context: cleared"
        )
    
    @app_commands.command(name='conversation-summary', description='Get an AI-generated summary of the current conversation.')
    async def conversation_summary(self, interaction: discord.Interaction):
        """Generate a summary of the conversation history."""
        await interaction.response.defer()
        
        settings_key, scope_msg, _ = get_settings_key_from_interaction(interaction)
        history_key = settings_key  # They use the same key format
        
        # Get conversation history
        history = message_history.get(history_key, [])
        
        if not history:
            await interaction.followup.send("📭 No conversation history found for this context. Start chatting first!")
            return
        
        if len(history) < 2:
            await interaction.followup.send("📝 Not enough conversation to summarize yet. Keep chatting!")
            return
        
        # Create a request for summary
        summary_prompt = """Provide a brief summary of this conversation in 2-4 bullet points.
Focus on: main topic, key conclusions or answers.
Be extremely concise - aim for under 150 words total.

Conversation to summarize:
"""
        
        # Build context from history
        conversation_text = []
        for content in history:
            if content.parts:
                for part in content.parts:
                    if hasattr(part, 'text') and part.text:
                        role = "User" if content.role == "user" else "AI"
                        # Truncate very long messages
                        text = part.text[:500] + "..." if len(part.text) > 500 else part.text
                        conversation_text.append(f"{role}: {text}")
        
        # Limit to last 30 messages to avoid token limits
        if len(conversation_text) > 30:
            conversation_text = conversation_text[-30:]
            summary_prompt += "\n(Showing last 30 messages)\n\n"
        
        full_prompt = summary_prompt + "\n\n".join(conversation_text)
        
        # Generate summary using Gemini (with minimal thinking for speed)
        settings = {"thinking_level": "minimal", "persona": None}
        summary = await generate_response_with_text(full_prompt, settings)
        
        # Check for 503 error
        from utils.retry import is_503_error
        if is_503_error(summary):
            await interaction.followup.send(
                "❌ The server is overloaded. Please try `/conversation-summary` again in a few moments."
            )
            return
        
        # Send the summary
        embed = discord.Embed(
            title="📋 Conversation Summary",
            description=summary[:4000] if len(summary) > 4000 else summary,
            color=discord.Color.green()
        )
        embed.set_footer(text=f"{len(history)} messages analyzed")
        
        await interaction.followup.send(content=f"-# Requested by {interaction.user.mention}", embed=embed)



async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Settings(bot))

