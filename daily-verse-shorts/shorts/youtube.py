"""YouTube API 연결 + 저장소 안 상태 파일 도우미."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def has_credentials():
    return all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def _creds():
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def youtube():
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=_creds(), cache_discovery=False)


def analytics():
    from googleapiclient.discovery import build

    return build("youtubeAnalytics", "v2", credentials=_creds(), cache_discovery=False)


def load(name, default):
    p = DATA / name
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def save(name, obj):
    p = DATA / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def append_jsonl(name, rows):
    p = DATA / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def channel_id(yt, state):
    if not state.get("channel_id"):
        res = yt.channels().list(part="id", mine=True).execute()
        state["channel_id"] = res["items"][0]["id"]
    return state["channel_id"]


def notify_owner(title, body):
    """급한 일은 GitHub 이슈로 알린다(사용자에게 이메일 알림이 간다). Actions 안에서만 동작."""
    import urllib.request

    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("[알림 생략: GitHub 밖에서 실행 중]", title)
        return
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=json.dumps({"title": title, "body": body}).encode(),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:  # 알림 실패가 전체 작업을 멈추지 않게
        print("[알림 실패]", e)
