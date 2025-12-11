import discord
from discord.ext import commands
from discord import app_commands
import requests
import os
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ------------------------------------------------------
#  MODAL FOR ANNOUNCE
# ------------------------------------------------------
class AnnounceModal(discord.ui.Modal, title="Create Announcement"):
    event_link = discord.ui.TextInput(
        label="Event Link", placeholder="https://truckersmp.com/events/12345"
    )
    destination = discord.ui.TextInput(
        label="Destination", placeholder="Example: Calais → Milano"
    )
    slot_image = discord.ui.TextInput(
        label="Slot Image URL (Large Image)", placeholder="Paste slot image URL"
    )

    def __init__(self):
        super().__init__()
        self.event_data = None

    async def on_submit(self, interaction: discord.Interaction):

        link = str(self.event_link.value).strip()

        try:
            event_id = link.rstrip("/").split("/")[-1]
            api = f"https://truckersmp.com/api/v2/events/{event_id}"
            r = requests.get(api)
            data = r.json()["response"]

            event_name = data.get("name", "Event")
            desc = data.get("description", "No description available.")
            route_img = data.get("route_image")

            meetup_utc = datetime.fromisoformat(data["meetup_at"].replace("Z", "+00:00"))
            start_utc = datetime.fromisoformat(data["start_at"].replace("Z", "+00:00"))

            npt = pytz.timezone("Asia/Kathmandu")
            meetup_npt = meetup_utc.astimezone(npt)
            start_npt = start_utc.astimezone(npt)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to fetch TruckerMP event.\nError: `{e}`",
                ephemeral=True
            )
            return

        self.event_data = {
            "name": event_name,
            "description": desc,
            "slot_image": str(self.slot_image.value),
            "route_image": route_img,
            "destination": str(self.destination.value),
            "meetup_utc": meetup_utc.strftime("%Y-%m-%d %H:%M UTC"),
            "meetup_npt": meetup_npt.strftime("%Y-%m-%d %H:%M NPT"),
            "start_utc": start_utc.strftime("%Y-%m-%d %H:%M UTC"),
            "start_npt": start_npt.strftime("%Y-%m-%d %H:%M NPT"),
        }

        # Ask for channel
        view = ChannelSelectView(self.event_data)
        await interaction.response.send_message(
            "Select a channel to send announcement:",
            view=view,
            ephemeral=True
        )


# ------------------------------------------------------
#  CHANNEL SELECT MENU
# ------------------------------------------------------
class ChannelSelect(discord.ui.Select):
    def __init__(self, event_data, channels):
        self.event_data = event_data

        options = [
            discord.SelectOption(label=ch.name, value=str(ch.id))
            for ch in channels
        ]

        super().__init__(
            placeholder="Choose a channel...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        channel_id = int(self.values[0])
        channel = interaction.guild.get_channel(channel_id)

        embed = discord.Embed(
            title=self.event_data["name"],
            description=self.event_data["description"],
            color=discord.Color.red()
        )

        embed.add_field(
            name="Destination",
            value=self.event_data["destination"],
            inline=False
        )
        embed.add_field(
            name="Meetup Time",
            value=f"{self.event_data['meetup_utc']} | {self.event_data['meetup_npt']}",
            inline=False
        )
        embed.add_field(
            name="Departure Time",
            value=f"{self.event_data['start_utc']} | {self.event_data['start_npt']}",
            inline=False
        )

        # Slot Image = main image
        embed.set_image(url=self.event_data["slot_image"])

        # Route Image = separate field link
        if self.event_data["route_image"]:
            embed.add_field(
                name="Route Image",
                value=f"[Click to Open]({self.event_data['route_image']})",
                inline=False
            )

        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Announcement sent to {channel.mention}",
            ephemeral=True
        )


class ChannelSelectView(discord.ui.View):
    def __init__(self, event_data):
        super().__init__()
        channels = interaction_user_channels  # FIX RUNTIME
        pass


# ------------------------------------------------------
#  FIX: Replace broken part with working version
# ------------------------------------------------------
class ChannelSelectView(discord.ui.View):
    def __init__(self, event_data):
        super().__init__()
        self.event_data = event_data

    @discord.ui.select(
        cls=discord.ui.Select,
        placeholder="Select channel to send announcement...",
        options=[]
    )
    async def select_callback(self, select: discord.ui.Select, interaction: discord.Interaction):
        # Populate the options dynamically
        if not select.options:
            channels = [
                ch for ch in interaction.guild.text_channels
                if ch.permissions_for(interaction.user).send_messages
            ]
            select.options = [
                discord.SelectOption(label=ch.name, value=str(ch.id))
                for ch in channels
            ]
            await interaction.response.edit_message(view=self)
            return

        channel_id = int(select.values[0])
        channel = interaction.guild.get_channel(channel_id)

        embed = discord.Embed(
            title=self.event_data["name"],
            description=self.event_data["description"],
            color=discord.Color.red()
        )

        embed.add_field(name="Destination", value=self.event_data["destination"], inline=False)
        embed.add_field(name="Meetup", value=f"{self.event_data['meetup_utc']} | {self.event_data['meetup_npt']}", inline=False)
        embed.add_field(name="Departure", value=f"{self.event_data['start_utc']} | {self.event_data['start_npt']}", inline=False)

        embed.set_image(url=self.event_data["slot_image"])

        if self.event_data["route_image"]:
            embed.add_field(
                name="Route Image",
                value=f"[Click to View]({self.event_data['route_image']})",
                inline=False
            )

        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Announcement sent to {channel.mention}",
            ephemeral=True
        )


# ------------------------------------------------------
#  SLASH COMMAND
# ------------------------------------------------------
@bot.tree.command(name="announce", description="Create an event announcement")
async def announce(interaction: discord.Interaction):
    await interaction.response.send_modal(AnnounceModal())


# ------------------------------------------------------
#  READY → SYNC COMMANDS
# ------------------------------------------------------
@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    print(f"✓ Synced slash commands to guild {GUILD_ID}")
    print(f"Bot logged in as {bot.user}")


bot.run(TOKEN)
