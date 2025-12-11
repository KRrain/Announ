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
