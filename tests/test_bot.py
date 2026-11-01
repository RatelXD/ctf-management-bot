import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from bot import CTFBot, CTFCommands, JoinView, HELP, dashboard_overwrites, info_embed


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = CTFBot(":memory:")
        self.event = dict(id=1, guild=2, role=3, status=4, join=5, announcements=6,
                          name="hitcon2026", slug="hitcon2026", start=1793530800, end=1793703600, url="https://example.com")
        self.bot.store.save_event(self.event)

    async def asyncTearDown(self):
        await self.bot.close()

    async def test_commands_and_slash_options(self):
        await self.bot.add_cog(CTFCommands(self.bot))
        commands = {c.name: c for c in self.bot.tree.get_commands()}
        self.assertEqual(set(commands), {"setup_ctf", "edit_challenge", "update_status", "solve_challenge", "unsolve_challenge"})
        self.assertEqual(commands["edit_challenge"].parameters[0].name, "name")
        self.assertEqual([p.name for p in commands["edit_challenge"].parameters], ["name", "category"])
        self.assertTrue(commands["solve_challenge"].parameters[0].required)
        self.assertEqual([c.value for c in commands["update_status"].parameters[0].choices],
                         ["working", "stuck", "stopped"])
        for command in commands.values():
            self.assertTrue(command.guild_only)
            # Exercise Discord command serialization with real library validation.
            command.to_dict(self.bot.tree)

    async def test_view_survives_restart_registration(self):
        first = JoinView(self.bot, self.event)
        second = JoinView(self.bot, self.bot.store.event(1))
        self.assertTrue(first.is_persistent())
        self.assertEqual(first.children[0].custom_id, second.children[0].custom_id)
        self.bot.add_view(first)
        self.assertIn(first, self.bot.persistent_views)

    async def test_join_then_leave_uses_fresh_member(self):
        role = SimpleNamespace(id=3)
        member = SimpleNamespace(roles=[], add_roles=AsyncMock(), remove_roles=AsyncMock())
        interaction = SimpleNamespace(guild_id=2, user=SimpleNamespace(id=10),
            response=SimpleNamespace(defer=AsyncMock()), followup=SimpleNamespace(send=AsyncMock()),
            guild=SimpleNamespace(fetch_member=AsyncMock(return_value=member), get_role=lambda _: role))
        view = JoinView(self.bot, self.event)
        await view.toggle(interaction)
        member.add_roles.assert_awaited_once()
        self.assertIn("참가", interaction.followup.send.call_args.args[0])
        member.roles = [role]
        await view.toggle(interaction)
        member.remove_roles.assert_awaited_once()
        self.assertIn("떠났", interaction.followup.send.call_args.args[0])
        self.assertTrue(interaction.followup.send.call_args.kwargs["ephemeral"])

    async def test_button_wrong_guild_does_not_grant_access(self):
        interaction = SimpleNamespace(guild_id=999, response=SimpleNamespace(defer=AsyncMock()))
        with self.assertRaises(ValueError):
            await JoinView(self.bot, self.event).toggle(interaction)

    async def test_info_has_start_end_url(self):
        embed = info_embed(self.event)
        self.assertEqual([f.name for f in embed.fields], ["Start", "End", "URL"])
        self.assertEqual(embed.url, "https://example.com")

    async def test_message_recreated_if_deleted(self):
        response = MagicMock(status=404, reason="Not Found")
        channel = SimpleNamespace(fetch_message=AsyncMock(side_effect=discord.NotFound(response, "missing")),
                                  send=AsyncMock(return_value=SimpleNamespace(id=99)))
        mid = await self.bot.upsert_message(channel, 12, embed=discord.Embed(title="demo"))
        self.assertEqual(mid, 99)
        channel.send.assert_awaited_once()

    async def test_existing_message_edited(self):
        message = SimpleNamespace(id=12, edit=AsyncMock())
        channel = SimpleNamespace(fetch_message=AsyncMock(return_value=message), send=AsyncMock())
        self.assertEqual(await self.bot.upsert_message(channel, 12, embed=discord.Embed()), 12)
        message.edit.assert_awaited_once()
        channel.send.assert_not_awaited()

    async def test_context_requires_membership(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.category_id = 1
        interaction = SimpleNamespace(channel=channel, guild_id=2,
            user=SimpleNamespace(guild_permissions=SimpleNamespace(manage_guild=False), roles=[]))
        cog = CTFCommands(self.bot)
        with self.assertRaises(ValueError):
            cog.context(interaction)
        interaction.user.roles = [SimpleNamespace(id=3)]
        self.assertEqual(cog.context(interaction)["id"], 1)

    async def test_actual_command_lifecycle(self):
        status = MagicMock(spec=discord.TextChannel)
        status.id, status.category_id = 4, 1
        channel = MagicMock(spec=discord.TextChannel)
        channel.id, channel.category_id = 100, 1
        channel.mention = "<#100>"
        channel.send = AsyncMock(return_value=SimpleNamespace(id=500))
        guild = SimpleNamespace(get_channel=lambda _: SimpleNamespace(id=1),
                                create_text_channel=AsyncMock(return_value=channel))
        interaction = SimpleNamespace(channel=status, channel_id=4, guild_id=2, guild=guild,
            response=SimpleNamespace(defer=AsyncMock()), followup=SimpleNamespace(send=AsyncMock()),
            user=SimpleNamespace(id=10, guild_permissions=SimpleNamespace(manage_guild=False),
                                 roles=[SimpleNamespace(id=3)]))
        cog = CTFCommands(self.bot)
        await cog.edit_challenge.callback(cog, interaction, "Demo", "web")
        ch = self.bot.store.challenge(100)
        self.assertEqual(ch["added_by"], 10)
        self.assertEqual(ch["name"], "web-demo")
        self.assertEqual(ch["info_message"], 500)
        interaction.channel, interaction.channel_id = channel, 100
        self.bot.upsert_message = AsyncMock(return_value=500)
        await cog.edit_challenge.callback(cog, interaction, "Renamed")
        self.assertEqual(self.bot.store.challenge(100)["name"], "web-renamed")
        await cog.edit_challenge.callback(cog, interaction, "Renamed", "pwn")
        self.assertEqual(self.bot.store.challenge(100)["name"], "pwn-renamed")
        await cog.update_status.callback(cog, interaction, "working")
        self.assertEqual(self.bot.store.challenge(100)["workers"], {"10": "working"})
        await cog.solve_challenge.callback(cog, interaction, "FLAG{ok}")
        self.assertEqual(self.bot.store.challenge(100)["solver"], 10)
        self.assertIn(1, self.bot.dirty)
        embed = channel.send.call_args.kwargs["embed"]
        self.assertIn("풀이 완료", embed.title)
        self.assertIn("FLAG", embed.description)
        await cog.unsolve_challenge.callback(cog, interaction)
        self.assertIsNone(self.bot.store.challenge(100)["solver"])

    async def test_dashboard_permissions(self):
        def role(id, manager=False):
            item = MagicMock(spec=discord.Role)
            item.id = id
            item.permissions = discord.Permissions(manage_guild=manager)
            return item
        everyone, participant, manager = role(1), role(2), role(3, True)
        bot_member = MagicMock(spec=discord.Member)
        guild = SimpleNamespace(default_role=everyone, me=bot_member,
                                roles=[everyone, participant, manager])
        inherited = {everyone: discord.PermissionOverwrite(view_channel=False),
                     participant: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                     bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True)}
        result = dashboard_overwrites(guild, inherited)
        for target in (everyone, participant):
            self.assertFalse(result[target].send_messages)
            self.assertFalse(result[target].send_messages_in_threads)
            self.assertFalse(result[target].create_public_threads)
        for target in (manager, bot_member):
            self.assertTrue(result[target].send_messages)
        self.assertFalse(result[everyone].view_channel)
        self.assertTrue(result[participant].view_channel)
        self.assertTrue(inherited[participant].send_messages)

    async def test_setup_creates_three_default_channels(self):
        everyone, participant = MagicMock(spec=discord.Role), MagicMock(spec=discord.Role)
        everyone.permissions = participant.permissions = discord.Permissions.none()
        participant.id = 3
        bot_member = MagicMock(spec=discord.Member)
        category = SimpleNamespace(id=9, overwrites={})
        async def create_category(name, **kwargs):
            category.overwrites = kwargs["overwrites"]
            return category
        next_id = iter(range(20, 30))
        async def create_text(name, **kwargs):
            return SimpleNamespace(id=next(next_id), name=name)
        guild = SimpleNamespace(id=2, roles=[everyone, participant], default_role=everyone,
            me=bot_member, text_channels=[], create_role=AsyncMock(return_value=participant),
            create_category=AsyncMock(side_effect=create_category),
            create_text_channel=AsyncMock(side_effect=create_text))
        interaction = SimpleNamespace(guild=guild, response=SimpleNamespace(defer=AsyncMock()),
                                      followup=SimpleNamespace(send=AsyncMock()))
        cog = CTFCommands(self.bot)
        await cog.setup_ctf.callback(cog, interaction, "My CTF", "2026-11-01T20:00+09:00",
                                     "2026-11-03T20:00+09:00", "https://example.com")
        self.assertEqual(guild.create_category.call_args.args[0], "⚔️My CTF⚔️")
        calls = guild.create_text_channel.call_args_list
        self.assertEqual([call.args[0] for call in calls],
                         ["announcement", "dashboard", "general", "ctf-join"])
        self.assertFalse(calls[1].kwargs["overwrites"][participant].send_messages)
        self.assertNotIn("topic", calls[1].kwargs)
        self.assertEqual(self.bot.store.event(9)["general"], 22)

    async def test_legacy_layout_migration_is_idempotent(self):
        category = SimpleNamespace(edit=AsyncMock(), text_channels=[])
        announcement = MagicMock(spec=discord.TextChannel)
        dashboard = MagicMock(spec=discord.TextChannel)
        announcement.edit, dashboard.edit = AsyncMock(), AsyncMock()
        dashboard.overwrites = {}
        everyone = MagicMock(spec=discord.Role)
        everyone.permissions = discord.Permissions.none()
        guild = SimpleNamespace(get_channel=lambda id: {4: dashboard, 6: announcement}.get(id),
            roles=[everyone], default_role=everyone, me=MagicMock(spec=discord.Member),
            create_text_channel=AsyncMock(return_value=SimpleNamespace(id=7)))
        await self.bot.migrate_layout(guild, category, self.event)
        category.edit.assert_awaited_once_with(name="⚔️hitcon2026⚔️", reason="CTF layout update")
        self.assertEqual(dashboard.edit.call_args.kwargs["name"], "dashboard")
        self.assertIsNone(dashboard.edit.call_args.kwargs["topic"])
        self.assertEqual(announcement.edit.call_args.kwargs["name"], "announcement")
        self.assertEqual(self.bot.store.event(1)["general"], 7)
        await self.bot.migrate_layout(guild, category, self.event)
        guild.create_text_channel.assert_awaited_once()
        self.assertIn("\n봇은 정답을 검증하지 않습니다.", HELP)

    async def test_category_delete_cleans_only_its_event(self):
        self.event["join_message"] = 44
        self.bot.store.save_event(self.event)
        self.bot.store.save_event(dict(id=8, guild=2))
        self.bot.store.save_challenge(dict(id=100, event=1))
        self.bot.store.save_challenge(dict(id=101, event=8))
        view = JoinView(self.bot, self.event)
        self.bot.add_view(view)
        card = SimpleNamespace(delete=AsyncMock())
        channel = SimpleNamespace(get_partial_message=lambda _: card)
        self.bot.get_channel = lambda _: channel
        category = MagicMock(spec=discord.CategoryChannel)
        category.id, category.guild.id = 1, 2
        self.bot.dirty.add(1)
        await self.bot.on_guild_channel_delete(category)
        self.assertIsNone(self.bot.store.event(1))
        self.assertIsNone(self.bot.store.challenge(100))
        self.assertIsNotNone(self.bot.store.challenge(101))
        self.assertNotIn(1, self.bot.dirty)
        self.assertTrue(view.is_finished())
        card.delete.assert_awaited_once()
        await self.bot.on_guild_channel_delete(category)
        card.delete.assert_awaited_once()

    async def test_offline_category_deletion_requires_confirmed_not_found(self):
        guild = SimpleNamespace(get_channel=lambda _: None,
            fetch_channel=AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "denied")))
        self.bot.get_guild = lambda _: guild
        with self.assertRaises(discord.Forbidden):
            await self.bot.render_event(self.event)
        self.assertIsNotNone(self.bot.store.event(1))
        guild.fetch_channel.side_effect = discord.NotFound(MagicMock(status=404, reason="Not Found"), "deleted")
        await self.bot.render_event(self.event)
        self.assertIsNone(self.bot.store.event(1))

    async def test_flag_channel_name_sync(self):
        ch = dict(id=100, event=1, name="web-demo", solver=10)
        self.bot.store.save_challenge(ch)
        channel = MagicMock(spec=discord.TextChannel)
        channel.name = "web-demo"
        async def rename(**kwargs):
            channel.name = kwargs["name"]
        channel.edit = AsyncMock(side_effect=rename)
        self.bot.get_channel = lambda _: channel
        await self.bot.sync_name(100)
        self.assertEqual(channel.name, "🚩-web-demo")
        ch["solver"] = None
        self.bot.store.save_challenge(ch)
        await self.bot.sync_name(100)
        self.assertEqual(channel.name, "web-demo")


if __name__ == "__main__":
    unittest.main()
