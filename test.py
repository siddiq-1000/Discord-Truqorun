import asyncio
from main import bot
async def test():
    await bot.load_extension("cogs.projects")
    commands = await bot.tree.sync()
    print([command.name for command in commands])

asyncio.run(test())
