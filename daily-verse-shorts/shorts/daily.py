"""매일 실행: 오늘의 구절 고르기 → 영상·썸네일 만들기 → 유튜브 업로드 → 썸네일·재생목록 설정.

  python3 -m shorts.daily            # 업로드까지 (YT_* 환경변수 필요)
  python3 -m shorts.daily --dry-run  # 영상만 만들고 업로드 안 함
"""
import argparse
import datetime as dt
import json
import time
from pathlib import Path
from urllib.parse import quote

from . import youtube as ytm
from .render import ROOT, hook_text, load_cfg, render

KST = dt.timezone(dt.timedelta(hours=9))


def today_kst():
    return dt.datetime.now(KST).date()


def pick_verse(verses, state):
    """아직 안 올린 구절 중 목록 순서상 첫 번째. 한 바퀴 다 돌면 처음부터 다시."""
    recent = [p["verse_id"] for p in sorted(state.get("posted", {}).values(), key=lambda p: p["date"])]
    recent = set(recent[-(len(verses) - 1):]) if len(verses) > 1 else set()
    for v in verses:
        if v["id"] not in recent:
            return v
    return verses[0]


def play_link(url):
    if not url:
        return ""
    ref = quote("utm_source=youtube&utm_medium=shorts&utm_campaign=daily_verse", safe="")
    return url + ("&" if "?" in url else "?") + "referrer=" + ref


def build_metadata(verse, date, cfg):
    yt = cfg["youtube"]
    title = yt["title_template"].format(hook=hook_text(verse["text"], 30), ref=verse["ref"], theme=verse["theme"])
    title = title.replace("<", "").replace(">", "")[:100]
    app = cfg["app"]
    lines = [
        verse["text"],
        f"- {verse['ref']} ({cfg.get('translation_label', '')})",
        "",
        f"📱 {app['name']} — 매일 아침 오늘의 말씀을 받아보세요",
    ]
    if app.get("play_store_url"):
        lines.append(f"▶ Android: {play_link(app['play_store_url'])}")
    if app.get("app_store_url"):
        lines.append(f"▶ iPhone: {app['app_store_url']}")
    lines += ["", " ".join(yt["hashtags"][:-1] + [f"#{verse['theme']}", yt["hashtags"][-1]])]
    tags = yt["tags"] + [verse["theme"], verse["ref"].split()[0]]
    return {
        "snippet": {
            "title": title,
            "description": "\n".join(lines)[:4900],
            "tags": tags,
            "categoryId": yt.get("category_id", "22"),
            "defaultLanguage": yt.get("language", "ko"),
        },
        "status": {
            "privacyStatus": yt.get("privacy", "public"),
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": False,
        },
    }


def upload(yt, files, body):
    from googleapiclient.http import MediaFileUpload

    req = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(files["video"]), mimetype="video/mp4", chunksize=-1, resumable=True),
    )
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


def wait_processed(yt, video_id, timeout=900):
    start = time.time()
    while time.time() - start < timeout:
        items = yt.videos().list(part="processingDetails,status", id=video_id).execute().get("items", [])
        if items:
            st = items[0].get("processingDetails", {}).get("processingStatus")
            if st == "succeeded":
                return True
            if st in ("failed", "terminated"):
                return False
        time.sleep(15)
    return False


def set_thumbnail(yt, video_id, path):
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    try:
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(path), mimetype="image/jpeg")).execute()
        return True
    except HttpError as e:
        # 403: 채널 전화번호 인증 전에는 맞춤 썸네일이 막혀 있음 → 영상 화면이 썸네일로 쓰임
        print(f"[썸네일 설정 실패, 건너뜀] {e.status_code}: {e.reason}")
        return False


def check_private_lock(yt, video_id, body, state, day):
    """심사 전 API 프로젝트는 업로드가 '비공개'로 잠길 수 있다 → 한 번만 주인에게 알림."""
    want = body["status"]["privacyStatus"]
    items = yt.videos().list(part="status", id=video_id).execute().get("items", [])
    got = items[0].get("status", {}).get("privacyStatus") if items else None
    if want == "public" and got == "private":
        if not state.get("private_lock_notified"):
            ytm.notify_owner(
                "유튜브가 자동 업로드 영상을 '비공개'로 잠갔어요",
                "Google Cloud 프로젝트가 아직 YouTube API 심사를 받지 않아서 생기는 제한입니다.\n"
                "docs/SETUP.md 의 '6. YouTube API 심사 신청' 을 진행해 주세요(답변 초안 포함).\n"
                "심사 통과 전까지 영상은 계속 만들어 비공개로 올라가고, 통과 후부터 공개됩니다.",
            )
            state["private_lock_notified"] = True
        state["posted"][day]["locked_private"] = True
    elif got == "public":
        state.pop("private_lock_notified", None)


def ensure_playlist(yt, state, cfg):
    pid = cfg["youtube"].get("playlist_id") or state.get("playlist_id")
    if pid:
        return pid
    res = yt.playlists().insert(part="snippet,status", body={
        "snippet": {"title": "오늘의 말씀 | 매일 성경 한 구절", "description": f"매일 아침 올라오는 오늘의 말씀 ({cfg['app']['name']})"},
        "status": {"privacyStatus": "public"},
    }).execute()
    state["playlist_id"] = res["id"]
    return res["id"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘, 한국 시간)")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()

    cfg = load_cfg()
    verses = json.loads((ROOT / "data/verses.json").read_text(encoding="utf-8"))
    state = ytm.load("state.json", {"posted": {}})
    date = dt.date.fromisoformat(a.date) if a.date else today_kst()

    if date.isoformat() in state["posted"] and not a.dry_run:
        print(f"{date} 은 이미 올렸음: {state['posted'][date.isoformat()]['video_id']}")
        return

    verse = pick_verse(verses, state)
    print(f"[{date}] {verse['ref']} ({verse['theme']}) — {verse['text']}")
    files = render(verse, date, cfg, a.out)
    body = build_metadata(verse, date, cfg)
    Path(a.out, "metadata.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")
    print("제목:", body["snippet"]["title"])

    if a.dry_run or not ytm.has_credentials():
        print("업로드 생략(dry-run 또는 유튜브 키 미설정). 결과물:", a.out)
        return

    yt = ytm.youtube()
    video_id = upload(yt, files, body)
    print("업로드 완료:", f"https://youtube.com/shorts/{video_id}")
    # 업로드는 끝났으니 상태부터 기록 (뒤 단계가 실패해도 같은 날 중복 업로드 방지)
    state["posted"][date.isoformat()] = {
        "date": date.isoformat(), "verse_id": verse["id"], "video_id": video_id,
        "title": body["snippet"]["title"], "theme": verse["theme"], "palette": files["palette"],
    }
    ytm.save("state.json", state)

    if wait_processed(yt, video_id):
        state["posted"][date.isoformat()]["thumbnail"] = set_thumbnail(yt, video_id, files["thumbnail"])
    check_private_lock(yt, video_id, body, state, date.isoformat())
    try:
        pid = ensure_playlist(yt, state, cfg)
        yt.playlistItems().insert(part="snippet", body={
            "snippet": {"playlistId": pid, "position": 0, "resourceId": {"kind": "youtube#video", "videoId": video_id}},
        }).execute()
    except Exception as e:
        print("[재생목록 추가 실패, 건너뜀]", e)
    ytm.save("state.json", state)


if __name__ == "__main__":
    main()
