import discord
from discord.ext import commands
from discord import app_commands
import requests
from datetime import datetime
import pytz
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))  # Your server ID

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------- Modal ---------------- #
class AnnounceModal(discord.ui.Modal, title="Create Event Announcement"):
    event_link = discord.ui.TextInput(label="Event Link", placeholder="Enter TruckerMP Event Link")
    destination = discord.ui.TextInput(label="Destination", placeholder="Enter Destination")
    slot_image = discord.ui.TextInput(label="Slot Image URL (Large)", placeholder="Enter Slot Image URL")

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        # Fetch event details from TruckerMP
        try:
            event_id = self.event_link.value.rstrip("/").split("/")[-1]
            response = requests.get(f"https://truckersmp.com/api/v2/events/{event_id}")
            data = response.json()["response"]

            event_name = data.get("name", "Unnamed Event")
            description = data.get("description", "No description")
            start_time_utc = datetime.fromisoformat(data["start_at"].replace("Z", "+00:00"))
            meetup_time_utc = datetime.fromisoformat(data["meetup_at"].replace("Z", "+00:00"))

            # Auto-fetch Route Image
            route_image = data.get("route_image") or None

            # Convert UTC -> NPT
            npt = pytz.timezone("Asia/Kathmandu")
            start_time_npt = start_time_utc.astimezone(npt)
            meetup_time_npt = meetup_time_utc.astimezone(npt)

        except Exception as e:
            await interaction.response.send_message(f"Failed to fetch event: {e}", ephemeral=True)
            return

        # Save event data
        self.event_data = {
            "name": event_name,
            "description": description,
            "destination": self.destination.value,
            "slot_image": self.slot_image.value,
            "route_image": route_image,
            "start_time_utc": start_time_utc.strftime("%Y-%m-%d %H:%M UTC"),
            "start_time_npt": start_time_npt.strftime("%Y-%m-%d %H:%M NPT"),
            "meetup_time_utc": meetup_time_utc.strftime("%Y-%m-%d %H:%M UTC"),
            "meetup_time_npt": meetup_time_npt.strftime("%Y-%m-%d %H:%M NPT")
        }

        # Ask user to select channel
        channels = [c for c in interaction.guild.text_channels if c.permissions_for(interaction.user).send_messages]
        view = ChannelSelectView(self.event_data, channels)
        await interaction.response.send_message("Select the channel to send the announcement:", view=view, ephemeral=True)


# ---------------- Channel Select ---------------- #
class ChannelSelect(discord.ui.Select):
    def __init__(self, event_data, channels):
        options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in channels]
        super().__init__(placeholder="Select channel...", min_values=1, max_values=1, options=options)
        self.event_data = event_data

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        channel = interaction.guild.get_channel(channel_id)

        # Single embed with Slot Image (main) + Route Image
        embed = discord.Embed(
            title=self.event_data["name"],
            description=self.event_data["description"],
            color=discord.Color.red()
        )
        embed.add_field(name="Destination", value=self.event_data["destination"], inline=False)
        embed.add_field(
            name="Meetup Time",
            value=f'{self.event_data["meetup_time_utc"]} | {self.event_data["meetup_time_npt"]}',
            inline=False
        )
        embed.add_field(
            name="Departure Time",
            value=f'{self.event_data["start_time_utc"]} | {self.event_data["start_time_npt"]}',
            inline=False
        )

        # Slot Image as main large image
        embed.set_image(url=self.event_data["slot_image"])

        # Route Image shown in a field with markdown
        if self.event_data["route_image"]:
            embed.add_field(
                name="Route Image",
                value=f"[View Route Image]({self.event_data['route_image']})",
                inline=False
            )

        await channel.send(embed=embed)
        await interaction.response.send_message(f"Announcement sent to {channel.mention}!", ephemeral=True)


class ChannelSelectView(discord.ui.View):
    def __init__(self, event_data, channels):
        super().__init__()
        self.add_item(ChannelSelect(event_data, channels))


# ---------------- Slash Command ---------------- #
@bot.tree.command(name="announce", description="Create an event announcement")
async def announce(interaction: discord.Interaction):
    await interaction.response.send_modal(AnnounceModal(bot))


# ---------------- Bot Ready ---------------- #
@bot.event
async def on_ready():
    try:
        # Register slash commands for your guild immediately
        guild = discord.Object(id=GUILD_ID)
        await bot.tree.sync(guild=guild)
        print(f"Slash commands synced for guild {GUILD_ID}")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    print(f"Bot is ready as {bot.user}")


bot.run(TOKEN)p
