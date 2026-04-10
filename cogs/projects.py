import discord
from discord.ext import commands
from discord import app_commands
import os

class ProjectAutomator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    task_group = app_commands.Group(name="task", description="Manage tasks and projects")

    # Helper function for custom admin check if needed
    def is_task_admin(self, member):
        if member.guild_permissions.manage_channels or member.guild_permissions.manage_roles or member.guild_permissions.administrator:
            return True
        
        # Check against a specific allowed Admin role ID in .env
        admin_role_id = os.getenv("ADMIN_ROLE_ID")
        if admin_role_id and admin_role_id.isdigit():
            for role in member.roles:
                if role.id == int(admin_role_id):
                    return True
        return False

    @task_group.command(name="create", description="Create a new task with a category, channels, and a role")
    @app_commands.default_permissions(manage_channels=True)
    async def task_create(self, interaction: discord.Interaction, name: str, deadline: str = None):
        if not self.is_task_admin(interaction.user):
            return await interaction.response.send_message("❌ You don't have access to create tasks. (Requires Manage Channels/Roles)", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        try:
            # Create Role
            role_name = f"Task: {name}"
            new_role = await guild.create_role(name=role_name, reason=f"Task role created by {interaction.user}")

            # Define permissions: Default = cannot see, Task Role = can see and type
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                new_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_roles=True)
            }

            # Create Category
            category = await guild.create_category(name=f"Task: {name}", overwrites=overwrites)

            # Create Text Channel
            text_channel = await guild.create_text_channel(name=f"task-{name.lower().replace(' ', '-')}", category=category)

            # Create Voice Channel
            voice_channel = await guild.create_voice_channel(name=f"🔊 {name}", category=category)

            # Send a welcome message in the text channel
            desc = f"This channel is dedicated to working on **{name}**. Admins can post updates here."
            if deadline:
                desc += f"\n\n⏰ **Deadline**: {deadline}"

            embed = discord.Embed(
                title=f"Welcome to Task: {name}",
                description=desc,
                color=discord.Color.blue()
            )
            await text_channel.send(content=f"{new_role.mention}", embed=embed)

            await interaction.followup.send(f"✅ Successfully created task **{name}**!\n- Role: {new_role.mention}\n- Category: {category.name}")
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to create task: {e}")

    @app_commands.command(name="assign", description="Assign a team member to a specific task role")
    @app_commands.default_permissions(manage_roles=True)
    async def assign(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if not self.is_task_admin(interaction.user):
            return await interaction.response.send_message("❌ You don't have access to assign tasks.", ephemeral=True)
        
        try:
            await member.add_roles(role)
            await interaction.response.send_message(f"✅ Executed: Assigned {member.mention} to task role **{role.name}**.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to assign user: {e}", ephemeral=True)

    @task_group.command(name="update", description="Send an updated instruction to a task role")
    @app_commands.default_permissions(manage_channels=True)
    async def task_update(self, interaction: discord.Interaction, task_role: discord.Role, instructions: str, deadline: str = None):
        if not self.is_task_admin(interaction.user):
            return await interaction.response.send_message("❌ You don't have access to update tasks.", ephemeral=True)

        try:
            # Find the text channel associated with the task role
            target_channel = None
            for channel in interaction.guild.text_channels:
                # Based on our role naming scheme "Task: <name>" and channel naming "task-<name>"
                expected_channel_name = role_name_cleaned = task_role.name.lower().replace('task: ', 'task-').replace(' ', '-')
                if channel.name == expected_channel_name:
                    target_channel = channel
                    break
            
            if not target_channel:
                return await interaction.response.send_message(f"⚠️ Could not automatically locate the channel for {task_role.name}. Are you sure it exists?", ephemeral=True)

            desc = instructions
            if deadline:
                desc += f"\n\n⏰ **Deadline**: {deadline}"

            embed = discord.Embed(
                title="📝 New Task Instructions / Update",
                description=desc,
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Update provided by {interaction.user.display_name}")
            await target_channel.send(content=f"{task_role.mention}", embed=embed)
            await interaction.response.send_message(f"✅ Sent update to {target_channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to send update: {e}", ephemeral=True)

    @app_commands.command(name="approve", description="Mark your current task as completed (run this inside your task channel)")
    async def approve_done(self, interaction: discord.Interaction):
        await interaction.response.defer()
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel) or "task-" not in channel.name:
            await interaction.followup.send("⚠️ You can only run this command inside a task channel.", ephemeral=True)
            return

        try:
            new_name = channel.name.replace("task-", "done-")
            await channel.edit(name=new_name)

            embed = discord.Embed(
                title="✅ Task Completed!",
                description=f"{interaction.user.mention} has marked this task as complete. Great work!\nAdmins have been notified.",
                color=discord.Color.brand_green()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Something went wrong while marking as complete: {e}")

async def setup(bot):
    await bot.add_cog(ProjectAutomator(bot))
