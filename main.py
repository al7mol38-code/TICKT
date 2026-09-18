import discord
from discord.ext import commands
import sqlite3
import os

# الأديانات / الرتب التي أرسلتها
OWNER_ROLE_ID = 1533463569683845160
CO_OWNER_ROLE_ID = 1533463570564649121

ROLE_COMPLAINT = [1533463592265977886, 1541351616907583560]
ROLE_STAFF_APP = [1533463608145477712]
ROLE_INQUIRY = [1533463604479791244]

LOG_CHANNEL_ID = 1533464062393057451
SETUP_CHANNEL_ID = 1533464055325528168

DB_PATH = '/data/bot_data.db' if os.path.exists('/data') else 'bot_data.db'

# لوحة الأزرار الستة الرئيسية
class MainTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, allowed_roles: list):
        guild = interaction.guild
        member = interaction.user

        channel_name = f"ticket-{ticket_type}-{member.name}".lower().replace(" ", "-")
        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            await interaction.response.send_message(f"❌ لديك تيكت مفتوحة مسبقاً من هذا النوع: {existing_channel.mention}", ephemeral=True)
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        for r_id in [OWNER_ROLE_ID, CO_OWN_ROLE_ID]:
            role = guild.get_role(r_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        for r_id in allowed_roles:
            role = guild.get_role(r_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # جلب الكاتيجوري الذي تنتمي له رسالة الإعدادات لتنفتح التيكت تحته مباشرة
        setup_channel = guild.get_channel(SETUP_CHANNEL_ID)
        category = setup_channel.category if setup_channel else None

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"نوع التيكت: {ticket_type} | صاحبها: {member.id}"
        )

        embed = discord.Embed(
            title=f"🎫 تيكت جديدة: {ticket_type}",
            description=f"مرحباً بك {member.mention}!\nنوع التيكت: **{ticket_type}**\nيرجى شرح طلبك أو مشكلتك بالتفصيل وسيقوم الفريق المسؤول بخدمتك في أقرب وقت.\n\n> *Farm of Legends* 🎬",
            color=discord.Color.red()
        )
        
        control_view = TicketControlView()
        await ticket_channel.send(content=f"{member.mention}", embed=embed, view=control_view)
        await interaction.response.send_message(f"✅ تم فتح التيكت الخاصة بك بنجاح: {ticket_channel.mention}", ephemeral=True)

        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="📂 فتح تيكت جديدة",
                description=f"**العضو:** {member.mention}\n**النوع:** {ticket_type}\n**الروم:** {ticket_channel.mention}",
                color=discord.Color.green()
            )
            await log_channel.send(embed=log_embed)

    @discord.ui.button(label="شكوى", style=discord.ButtonStyle.danger, custom_id="ticket_complaint")
    async def btn_complaint(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "شكوى", ROLE_COMPLAINT)

    @discord.ui.button(label="تقديم على رتبة المنظمين", style=discord.ButtonStyle.primary, custom_id="ticket_staff_app")
    async def btn_staff_app(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "تقديم على رتبة المنظمين", ROLE_STAFF_APP)

    @discord.ui.button(label="استفسار & اقتراح", style=discord.ButtonStyle.secondary, custom_id="ticket_inquiry")
    async def btn_inquiry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "استفسار & اقتراح", ROLE_INQUIRY)

    @discord.ui.button(label="VIP", style=discord.ButtonStyle.success, custom_id="ticket_vip")
    async def btn_vip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "VIP", [])

    @discord.ui.button(label="شكوى على إداري", style=discord.ButtonStyle.danger, custom_id="ticket_admin_complaint")
    async def btn_admin_complaint(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "شكوى على إداري", [])

    @discord.ui.button(label="بوست لورد", style=discord.ButtonStyle.success, custom_id="ticket_boost_lord")
    async def btn_boost_lord(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "بوست لورد", [])


