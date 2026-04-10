import discord
from discord import app_commands
from discord.ext import commands

class ProjectManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="create_project", description="Build a new private project workspace")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_project(self, interaction: discord.Interaction, project_name: str):
        guild = interaction.guild
        
        # 1. Create the Private Project Role
        project_role = await guild.create_role(name=f"Project: {project_name}")

        # 2. Set Permissions (Hidden from everyone except the new role and bot)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            project_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, administrator=True)
        }

        # 3. Create Category & Channels
        category = await guild.create_category(name=f"📁 {project_name}", overwrites=overwrites)
        
        # Create Text, Ads/Resources, and Voice channels
        chat = await guild.create_text_channel(f"💬-{project_name}-chat", category=category)
        ads = await guild.create_text_channel(f"📢-{project_name}-ads", category=category)
        await guild.create_voice_channel(f"🔊 {project_name} Meeting", category=category)

        # 4. Post an initial "Startup Guide" in the Ads channel
        embed = discord.Embed(
            title=f"🚀 Project {project_name} Initialized",
            description=f"Welcome to the workspace for **{project_name}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="Ad Resources", value="Post all creative assets and ad links here.", inline=False)
        await ads.send(embed=embed)

        await interaction.response.send_message(f"✅ Created workspace and {project_role.mention} role for **{project_name}**!")

# This function tells the main bot to load this file
async def setup(bot: commands.Bot):
    await bot.add_cog(ProjectManager(bot))