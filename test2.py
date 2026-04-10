import asyncio
import discord
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

class ProjectAutomator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    task_group = app_commands.Group(name="task", description="Manage tasks")

    @task_group.command(name="create")
    async def create(self, interaction: discord.Interaction, name: str):
        pass

    @app_commands.command(name="assign")
    async def assign(self, interaction: discord.Interaction):
        pass

async def test():
    await bot.add_cog(ProjectAutomator(bot))
    commands = bot.tree.get_commands()
    print("Commands in tree:", [cmd.name for cmd in commands])

asyncio.run(test())
