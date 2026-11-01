"""Regenerate the README illustrations: pip install pillow; python scripts/render_readme_assets.py."""
from pathlib import Path
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets"
SCALE = 2
FONT_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"


def font(size, bold=False):
    candidates = [FONT_DIR / ("malgunbd.ttf" if bold else "malgun.ttf"),
                  Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
                       "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size * SCALE)
    raise RuntimeError("Install Malgun Gothic (Korean) or DejaVu Sans fonts before rendering.")


class Canvas:
    def __init__(self, width, height):
        self.image = Image.new("RGB", (width * SCALE, height * SCALE), "#10121e")
        self.draw = ImageDraw.Draw(self.image)
        self.width, self.height = width, height
        for y in range(height * SCALE):
            t = y / (height * SCALE)
            self.draw.line((0, y, width * SCALE, y), fill=(int(19 - t * 5), int(22 - t * 5), int(40 - t * 11)))

    def box(self, coords, fill, radius=14, outline=None):
        self.draw.rounded_rectangle(tuple(v * SCALE for v in coords), radius=radius * SCALE,
                                    fill=fill, outline=outline, width=SCALE)

    def text(self, xy, text, size=20, color="#eef0ff", bold=False):
        self.draw.text(tuple(v * SCALE for v in xy), text, font=font(size, bold), fill=color)

    def line(self, coords, color="#353951", width=1):
        self.draw.line(tuple(v * SCALE for v in coords), fill=color, width=width * SCALE)

    def flag(self, x, y, color="#ff667f", size=28):
        self.line((x, y, x, y + size), color, 3)
        self.draw.polygon([(x * SCALE, y * SCALE), ((x + size) * SCALE, (y + size * .32) * SCALE),
                           (x * SCALE, (y + size * .64) * SCALE)], fill=color)

    def save(self, name):
        OUT.mkdir(parents=True, exist_ok=True)
        self.image.save(OUT / name, optimize=True)


def banner():
    c = Canvas(1440, 640)
    for x in range(0, 1440, 48):
        c.line((x, 0, x, 640), "#1b1e31")
    for y in range(0, 640, 48):
        c.line((0, y, 1440, y), "#1b1e31")
    c.box((60, 56, 114, 110), "#292b48", 14)
    c.flag(78, 70, size=25)
    c.text((130, 67), "YOUR TEAM. ONE WORKSPACE.", 19, "#9fa8d6", True)
    c.text((60, 158), "CTF", 76, bold=True)
    c.text((60, 257), "Management Bot", 53, bold=True)
    c.text((64, 351), "참가부터 풀이 완료까지, Discord 안에서.", 22, "#bac1df")
    c.box((64, 416, 201, 453), "#282b45", 8)
    c.text((79, 421), "JOIN / LEAVE", 15, "#c5c9ff", True)
    c.box((215, 416, 360, 453), "#173631", 8)
    c.text((231, 421), "LIVE STATUS", 15, "#8fe8c6", True)
    c.text((64, 543), "Python  /  discord.py  /  SQLite", 18, "#8d96b7")
    c.box((718, 82, 1380, 555), "#0b0d18", 24, "#393d59")
    c.box((732, 96, 1366, 541), "#1b1e30", 16)
    c.text((761, 116), "#  dashboard", 23, bold=True)
    c.box((1220, 117, 1335, 147), "#173b32", 7)
    c.text((1235, 121), "MY CTF", 13, "#8fe8c6", True)
    c.line((756, 168, 1340, 168))
    c.box((760, 192, 1338, 464), "#24283e", 12)
    c.box((760, 192, 765, 464), "#8f94ff", 2)
    c.text((789, 215), "my-ctf", 24, bold=True)
    c.text((790, 254), "1 / 3 solved", 17, "#aab1d5")
    c.box((788, 300, 814, 326), "#76d9af", 5)
    c.line((794, 312, 799, 318), "#142b27", 3)
    c.line((799, 318, 809, 306), "#142b27", 3)
    c.flag(830, 305, size=19)
    c.text((862, 300), "web-solved", 18, "#d5d9ff", True)
    c.text((1031, 300), "solved by @alice", 17, "#9da7cd")
    c.text((790, 355), "# web-example", 19, "#d5d9ff", True)
    c.text((1031, 355), "working · @bob", 17, "#8fe8c6")
    c.text((790, 405), "# pwn-example", 19, "#d5d9ff", True)
    c.text((1031, 405), "SOS · @charlie", 17, "#ffb6c4")
    c.text((761, 489), "/edit_challenge   /update_status   /solve_challenge", 13, "#9ca7d3")
    c.text((719, 578), "기능 예시 · 실제 Discord 화면을 캡처한 이미지가 아닙니다", 14, "#7e89af")
    c.save("banner.png")


def workflow():
    c = Canvas(1440, 360)
    c.text((48, 27), "FROM JOIN TO FLAG", 23, bold=True)
    c.text((48, 67), "처음 한 번 설정하고, 팀원은 Discord 명령어로 함께 진행하세요.", 18, "#aab3d2")
    data = [
        ("01", "대회 설정", "/setup_ctf", "대회명 · 일정 · URL 입력", "#a4a1ff"),
        ("02", "참가하기", "JOIN / LEAVE", "버튼으로 카테고리 표시·숨김", "#a4a1ff"),
        ("03", "문제 함께 풀기", "/edit_challenge  /update_status", "문제 추가 · 작업자 · SOS 표시", "#82d7e9"),
        ("04", "풀이 완료", "/solve_challenge", "완료 알림 · 깃발 · 해결자 표시", "#8fe8c6"),
    ]
    for i, (num, title, command, subtitle, accent) in enumerate(data):
        x = 48 + i * 345
        c.box((x, 117, x + 309, 304), "#202438", 15, "#383e5b")
        c.text((x + 20, 133), num, 18, accent, True)
        c.text((x + 20, 174), title, 25, bold=True)
        c.text((x + 20, 223), command, 17, accent, True)
        c.text((x + 20, 264), subtitle, 14, "#aab3d2")
        if i < 3:
            c.text((x + 319, 194), "›", 26, "#7a83b0", True)
    c.save("workflow.png")


if __name__ == "__main__":
    banner()
    workflow()
