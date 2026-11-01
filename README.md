<a id="readme-top"></a>

<div align="center">
  <img src="docs/assets/banner.png" alt="CTF Management Bot — 참가, 문제 채널, 작업 상태와 풀이 완료를 Discord에서 관리" width="100%">

  <h1>ctf-management-bot</h1>
  <p><strong>참가부터 풀이 완료까지, 팀의 CTF 진행 상황을 한곳에서.</strong></p>
  <p>
    <a href="#getting-started"><strong>설치 시작하기 »</strong></a>
    <br><br>
    <a href="#configuration">처음 설정할 값</a> ·
    <a href="#usage">명령어 안내</a> ·
    <a href="https://github.com/RatelXD/ctf-management-bot/issues">버그 제보 · 기능 제안</a>
  </p>
  <p>
    <a href="https://github.com/RatelXD/ctf-management-bot/actions/workflows/tests.yml"><img src="https://github.com/RatelXD/ctf-management-bot/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.11 이상"></a>
    <a href="https://discordpy.readthedocs.io/"><img src="https://img.shields.io/badge/discord.py-2.x-5865F2?logo=discord&amp;logoColor=white" alt="discord.py 2.x"></a>
    <a href="https://www.sqlite.org/"><img src="https://img.shields.io/badge/Storage-SQLite-4AA5B5?logo=sqlite&amp;logoColor=white" alt="SQLite 저장"></a>
    <a href="https://github.com/RatelXD/ctf-management-bot/stargazers"><img src="https://img.shields.io/github/stars/RatelXD/ctf-management-bot?style=flat" alt="GitHub stars"></a>
  </p>
</div>

