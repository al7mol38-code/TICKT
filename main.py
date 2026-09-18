import discord
from discord.ext import commands
import sqlite3
import os

# الأديانات التي أرسلتها
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

        # منع فتح أكثر من تيكت لنفس النوع أو تيكت عامة مفعلة
        channel_name = f"ticket-{ticket_type}-{member.name}".lower().replace(" ", "-")
        existing_channel = discord.utils.get(guild.text_channels, name=channel_name)
        if existing_channel:
            await interaction.response.send_message(f"❌ لديك تيكت مفتوحة مسبقاً من هذا النوع: {existing_channel.mention}", ephemeral=True)
            return

        # الصلاحيات: صاحب التيكت + الأونر + الكو أونر + الرتب المسؤولة فقط
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        # إضافة صلاحية للأونر والكو أونر تلقائياً
        for r_id in [OWNER_ROLE_ID, CO_OWNER_ROLE_ID]:
            role = guild.get_role(r_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # إضافة صلاحيات الرتب المحددة للقسم
        for r_id in allowed_roles:
            role = guild.get_role(r_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"نوع التيكت: {ticket_type} | صاحبها: {member.id}"
        )

        # إرسال رسالة الترحيب داخل التيكت مع أزرار التحكم بالمشرفين
        embed = discord.Embed(
            title=f"🎫 تيكت جديدة: {ticket_type}",
            description=f"مرحباً بك {member.mention}!\nنوع التيكت: **{ticket_type}**\nيرجى شرح طلبك أو مشكلتك بالتفصيل وسيقوم الفريق المسؤول بخدمتك في أقرب وقت.\n\n> *Farm of Legends* 🎬",
            color=discord.Color.red()
        )
        
        control_view = TicketControlView()
        msg = await ticket_channel.send(content=f"{member.mention}", embed=embed, view=control_view)
        
        # تثبيت رسالة التحكم أو حفظها إن أردت
        await interaction.response.send_message(f"✅ تم فتح التيكت الخاصة بك بنجاح: {ticket_channel.mention}", ephemeral=True)

        # إرسال لوق الفتح
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
        # VIP فقط للأونر والكو أونر والمشرف العام
        await self.create_ticket(interaction, "VIP", [])

    @discord.ui.button(label="شكوى على إداري", style=discord.ButtonStyle.danger, custom_id="ticket_admin_complaint")
    async def btn_admin_complaint(self, interaction: discord.Interaction, button: discord.ui.Button):
        # شكوى على إداري موجهة للأونر والكو أونر حصراً
        await self.create_ticket(interaction, "شكوى على إداري", [])

    @discord.ui.button(label="بوست لورد", style=discord.ButtonStyle.success, custom_id="ticket_boost_lord")
    async def btn_boost_lord(self, interaction: discord.Interaction, button: discord.ui.Button):
        # بوست لورد للأونر والكو أونر فقط
        await self.create_ticket(interaction, "بوست لورد", [])


# أزرار التحكم داخل التيكت (استلام، استدعاء، إغلاق)
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📌 استلام التيكت", style=discord.ButtonStyle.blurple, custom_id="claim_ticket_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        staff = interaction.user
        await interaction.response.send_message(f"📌 تم استلام هذه التيكت بواسطة المشرف: {staff.mention}", ephemeral=False)

    @discord.ui.button(label="🔔 استدعاء العضو", style=discord.ButtonStyle.gray, custom_id="call_member_btn")
    async def call_member(self, interaction: discord.Interaction, button: discord.ui.Button):
        # استخراج العضو من اسم الروم أو الـ topic
        topic = interaction.channel.topic or ""
        await interaction.response.send_message(f"🔔 تنبيه لصاحب التيكت، يرجى الرد هنا في حال تواجدك!", ephemeral=False)

    @discord.ui.button(label="🔒 إغلاق التيكت", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user_roles = [r.id for r in interaction.user.roles]
        
        is_admin = (OWNER_ROLE_ID in user_roles or CO_OWNER_ROLE_ID in user_roles or interaction.user.guild_permissions.administrator)

        if not is_admin:
            await interaction.response.send_message("❌ عذراً، زر الإغلاق مخصص للإدارة العليا فقط لإعطاء النقاط وتقييم الأداء قبل الحذف.", ephemeral=True)
            return

        # إخفاء الروم عن العضو صاحب التيكت وإبقاؤها ظاهرة للإدارة والأونر
        # نستخرج صاحب التيكت من الـ topic
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
                # إزالة صلاحية العضو في الروم
                await interaction.channel.set_permissions(member, view_channel=False)

        await interaction.response.send_message(f"🔒 **تم إغلاق التيكت وإخفاؤها عن العضو.**\nالباب مفتوح للأونر والكو أونر والمشرفين لإعطاء النقاط والتقييم، ثم يمكن حذف الروم نهائياً.", ephemeral=False)

        # إرسال لوق الإغلاق
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🔒 إغلاق تيكت",
                description=f"**الروم:** {interaction.channel.name}\n**بواسطة الإداري:** {interaction.user.mention}",
                color=discord.Color.orange()
            )
            await log_channel.send(embed=log_embed)

class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setup_tickets", aliases=["تيكتات"])
    async def setup_tickets(self, ctx):
        if not (OWNER_ROLE_ID in [r.id for r in ctx.author.roles] or CO_OWNER_ROLE_ID in [r.id for r in ctx.author.roles]):
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
        embed.set_image(url="https://i.imgur.com/ضع_رابط_صورة_الفارم_هنا.jpg") # استبدلها برابط صورتك المباشر إن أردت

        view = MainTicketView()
        target_channel = self.bot.get_channel(SETUP_CHANNEL_ID) or ctx.channel
        await target_channel.send(embed=embed, view=view)
        await ctx.reply("✅ تم نشر لوحة التيكتات بنجاح!", delete_after=5)

async def setup(bot):
    await bot.add_cog(TicketCog(bot))
