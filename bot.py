"""Run with python bot.py. No message-content or members privileged intent needed."""
import asyncio
import logging
import os
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from core import Store, board_pages, channel_name, event_details, set_status, solve, unsolve

log = logging.getLogger("ctf")
HELP = ("`/edit_ch name:문제명` → 문제 채널 생성 (문제 채널에서는 수정)\n"
        "`/update_status status:working` → 🔨 푸는 중\n"
        "`/update_status status:stuck` → 🆘 막힘·도움 필요 SOS\n"
        "`/update_status status:stopped` → 그만둠\n"
        "`/solve_ch flag:FLAG{...}` → 🚩 풀이 완료\n"
        "`/unsolve_ch` → 풀이 취소\n\n"
        "대회 사이트에서 먼저 정답 인증 후 /solve_ch를 사용하세요. 봇은 정답을 검증하지 않습니다.")


def info_embed(event):
    embed = discord.Embed(title=event["name"], url=event["url"], color=0x3498DB)
    embed.add_field(name="Start", value=f"<t:{event['start']}:F>\n<t:{event['start']}:R>")
    embed.add_field(name="End", value=f"<t:{event['end']}:F>\n<t:{event['end']}:R>")
    embed.add_field(name="URL", value=event["url"], inline=False)
    return embed


async def report(interaction, error):
    error = getattr(error, "original", error)
    if isinstance(error, (ValueError, app_commands.CheckFailure)):
        message = str(error) if isinstance(error, ValueError) else "이 명령을 실행할 권한이 없습니다."
    elif isinstance(error, discord.Forbidden):
        message = "봇 권한과 역할 순서를 확인해 주세요. 봇 역할이 CTF 참가 역할보다 위에 있어야 합니다."
    else:
        log.error("Discord operation failed (%s)", type(error).__name__)
        message = "처리 중 오류가 발생했습니다. 잠시 후 다시 시도하거나 봇 로그를 확인해 주세요."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


