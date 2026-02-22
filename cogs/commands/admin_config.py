import discord
from discord import app_commands, ui
from discord.ext import commands

from utils.config_manager import dynamic_config

def is_admin(interaction: discord.Interaction):
    return interaction.user.id in dynamic_config.admin_user_ids

class ModelsModal(ui.Modal, title="Configure Models"):
    gemini_model = ui.TextInput(label="Text Generation Model")
    image_model = ui.TextInput(label="Image Generation Model")
    aspect_ratio = ui.TextInput(label="Default Aspect Ratio", placeholder="1:1, 16:9, etc.")

    def __init__(self):
        super().__init__()
        self.gemini_model.default = str(dynamic_config.gemini_model)
        self.image_model.default = str(dynamic_config.image_model)
        self.aspect_ratio.default = str(dynamic_config.default_aspect_ratio)

    async def on_submit(self, interaction: discord.Interaction):
        dynamic_config.set("gemini_model", self.gemini_model.value)
        dynamic_config.set("image_model", self.image_model.value)
        dynamic_config.set("default_aspect_ratio", self.aspect_ratio.value)
        await interaction.response.send_message("✅ Models updated successfully.", ephemeral=True)

class AISettingsModal(ui.Modal, title="Configure AI Settings"):
    temp = ui.TextInput(label="Temperature")
    top_p = ui.TextInput(label="Top P")
    tokens = ui.TextInput(label="Max Output Tokens")
    history = ui.TextInput(label="Max Message History")

    def __init__(self):
        super().__init__()
        gen_cfg = dynamic_config.generation_config
        self.temp.default = str(gen_cfg.get("temperature", 1.0))
        self.top_p.default = str(gen_cfg.get("top_p", 0.95))
        self.tokens.default = str(gen_cfg.get("max_output_tokens", 8192))
        self.history.default = str(dynamic_config.max_history)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            gen_cfg = dynamic_config.generation_config.copy()
            gen_cfg["temperature"] = float(self.temp.value)
            gen_cfg["top_p"] = float(self.top_p.value)
            gen_cfg["max_output_tokens"] = int(self.tokens.value)
            
            dynamic_config.set("generation_config", gen_cfg)
            dynamic_config.set("max_history", int(self.history.value))
            await interaction.response.send_message("✅ AI Settings updated successfully.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid format. Please use numbers only.", ephemeral=True)

class PromptsModal(ui.Modal, title="Configure Default Prompts"):
    url_prompt = ui.TextInput(label="Default URL Prompt", style=discord.TextStyle.paragraph)
    pdf_txt_prompt = ui.TextInput(label="Default PDF/TXT Prompt", style=discord.TextStyle.paragraph)
    img_prompt = ui.TextInput(label="Default Image Prompt", style=discord.TextStyle.paragraph)

    def __init__(self):
        super().__init__()
        self.url_prompt.default = str(dynamic_config.default_url_prompt)
        self.pdf_txt_prompt.default = str(dynamic_config.default_pdf_and_txt_prompt)
        self.img_prompt.default = str(dynamic_config.default_image_prompt)

    async def on_submit(self, interaction: discord.Interaction):
        dynamic_config.set("default_url_prompt", self.url_prompt.value)
        dynamic_config.set("default_pdf_and_txt_prompt", self.pdf_txt_prompt.value)
        dynamic_config.set("default_image_prompt", self.img_prompt.value)
        await interaction.response.send_message("✅ Default prompts updated successfully.", ephemeral=True)

class SystemPromptModal(ui.Modal, title="Configure System Prompt"):
    system_prompt = ui.TextInput(
        label="System Instruction Base",
        style=discord.TextStyle.paragraph,
        max_length=4000
    )

    def __init__(self):
        super().__init__()
        self.system_prompt.default = str(dynamic_config.system_instruction_base)

    async def on_submit(self, interaction: discord.Interaction):
        dynamic_config.set("system_instruction_base", self.system_prompt.value)
        await interaction.response.send_message("✅ System Prompt updated successfully.", ephemeral=True)


class AdminConfigView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @ui.button(label="Models", style=discord.ButtonStyle.primary, emoji="🤖")
    async def btn_models(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ModelsModal())

    @ui.button(label="AI Settings", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def btn_ai(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AISettingsModal())

    @ui.button(label="Prompts", style=discord.ButtonStyle.primary, emoji="📝")
    async def btn_prompts(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(PromptsModal())

    @ui.button(label="System Prompt", style=discord.ButtonStyle.primary, emoji="📋")
    async def btn_system_prompt(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(SystemPromptModal())

    @ui.button(label="Toggle Web Search", style=discord.ButtonStyle.secondary, emoji="✨", row=1)
    async def btn_features(self, interaction: discord.Interaction, button: ui.Button):
        current = dynamic_config.enable_google_search
        dynamic_config.set("enable_google_search", not current)
        status = "enabled" if not current else "disabled"
        await interaction.response.send_message(f"✅ Google Search is now **{status}**.", ephemeral=True)

    @ui.button(label="Reset All Config", style=discord.ButtonStyle.danger, emoji="🔄", row=1)
    async def btn_reset(self, interaction: discord.Interaction, button: ui.Button):
        dynamic_config.overrides.clear()
        dynamic_config.save()
        await interaction.response.send_message("🔄 All dynamic configuration overrides have been reset to defaults.", ephemeral=True)


class AdminConfig(commands.Cog):
    """Cog for the admin configuration command."""
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admin-config", description="Open the admin-only configuration panel to modify global bot settings")
    async def admin_config(self, interaction: discord.Interaction):
        """Open the admin configuration settings menu."""
        if not is_admin(interaction):
            await interaction.response.send_message("❌ You do not have permission to use this command. You must be added to the admin pool in config.py.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🛠️ Admin Configuration Settings",
            description="Manage global bot settings interactively.\nThese settings apply everywhere and override `config.py` temporarily or until reset.",
            color=discord.Color.red()
        )
        embed.add_field(name="Models", value="Change text and image generation models.", inline=True)
        embed.add_field(name="AI Settings", value="Change temperature, tokens, and history.", inline=True)
        embed.add_field(name="Prompts", value="Modify the system prompt and default responses.", inline=True)

        view = AdminConfigView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminConfig(bot))
