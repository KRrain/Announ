# bot.py
# Discord Ticket Bot (single-file)
# Requires: discord.py v2.x (python -m pip install -U "discord.py>=2.0.0")

import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
from datetime import datetime

# --- Configuration (edit as needed or use environment variables) ---
TOKEN = os.getenv("DISCORD_TOKEN")            # required
GUILD_ID = int(os.getenv("GUILD_ID", "0"))    # optional for fast command registration; set to your dev-guild id
TICKET_CATEGORY_NAME = os.getenv("TICKET_CATEGORY_NAME", "Tickets")
STAFF_ROLE_NAME = os.getenv("STAFF_ROLE_NAME", "Staff")  # role that can see all tickets
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))   # optional channel id for logs (0 = disabled)
TICKET_CHANNEL_PREFIX = os.getenv("TICKET_CHANNEL_PREFIX", "ticket-")
# -----------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = False
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Helpers ----------------------------------------------------------------

async def ensure_ticket_category(guild: discord.Guild):
    """Return the ticket category (create if missing)."""
    for cat in guild.categories:
        if cat.name == TICKET_CATEGORY_NAME:
            return cat
    # not found -> create
    overwrites = {}
    return await guild.create_category(TICKET_CATEGORY_NAME, overwrites=overwrites, reason="Create ticket category")

def make_channel_overwrites(guild: discord.Guild, user: discord.Member):
    """Create overwrites for the new ticket channel."""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
    }
    # give staff role access
    staff_role = discord.utils.get(guild.roles, name=STAFF_ROLE_NAME)
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
    # bot always needs perms
    overwrites[guild.me] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    return overwrites

async def save_transcript(channel: discord.TextChannel) -> str:
    """Collect messages in the channel and return a simple text transcript."""
    msgs = []
    async for m in channel.history(limit=None, oldest_first=True):
        ts = m.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        author = f"{m.author} ({m.author.id})"
        content = m.clean_content
        attachment_urls = " ".join(a.url for a in m.attachments)
        line = f"[{ts}] {author}: {content}"
        if attachment_urls:
            line += f" [attachments: {attachment_urls}]"
        msgs.append(line)
    transcript = "\n".join(msgs)
    return transcript

async def log(guild: discord.Guild, text: str):
    if LOG_CHANNEL_ID:
        ch = guild.get_channel(LOG_CHANNEL_ID)
        if ch:
            await ch.send(text)

# --- UI Views ----------------------------------------------------------------

class TicketView(discord.ui.View):
    def __init__(self, owner: discord.Member, timeout=None):
        super().__init__(timeout=timeout)
        self.owner = owner

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only allow the ticket owner or staff to close
        if interaction.user.id != self.owner.id and not discord.utils.get(interaction.user.roles, name=STAFF_ROLE_NAME):
            await interaction.response.send_message("You don't have permission to close this ticket.", ephemeral=True)
            return

        await interaction.response.send_message("Closing ticket... generating transcript.", ephemeral=True)
        # generate transcript
        transcript = await save_transcript(interaction.channel)
        filename = f"transcript-{interaction.channel.name}.txt"
        # send transcript to ticket owner and optionally log channel
        try:
            await interaction.user.send(f"Here is the transcript for {interaction.channel.name}:", file=discord.File(fp=discord.File(fp=discord.BytesIO(transcript.encode('utf-8')), filename=filename).fp, filename=filename))
        except Exception:
            # fallback: attach to guild log channel or attach to channel before deletion
            pass

        # also send to log channel if configured
        if LOG_CHANNEL_ID:
            log_chan = interaction.guild.get_channel(LOG_CHANNEL_ID)
            if log_chan:
                try:
                    await log_chan.send(content=f"Ticket {interaction.channel.name} closed by {interaction.user} (ID: {interaction.user.id})", file=discord.File(fp=discord.BytesIO(transcript.encode('utf-8')), filename=filename))
                except Exception:
                    await log_chan.send(f"Ticket {interaction.channel.name} closed by {interaction.user}. Transcript failed to attach.")

        # set channel to read-only and rename
        try:
            await interaction.channel.set_permissions(self.owner, read_messages=True, send_messages=False)
            await interaction.channel.edit(name=f"closed-{interaction.channel.name}", reason="Ticket closed")
        except Exception:
            pass

        await interaction.followup.send("Ticket closed. Channel locked.", ephemeral=True)

    @discord.ui.button(label="Delete Channel", style=discord.ButtonStyle.gray, custom_id="delete_ticket_btn")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only staff can delete
        if not discord.utils.get(interaction.user.roles, name=STAFF_ROLE_NAME):
            await interaction.response.send_message("Only staff can delete ticket channels.", ephemeral=True)
            return
        await interaction.response.send_message("Deleting channel in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Deleted by {interaction.user} via Delete Channel button")
        except Exception as e:
            await interaction.followup.send(f"Failed to delete channel: {e}", ephemeral=True)

