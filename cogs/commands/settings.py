"""
Settings commands cog - AI settings commands with Discord UI.
"""
import discord
from discord import app_commands, ui
from discord.ext import commands

from config import tracked_channels, max_history
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
    return (("mention", user_id), f"{user_mention} via @mentions", False)


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
        
        # Update the view to reflect new selection
        await interaction.response.edit_message(
            content=f"🧠 Thinking level set to **{self.values[0]}** for {scope_msg}.",
            view=SettingsView(settings_key, scope_msg)
        )

        # Broadcast change if in tracked channel or thread
        if interaction.channel.id in tracked_channels or interaction.channel.id in tracked_threads:
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
        
        if not self.persona_input.value or self.persona_input.value.lower() == "default":
            current_settings["persona"] = None
            set_settings_for_context(self.settings_key, current_settings)
            await interaction.response.send_message(f"🎭 Persona reset to default for {self.scope_msg}.", ephemeral=True)
            
            # Broadcast change if in tracked channel or thread
            if interaction.channel.id in tracked_channels or interaction.channel.id in tracked_threads:
                await interaction.channel.send(f"🎭 Persona reset to default for {self.scope_msg}.")
        else:
            current_settings["persona"] = self.persona_input.value
            set_settings_for_context(self.settings_key, current_settings)
            persona_preview = self.persona_input.value[:100] + "..." if len(self.persona_input.value) > 100 else self.persona_input.value
            await interaction.response.send_message(f"🎭 Persona set for {self.scope_msg}:\n> {persona_preview}", ephemeral=True)

            # Broadcast change if in tracked channel or thread
            if interaction.channel.id in tracked_channels or interaction.channel.id in tracked_threads:
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
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Fetch messages from channel history
            messages = []
            async for msg in self.channel.history(limit=count * 3):
                if msg.author.id == bot.user.id:
                    continue
                messages.append(msg)
                if len(messages) >= count:
                    break
            
            if not messages:
                await interaction.followup.send("❌ No messages found to load as context.", ephemeral=True)
                return
            
            messages.reverse()
            
            from google.genai.types import Part, Content
            context_contents = []
            for msg in messages:
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
                text = f"[{timestamp}] {msg.author.display_name} (@{msg.author.name}): {msg.content}"
                if msg.attachments:
                    attachment_names = [att.filename for att in msg.attachments]
                    text += f" [Attachments: {', '.join(attachment_names)}]"
                context_contents.append(Content(role="user", parts=[Part(text=text)]))
            
            set_pending_context(self.context_key, context_contents, remaining_uses=duration, listen_channel_id=None)
            
            await interaction.followup.send(
                f"✅ Loaded {len(messages)} messages as context. Will persist for your next {duration} messages.",
                ephemeral=True
            )

            # Broadcast change if in tracked channel or thread
            if interaction.channel_id in tracked_channels or interaction.channel_id in tracked_threads:
                await interaction.channel.send(f"✅ Loaded {len(messages)} messages as context. Will persist for your next {duration} messages.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error loading context: {str(e)}", ephemeral=True)


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
        set_settings_for_context(self.settings_key, default_settings.copy())
        await interaction.response.edit_message(
            content=f"✅ All settings reset to default for {self.scope_msg}.",
            view=SettingsView(self.settings_key, self.scope_msg, interaction.user.id, interaction.channel)
        )
        
        # Broadcast change if in tracked channel or thread
        if interaction.channel.id in tracked_channels or interaction.channel.id in tracked_threads:
            await interaction.channel.send(f"✅ All settings reset to default for {self.scope_msg}.")


class SettingsView(ui.View):
    """View containing all settings controls."""
    
    def __init__(self, settings_key, scope_msg, user_id=None, channel=None, timeout=180):
        super().__init__(timeout=timeout)
        
        current_settings = context_settings.get(settings_key, default_settings.copy())
        current_thinking = current_settings.get("thinking_level", "minimal")
        
        # Add the thinking dropdown
        self.add_item(ThinkingSelect(current_thinking))
        
        # Add buttons
        self.add_item(PersonaButton(settings_key, scope_msg))
        # Add context button if we have channel (settings_key serves as context_key)
        if channel:
            has_context = settings_key in pending_context
            self.add_item(ContextButton(settings_key, channel, has_context))
        self.add_item(ResetButton(settings_key, scope_msg))




class Settings(commands.Cog):
    """Cog for AI settings commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='settings', description='View and adjust AI settings with an interactive menu.')
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
        # Bug 9: Thread settings should be public (not ephemeral) so everyone can see
        await interaction.response.send_message(embed=embed, view=view, ephemeral=not is_shared)

    
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
        summary_prompt = f"""Summarize the following conversation in a concise yet informative way.
Include:
- Main topics discussed
- Key questions asked and answers given
- Any important decisions or conclusions
- Notable exchanges or highlights

Keep the summary under 500 words and format it nicely with bullet points where appropriate.

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
        embed.set_footer(text=f"Context: {scope_msg} • {len(history)} messages analyzed")
        
        await interaction.followup.send(embed=embed)



async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Settings(bot))

