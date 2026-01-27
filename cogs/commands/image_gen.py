"""
Image generation command cog - /image command for generating/editing images.
"""
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from io import BytesIO

from utils.gemini import generate_or_edit_image


class ImageGen(commands.Cog):
    """Cog for the image generation command."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name='image', description='Generate or edit images using AI. Note: Requires a paid API key.')
    @app_commands.describe(
        prompt='What to generate or how to edit the image(s)',
        image1='First image to edit (optional)',
        image2='Second image to edit (optional)',
        image3='Third image to edit (optional)',
        aspect_ratio='Output aspect ratio (optional)'
    )
    @app_commands.choices(aspect_ratio=[
        app_commands.Choice(name='1:1 - Square', value='1:1'),
        app_commands.Choice(name='16:9 - Landscape', value='16:9'),
        app_commands.Choice(name='9:16 - Portrait', value='9:16'),
        app_commands.Choice(name='4:3 - Standard', value='4:3'),
        app_commands.Choice(name='3:4 - Standard Portrait', value='3:4'),
    ])
    async def image_command(
        self,
        interaction: discord.Interaction, 
        prompt: str,
        image1: discord.Attachment = None,
        image2: discord.Attachment = None,
        image3: discord.Attachment = None,
        aspect_ratio: app_commands.Choice[str] = None
    ):
        """Generate or edit images using AI."""
        # Defer since image generation can take a while
        await interaction.response.defer()
        
        try:
            # Collect all provided images
            images = []
            for attachment in [image1, image2, image3]:
                if attachment is not None:
                    # Check if it's an image
                    if not any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                        await interaction.followup.send("❌ Only image files (PNG, JPG, JPEG, GIF, WEBP) are supported.")
                        return
                    
                    # Download the image
                    async with aiohttp.ClientSession() as session:
                        async with session.get(attachment.url) as resp:
                            if resp.status != 200:
                                await interaction.followup.send(f"❌ Failed to download {attachment.filename}")
                                return
                            img_bytes = await resp.read()
                            
                    # Determine mime type
                    ext = attachment.filename.lower().split('.')[-1]
                    mime_types = {
                        'png': 'image/png',
                        'jpg': 'image/jpeg',
                        'jpeg': 'image/jpeg',
                        'gif': 'image/gif',
                        'webp': 'image/webp'
                    }
                    mime_type = mime_types.get(ext, 'image/png')
                    images.append((img_bytes, mime_type))
            
            # Get aspect ratio value
            ar_value = aspect_ratio.value if aspect_ratio else None
            
            # Generate or edit image
            print(f"Image generation request from {interaction.user.name}: {prompt}")
            text_response, image_bytes, image_mime_type = await generate_or_edit_image(
                prompt=prompt,
                images=images if images else None,
                aspect_ratio=ar_value
            )
            
            # Send the response
            if image_bytes:
                # Determine file extension from mime type
                ext_map = {
                    'image/png': 'png',
                    'image/jpeg': 'jpg',
                    'image/gif': 'gif',
                    'image/webp': 'webp'
                }
                file_ext = ext_map.get(image_mime_type, 'png')
                
                # Create Discord file from bytes
                image_file = discord.File(BytesIO(image_bytes), filename=f"generated_image.{file_ext}")
                
                if text_response:
                    await interaction.followup.send(content=text_response, file=image_file)
                else:
                    await interaction.followup.send(file=image_file)
            elif text_response:
                await interaction.followup.send(text_response)
            else:
                await interaction.followup.send("❌ No image or text was generated. Please try again.")
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error generating image: {str(e)}")


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(ImageGen(bot))
