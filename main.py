# --- KEEP ALIVE FOR RENDER FREE ---
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "NEXUS TICKET is online!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()
# --- END KEEP ALIVE ---

import discord, os, json, asyncio, io, datetime
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

DB_FILE = "tickets.json"
def load_db():
    try:
        with open(DB_FILE) as f: return json.load(f)
    except: return {"configs": {}, "tickets": {}}
def save_db():
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=2)
db = load_db()

# ---------- TICKET CONTROLS ----------
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, emoji="✋", custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = db["configs"].get(str(interaction.guild.id))
        if not cfg: return await interaction.response.send_message("No config!", ephemeral=True)
        staff_role = interaction.guild.get_role(int(cfg["staff_role_id"]))
        if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Staff only!", ephemeral=True)
        tid = str(interaction.channel.id)
        db["tickets"][tid] = db["tickets"].get(tid, {})
        db["tickets"][tid]["claimed_by"] = interaction.user.id
        save_db()
        await interaction.response.send_message(f"✋ Ticket claimed by {interaction.user.mention}")
        await interaction.channel.send(f"👋 {interaction.user.mention} will help you now!")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = db["configs"].get(str(interaction.guild.id))
        if not cfg: return await interaction.response.send_message("No config!", ephemeral=True)
        staff_role = interaction.guild.get_role(int(cfg["staff_role_id"]))
        if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Staff only!", ephemeral=True)
        tid = str(interaction.channel.id)
        ticket = db["tickets"].get(tid, {})
        owner_id = ticket.get("owner_id")
        if owner_id:
            member = interaction.guild.get_member(int(owner_id))
            if member:
                await interaction.channel.set_permissions(member, view_channel=False, send_messages=False)
        await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=False)
        await interaction.response.send_message(f"🔒 Ticket closed by {interaction.user.mention}. Use Reopen to open again.")
        await interaction.channel.send("Ticket is closed.", view=TicketClosedView())

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = db["configs"].get(str(interaction.guild.id))
        staff_role = interaction.guild.get_role(int(cfg["staff_role_id"])) if cfg else None
        if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Staff only!", ephemeral=True)
        await interaction.response.send_message("🗑️ Deleting in 3 seconds...")
        await asyncio.sleep(3)
        db["tickets"].pop(str(interaction.channel.id), None)
        save_db()
        await interaction.channel.delete(reason=f"Deleted by {interaction.user}")

    @discord.ui.button(label="Delete + Transcript", style=discord.ButtonStyle.danger, emoji="📄", custom_id="ticket_transcript_delete")
    async def transcript_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = db["configs"].get(str(interaction.guild.id))
        staff_role = interaction.guild.get_role(int(cfg["staff_role_id"])) if cfg else None
        if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Staff only!", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        transcript = await make_transcript(interaction.channel)
        file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.txt")
        if cfg and cfg.get("log_channel_id"):
            log_ch = interaction.guild.get_channel(int(cfg["log_channel_id"]))
            if log_ch:
                await log_ch.send(f"📄 Transcript for {interaction.channel.name} - Deleted by {interaction.user.mention}", file=file)
        tid = str(interaction.channel.id)
        owner_id = db["tickets"].get(tid, {}).get("owner_id")
        if owner_id:
            member = interaction.guild.get_member(int(owner_id))
            if member:
                try:
                    file2 = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.txt")
                    await member.send(f"📄 Here is your transcript for ticket **{interaction.channel.name}** in **{interaction.guild.name}**", file=file2)
                except: pass
        await interaction.followup.send("📄 Transcript saved! Deleting in 3 seconds...", ephemeral=True)
        await asyncio.sleep(3)
        db["tickets"].pop(str(interaction.channel.id), None)
        save_db()
        await interaction.channel.delete(reason=f"Transcript+Delete by {interaction.user}")

class TicketClosedView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.success, emoji="🔓", custom_id="ticket_reopen")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        cfg = db["configs"].get(str(interaction.guild.id))
        staff_role = interaction.guild.get_role(int(cfg["staff_role_id"])) if cfg else None
        if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Staff only!", ephemeral=True)
        tid = str(interaction.channel.id)
        owner_id = db["tickets"].get(tid, {}).get("owner_id")
        if owner_id:
            member = interaction.guild.get_member(int(owner_id))
            if member:
                await interaction.channel.set_permissions(member, view_channel=True, send_messages=True)
        await interaction.response.send_message(f"🔓 Reopened by {interaction.user.mention}")
        await interaction.channel.send("Ticket reopened.", view=TicketControlView())

async def make_transcript(channel):
    lines = [f"Transcript for #{channel.name} - {datetime.datetime.now()}\n"]
    async for msg in channel.history(limit=500, oldest_first=True):
        time = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"[{time}] {msg.author} : {msg.content}")
        for att in msg.attachments:
            lines.append(f"  [Attachment] {att.url}")
    return "\n".join(lines)