# --- Slash Commands ----------------------------------------------------------

@bot.event
async def on_ready():
    # sync commands to a single guild if provided (faster) else global (can take up to 1 hour)
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        await bot.tree.sync(guild=guild)
        print(f"Synced commands to guild {GUILD_ID}")
    else:
        await bot.tree.sync()
        print("Synced global commands")
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

@bot.tree.command(name="ticket", description="Create a new ticket channel")
@app_commands.describe(reason="Why are you opening this ticket? (optional)")
async def ticket(interaction: discord.Interaction, reason: str = None):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    member = interaction.user

    if not guild:
        await interaction.followup.send("This command must be used in a server.")
        return

    # ensure category exists
    category = await ensure_ticket_category(guild)

    # find an existing open ticket for this user
    existing = None
    for ch in category.text_channels:
        if ch.name.startswith(TICKET_CHANNEL_PREFIX) and (ch.overwrites_for(member).read_messages):
            # crude check: if the user can read the channel and name matches prefix
            existing = ch
            break
    if existing:
        await interaction.followup.send(f"You already have a ticket open: {existing.mention}", ephemeral=True)
        return

    # create channel name unique
    channel_name = f"{TICKET_CHANNEL_PREFIX}{member.name}".lower().replace(" ", "-")
    # ensure uniqueness
    i = 1
    base = channel_name
    while discord.utils.get(guild.text_channels, name=channel_name):
        i += 1
        channel_name = f"{base}-{i}"

    overwrites = make_channel_overwrites(guild, member)
    try:
        channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites, category=category, reason=f"Ticket created by {member}")
    except Exception as e:
        await interaction.followup.send(f"Failed to create ticket channel: {e}", ephemeral=True)
        return

    # initial embed
    embed = discord.Embed(title="Ticket created", description=f"Hello {member.mention}, a staff member will be with you shortly.\n\n**Reason:** {reason or 'No reason provided.'}", color=discord.Color.brand_red() if hasattr(discord.Color, "brand_red") else discord.Color.red())
    embed.set_footer(text=f"Ticket for {member} • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    view = TicketView(owner=member)
    # send message in ticket channel
    msg = await channel.send(content=f"{member.mention} — {discord.utils.get(guild.roles, name=STAFF_ROLE_NAME).mention if discord.utils.get(guild.roles, name=STAFF_ROLE_NAME) else '@here'}", embed=embed, view=view)
    # notify user
    await interaction.followup.send(f"Ticket created: {channel.mention}", ephemeral=True)
    await log(guild, f"Ticket {channel.name} created by {member} (Reason: {reason})")

# Admin convenience: send a persistent 'Open Ticket' message in a channel
@bot.tree.command(name="ticket-message", description="(Admin) Post a persistent 'Open Ticket' message with button")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(channel="Channel to post the ticket-open message in")
async def ticket_message(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(title="Open a Ticket", description="Click the button below to open a new ticket.", color=discord.Color.blue())
    view = discord.ui.View()
    async def open_cb(inner_interaction: discord.Interaction):
        # call the /ticket command programmatically
        await ticket(inner_interaction)
    btn = discord.ui.Button(label="Open Ticket", style=discord.ButtonStyle.green)
    btn.callback = open_cb
    view.add_item(btn)
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"Posted ticket message in {channel.mention}", ephemeral=True)

# Error handlers for command permission checks
@ticket_message.error
async def ticket_message_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("You need Manage Server permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Error: {error}", ephemeral=True)

# Run the bot
if __name__ == "__main__":
    if not TOKEN:
        print("Set DISCORD_TOKEN environment variable.")
        raise SystemExit(1)
    bot.run(TOKEN)
