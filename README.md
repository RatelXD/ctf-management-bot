# ctf-management-bot

사진과 같은 참가 버튼, 문제별 채널, 참가자별 작업 상태와 풀이 현황을 관리하는 Python 봇입니다. Discord 서버를 새로 만들 필요 없이 관리 권한이 있는 기존 서버에 초대하면 됩니다. 실행용 개인 서버도 필수는 아닙니다. PC에서 실행할 수 있으며, 봇이 켜져 있는 동안 명령어와 버튼이 동작합니다.

## 1. 봇 생성과 초대

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 **New Application**을 만들고 Bot 메뉴에서 봇 토큰을 발급합니다.
2. Installation 또는 OAuth2 URL Generator에서 **서버 설치(Guild Install)**, `bot`, `applications.commands`를 선택합니다.
3. 봇 권한: **Manage Channels, Manage Roles, View Channels, Send Messages, Embed Links, Read Message History**. Administrator는 필요 없습니다.
4. 초대 링크를 열어 사용할 Discord 서버에 초대합니다.
5. 서버 설정 → 역할에서 **봇 역할을 CTF 참가 역할보다 위로** 올려 둡니다. 새 참가 역할은 봇이 생성합니다. 자동으로 위에 배치되지만, 나중에 순서를 바꾸면 참가 버튼이 실패할 수 있습니다.

Message Content Intent, Server Members Intent 등 privileged intent는 켤 필요가 없습니다. 토큰은 `.env`에만 보관하고 공개 저장소에 올리지 마세요. 기존 사용자 계정 토큰은 사용하지 않습니다.

## 2. Windows에서 실행

Python 3.11 이상을 설치하고 이 폴더에서 PowerShell로 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

`.env`의 `DISCORD_TOKEN`에 **봇 토큰**을 넣습니다. Discord 개발자 모드에서 서버 ID를 복사해 `DISCORD_GUILD_ID`에도 넣으면 그 서버에 명령어를 즉시 등록합니다. 비우면 전역 등록으로 전파에 시간이 걸릴 수 있습니다. 서버 한 곳에서 쓸 때는 ID를 넣는 편이 간편합니다. 실행 중 설정을 바꿨으면 재시작하세요. 전역/서버 등록을 전환하면 예전 등록 명령이 남을 수 있으므로 운영에서는 한 방식을 유지하세요.

```powershell
.\.venv\Scripts\python.exe bot.py
```

Ready 로그가 나오면 Discord에서 아래 설정 명령을 실행합니다. PowerShell 창을 닫거나 PC를 끄면 봇도 꺼집니다. 공개 IP, 포트 포워딩, 웹 도메인은 필요 없습니다.

## 3. 대회 생성

서버 관리(Manage Server) 권한이 있는 사람이 Discord에서 실행합니다. 슬래시 명령을 선택한 다음 각 옵션 칸에 값을 넣으세요.

```text
/setup_ctf name:hitcon2026 start:2026-11-01T20:00+09:00 end:2026-11-03T20:00+09:00 url:https://example.com
```

위 날짜와 URL은 실행 예시이며 실제 HITCON 일정이 아닙니다.

자동 생성:

- 공개 `#ctf-join`: 대회명, Start, End, URL, 참가/탈퇴 버튼
- 참가 역할 `CTF-hitcon2026`
- 비공개 `hitcon2026-everyone` 카테고리
- 카테고리 아래 `#announcements`, `#status`

같은 대회명으로 `/setup_ctf`를 다시 실행하면 날짜와 URL을 수정합니다. 대회를 여러 개 만들면 `#ctf-join`에 대회별 카드와 버튼이 생깁니다. 카테고리 밖의 기존 `#ctf-join`이 있으면 재사용하므로, 그 채널은 일반 참가자에게 보이고 봇이 메시지를 쓸 수 있어야 합니다.

버튼을 누르면 **그 사람에게만 보이는 응답**과 함께 역할을 부여합니다. 다시 누르면 역할을 회수하고 떠났다고 응답합니다. 카테고리와 문제 채널은 참가자에게 보였다가 숨겨집니다. 채널이나 기록을 삭제하지 않으므로 다른 참가자에게 영향이 없습니다. Discord의 Administrator 권한이 있는 사람과 서버 소유자는 권한 우회로 카테고리를 계속 볼 수 있습니다.

## 4. 문제와 풀이 관리

먼저 참가 버튼을 누른 뒤 **해당 대회의 `#status` 또는 `#announcements`에서** 실행합니다.

```text
/edit_ch name:web-php2shell-real
/edit_ch name:web-php2shell-real category:web description:문제 설명
```

해당 이름의 텍스트 채널과 `Added by @생성자` 카드가 만들어집니다. 이름은 Discord 채널에 맞게 소문자·하이픈으로 정리됩니다. 생성자 기록은 수정해도 유지됩니다. **이미 만들어진 문제 채널 안에서** `/edit_ch`를 쓰면 그 문제의 이름·분야·설명을 수정합니다. 다른 새 문제를 만들려면 다시 `#status`로 이동하세요. 수정은 생성자와 서버 관리자만 할 수 있습니다.

**문제 채널 안에서** 다음 명령을 실행합니다.

