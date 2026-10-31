import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from bot import CTFBot, CTFCommands, JoinView, info_embed


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = CTFBot(":memory:")
        self.event = dict(id=1, guild=2, role=3, status=4, join=5, announcements=6,
                          name="hitcon2026", start=1793530800, end=1793703600, url="https://example.com")
        self.bot.store.save_event(self.event)

    async def asyncTearDown(self):
        await self.bot.close()

    async def test_commands_and_slash_options(self):
        await self.bot.add_cog(CTFCommands(self.bot))
        commands = {c.name: c for c in self.bot.tree.get_commands()}
        self.assertEqual(set(commands), {"setup_ctf", "edit_ch", "update_status", "solve_ch", "unsolve_ch"})
        self.assertEqual(commands["edit_ch"].parameters[0].name, "name")
        self.assertTrue(commands["solve_ch"].parameters[0].required)
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
        await cog.edit_ch.callback(cog, interaction, "Web Demo", "web", "Test problem")
        ch = self.bot.store.challenge(100)
        self.assertEqual(ch["added_by"], 10)
        self.assertEqual(ch["name"], "web-demo")
        self.assertEqual(ch["info_message"], 500)
        interaction.channel, interaction.channel_id = channel, 100
        await cog.update_status.callback(cog, interaction, "working")
        self.assertEqual(self.bot.store.challenge(100)["workers"], {"10": "working"})
        await cog.solve_ch.callback(cog, interaction, "FLAG{ok}")
        self.assertEqual(self.bot.store.challenge(100)["solver"], 10)
        self.assertIn(1, self.bot.dirty)
        embed = channel.send.call_args.kwargs["embed"]
        self.assertIn("풀이 완료", embed.title)
        self.assertIn("FLAG", embed.description)
        await cog.unsolve_ch.callback(cog, interaction)
        self.assertIsNone(self.bot.store.challenge(100)["solver"])

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
