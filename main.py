import os
import discord
import json
import uuid
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

# 1. Load secrets
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

DATA_FILE = "data/tasks.json"

# Helper for Database
def load_db():
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# 2. Define Bot with Intents
class Truqorun(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.tree.add_command(project_group)
        self.tree.add_command(task_group)
        await self.tree.sync()
        print(f"Synced slash commands for {self.user}")
        self.reminder_loop.start()

    @tasks.loop(hours=12)
    async def reminder_loop(self):
        print("Running automatic task reminder loop...")
        db = load_db()
        for task_id, task_data in db.items():
            if task_data.get("status") == "pending":
                channel = self.get_channel(task_data["channel_id"])
                if channel:
                    user_id = task_data["user_id"]
                    deadline = task_data["deadline"]
                    await channel.send(f"⏰ **Reminder** for <@{user_id}>: Please complete your assigned task by **{deadline}**.")

    @reminder_loop.before_loop
    async def before_reminder(self):
        await self.wait_until_ready()

bot = Truqorun()

# ----------------- ADMIN CHECK HELPER -----------------
def is_task_admin(member):
    if member.guild_permissions.manage_channels or member.guild_permissions.manage_roles or member.guild_permissions.administrator:
        return True
    admin_role_id = os.getenv("ADMIN_ROLE_ID")
    if admin_role_id and admin_role_id.isdigit():
        for role in member.roles:
            if role.id == int(admin_role_id):
                return True
    return False


# ----------------- REGULAR COMMANDS -----------------
@bot.tree.command(name="about", description="Details about our startup")
async def about(interaction: discord.Interaction):
    embed = discord.Embed(title=f"Welcome to {os.getenv('STARTUP_NAME', 'Truqorun')}")
    embed.add_field(name="Mission", value="To provide world-class service.", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="promote", description="Assign a role to a member")
@app_commands.default_permissions(manage_roles=True)
async def promote(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    try:
        await member.add_roles(role)
        await interaction.response.send_message(f"✅ {member.mention} promoted to **{role.name}**!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)


# ----------------- PROJECT MANAGEMENT -----------------
project_group = app_commands.Group(name="project", description="Manage Projects (Categories & VCs)")

@project_group.command(name="new", description="Create a new Project Category, Text Channel, and custom Voice Channels")
async def project_new(interaction: discord.Interaction, name: str, vc_count: int = 0, text_channel_name: str = None):
    if not is_task_admin(interaction.user):
        return await interaction.response.send_message("❌ Access Denied.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild

    try:
        # Create default Role for this project
        new_role = await guild.create_role(name=f"Project: {name}")

        # Set specific permissions for category
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            new_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, connect=True, speak=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, manage_channels=True, manage_roles=True)
        }

        # Setup Channels
        category = await guild.create_category(name=name, overwrites=overwrites)
        
        # Decide text channel name based on user input
        final_text_name = text_channel_name if text_channel_name else f"chat-{name.lower().replace(' ', '-')}"
        text_channel = await guild.create_text_channel(name=final_text_name, category=category)

        
        for i in range(vc_count):
            await guild.create_voice_channel(name=f"🔊 VC {i+1}", category=category)

        await text_channel.send(f"Welcome to Project **{name}**! {new_role.mention}")
        await interaction.followup.send(f"✅ Created Project **{name}** with {vc_count} Voice Channels!\nRole: {new_role.mention}")
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create project: {e}")


@project_group.command(name="appoint", description="Appoint a user to a specific project role")
async def project_appoint(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not is_task_admin(interaction.user):
        return await interaction.response.send_message("❌ Access Denied.", ephemeral=True)
    try:
        await member.add_roles(role)
        await interaction.response.send_message(f"✅ {member.mention} added to **{role.name}**.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)

@project_group.command(name="delete", description="Selectively delete a Category (and everything inside), a Text Channel, a VC, or a Role.")
async def project_delete(interaction: discord.Interaction, category: discord.CategoryChannel = None, text_channel: discord.TextChannel = None, voice_channel: discord.VoiceChannel = None, role: discord.Role = None):
    if not is_task_admin(interaction.user):
        return await interaction.response.send_message("❌ Access Denied.", ephemeral=True)

    if not category and not text_channel and not voice_channel and not role:
        return await interaction.response.send_message("⚠️ Please select at least one optional parameter to delete!", ephemeral=True)

    await interaction.response.defer(ephemeral=True)
    deleted_items = []

    try:
        if role:
            name = role.name
            await role.delete()
            deleted_items.append(f"Role: {name}")

        if voice_channel:
            name = voice_channel.name
            await voice_channel.delete()
            deleted_items.append(f"Voice Channel: {name}")
            
        if text_channel:
            name = text_channel.name
            await text_channel.delete()
            deleted_items.append(f"Text Channel: {name}")

        if category:
            name = category.name
            # Discord doesn't recursively delete channels when a category is deleted, so we have to loop through them!
            for ch in category.channels:
                deleted_items.append(f"Inside Category: {ch.name}")
                await ch.delete()
            await category.delete()
            deleted_items.append(f"Category: {name}")
            
            # Automatically delete the associated Project role if it exists
            target_role_name = f"Project: {name}"
            for r in interaction.guild.roles:
                if r.name == target_role_name:
                    await r.delete()
                    deleted_items.append(f"Associated Role: {target_role_name}")
                    break

        await interaction.followup.send(f"✅ Successfully deleted the following:\n- " + "\n- ".join(deleted_items))
    except Exception as e:
        await interaction.followup.send(f"❌ Something failed during deletion: {e}")


# ----------------- TASK MANAGEMENT -----------------
task_group = app_commands.Group(name="task", description="Manage specific tasks inside a project")

@task_group.command(name="assign", description="Assign a specific task to a user inside the current project channel")
async def task_assign(interaction: discord.Interaction, user: discord.Member, instructions: str, deadline: str):
    if not is_task_admin(interaction.user):
        return await interaction.response.send_message("❌ Access Denied.", ephemeral=True)
    
    # Save to db
    db = load_db()
    task_id = str(uuid.uuid4())[:6] # unique 6 char ID
    db[task_id] = {
        "user_id": user.id,
        "instructions": instructions,
        "deadline": deadline,
        "channel_id": interaction.channel.id,
        "status": "pending"
    }
    save_db(db)

    embed = discord.Embed(
        title=f"📝 New Task Assigned (ID: `{task_id}`)",
        description=instructions,
        color=discord.Color.brand_red()
    )
    embed.add_field(name="Deadline", value=deadline)
    embed.set_footer(text="Use /approve when finished!")
    
    await interaction.response.send_message(content=user.mention, embed=embed)


@task_group.command(name="my_work", description="Check tasks assigned to you this week")
async def task_mywork(interaction: discord.Interaction):
    db = load_db()
    tasks = [tid for tid, tdata in db.items() if tdata["user_id"] == interaction.user.id and tdata["status"] == "pending"]

    if not tasks:
        return await interaction.response.send_message("🎉 You have no pending tasks this week! Great job!", ephemeral=True)

    desc = "\n\n".join([f"**Task ID {tid}** - (Deadline: {db[tid]['deadline']})\n{db[tid]['instructions']}" for tid in tasks])
    embed = discord.Embed(title="Your Assigned Tasks", description=desc, color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, ephemeral=True)


@task_group.command(name="review", description="Admin command to review and grade a user's task")
@app_commands.choices(status=[
    app_commands.Choice(name="Yes - Approve Task (Removes user's role)", value="approve"),
    app_commands.Choice(name="No - Reject Task (Requests fixes)", value="reject")
])
async def task_review(interaction: discord.Interaction, task_id: str, status: app_commands.Choice[str], project_role: discord.Role, assigned_user: discord.Member, feedback: str = None):
    if not is_task_admin(interaction.user):
        return await interaction.response.send_message("❌ Access Denied.", ephemeral=True)
    
    db = load_db()
    if task_id not in db:
        return await interaction.response.send_message("❌ Invalid Task ID.", ephemeral=True)

    await interaction.response.defer()

    if status.value == "approve":
        db[task_id]["status"] = "completed"
        save_db(db)
        try:
            await assigned_user.remove_roles(project_role)
        except Exception:
            pass # ignore if they don't have it
        embed = discord.Embed(title="✅ Task Officially Approved!", description=f"{assigned_user.mention} your work for `{task_id}` is completely approved. The channel remains open for archive purposes.", color=discord.Color.brand_green())
        await interaction.followup.send(embed=embed)

    elif status.value == "reject":
        db[task_id]["status"] = "pending"  # return to pending
        save_db(db)
        err = f"❌ Task `{task_id}` has been **rejected** by admin.\n\n**Fixes Required:** {feedback}"
        await interaction.followup.send(content=assigned_user.mention, embed=discord.Embed(description=err, color=discord.Color.red()))


# User Approve Command
@bot.tree.command(name="approve", description="Submit your task for Admin review")
async def user_approve(interaction: discord.Interaction, task_id: str):
    db = load_db()
    if task_id not in db or db[task_id]["user_id"] != interaction.user.id:
        return await interaction.response.send_message("❌ Invalid Task ID or you do not own it.", ephemeral=True)

    db[task_id]["status"] = "review"
    save_db(db)

    embed = discord.Embed(title="Task Ready For Review!", description=f"Admin, {interaction.user.mention} has requested a review on Task `{task_id}`. Please use `/task review` to securely grade it.", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)


# ----------------- ADMIN TOOLS -----------------
@bot.tree.command(name="create-role", description="Admin tool: Create a new server role instantly")
async def create_role(interaction: discord.Interaction, name: str):
    if not is_task_admin(interaction.user):
        return await interaction.response.send_message("❌ Access Denied.", ephemeral=True)
    try:
        new_role = await interaction.guild.create_role(name=name)
        await interaction.response.send_message(f"✅ Successfully created role: {new_role.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)


@bot.tree.command(name="copypermissions", description="Admin tool: Copy discord permissions from one role to another")
async def copy_permissions(interaction: discord.Interaction, from_role: discord.Role, to_role: discord.Role):
    if not is_task_admin(interaction.user):
        return await interaction.response.send_message("❌ Access Denied.", ephemeral=True)
    try:
        await to_role.edit(permissions=from_role.permissions)
        await interaction.response.send_message(f"✅ Successfully copied all permissions from {from_role.name} to {to_role.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)


@bot.tree.command(name="delete", description="Admin tool: Delete a category (or channel) by its exact ID")
async def delete_by_id(interaction: discord.Interaction, target_id: str):
    if not is_task_admin(interaction.user):
        return await interaction.response.send_message("❌ Access Denied.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    try:
        channel_id = int(target_id)
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            return await interaction.followup.send("❌ Could not find a category or channel with that ID.")
        
        name = channel.name
        # If it's a category, wipe everything inside it like the other command
        if isinstance(channel, discord.CategoryChannel):
            for ch in channel.channels:
                await ch.delete()
        
        await channel.delete()
        await interaction.followup.send(f"✅ Successfully force-deleted: **{name}**")
    except ValueError:
        await interaction.followup.send("❌ Invalid ID formats. Make sure you use the numerical ID!")
    except Exception as e:
        await interaction.followup.send(f"❌ Failed: {e}")

@bot.tree.command(name="duplicate-category", description="Admin tool: Duplicate an entire Category and all its channels")
async def duplicate_category(interaction: discord.Interaction, original_category: discord.CategoryChannel, new_category_name: str, replace_word: str = None, new_word: str = None):
    if not is_task_admin(interaction.user):
        return await interaction.response.send_message("❌ Access Denied.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Clone the category first (retains the exact permission overwrites of the original)
        new_category = await original_category.clone(name=new_category_name)
        
        # Now clone every individual channel inside the original category and put it in the new one
        for channel in original_category.channels:
            # Determine logic for the cloned channel's name
            new_channel_name = channel.name
            if replace_word and new_word:
                new_channel_name = new_channel_name.replace(replace_word, new_word)
                
            # Create a true clone of the channel (copying bitrate, roles, properties) placed into the new category
            await channel.clone(name=new_channel_name, category=new_category)
            
        await interaction.followup.send(f"✅ Successfully duplicated `{original_category.name}` into brand new Category: **{new_category.name}** with {len(original_category.channels)} channels inside!")
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to duplicate the category completely: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    bot.tree.copy_global_to(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("✅ Sent an instant sync exactly to this server! Refresh Discord (Ctrl+R) if you don't see them yet.")

@bot.command()
@commands.has_permissions(administrator=True)
async def clearsync(ctx):
    # Wipes duplicate guild-specific commands
    bot.tree.clear_commands(guild=ctx.guild)
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("🧹 **Cleared Duplicate Commands!** Restart your Discord App (Ctrl+R/Swipe close on phone) and the duplicates will be permanently gone.")

if __name__ == "__main__":
    bot.run(TOKEN)