| 명령 | 동작 |
| --- | --- |
| `/update_status status:working` | 내 이름을 🔨 푸는 중으로 표시 |
| `/update_status status:stuck` | 내 이름을 🆘 막힘·도움 필요 SOS로 표시 |
| `/update_status status:stopped` | 내 이름을 작업자 목록에서 제거 |
| `/solve_ch flag:FLAG{...}` | 실행자를 해결자로 기록, 풀이 완료 알림과 플래그 공개, 채널명 앞에 🚩 |
| `/unsolve_ch` | 풀이 완료 취소, 🚩 제거, 작업자 목록 초기화 |

여러 사람이 working/stuck 상태를 등록할 수 있습니다. 해결 시 작업자 목록을 비우고 해결자 한 명만 표시합니다. 풀이 취소는 해결자 또는 서버 관리자만 가능합니다. 이미 해결된 문제에 추가 solve나 작업 상태 변경은 허용하지 않습니다.

**플래그 인증은 대회 사이트에서 먼저 해야 합니다.** 봇은 입력된 플래그의 정답 여부를 검증하거나 대회에 자동 제출하지 않습니다. `/solve_ch`는 팀원 간 완료 기록용입니다. 플래그는 해당 비공개 문제 채널 참가자들에게 공개됩니다.

`#status`는 다음 모양으로 자동 갱신됩니다. 미해결 줄 앞에는 체크박스가 없습니다.

```text
📋 hitcon2026 — 1 / 3 solved

✅ #🚩-web-repo-cassette · solved by @해결자
#web-php2shell-real · 🔨 @작업자 · 🆘 @도움필요
#pwn-example · 미해결
```

상태판은 보통 5초 안에 반영됩니다. 채널 이름 변경은 Discord의 별도 rate limit에 걸리면 수 분 늦어질 수 있습니다. 상태판과 명령 응답은 이름 변경을 기다리지 않습니다. 상태판·참가 메시지를 지운 경우 다음 상태 변경 또는 봇 재시작 때 다시 생성합니다.

## 5. 저장과 운영

SQLite `data/ctf.sqlite3`에 대회 ID, 채널 ID, 생성자, 작업 상태, 해결자, 플래그, 메시지 ID를 저장합니다. 재시작 후에도 참가 버튼이 동작합니다. **봇 인스턴스는 하나만 실행**하세요. 백업은 봇을 종료한 뒤 `data` 폴더를 복사하면 됩니다. 카테고리·역할·문제 채널을 Discord에서 수동 삭제하는 경우 자동 복원하지 않으므로 삭제하지 마세요. `/unsolve_ch`는 기존 채팅의 완료 알림을 지우지 않습니다.

Docker를 쓸 수 있는 PC/VM에서는:

```sh
docker compose up -d --build
docker compose logs -f
```

데이터를 호스트의 `./data` 폴더에 보관하고 재부팅 후 자동 재시작하도록 설정했습니다.

## 6. 무료 실행 방법

2026-11-01 공식 문서 확인 기준:

- **가장 간편한 무료 방법: 내 PC에서 실행.** 위 명령으로 실행하면 되고 PC가 켜져 있어야 합니다. 대회 기간에만 켜 두는 방식에 적합합니다.
- **PC를 끄고 계속 실행: Oracle Cloud Always Free VM 등 상시 실행 가능한 VM.** [공식 안내](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)를 확인해 무료 대상 인스턴스를 만들고 이 폴더와 `.env`를 옮긴 뒤 Docker Compose로 실행할 수 있습니다. 계정 가입과 초기 서버 설정이 필요하고, 무료 자원 가용성과 유휴 인스턴스 회수 조건이 있습니다.
- **Render 무료 Web Service:** [공식 제한](https://render.com/docs/free)에 따르면 유휴 중단과 로컬 SQLite 소실이 있습니다. 이 봇은 지속 실행 프로세스와 영속 디스크가 필요하므로 그대로 올릴 배포 대상에 맞지 않습니다. 무료 Background Worker도 제공하지 않습니다.

질문의 “muse”가 특정 호스팅 서비스라면 정확한 서비스 링크를 확인해야 지원 여부를 판단할 수 있습니다. 이 프로젝트는 일반 Python 프로세스 또는 Docker 컨테이너를 상시 실행하고 데이터 폴더를 유지할 수 있는 환경에서 실행됩니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

실제 토큰 없이 상태 전이, SQLite 재시작 보존, 상태판 분할, 슬래시 명령 등록, 참가 버튼 및 메시지 복구를 검사합니다. 실제 Discord 서버에서는 초대 후 아래 동작을 확인하세요.

1. 일반 계정으로 참가 → 카테고리 보임 → 재클릭으로 숨김 → 재참가
2. `#status`에서 문제 생성 후 Added by 확인
3. 두 계정으로 working/stuck → 둘 다 상태판 표시, stopped → 해당 사람만 사라짐
4. solve → 완료 알림·해결자·🚩, unsolve → ✅·🚩 제거
5. 봇 재시작 후 기존 참가 버튼과 상태판 유지

실제 Discord API 연동은 봇 토큰과 테스트 서버가 있어야 검증할 수 있습니다.