<details>
  <summary><strong>목차 · 필요한 곳으로 바로 이동</strong></summary>

  - [프로젝트 소개](#about-the-project)
  - [처음 설정할 값](#configuration)
  - [설치와 실행](#getting-started)
  - [대회 만들기](#create-event)
  - [문제와 풀이 관리](#usage)
  - [저장과 운영](#operations)
  - [무료 실행 방법](#hosting)
  - [검증](#testing)
  - [기여와 문의](#contributing)
  - [참고한 자료](#acknowledgments)

</details>

<a id="about-the-project"></a>

## 프로젝트 소개

CTF 참가 버튼, 문제별 채널, 참가자별 작업 상태와 풀이 현황을 관리하는 Discord 봇입니다. 관리 권한이 있는 기존 Discord 서버에 초대해 사용할 수 있으며, 내 PC에서 실행할 수 있습니다.

**대회명은 사용자가 `/setup_ctf`에서 정합니다.** 특정 대회나 참가 역할이 코드에 고정되어 있지 않습니다. 아래의 `my-ctf`는 예시이므로 운영할 대회명으로 바꾸세요.

| 참가 관리 | 문제별 협업 | 풀이 현황 |
| --- | --- | --- |
| 버튼 하나로 참가·탈퇴 | 문제 채널과 생성자 기록 | 해결자만 남는 `#dashboard` 현황판 |
| 역할로 카테고리 표시·숨김 | 🔨 푸는 중 · 🆘 도움 요청 | 완료 알림과 🚩 채널명 |
| 재시작 후에도 버튼 유지 | 참여자별 작업 상태 관리 | SQLite로 기록 보존 |

<p align="center">
  <img src="docs/assets/workflow.png" alt="대회 설정 → 참가 버튼 → 문제 추가와 작업 상태 등록 → 풀이 완료" width="100%">
</p>

**기술 구성:** Python 3.11+ · discord.py 2.x · SQLite · Docker Compose(선택)

<p align="right"><a href="#readme-top">맨 위로 ↑</a></p>

<a id="configuration"></a>

## 처음 설정할 값 한눈에 보기

| 사용자가 정할 값 | 입력 위치 | 필수 여부 | 입력 방법 / 예시 |
| --- | --- | --- | --- |
| 봇 이름 | Discord Developer Portal → 애플리케이션 생성 | 필수 | 서버에서 사용할 봇 이름을 자유롭게 지정 |
| 사용할 Discord 서버 | 봇 초대 화면 | 필수 | 본인이 관리하는 서버 선택 |
| 봇 토큰 | `.env` → `DISCORD_TOKEN` | 필수 | Developer Portal의 Bot 메뉴에서 발급한 토큰 |
| Discord 서버 ID | `.env` → `DISCORD_GUILD_ID` | 권장 | 개발자 모드를 켜고 서버 우클릭 → 서버 ID 복사 |
| 대회명 | Discord → `/setup_ctf`의 `name` | 필수 | `my-ctf` → 실제 대회명으로 변경 |
| 시작 시각 | `/setup_ctf`의 `start` | 필수 | `2026-11-01T20:00+09:00` → 실제 시작 시각 |
| 종료 시각 | `/setup_ctf`의 `end` | 필수 | `2026-11-03T20:00+09:00` → 실제 종료 시각 |
| 대회 사이트 주소 | `/setup_ctf`의 `url` | 필수 | `https://example.com` → 실제 대회 URL |
| 데이터 저장 경로 | `.env` → `DATABASE_PATH` | 선택 | 기본값 `data/ctf.sqlite3`를 그대로 사용 가능 |

**직접 만들어 둘 필요가 없는 항목**은 다음과 같습니다. 대회명을 `my-ctf`로 입력했다면:

| 항목 | 만들어지는 이름 / 내용 | 이름을 정하는 방식 |
| --- | --- | --- |
| 참가 역할 | `CTF-my-ctf` | `CTF-` + 대회명 자동 변환값 |
| 비공개 카테고리 | `⚔️my-ctf⚔️` | 입력한 대회명 양 끝에 ⚔️ |
| 참가 버튼 | `my-ctf (for everyone)` | 입력한 대회명으로 자동 생성 |
| 참가 안내 채널 | `#ctf-join` | 고정 이름, 카테고리 밖에 같은 채널이 있으면 재사용 |
| 대회 안내 채널 | `#announcement` | 대회 카테고리 안에 고정 이름으로 생성 |
| 풀이 현황 채널 | `#dashboard` | 대회 카테고리 안에 고정 이름으로 생성 |
| 일반 대화 채널 | `#general` | 참가자 대화와 문제 생성용 |
| 문제 채널 | `/edit_challenge name:`에 입력한 이름 | 참가자가 문제를 추가할 때 지정 |

대회명 자동 변환값은 소문자와 하이픈 형태로 정리됩니다. 예를 들어 `My CTF`는 역할에 `CTF-my-ctf`, 카테고리에 `⚔️My CTF⚔️`으로 반영됩니다. **참가 역할명과 카테고리명을 별도로 지정하는 옵션은 현재 없습니다.** 채널 이름 `ctf-join`, `announcement`, `dashboard`, `general`도 현재 `.env` 설정 항목이 아닙니다.

설정 순서: **① 봇 생성·초대 → ② `.env` 작성·봇 실행 → ③ Discord에서 `/setup_ctf` → ④ 참가 버튼 → ⑤ 문제 추가**

<p align="right"><a href="#readme-top">맨 위로 ↑</a></p>

<a id="getting-started"></a>

## 설치와 실행

### 준비물

| 준비물 | 용도 |
| --- | --- |
| Python 3.11 이상 · Git | 코드 다운로드와 봇 실행 |
| 관리 권한이 있는 Discord 서버 | 봇 초대와 대회 생성 |
| Discord 애플리케이션과 봇 토큰 | Discord API 연결 |

### 1. 봇 생성과 초대

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 **New Application**을 만들고 Bot 메뉴에서 봇 토큰을 발급합니다.
2. Installation 또는 OAuth2 URL Generator에서 **서버 설치(Guild Install)**, `bot`, `applications.commands`를 선택합니다.
3. 봇 권한: **Manage Channels, Manage Roles, View Channels, Send Messages, Embed Links, Read Message History**. Administrator는 필요 없습니다.
4. 초대 링크를 열어 사용할 Discord 서버에 초대합니다.
5. 서버 설정 → 역할에서 **봇 역할을 CTF 참가 역할보다 위로** 올려 둡니다. 새 참가 역할은 봇이 생성합니다. 자동으로 위에 배치되지만, 나중에 순서를 바꾸면 참가 버튼이 실패할 수 있습니다.

Message Content Intent, Server Members Intent 등 privileged intent는 켤 필요가 없습니다. 토큰은 `.env`에만 보관하고 공개 저장소에 올리지 마세요. 기존 사용자 계정 토큰은 사용하지 않습니다.

### 2. Windows에서 실행

Python 3.11 이상과 Git을 설치한 뒤 PowerShell에서 프로젝트를 내려받습니다. 이미 다운로드했다면 해당 폴더에서 다음 설치 단계부터 진행하세요.

```powershell
git clone https://github.com/RatelXD/ctf-management-bot.git
cd ctf-management-bot
```

가상환경을 만들고 설정 파일을 엽니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

`.env`에서 아래 두 값을 본인 값으로 바꾸고 저장합니다. 대회명이나 참가 역할명은 이 파일에 넣지 않습니다.

```dotenv
DISCORD_TOKEN=여기에_발급받은_봇_토큰
DISCORD_GUILD_ID=여기에_Discord_서버_ID
DATABASE_PATH=data/ctf.sqlite3
```

`DISCORD_GUILD_ID`에 서버 ID를 넣으면 그 서버에 명령어를 즉시 등록합니다. 비우면 전역 등록으로 전파에 시간이 걸릴 수 있습니다. 실행 중 `.env`를 수정했다면 봇을 재시작하세요. 전역/서버 등록을 전환하면 예전 등록 명령이 남을 수 있으므로 운영에서는 한 방식을 유지하세요.

```powershell
.\.venv\Scripts\python.exe bot.py
```

Ready 로그가 나오면 Discord에서 아래 설정 명령을 실행합니다. PowerShell 창을 닫거나 PC를 끄면 봇도 꺼집니다. 공개 IP, 포트 포워딩, 웹 도메인은 필요 없습니다.

<p align="right"><a href="#readme-top">맨 위로 ↑</a></p>

<a id="create-event"></a>

## 대회 만들기

서버 관리(Manage Server) 권한이 있는 사람이 **Discord 서버의 텍스트 채널에서** `/setup_ctf`를 선택하고 네 옵션을 입력합니다. 터미널에 입력하는 명령이 아닙니다.

| 옵션 | 넣을 값 | 주의사항 |
| --- | --- | --- |
| `name` | 운영할 대회명 | 참가 역할·카테고리·버튼 이름의 기준이 됨 |
| `start` | 실제 시작 일시 | `연도-월-일T시:분+09:00` 형식. `+09:00`은 한국 시간 |
| `end` | 실제 종료 일시 | 시작보다 늦은 시각. 시간대도 반드시 포함 |
| `url` | 실제 대회 사이트 주소 | `https://` 또는 `http://`로 시작 |

아래는 **형식 확인용 예시**입니다. 대회명·날짜·URL을 모두 실제 값으로 바꿔 입력하세요.

```text
/setup_ctf name:my-ctf start:2026-11-01T20:00+09:00 end:2026-11-03T20:00+09:00 url:https://example.com
```

실행하면 위의 자동 생성 표에 나온 역할·카테고리·채널이 만들어집니다. `#ctf-join`의 카드에는 Start, End, URL과 참가/탈퇴 버튼이 표시됩니다.

**일정·URL 수정:** 같은 대회명으로 `/setup_ctf`를 다시 실행하세요. **새 대회 추가:** 다른 대회명으로 실행하세요. 다른 이름을 넣으면 기존 대회의 이름을 바꾸는 것이 아니라 별도 대회를 생성합니다. 기존 대회명을 바꾸는 전용 명령은 현재 없습니다.

대회를 여러 개 만들면 `#ctf-join`에 대회별 카드와 버튼이 생깁니다. 카테고리 밖의 기존 `#ctf-join`이 있으면 재사용하므로, 그 채널은 일반 참가자에게 보이고 봇이 메시지를 쓸 수 있어야 합니다.

버튼을 누르면 **그 사람에게만 보이는 응답**과 함께 역할을 부여합니다. 다시 누르면 역할을 회수하고 떠났다고 응답합니다. 카테고리와 문제 채널은 참가자에게 보였다가 숨겨집니다. 채널이나 기록을 삭제하지 않으므로 다른 참가자에게 영향이 없습니다. Discord의 Administrator 권한이 있는 사람과 서버 소유자는 권한 우회로 카테고리를 계속 볼 수 있습니다.

<p align="right"><a href="#readme-top">맨 위로 ↑</a></p>

<a id="usage"></a>

## 문제와 풀이 관리

먼저 참가 버튼을 누른 뒤 **해당 대회의 `#general` 또는 `#announcement`에서** 실행합니다.

```text
/edit_challenge name:web-example
/edit_challenge name:example category:web
```

해당 이름의 텍스트 채널과 `Added by @생성자` 카드가 만들어집니다. 이름은 Discord 채널에 맞게 소문자·하이픈으로 정리됩니다. `category:web name:example`은 `web-example` 채널을 만듭니다. 수정할 때 분야를 생략하면 기존 분야를 유지합니다. `description` 옵션은 없습니다. 생성자 기록은 수정해도 유지됩니다. **이미 만들어진 문제 채널 안에서** `/edit_challenge`를 쓰면 그 문제의 이름·분야를 수정합니다. 다른 새 문제를 만들려면 다시 `#general`로 이동하세요. 수정은 생성자와 서버 관리자만 할 수 있습니다.

**문제 채널 안에서** 다음 명령을 실행합니다.

| 명령 | 동작 |
| --- | --- |
| `/update_status status:working` | 내 이름을 🔨 푸는 중으로 표시 |
| `/update_status status:stuck` | 내 이름을 🆘 막힘·도움 필요 SOS로 표시 |
| `/update_status status:stopped` | 내 이름을 작업자 목록에서 제거 |
| `/solve_challenge flag:FLAG{...}` | 실행자를 해결자로 기록, 풀이 완료 알림과 플래그 공개, 채널명 앞에 🚩 |
| `/unsolve_challenge` | 풀이 완료 취소, 🚩 제거, 작업자 목록 초기화 |

여러 사람이 working/stuck 상태를 등록할 수 있습니다. 해결 시 작업자 목록을 비우고 해결자 한 명만 표시합니다. 풀이 취소는 해결자 또는 서버 관리자만 가능합니다. 이미 해결된 문제에 추가 solve나 작업 상태 변경은 허용하지 않습니다.

**플래그 인증은 대회 사이트에서 먼저 해야 합니다.** 봇은 입력된 플래그의 정답 여부를 검증하거나 대회에 자동 제출하지 않습니다. `/solve_challenge`는 팀원 간 완료 기록용입니다. 플래그는 해당 비공개 문제 채널 참가자들에게 공개됩니다.

`#dashboard`는 운영자(서버 관리 또는 Administrator 권한)와 봇만 메시지를 보낼 수 있고 채널 주제에는 명령어 가이드를 넣지 않습니다. 명령어 가이드는 `#announcement`에 유지됩니다. 다음 모양으로 자동 갱신됩니다. 미해결 줄 앞에는 체크박스가 없습니다.

```text
📋 my-ctf — 1 / 3 solved

✅ #🚩-web-solved · solved by @해결자
#web-example · 🔨 @작업자 · 🆘 @도움필요
#pwn-example · 미해결
```

상태판은 보통 5초 안에 반영됩니다. 채널 이름 변경은 Discord의 별도 rate limit에 걸리면 수 분 늦어질 수 있습니다. 상태판과 명령 응답은 이름 변경을 기다리지 않습니다. 상태판·참가 메시지를 지운 경우 다음 상태 변경 또는 봇 재시작 때 다시 생성합니다.

<p align="right"><a href="#readme-top">맨 위로 ↑</a></p>

<a id="operations"></a>

## 저장과 운영

SQLite `data/ctf.sqlite3`에 대회 ID, 채널 ID, 생성자, 작업 상태, 해결자, 플래그, 메시지 ID를 저장합니다. 재시작 후에도 참가 버튼이 동작합니다. **봇 인스턴스는 하나만 실행**하세요. 백업은 봇을 종료한 뒤 `data` 폴더를 복사하면 됩니다. 카테고리를 Discord에서 삭제하면 봇의 해당 대회·문제 기록을 SQLite에서 정리하고 참가 카드도 삭제합니다. 봇이 꺼진 동안 삭제된 경우 재시작 후 확인합니다. 남은 Discord 하위 채널과 참가 역할은 자동 삭제하지 않습니다. 역할·문제 채널의 수동 삭제는 자동 복원하지 않습니다. `/unsolve_challenge`는 기존 채팅의 완료 알림을 지우지 않습니다.

### 기존 설치 업데이트

서버에서 코드를 업데이트하고 서비스를 재시작합니다. 기존 SQLite 파일은 유지하세요.

```sh
cd /root/cert-ctf/ctf-management-bot
git pull --ff-only
systemctl restart ctf-management-bot
journalctl -u ctf-management-bot -n 30 --no-pager
```

재시작 후 기존 카테고리 이름과 `announcement`·`dashboard` 권한이 갱신되고 `general`이 추가됩니다. 기존 메시지와 문제 기록은 유지합니다. 기존 문제의 분야 접두사는 `/edit_challenge name:문제명 category:web`으로 수정하면 적용됩니다. 슬래시 명령도 새 이름으로 다시 동기화됩니다.

Docker를 쓸 수 있는 PC/VM에서는:

```sh
docker compose up -d --build
docker compose logs -f
```

데이터를 호스트의 `./data` 폴더에 보관하고 재부팅 후 자동 재시작하도록 설정했습니다.

<details>
<summary><strong>폴더 구성</strong></summary>

```text
ctf-management-bot/
├── bot.py                      # Discord 명령어 · 버튼 · 상태판
├── core.py                     # 상태 관리 · SQLite 저장
├── .env.example                # 복사해서 사용할 환경 설정 예시
├── compose.yaml                # Docker 실행 설정
├── docs/assets/                # README 배너와 사용 흐름 그림
├── scripts/render_readme_assets.py  # 그림 재생성 도구 (Pillow 필요)
└── tests/                      # 상태 전이 · 명령어 · 버튼 테스트
```

</details>

<p align="right"><a href="#readme-top">맨 위로 ↑</a></p>

<a id="hosting"></a>

## 무료 실행 방법

2026-11-01 공식 문서 확인 기준:

- **가장 간편한 무료 방법: 내 PC에서 실행.** 위 명령으로 실행하면 되고 PC가 켜져 있어야 합니다. 대회 기간에만 켜 두는 방식에 적합합니다.
- **PC를 끄고 계속 실행: Oracle Cloud Always Free VM 등 상시 실행 가능한 VM.** [공식 안내](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)를 확인해 무료 대상 인스턴스를 만들고 이 폴더와 `.env`를 옮긴 뒤 Docker Compose로 실행할 수 있습니다. 계정 가입과 초기 서버 설정이 필요하고, 무료 자원 가용성과 유휴 인스턴스 회수 조건이 있습니다.
- **Render 무료 Web Service:** [공식 제한](https://render.com/docs/free)에 따르면 유휴 중단과 로컬 SQLite 소실이 있습니다. 이 봇은 지속 실행 프로세스와 영속 디스크가 필요하므로 그대로 올릴 배포 대상에 맞지 않습니다. 무료 Background Worker도 제공하지 않습니다.

그 밖의 호스팅을 선택할 때는 일반 Python 프로세스 또는 Docker 컨테이너를 상시 실행하고 데이터 폴더를 유지할 수 있는지 확인하세요.

<p align="right"><a href="#readme-top">맨 위로 ↑</a></p>

<a id="testing"></a>

## 검증

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

실제 토큰 없이 상태 전이, SQLite 재시작 보존, 상태판 분할, 슬래시 명령 등록, 참가 버튼 및 메시지 복구를 검사합니다. 실제 Discord 서버에서는 초대 후 아래 동작을 확인하세요.

1. 일반 계정으로 참가 → 카테고리 보임 → 재클릭으로 숨김 → 재참가
2. `#general`에서 문제 생성 후 Added by 확인
3. 두 계정으로 working/stuck → 둘 다 상태판 표시, stopped → 해당 사람만 사라짐
4. solve → 완료 알림·해결자·🚩, unsolve → ✅·🚩 제거
5. 봇 재시작 후 기존 참가 버튼과 상태판 유지

실제 Discord API 연동은 봇 토큰과 테스트 서버가 있어야 검증할 수 있습니다.

<p align="right"><a href="#readme-top">맨 위로 ↑</a></p>

<a id="contributing"></a>

## 기여와 문의

버그는 [Issues](https://github.com/RatelXD/ctf-management-bot/issues)에 실행 환경과 재현 방법을 함께 남겨 주세요. 기능 제안도 같은 곳에서 받습니다. 코드 변경은 저장소를 Fork한 뒤 브랜치를 만들어 Pull Request로 제안할 수 있습니다.

프로젝트 관리: [@RatelXD](https://github.com/RatelXD) · [저장소](https://github.com/RatelXD/ctf-management-bot)

<a id="acknowledgments"></a>

## 참고한 자료

- [Best-README-Template](https://github.com/othneildrew/Best-README-Template) — 중앙 헤더, 배지, 접이식 목차와 섹션 구성
- [discord.py](https://discordpy.readthedocs.io/) — Discord 봇 라이브러리
- [Shields.io](https://shields.io/) — README 기술 배지

배너와 사용 흐름 그림은 이 프로젝트를 위해 제작했습니다. 배너 속 화면은 기능을 설명하기 위한 예시입니다.

<p align="right"><a href="#readme-top">맨 위로 ↑</a></p>
