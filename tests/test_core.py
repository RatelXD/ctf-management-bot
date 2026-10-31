import tempfile
import unittest
from pathlib import Path

from core import Store, board_pages, channel_name, event_details, set_status, solve, unsolve


class StateTests(unittest.TestCase):
    def setUp(self):
        self.ch = dict(id=100, event=1, name="web-demo", added_by=10, workers={}, solver=None, flag=None)

    def test_working_stuck_stopped_are_per_user(self):
        set_status(self.ch, 10, "working")
        set_status(self.ch, 20, "stuck")
        self.assertEqual(self.ch["workers"], {"10": "working", "20": "stuck"})
        set_status(self.ch, 10, "stopped")
        self.assertEqual(self.ch["workers"], {"20": "stuck"})

    def test_solve_clears_workers_and_preserves_creator(self):
        set_status(self.ch, 10, "working")
        solve(self.ch, 20, "FLAG{ok}")
        self.assertEqual(self.ch["solver"], 20)
        self.assertEqual(self.ch["added_by"], 10)
        self.assertEqual(self.ch["workers"], {})
        with self.assertRaises(ValueError):
            solve(self.ch, 10, "FLAG{again}")
        with self.assertRaises(ValueError):
            set_status(self.ch, 10, "working")

    def test_unsolve_permissions_and_reset(self):
        solve(self.ch, 20, "FLAG{ok}")
        with self.assertRaises(ValueError):
            unsolve(self.ch, 10, False)
        unsolve(self.ch, 20, False)
        self.assertIsNone(self.ch["solver"])
        self.assertIsNone(self.ch["flag"])
        self.assertEqual(self.ch["workers"], {})
        solve(self.ch, 20, "FLAG{ok}")
        unsolve(self.ch, 99, True)
        self.assertIsNone(self.ch["solver"])

    def test_invalid_inputs(self):
        for value in ("", " " * 4, "x" * 1001):
            with self.assertRaises(ValueError):
                solve(self.ch, 10, value)
        with self.assertRaises(ValueError):
            set_status(self.ch, 10, "arbitrary")
        with self.assertRaises(ValueError):
            unsolve(self.ch, 10, True)

    def test_board_unsolved_has_no_checkbox(self):
        set_status(self.ch, 10, "working")
        set_status(self.ch, 20, "stuck")
        page = board_pages({"name": "demo"}, [self.ch])[0]
        self.assertIn("<@10>", page)
        self.assertIn("🆘 <@20>", page)
        self.assertNotIn("✅", page)
        self.assertNotIn("⬜", page)
        solve(self.ch, 30, "FLAG{ok}")
        page = board_pages({"name": "demo"}, [self.ch])[0]
        self.assertIn("✅ <#100> · solved by <@30>", page)
        self.assertNotIn("<@10>", page)
        self.assertNotIn("<@20>", page)

    def test_board_pagination(self):
        challenges = [dict(self.ch, id=i, name=f"web-{i}", workers={str(i): "working"}) for i in range(500)]
        pages = board_pages({"name": "a" * 80}, challenges)
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(p) <= 4096 for p in pages))
        combined = "\n".join(pages)
        for i in range(500):
            self.assertEqual(combined.count(f"<#{i}>"), 1)

    def test_empty_board(self):
        self.assertIn("0 / 0 solved", board_pages({"name": "demo"}, [])[0])

    def test_sqlite_restart_and_event_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "data" / "ctf.db")
            db = Store(path)
            db.save_event(dict(id=1, name="demo"))
            db.save_event(dict(id=2, name="other"))
            set_status(self.ch, 10, "stuck")
            db.save_challenge(self.ch)
            db.db.close()
            db = Store(path)
            self.assertEqual(db.challenge(100)["workers"], {"10": "stuck"})
            self.assertEqual(len(db.challenges(1)), 1)
            self.assertEqual(db.challenges(2), [])
            self.assertEqual(len(db.events()), 2)
            self.assertIsNone(db.event(None))
            solve(self.ch, 20, "FLAG{stored}")
            db.save_challenge(self.ch)
            db.db.close()
            db = Store(path)
            self.assertEqual(db.challenge(100)["flag"], "FLAG{stored}")
            self.assertEqual(db.challenge(100)["solver"], 20)
            db.db.close()

    def test_channel_normalization(self):
        self.assertEqual(channel_name(" Web PHP2Shell_REAL "), "web-php2shell-real")
        self.assertEqual(channel_name("한글 문제"), "한글-문제")
        self.assertLessEqual(len(channel_name("a" * 150)), 96)
        with self.assertRaises(ValueError):
            channel_name("🚩 !!!")

    def test_event_input(self):
        begin, finish = event_details("2026-11-01T20:00+09:00", "2026-11-03T20:00+09:00", "https://example.com")
        self.assertEqual(finish - begin, 172800)
        for start, end, url in [
            ("bad", "bad", "https://example.com"),
            ("2026-11-01T20:00", "2026-11-03T20:00", "https://example.com"),
            ("2026-11-03T20:00+09:00", "2026-11-01T20:00+09:00", "https://example.com"),
            ("2026-11-01T20:00+09:00", "2026-11-03T20:00+09:00", "javascript:alert(1)"),
        ]:
            with self.assertRaises(ValueError):
                event_details(start, end, url)


if __name__ == "__main__":
    unittest.main()