# ---------- PANEL ----------
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, emoji: str):
        cfg = db["configs"].get(str(interaction.guild.id))
        if not cfg:
            return await interaction.response.send_message("❌ Tickets not setup yet! Admin use /setup-tickets", ephemeral=True)
        for tid, t in db["tickets"].items():
            if t.get("owner_id") == interaction.user.id and t.get("guild_id") == interaction.guild.id and t.get("open", True):
                ch = interaction.guild.get_channel(int(tid))
                if ch:
                    return await interaction.response.send_message(f"❌ You already have a ticket open: {ch.mention}", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        category = interaction.guild.get_channel(int(cfg["category_id"])) if cfg.get("category_id") else None
        staff_role = interaction.guild.get_role(int(cfg["staff_role_id"]))
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            interaction.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        channel = await interaction.guild.create_text_channel(
            name=f"{ticket_type.lower().replace(' ', '-')}-{interaction.user.name}",
            category=category,
            overwrites=overwrites,
            reason=f"Ticket by {interaction.user}"
        )
        db["tickets"][str(channel.id)] = {"owner_id": interaction.user.id, "guild_id": interaction.guild.id, "type": ticket_type, "open": True}
        save_db()
        embed = discord.Embed(title=f"{emoji} {ticket_type} Ticket", description=f"Hello {interaction.user.mention}!\n\nStaff will be with you shortly.\nPlease describe your issue in detail.\n\n**Type:** {ticket_type}", color=0x2b2d31)
        embed.set_footer(text="NEXUS TICKET")
        await channel.send(f"{interaction.user.mention} {staff_role.mention if staff_role else ''}", embed=embed, view=TicketControlView())
        await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

    @discord.ui.button(label="Support", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="panel_support")
    async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Support", "🎫")
    @discord.ui.button(label="Report a Member", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="panel_report")
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Report a Member", "🚨")
    @discord.ui.button(label="Bug Report", style=discord.ButtonStyle.secondary, emoji="🛠️", custom_id="panel_bug")
    async def bug(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Bug Report", "🛠️")
    @discord.ui.button(label="Donate / Premium", style=discord.ButtonStyle.success, emoji="💰", custom_id="panel_donate")
    async def donate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Donate / Premium", "💰")
    @discord.ui.button(label="Partnership", style=discord.ButtonStyle.primary, emoji="🤝", custom_id="panel_partner")
    async def partner(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Partnership", "🤝")

# ---------- SETUP ----------
@bot.tree.command(name="setup-tickets", description="Setup NEXUS TICKET")
@app_commands.describe(panel_channel="Where panel goes", staff_role="Staff role", log_channel="Where transcripts go", category="Category for tickets")
async def setup_tickets(interaction: discord.Interaction, panel_channel: discord.TextChannel, staff_role: discord.Role, log_channel: discord.TextChannel, category: discord.CategoryChannel):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin only!", ephemeral=True)
    db["configs"][str(interaction.guild.id)] = {
        "panel_channel_id": panel_channel.id,
        "staff_role_id": staff_role.id,
        "log_channel_id": log_channel.id,
        "category_id": category.id
    }
    save_db()
    embed = discord.Embed(title="🎫 NEXUS TICKET", description="Need help? Click a button below to open a ticket!\n\n🎫 **Support** - General help\n🚨 **Report a Member** - Report rule breakers\n🛠️ **Bug Report** - Found a bug?\n💰 **Donate / Premium** - Support the server\n🤝 **Partnership** - Partner with us\n\nStaff will respond ASAP!", color=0x2b2d31)
    embed.set_footer(text="NEXUS TICKET • One ticket at a time")
    await panel_channel.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message(f"✅ Setup done! Panel sent to {panel_channel.mention}", ephemeral=True)

@bot.tree.command(name="panel", description="Resend ticket panel")
async def panel_cmd(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Admin only!", ephemeral=True)
    cfg = db["configs"].get(str(interaction.guild.id))
    if not cfg: return await interaction.response.send_message("Run /setup-tickets first!", ephemeral=True)
    ch = interaction.guild.get_channel(int(cfg["panel_channel_id"]))
    embed = discord.Embed(title="🎫 NEXUS TICKET", description="Need help? Click a button below!\n\n🎫 Support • 🚨 Report • 🛠️ Bug • 💰 Donate • 🤝 Partnership", color=0x2b2d31)
    await ch.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("✅ Panel resent!", ephemeral=True)

@bot.tree.command(name="help", description="Show all NEXUS TICKET commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🎫 NEXUS TICKET - Help", description="All commands for NEXUS TICKET", color=0x2b2d31)
    embed.add_field(name="/setup-tickets", value="Setup panel, staff role, log channel, category\nAdmin only", inline=False)
    embed.add_field(name="/panel", value="Resend the ticket panel\nAdmin only", inline=False)
    embed.add_field(name="/help", value="Show this help menu", inline=False)
    embed.add_field(name="Ticket Buttons", value="**Claim** - Staff takes the ticket\n**Close** - Lock ticket, can Reopen\n**Reopen** - Unlock closed ticket\n**Delete** - Delete channel forever\n**Delete + Transcript** - Save log to #ticket-logs + DM user, then delete", inline=False)
    embed.add_field(name="Panel Buttons", value="🎫 Support • 🚨 Report a Member • 🛠️ Bug Report • 💰 Donate / Premium • 🤝 Partnership", inline=False)
    embed.set_footer(text="NEXUS TICKET")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())
    bot.add_view(TicketClosedView())
    try: await bot.tree.sync()
    except Exception as e: print(e)
    print(f"Logged in as {bot.user} - NEXUS TICKET READY")

bot.run(os.getenv("DISCORD_TOKEN"))
