import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from bot import CTFBot, CTFCommands, JoinView, HELP, dashboard_overwrites, info_embed, report


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
        self.assertEqual(set(commands), {"setup_ctf", "remove_ctf", "edit_challenge", "update_status", "solve_challenge", "unsolve_challenge"})
        self.assertEqual(commands["edit_challenge"].parameters[0].name, "name")
        self.assertEqual([p.name for p in commands["edit_challenge"].parameters], ["name", "category", "erase"])
        self.assertFalse(commands["edit_challenge"].parameters[0].required)
        self.assertTrue(commands["solve_challenge"].parameters[0].required)
        self.assertTrue(commands["remove_ctf"].default_permissions.manage_guild)
        self.assertEqual([p.name for p in commands["remove_ctf"].parameters], ["name"])
        self.assertTrue(commands["remove_ctf"].parameters[0].autocomplete)
        self.assertTrue(commands["setup_ctf"].parameters[0].autocomplete)
        self.assertEqual([p.required for p in commands["setup_ctf"].parameters], [True, False, False, False])
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

    def problem_removal_interaction(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.id, channel.guild.id = 100, 2
        channel.delete = AsyncMock()
        self.bot.store.save_challenge(dict(id=100, event=1, name="demo", workers={}, solver=10))
        interaction = SimpleNamespace(channel=channel, guild_id=2, user=SimpleNamespace(guild_permissions=discord.Permissions(manage_guild=True)),
            response=SimpleNamespace(defer=AsyncMock()), followup=SimpleNamespace(send=AsyncMock()))
        return interaction, channel

    async def test_erase_challenge_deletes_only_selected_problem(self):
        interaction, channel = self.problem_removal_interaction()
        self.bot.store.save_challenge(dict(id=101, event=1, name="keep", workers={}, solver=None))
        cog = CTFCommands(self.bot)
        await cog.edit_challenge.callback(cog, interaction, erase=True)
        channel.delete.assert_awaited_once()
        self.assertIsNone(self.bot.store.challenge(100))
        self.assertIsNotNone(self.bot.store.challenge(101))
        self.assertIsNotNone(self.bot.store.event(1))
        self.assertIn(1, self.bot.dirty)
        interaction.followup.send.assert_awaited_once()

    async def test_erase_challenge_keeps_state_on_failure(self):
        interaction, channel = self.problem_removal_interaction()
        channel.delete.side_effect = discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "denied")
        cog = CTFCommands(self.bot)
        with self.assertRaises(discord.Forbidden):
            await cog.edit_challenge.callback(cog, interaction, erase=True)
        self.assertIsNotNone(self.bot.store.challenge(100))
        channel.delete.side_effect = discord.NotFound(MagicMock(status=404, reason="Not Found"), "gone")
        await cog.edit_challenge.callback(cog, interaction, erase=True)
        self.assertIsNone(self.bot.store.challenge(100))

    async def test_erase_challenge_permissions_and_scope(self):
        interaction, channel = self.problem_removal_interaction()
        cog = CTFCommands(self.bot)
        interaction.user.guild_permissions = discord.Permissions.none()
        with self.assertRaisesRegex(ValueError, "관리자"):
            await cog.edit_challenge.callback(cog, interaction, erase=True)
        interaction.user.guild_permissions = discord.Permissions(manage_guild=True)
        with self.assertRaisesRegex(ValueError, "함께"):
            await cog.edit_challenge.callback(cog, interaction, name="demo", erase=True)
        interaction.guild_id = 999
        with self.assertRaises(ValueError):
            await cog.edit_challenge.callback(cog, interaction, erase=True)
        interaction.guild_id, channel.id = 2, 4
        with self.assertRaises(ValueError):
            await cog.edit_challenge.callback(cog, interaction, erase=True)
        channel.delete.assert_not_awaited()

    async def test_manual_problem_deletion_cleans_dashboard_state(self):
        interaction, channel = self.problem_removal_interaction()
        task = MagicMock()
        self.bot.rename_tasks[100] = task
        await self.bot.on_guild_channel_delete(channel)
        self.assertIsNone(self.bot.store.challenge(100))
        self.assertIn(1, self.bot.dirty)
        task.cancel.assert_called_once()
        self.assertNotIn(100, self.bot.rename_tasks)
        self.assertIsNotNone(self.bot.store.event(1))

    async def test_offline_problem_deletion_requires_confirmed_not_found(self):
        self.problem_removal_interaction()
        guild = SimpleNamespace(get_channel=lambda _: None,
            fetch_channel=AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "denied")))
        with self.assertRaises(discord.Forbidden):
            await self.bot.prune_missing_challenges(guild, self.event)
        self.assertIsNotNone(self.bot.store.challenge(100))
        guild.fetch_channel.side_effect = None
        guild.fetch_channel.return_value = SimpleNamespace(id=100)
        await self.bot.prune_missing_challenges(guild, self.event)
        self.assertIsNotNone(self.bot.store.challenge(100))
        guild.fetch_channel.side_effect = discord.NotFound(MagicMock(status=404, reason="Not Found"), "gone")
        await self.bot.prune_missing_challenges(guild, self.event)
        self.assertIsNone(self.bot.store.challenge(100))

    def removal_interaction(self):
        category = SimpleNamespace(id=1, name="⚔️hitcon2026⚔️", category_id=None, delete=AsyncMock())
        child = SimpleNamespace(id=4, category_id=1, delete=AsyncMock())
        other = SimpleNamespace(id=20, category_id=8, delete=AsyncMock())
        role = SimpleNamespace(delete=AsyncMock())
        guild = SimpleNamespace(id=2, fetch_channels=AsyncMock(return_value=[category, child, other]),
                                get_role=lambda _: role, get_channel=lambda id: category if id == 1 else None)
        interaction = SimpleNamespace(guild=guild, response=SimpleNamespace(defer=AsyncMock()),
                                      followup=SimpleNamespace(send=AsyncMock()))
        return interaction, category, child, other, role

    async def test_remove_ctf_exact_name_and_guild(self):
        interaction, category, child, other, role = self.removal_interaction()
        cog = CTFCommands(self.bot)
        for name in ("hitcon", "hitcon2026x", "ctf:999"):
            with self.assertRaisesRegex(ValueError, "일치"):
                await cog.remove_ctf.callback(cog, interaction, name)
        interaction.guild.id = 999
        with self.assertRaisesRegex(ValueError, "일치"):
            await cog.remove_ctf.callback(cog, interaction, "hitcon2026")
        interaction.guild.fetch_channels.assert_not_awaited()
        category.delete.assert_not_awaited()
        self.assertIsNotNone(self.bot.store.event(1))

    async def test_remove_ctf_accepts_copied_category_and_autocomplete_id(self):
        interaction, category, *_ = self.removal_interaction()
        cog = CTFCommands(self.bot)
        for name in ("⚔️hitcon2026⚔️", "⚔hitcon2026⚔", " HITCON2026 ", "ctf:1"):
            self.assertEqual(cog.resolve_removal(interaction.guild, name)["id"], 1)
        category.name = "⚔️test WHS4 CTF⚔️"
        await cog.remove_ctf.callback(cog, interaction, "⚔️test WHS4 CTF⚔️")
        self.assertIsNone(self.bot.store.event(1))

    async def test_remove_ctf_autocomplete_matches_and_is_scoped(self):
        interaction, *_ = self.removal_interaction()
        interaction.permissions = discord.Permissions(manage_guild=True)
        self.bot.store.save_event(dict(id=8, guild=999, name="hitcon private"))
        cog = CTFCommands(self.bot)
        for query in ("", "hit", "⚔️hitcon⚔️", "hitcn2026"):
            choices = await cog.remove_ctf_name_autocomplete(interaction, query)
            self.assertEqual([(c.name, c.value) for c in choices], [("⚔️hitcon2026⚔️", "ctf:1")])
        # A partial suggestion is never an instruction to delete the closest event.
        with self.assertRaises(ValueError):
            cog.resolve_removal(interaction.guild, "hit")
        interaction.permissions = discord.Permissions.none()
        self.assertEqual(await cog.remove_ctf_name_autocomplete(interaction, ""), [])
        interaction.guild = None
        self.assertEqual(await cog.remove_ctf_name_autocomplete(interaction, ""), [])

    async def test_remove_ctf_autocomplete_limit_and_ambiguous_names(self):
        interaction, *_ = self.removal_interaction()
        interaction.permissions = discord.Permissions(manage_guild=True)
        for id in range(10, 40):
            self.bot.store.save_event(dict(id=id, guild=2, name=f"CTF {id}"))
        cog = CTFCommands(self.bot)
        self.assertEqual(len(await cog.remove_ctf_name_autocomplete(interaction, "")), 25)
        self.bot.store.save_event(dict(id=50, guild=2, name="HITCON2026"))
        with self.assertRaisesRegex(ValueError, "여러 개"):
            cog.resolve_removal(interaction.guild, " Hitcon2026 ")
        self.assertEqual(cog.resolve_removal(interaction.guild, "ctf:50")["id"], 50)

    async def test_remove_ctf_missing_name_returns_deferred_error(self):
        from discord import app_commands
        interaction, *_ = self.removal_interaction()
        interaction.response.is_done = lambda: True
        cog = CTFCommands(self.bot)
        try:
            await cog.remove_ctf.callback(cog, interaction, "missing")
        except ValueError as error:
            await report(interaction, app_commands.CommandInvokeError(cog.remove_ctf, error))
        interaction.response.defer.assert_awaited_once()
        self.assertIn("자동완성", interaction.followup.send.call_args.args[0])

    async def test_remove_ctf_deletes_resources_and_preserves_other_ctfs(self):
        interaction, category, child, other, role = self.removal_interaction()
        self.bot.store.save_event(dict(id=8, guild=2, name="other"))
        self.bot.store.save_challenge(dict(id=100, event=1))
        self.bot.store.save_challenge(dict(id=101, event=8))
        cog = CTFCommands(self.bot)
        await cog.remove_ctf.callback(cog, interaction, "hitcon2026")
        category.delete.assert_awaited_once()
        child.delete.assert_awaited_once()
        role.delete.assert_awaited_once()
        other.delete.assert_not_awaited()
        self.assertIsNone(self.bot.store.event(1))
        self.assertIsNone(self.bot.store.challenge(100))
        self.assertIsNotNone(self.bot.store.challenge(101))
        interaction.followup.send.assert_awaited_once()

    async def test_remove_ctf_partial_failure_can_be_retried(self):
        interaction, category, child, other, role = self.removal_interaction()
        child.delete.side_effect = discord.Forbidden(MagicMock(status=403, reason="Forbidden"), "denied")
        cog = CTFCommands(self.bot)
        with self.assertRaisesRegex(ValueError, "같은 /remove_ctf"):
            await cog.remove_ctf.callback(cog, interaction, "hitcon2026")
        self.assertTrue(self.bot.store.event(1)["removing"])
        category.delete.assert_not_awaited()
        role.delete.assert_not_awaited()
        child.delete.side_effect = discord.NotFound(MagicMock(status=404, reason="Not Found"), "gone")
        await cog.remove_ctf.callback(cog, interaction, "hitcon2026")
        self.assertIsNone(self.bot.store.event(1))

    async def test_remove_ctf_runtime_permission_check(self):
        from discord import app_commands
        command = CTFCommands(self.bot).remove_ctf
        for allowed in (False, True):
            interaction = SimpleNamespace(permissions=discord.Permissions(manage_guild=allowed))
            if allowed:
                self.assertTrue(command.checks[0](interaction))
            else:
                with self.assertRaises(app_commands.MissingPermissions):
                    command.checks[0](interaction)

    async def test_setup_ctf_updates_only_supplied_fields(self):
        interaction, *_ = self.removal_interaction()
        cog = CTFCommands(self.bot)
        original = self.bot.store.event(1)
        await cog.setup_ctf.callback(cog, interaction, "⚔️hitcon2026⚔️", url="https://new.example.com")
        updated = self.bot.store.event(1)
        self.assertEqual(updated["url"], "https://new.example.com")
        for field in ("id", "name", "role", "slug", "start", "end"):
            self.assertEqual(updated[field], original[field])
        await cog.setup_ctf.callback(cog, interaction, "ctf:1", end="2026-12-01T20:00+09:00")
        self.assertGreater(self.bot.store.event(1)["end"], original["end"])
        await cog.setup_ctf.callback(cog, interaction, "HITCON2026", start="2026-10-01T20:00+09:00")
        self.assertLess(self.bot.store.event(1)["start"], original["start"])
        self.assertEqual(len(self.bot.store.events()), 1)
        self.assertIn(1, self.bot.dirty)

    async def test_setup_ctf_rejects_invalid_partial_updates_without_saving(self):
        interaction, *_ = self.removal_interaction()
        cog = CTFCommands(self.bot)
        original = self.bot.store.event(1)
        for options in ({}, {"url": "bad"}, {"end": "2020-01-01T00:00+09:00"},
                        {"start": "2099-01-01T00:00+09:00"}, {"url": ""}):
            with self.assertRaises(ValueError):
                await cog.setup_ctf.callback(cog, interaction, "hitcon2026", **options)
            self.assertEqual(self.bot.store.event(1), original)
        with self.assertRaisesRegex(ValueError, "모두"):
            await cog.setup_ctf.callback(cog, interaction, "new-ctf", url="https://example.com")
        self.assertEqual(len(self.bot.store.events()), 1)

    async def test_setup_ctf_autocomplete_is_scoped_and_can_select_existing(self):
        interaction, *_ = self.removal_interaction()
        interaction.permissions = discord.Permissions(manage_guild=True)
        self.bot.store.save_event(dict(id=8, guild=999, name="hitcon-other"))
        cog = CTFCommands(self.bot)
        choices = await cog.setup_ctf_name_autocomplete(interaction, "hitcn")
        self.assertEqual([c.value for c in choices], ["ctf:1"])
        await cog.setup_ctf.callback(cog, interaction, choices[0].value, url="https://new.example.com")
        interaction.permissions = discord.Permissions.none()
        self.assertEqual(await cog.setup_ctf_name_autocomplete(interaction, ""), [])

    async def test_existing_role_is_renamed_without_replacing_it(self):
        role = SimpleNamespace(id=3, name="CTF-hitcon2026", edit=AsyncMock())
        guild = SimpleNamespace(get_role=lambda _: role)
        await self.bot.sync_event_role(guild, "⚔️hitcon2026⚔️", self.event)
        role.edit.assert_awaited_once_with(name="⚔️hitcon2026⚔️", reason="Match CTF category name")
        self.assertEqual(self.bot.store.event(1)["role"], 3)
        role.name = "⚔️hitcon2026⚔️"
        await self.bot.sync_event_role(guild, "⚔️hitcon2026⚔️", self.event)
        role.edit.assert_awaited_once()

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
        guild = SimpleNamespace(id=2, get_channel=lambda _: None, roles=[everyone, participant], default_role=everyone,
            me=bot_member, text_channels=[], create_role=AsyncMock(return_value=participant),
            create_category=AsyncMock(side_effect=create_category),
            create_text_channel=AsyncMock(side_effect=create_text))
        interaction = SimpleNamespace(guild=guild, response=SimpleNamespace(defer=AsyncMock()),
                                      followup=SimpleNamespace(send=AsyncMock()))
        cog = CTFCommands(self.bot)
        await cog.setup_ctf.callback(cog, interaction, "My CTF", "2026-11-01T20:00+09:00",
                                     "2026-11-03T20:00+09:00", "https://example.com")
        self.assertEqual(guild.create_category.call_args.args[0], "⚔️My CTF⚔️")
        self.assertEqual(guild.create_role.call_args.kwargs["name"], "⚔️My CTF⚔️")
        calls = guild.create_text_channel.call_args_list
        self.assertEqual([call.args[0] for call in calls],
                         ["📢│announcements", "📊│dashboard", "💬│general", "ctf-join"])
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
        self.assertEqual(dashboard.edit.call_args.kwargs["name"], "📊│dashboard")
        self.assertIsNone(dashboard.edit.call_args.kwargs["topic"])
        self.assertEqual(announcement.edit.call_args.kwargs["name"], "📢│announcements")
        self.assertEqual(self.bot.store.event(1)["general"], 7)
        await self.bot.migrate_layout(guild, category, self.event)
        guild.create_text_channel.assert_awaited_once()
        self.assertIn("\n봇은 정답을 검증하지 않습니다.", HELP)

    async def test_version_one_layout_renames_existing_general(self):
        self.event.update(layout_version=1, general=7)
        category = SimpleNamespace(edit=AsyncMock(), text_channels=[])
        channels = {}
        for id in (4, 6, 7):
            channel = MagicMock(spec=discord.TextChannel)
            channel.id, channel.edit, channel.overwrites = id, AsyncMock(), {}
            channels[id] = channel
        everyone = MagicMock(spec=discord.Role)
        everyone.permissions = discord.Permissions.none()
        guild = SimpleNamespace(get_channel=channels.get, default_role=everyone,
            roles=[everyone], me=MagicMock(spec=discord.Member), create_text_channel=AsyncMock())
        await self.bot.migrate_layout(guild, category, self.event)
        self.assertEqual(channels[6].edit.call_args.kwargs["name"], "📢│announcements")
        self.assertEqual(channels[4].edit.call_args.kwargs["name"], "📊│dashboard")
        self.assertEqual(channels[7].edit.call_args.kwargs["name"], "💬│general")
        self.assertEqual(self.bot.store.event(1)["layout_version"], 2)
        guild.create_text_channel.assert_not_awaited()
        await self.bot.migrate_layout(guild, category, self.event)
        channels[7].edit.assert_awaited_once()

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
            return channel
        channel.edit = AsyncMock(side_effect=rename)
        self.bot.get_channel = lambda _: channel
        await self.bot.sync_name(100)
        self.assertEqual(channel.name, "🚩-web-demo")
        ch["solver"] = None
        self.bot.store.save_challenge(ch)
        await self.bot.sync_name(100)
        self.assertEqual(channel.name, "web-demo")

    async def test_name_sync_does_not_repeat_edits_against_stale_gateway_cache(self):
        self.bot.store.save_challenge(dict(id=100, event=1, name="pwn-runner", solver=None))
        stale = MagicMock(spec=discord.TextChannel)
        stale.name = "🚩-pwn-runner"
        updated = MagicMock(spec=discord.TextChannel)
        updated.name = "pwn-runner"
        stale.edit = AsyncMock(return_value=updated)
        self.bot.get_channel = lambda _: stale
        await self.bot.sync_name(100)
        stale.edit.assert_awaited_once_with(name="pwn-runner", reason="CTF challenge status")
        updated.edit.assert_not_called()

    async def test_unsolve_during_inflight_solve_rename_removes_flag(self):
        ch = dict(id=100, event=1, name="runner", solver=10)
        self.bot.store.save_challenge(ch)
        started, release = asyncio.Event(), asyncio.Event()
        stale = MagicMock(spec=discord.TextChannel)
        stale.name = "runner"
        flagged = MagicMock(spec=discord.TextChannel)
        flagged.name = "🚩-runner"
        restored = MagicMock(spec=discord.TextChannel)
        restored.name = "runner"
        async def solve_rename(**kwargs):
            started.set()
            await release.wait()
            return flagged
        stale.edit = AsyncMock(side_effect=solve_rename)
        flagged.edit = AsyncMock(return_value=restored)
        self.bot.get_channel = lambda _: stale
        self.bot.queue_name_sync(100)
        await started.wait()
        ch["solver"] = None
        self.bot.store.save_challenge(ch)
        prior = self.bot.rename_tasks[100]
        self.bot.queue_name_sync(100)
        self.assertIs(self.bot.rename_tasks[100], prior)
        release.set()
        await prior
        flagged.edit.assert_awaited_once_with(name="runner", reason="CTF challenge status")

    async def test_edit_category_only_inside_existing_problem(self):
        interaction, *_ = self.removal_interaction()
        channel = MagicMock(spec=discord.TextChannel)
        channel.id, channel.category_id, channel.mention = 100, 1, "<#100>"
        interaction.channel, interaction.channel_id, interaction.guild_id = channel, 100, 2
        interaction.user = SimpleNamespace(id=10, guild_permissions=discord.Permissions.none(),
                                           roles=[SimpleNamespace(id=3)])
        self.bot.upsert_message = AsyncMock(return_value=500)
        self.bot.store.save_challenge(dict(id=100, event=1, name="runner", category="", added_by=10,
                                           solver=None, workers={}))
        cog = CTFCommands(self.bot)
        await cog.edit_challenge.callback(cog, interaction, category="pwn")
        self.assertEqual(self.bot.store.challenge(100)["name"], "pwn-runner")
        await cog.edit_challenge.callback(cog, interaction, category="web")
        self.assertEqual(self.bot.store.challenge(100)["name"], "web-runner")
        self.assertEqual(self.bot.store.challenge(100)["added_by"], 10)
        # Legacy categorized records have no separate problem_name field.
        ch = self.bot.store.challenge(100)
        ch.pop("problem_name")
        self.bot.store.save_challenge(ch)
        await cog.edit_challenge.callback(cog, interaction, category="crypto")
        self.assertEqual(self.bot.store.challenge(100)["name"], "crypto-runner")
        interaction.channel_id = 4
        with self.assertRaisesRegex(ValueError, "name"):
            await cog.edit_challenge.callback(cog, interaction, category="web")
        interaction.channel_id = 100
        interaction.user.id = 20
        with self.assertRaisesRegex(ValueError, "관리자"):
            await cog.edit_challenge.callback(cog, interaction, category="web")


if __name__ == "__main__":
    unittest.main()