# أزرار التحكم داخل التيكت (استلام، استدعاء، إغلاق، حذف)
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📌 استلام التيكت", style=discord.ButtonStyle.blurple, custom_id="claim_ticket_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff = interaction.user
        await interaction.response.send_message(f"📌 تم استلام هذه التيكت بواسطة المشرف: {staff.mention}", ephemeral=False)

    @discord.ui.button(label="🔔 استدعاء العضو", style=discord.ButtonStyle.gray, custom_id="call_member_btn")
    async def call_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        topic = interaction.channel.topic or ""
        member_id = None
        
        # استخراج صاحب التيكت من الـ topic
        for part in topic.split("|"):
            if "صاحبها:" in part:
                try:
                    member_id = int(part.replace("صاحبها:", "").strip())
                except:
                    pass

        if not member_id:
            await interaction.response.send_message("❌ لم يتم العثور على صاحب التيكت في وصف الروم.", ephemeral=True)
            return

        member = guild.get_member(member_id)
        if not member:
            try:
                member = await guild.fetch_member(member_id)
            except:
                member = None

        if not member:
            await interaction.response.send_message("❌ عذراً، لم أتمكن من العثور على العضو في السيرفر.", ephemeral=True)
            return

        # محاولة إرسال رسالة خاصة للعضو
        dm_sent = True
        try:
            dm_embed = discord.Embed(
                title="🔔 تنبيه استدعاء تيكت",
                description=f"مرحباً {member.mention}، يرجى التوجه إلى تيكتك في سيرفر **{guild.name}** لأن الفريق بانتظارك:\n🔗 {interaction.channel.mention}",
                color=discord.Color.gold()
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            dm_sent = False # إذا كان العضو قافل الخاص

        # الرد في روم التيكت
        msg = f"🔔 تم إرسال تنبيه استدعاء لصاحب التيكت {member.mention}!"
        if not dm_sent:
            msg += "\n⚠️ *(ملاحظة: خاصة مغلقة، تم التنبيه هنا فقط).*કના"

        await interaction.response.send_message(msg, ephemeral=False)

    @discord.ui.button(label="🔒 إغلاق التيكت", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user_roles = [r.id for r in interaction.user.roles]
        
        is_admin = (OWNER_ROLE_ID in user_roles or CO_OWN_ROLE_ID in user_roles or interaction.user.guild_permissions.administrator)

        if not is_admin:
            await interaction.response.send_message("❌ عذراً، زر الإغلاق مخصص للإدارة العليا فقط لإعطاء النقاط وتقييم الأداء قبل الحذف.", ephemeral=True)
            return

        topic = interaction.channel.topic or ""
        member_id = None
        for part in topic.split("|"):
            if "صاحبها:" in part:
                try:
                    member_id = int(part.replace("صاحبها:", "").strip())
                except:
                    pass
        
        if member_id:
            member = guild.get_member(member_id)
            if member:
                await interaction.channel.set_permissions(member, view_channel=False)

        await interaction.response.send_message(f"🔒 **تم إغلاق التيكت وإخفاؤها عن العضو.**\nالباب مفتوح للأونر والكو أونر والمشرفين لإعطاء النقاط والتقييم، ثم يمكن حذف الروم نهائياً.", ephemeral=False)

        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🔒 إغلاق تيكت",
                description=f"**الروم:** {interaction.channel.name}\n**بواسطة الإداري:** {interaction.user.mention}",
                color=discord.Color.orange()
            )
            await log_channel.send(embed=log_embed)

    @discord.ui.button(label="🗑️ حذف التيكت", style=discord.ButtonStyle.danger, custom_id="delete_ticket_btn")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user_roles = [r.id for r in interaction.user.roles]
        
        is_admin = (OWNER_ROLE_ID in user_roles or CO_OWN_ROLE_ID in user_roles or interaction.user.guild_permissions.administrator)

        if not is_admin:
            await interaction.response.send_message("❌ عذراً، زر الحذف مخصص للإدارة العليا فقط.", ephemeral=True)
            return

        await interaction.response.send_message("🗑️ جاري حذف التيكت نهائياً...", ephemeral=True)
        
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🗑️ حذف تيكت نهائياً",
                description=f"**الروم:** {interaction.channel.name}\n**بواسطة الإداري:** {interaction.user.mention}",
                color=discord.Color.dark_red()
            )
            await log_channel.send(embed=log_embed)

        await interaction.channel.delete()

# إعداد البوت والتشغيل
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    bot.add_view(MainTicketView())
    bot.add_view(TicketControlView())
    print("✅ تم تفعيل أزرار التيكتات بنجاح!")

@bot.command(name="setup_tickets", aliases=["تيكتات"])
async def setup_tickets(ctx):
    if not (OWNER_ROLE_ID in [r.id for r in ctx.author.roles] or CO_OWN_ROLE_ID in [r.id for r in ctx.author.roles]):
        await ctx.reply("عذراً، هذا الأمر مخصص للأونر والكو أونر فقط.", delete_after=5)
        return

    embed = discord.Embed(
        title="🎫 نظام التذاكر الرسمي - Farm of Legends",
        description="يرجى اختيار القسم المناسب لطلبك بالضغط على الزر أدناه.\n\n"
                    "• **شكوى**: للإبلاغ عن مشكلة.\n"
                    "• **تقديم على رتبة المنظمين**: للانضمام لفريق العمل.\n"
                    "• **استفسار & اقتراح**: لأي استفسارات أو أفكار.\n"
                    "• **VIP**: مخصص لأعضاء الـ VIP (إدارة فقط).\n"
                    "• **شكوى على إداري**: مراجعة الإدارة العليا.\n"
                    "• **بوست لورد**: خاص بداعمين السيرفر.\n\n"
                    "> *Farm of Legends* 🎬",
        color=discord.Color.dark_embed()
    )

    view = MainTicketView()
    target_channel = bot.get_channel(SETUP_CHANNEL_ID) or ctx.channel
    await target_channel.send(embed=embed, view=view)
    await ctx.reply("✅ تم نشر لوحة التيكتات بنجاح!", delete_after=5)

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ خطأ: يجيب وضع توكن البوت في متغيرات البيئة DISCORD_TOKEN.")
