"""Persistent CTF state, independent of Discord/network access."""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


def channel_name(name: str) -> str:
    name = re.sub(r"[^\w\-가-힣]", "-", name.strip().lower(), flags=re.UNICODE)
    name = re.sub(r"[-_]+", "-", name).strip("-")[:96]
    if not name:
        raise ValueError("문제명에 문자나 숫자를 넣어 주세요.")
    return name


def event_details(start: str, end: str, url: str) -> tuple[int, int]:
    try:
        dates = [datetime.fromisoformat(s) for s in (start, end)]
    except ValueError:
        raise ValueError("일시는 2026-11-01T20:00+09:00 형식으로 입력해 주세요.") from None
    if any(d.tzinfo is None for d in dates):
        raise ValueError("일시에 시간대(+09:00 등)를 넣어 주세요.")
    if dates[1] <= dates[0]:
        raise ValueError("종료 시각은 시작 시각보다 늦어야 합니다.")
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or len(url) > 1000:
        raise ValueError("올바른 http/https URL을 입력해 주세요.")
    return tuple(int(d.timestamp()) for d in dates)


def set_status(ch: dict, user: int, status: str) -> None:
    if ch.get("solver"):
        raise ValueError("이미 해결된 문제입니다. /unsolve_ch 후 상태를 변경해 주세요.")
    if status not in ("working", "stuck", "stopped"):
        raise ValueError("working, stuck, stopped 중에서 골라 주세요.")
    if status == "stopped":
        ch["workers"].pop(str(user), None)
    else:
        ch["workers"][str(user)] = status


def solve(ch: dict, user: int, flag: str) -> None:
    if ch.get("solver"):
        raise ValueError("이미 해결된 문제입니다.")
    if not flag.strip() or len(flag) > 1000:
        raise ValueError("플래그는 1~1000자로 입력해 주세요.")
    ch.update(solver=user, flag=flag, workers={})


def unsolve(ch: dict, user: int, manager: bool) -> None:
    if not ch.get("solver"):
        raise ValueError("아직 해결되지 않은 문제입니다.")
    if ch["solver"] != user and not manager:
        raise ValueError("해결자 또는 서버 관리 권한이 있는 사람만 취소할 수 있습니다.")
    ch.update(solver=None, flag=None, workers={})


def board_pages(event: dict, challenges: list[dict]) -> list[str]:
    solved = sum(bool(c.get("solver")) for c in challenges)
    heading = f"📋 {event['name']} — {solved} / {len(challenges)} solved"
    pages, lines = [], []
    for ch in sorted(challenges, key=lambda c: c["name"]):
        if ch.get("solver"):
            line = f"✅ <#{ch['id']}> · solved by <@{ch['solver']}>"
        else:
            people = " · ".join(f"{'🔨' if status == 'working' else '🆘'} <@{user}>"
                                for user, status in ch["workers"].items())
            line = f"<#{ch['id']}>" + (f" · {people}" if people else " · 미해결")
        # Split very large teams across lines and pages, below Discord embed limits.
        for offset in range(0, len(line), 3500):
            piece = line[offset:offset + 3500]
            if sum(len(s) + 1 for s in lines) + len(piece) > 3800:
                pages.append("\n".join(lines))
                lines = []
            lines.append(piece)
    pages.append("\n".join(lines) or "문제가 없습니다. /edit_ch name:문제명 으로 추가하세요.")
    return [(heading + "\n\n" + page) for page in pages]


class Store:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, data TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS challenges (id INTEGER PRIMARY KEY, event INTEGER NOT NULL, data TEXT NOT NULL)")
        self.db.commit()

    def events(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT data FROM events")]

    def event(self, category: int | None):
        row = self.db.execute("SELECT data FROM events WHERE id=?", (category,)).fetchone()
        return json.loads(row[0]) if row else None

    def challenge(self, channel: int):
        row = self.db.execute("SELECT data FROM challenges WHERE id=?", (channel,)).fetchone()
        return json.loads(row[0]) if row else None

    def challenges(self, event: int):
        return [json.loads(row[0]) for row in self.db.execute("SELECT data FROM challenges WHERE event=?", (event,))]

    def save_event(self, event: dict):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO events VALUES (?, ?)", (event["id"], json.dumps(event)))

    def save_challenge(self, ch: dict):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO challenges VALUES (?, ?, ?)", (ch["id"], ch["event"], json.dumps(ch)))