class JoinView(discord.ui.View):
    def __init__(self, bot, event):
        super().__init__(timeout=None)
        self.bot, self.event_id = bot, event["id"]
        button = discord.ui.Button(label=f"{event['name']} (for everyone)"[:80],
                                   style=discord.ButtonStyle.primary,
                                   custom_id=f"ctf:toggle:{event['id']}")
        button.callback = self.toggle
        self.add_item(button)

    async def toggle(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        event = self.bot.store.event(self.event_id)
        if not event or interaction.guild_id != event["guild"]:
            raise ValueError("이 서버의 대회 버튼이 아닙니다.")
        # Fetch a fresh member so double clicks cannot toggle using stale role data.
        async with self.bot.locks[("join", event["id"], interaction.user.id)]:
            member = await interaction.guild.fetch_member(interaction.user.id)
            role = interaction.guild.get_role(event["role"])
            if not role:
                raise ValueError("참가 역할이 삭제되었습니다. 관리자에게 문의해 주세요.")
            if role in member.roles:
                await member.remove_roles(role, reason="CTF leave button")
                text = f"**{event['name']}**에서 떠났습니다."
            else:
                await member.add_roles(role, reason="CTF join button")
                text = f"**{event['name']}**에 참가했습니다! <#{event['status']}>에서 시작하세요."
            await interaction.followup.send(text, ephemeral=True)

    async def on_error(self, interaction, error, item):
        await report(interaction, error)


class CTFBot(commands.Bot):
    def __init__(self, database, guild_id=None):
        super().__init__(command_prefix=commands.when_mentioned, intents=discord.Intents(guilds=True),
                         allowed_mentions=discord.AllowedMentions.none())
        self.store = Store(database)
        self.test_guild = guild_id
        self.locks = defaultdict(asyncio.Lock)
        self.dirty = set()
        self.rename_tasks = {}

    async def setup_hook(self):
        await self.add_cog(CTFCommands(self))
        for event in self.store.events():
            self.add_view(JoinView(self, event))
            self.dirty.add(event["id"])
        if self.test_guild:
            guild = discord.Object(id=int(self.test_guild))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()
        self.refresh.start()

    async def close(self):
        self.refresh.cancel()
        pending = list(self.rename_tasks.values())
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await super().close()
        self.store.db.close()

    async def on_ready(self):
        log.info("Ready as %s", self.user)

    async def sync_name(self, channel_id):
        # Discord may rate-limit channel renames for minutes. Keep them out of responses.
        try:
            while True:
                ch = self.store.challenge(channel_id)
                channel = self.get_channel(channel_id)
                if not ch or not isinstance(channel, discord.TextChannel):
                    return
                desired = ("🚩-" if ch.get("solver") else "") + ch["name"]
                if channel.name == desired:
                    return
                await channel.edit(name=desired, reason="CTF challenge status")
        except discord.HTTPException:
            ch = self.store.challenge(channel_id)
            if ch:
                self.dirty.add(ch["event"])
            log.warning("Channel name sync failed for %s; will retry", channel_id)

    async def upsert_message(self, channel, message_id, **kwargs):
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(**kwargs)
                return message.id
            except discord.NotFound:
                pass
        return (await channel.send(**kwargs)).id

    async def render_event(self, event):
        guild = self.get_guild(event["guild"])
        if not guild:
            return
        status = guild.get_channel(event["status"])
        join = guild.get_channel(event["join"])
        announcements = guild.get_channel(event["announcements"])
        if not all(isinstance(c, discord.TextChannel) for c in (status, join, announcements)):
            raise ValueError("CTF 기본 채널이 삭제되었습니다.")
        embed = info_embed(event)
        embed.description = "버튼을 누르면 참가하고, 다시 누르면 떠납니다."
        event["join_message"] = await self.upsert_message(
            join, event.get("join_message"), embed=embed, view=JoinView(self, event))
        self.store.save_event(event)
        announcement = info_embed(event)
        announcement.description = HELP
        event["info_message"] = await self.upsert_message(
            announcements, event.get("info_message"), embed=announcement)
        self.store.save_event(event)
        pages = board_pages(event, self.store.challenges(event["id"]))
        ids = event.setdefault("board_messages", [])
        for index, page in enumerate(pages):
            board = discord.Embed(description=page, color=0x3498DB)
            board.set_footer(text="🔨 working · 🆘 stuck · 문제 채널에서 /update_status")
            mid = await self.upsert_message(status, ids[index] if index < len(ids) else None, embed=board)
            if index < len(ids):
                ids[index] = mid
            else:
                ids.append(mid)
            self.store.save_event(event)
        for mid in ids[len(pages):]:
            try:
                await status.get_partial_message(mid).delete()
            except discord.NotFound:
                pass
        event["board_messages"] = ids[:len(pages)]
        self.store.save_event(event)

    @tasks.loop(seconds=5)
    async def refresh(self):
        for event_id in list(self.dirty):
            self.dirty.discard(event_id)
            try:
                # Share the lock with setup/edit so stale copies cannot overwrite metadata.
                async with self.locks[("event", event_id)]:
                    event = self.store.event(event_id)
                    if event:
                        await self.render_event(event)
            except (discord.HTTPException, ValueError):
                log.warning("CTF %s refresh failed; will retry", event_id)
                self.dirty.add(event_id)
        for event in self.store.events():
            for ch in self.store.challenges(event["id"]):
                channel = self.get_channel(ch["id"])
                desired = ("🚩-" if ch.get("solver") else "") + ch["name"]
                prior = self.rename_tasks.get(ch["id"])
                if channel and channel.name != desired and (prior is None or prior.done()):
                    self.rename_tasks[ch["id"]] = asyncio.create_task(self.sync_name(ch["id"]))

    @refresh.before_loop
    async def before_refresh(self):
        await self.wait_until_ready()


class CTFCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def context(self, interaction):
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            raise ValueError("CTF 카테고리의 텍스트 채널에서 사용해 주세요.")
        event = self.bot.store.event(channel.category_id)
        if not event or event["guild"] != interaction.guild_id:
            raise ValueError("먼저 /setup_ctf로 대회를 만들고 해당 카테고리에서 사용해 주세요.")
        member = interaction.user
        if not member.guild_permissions.manage_guild and not any(r.id == event["role"] for r in member.roles):
            raise ValueError("#ctf-join 버튼으로 먼저 참가해 주세요.")
        return event

    def challenge(self, interaction):
        self.context(interaction)
        ch = self.bot.store.challenge(interaction.channel_id)
        if not ch:
            raise ValueError("문제 채널 안에서 사용해 주세요.")
        return ch

    @app_commands.command(name="setup_ctf", description="CTF 참가 버튼과 비공개 카테고리를 생성/수정합니다 (관리자)")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(name="대회 이름 (예: hitcon2026)", start="2026-11-01T20:00+09:00",
                           end="2026-11-03T20:00+09:00", url="대회 사이트 URL")
    async def setup_ctf(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 80],
                        start: str, end: str, url: str):
        begin, finish = event_details(start, end, url)
        slug = channel_name(name)
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        async with self.bot.locks[("setup", guild.id)]:
            existing = next((e for e in self.bot.store.events() if e["guild"] == guild.id and e["slug"] == slug), None)
            if existing:
                async with self.bot.locks[("event", existing["id"])]:
                    existing.update(name=name, start=begin, end=finish, url=url)
                    self.bot.store.save_event(existing)
                    self.bot.dirty.add(existing["id"])
                await interaction.followup.send("대회 정보를 수정했습니다.", ephemeral=True)
                return
            created = []
            try:
                role = await guild.create_role(name=f"CTF-{slug}", reason="CTF participants")
                created.append(role)
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True,
                                                         read_message_history=True, embed_links=True),
                }
                category = await guild.create_category(f"{slug}-everyone", overwrites=overwrites)
                created.append(category)
                announcements = await guild.create_text_channel("announcements", category=category)
                created.append(announcements)
                status = await guild.create_text_channel("status", category=category, topic=HELP[:1024])
                created.append(status)
                join = next((c for c in guild.text_channels if c.name == "ctf-join" and c.category_id is None), None)
                if join is None:
                    join = await guild.create_text_channel("ctf-join", overwrites={
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True,
                                                             read_message_history=True, embed_links=True),
                    })
                    created.append(join)
                event = dict(id=category.id, guild=guild.id, slug=slug, name=name, start=begin, end=finish,
                             url=url, role=role.id, status=status.id, announcements=announcements.id, join=join.id)
                self.bot.store.save_event(event)
            except Exception:
                for resource in reversed(created):
                    try:
                        await resource.delete(reason="Incomplete CTF setup rollback")
                    except discord.HTTPException:
                        log.warning("Could not roll back resource %s", resource.id)
                raise
            self.bot.add_view(JoinView(self.bot, event))
            self.bot.dirty.add(event["id"])
        await interaction.followup.send(f"대회를 만들었습니다. <#{join.id}>에 참가 버튼이 곧 표시됩니다.", ephemeral=True)

    @app_commands.command(name="edit_ch", description="문제 채널 생성 또는 현재 문제의 이름·분야·설명 수정")
    @app_commands.guild_only()
    @app_commands.describe(name="문제명", category="분야 (예: web, pwn, crypto)", description="문제 설명")
    async def edit_ch(self, interaction: discord.Interaction, name: app_commands.Range[str, 1, 96],
                      category: app_commands.Range[str, 1, 40] = "", description: app_commands.Range[str, 1, 2000] = ""):
        event = self.context(interaction)
        base = channel_name(name)
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.locks[("event", event["id"])]:
            ch = self.bot.store.challenge(interaction.channel_id)
            if any(c["name"] == base and (not ch or c["id"] != ch["id"])
                   for c in self.bot.store.challenges(event["id"])):
                raise ValueError("같은 이름의 문제가 이미 있습니다.")
            if not ch:
                parent = interaction.guild.get_channel(event["id"])
                channel = await interaction.guild.create_text_channel(base, category=parent)
                ch = dict(id=channel.id, event=event["id"], name=base, added_by=interaction.user.id,
                          workers={}, solver=None, flag=None, category=category, description=description)
                self.bot.store.save_challenge(ch)
            else:
                if ch["added_by"] != interaction.user.id and not interaction.user.guild_permissions.manage_guild:
                    raise ValueError("문제를 만든 사람 또는 서버 관리자만 수정할 수 있습니다.")
                channel = interaction.channel
                ch["name"] = base
                if category:
                    ch["category"] = category
                if description:
                    ch["description"] = description
                self.bot.store.save_challenge(ch)
            self.bot.dirty.add(event["id"])
            embed = discord.Embed(title=ch["name"], description=ch["description"] or None, color=0x3498DB)
            embed.add_field(name="Added by", value=f"<@{ch['added_by']}>")
            if ch["category"]:
                embed.add_field(name="분야", value=ch["category"])
            embed.set_footer(text="/update_status로 작업 상태 표시 · /solve_ch로 풀이 완료")
            ch["info_message"] = await self.bot.upsert_message(channel, ch.get("info_message"), embed=embed)
            self.bot.store.save_challenge(ch)
        await interaction.followup.send(f"문제를 저장했습니다: {channel.mention}", ephemeral=True)

    @app_commands.command(name="update_status", description="현재 문제의 내 작업 상태를 변경합니다")
    @app_commands.guild_only()
    @app_commands.choices(status=[app_commands.Choice(name="working — 푸는 중", value="working"),
                                 app_commands.Choice(name="stuck — 막힘·도움 필요 SOS", value="stuck"),
                                 app_commands.Choice(name="stopped — 그만둠", value="stopped")])
    async def update_status(self, interaction: discord.Interaction, status: str):
        self.challenge(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.locks[("event", interaction.channel.category_id)]:
            ch = self.challenge(interaction)
            set_status(ch, interaction.user.id, status)
            self.bot.store.save_challenge(ch)
            self.bot.dirty.add(ch["event"])
        await interaction.followup.send(f"상태를 {status}(으)로 변경했습니다.", ephemeral=True)

    @app_commands.command(name="solve_ch", description="대회 사이트에서 인증한 문제를 풀이 완료로 기록합니다")
    @app_commands.guild_only()
    @app_commands.describe(flag="대회에서 정답 인증을 마친 플래그 (참가자에게 공개됩니다)")
    async def solve_ch(self, interaction: discord.Interaction, flag: app_commands.Range[str, 1, 1000]):
        self.challenge(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.locks[("event", interaction.channel.category_id)]:
            ch = self.challenge(interaction)
            solve(ch, interaction.user.id, flag)
            self.bot.store.save_challenge(ch)
            self.bot.dirty.add(ch["event"])
        embed = discord.Embed(title="🚩 풀이 완료!", description=(
            f"<#{ch['id']}> · solved by <@{interaction.user.id}>\n\n"
            f"**Flag**\n{discord.utils.escape_markdown(flag)}"), color=0x2ECC71)
        await interaction.channel.send(embed=embed)
        await interaction.followup.send("🚩 풀이 완료로 기록했습니다. 상태판과 채널 이름을 갱신합니다.", ephemeral=True)

    @app_commands.command(name="unsolve_ch", description="현재 문제의 풀이 완료를 취소합니다")
    @app_commands.guild_only()
    async def unsolve_ch(self, interaction: discord.Interaction):
        self.challenge(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        async with self.bot.locks[("event", interaction.channel.category_id)]:
            ch = self.challenge(interaction)
            unsolve(ch, interaction.user.id, interaction.user.guild_permissions.manage_guild)
            self.bot.store.save_challenge(ch)
            self.bot.dirty.add(ch["event"])
        await interaction.channel.send(f"↩️ <@{interaction.user.id}>님이 <#{ch['id']}>의 풀이 완료를 취소했습니다.")
        await interaction.followup.send("풀이를 취소했습니다. 다시 /update_status로 작업자를 등록할 수 있습니다.", ephemeral=True)


def main():
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "")
    if not token or token == "your_bot_token_here":
        raise SystemExit(".env에 DISCORD_TOKEN을 설정해 주세요. README.md 참고")
    bot = CTFBot(os.getenv("DATABASE_PATH", "data/ctf.sqlite3"), os.getenv("DISCORD_GUILD_ID"))
    bot.tree.on_error = report
    bot.run(token, log_level=logging.INFO)


if __name__ == "__main__":
    main()
