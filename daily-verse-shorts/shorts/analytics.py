"""매일 실행: 채널·영상 성과를 data/stats/ 에 쌓는다. (주간 검토 때 이 파일들을 보고 전략을 조정)

  data/stats/channel_daily.jsonl  — 날짜별 구독자 수·총 조회수 스냅샷
  data/stats/videos.json          — 올린 영상별 조회수·좋아요·댓글 + 최근 28일 시청 지속률 등
"""
import datetime as dt

from . import youtube as ytm
from .daily import today_kst


def main():
    if not ytm.has_credentials():
        print("유튜브 키 미설정 → 통계 수집 생략")
        return
    yt = ytm.youtube()
    state = ytm.load("state.json", {"posted": {}})
    today = today_kst().isoformat()

    ch = yt.channels().list(part="statistics", mine=True).execute()["items"][0]["statistics"]
    ytm.append_jsonl("stats/channel_daily.jsonl", [{
        "date": today,
        "subscribers": int(ch.get("subscriberCount", 0)),
        "views": int(ch.get("viewCount", 0)),
        "videos": int(ch.get("videoCount", 0)),
    }])

    posted = {p["video_id"]: p for p in state["posted"].values()}
    videos = ytm.load("stats/videos.json", {})
    ids = list(posted)
    for i in range(0, len(ids), 50):
        res = yt.videos().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
        for it in res.get("items", []):
            s = it["statistics"]
            p = posted[it["id"]]
            videos[it["id"]] = {
                **videos.get(it["id"], {}),
                "date": p["date"], "verse_id": p["verse_id"], "theme": p["theme"],
                "palette": p.get("palette"), "title": p["title"],
                "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)), "updated": today,
            }

    # 시청 지속률·구독 전환 (YouTube Analytics, 2~3일 늦게 반영됨)
    try:
        end = dt.date.fromisoformat(today)
        rep = ytm.analytics().reports().query(
            ids="channel==MINE",
            startDate=(end - dt.timedelta(days=28)).isoformat(), endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,shares",
            dimensions="video", sort="-views", maxResults=200,
        ).execute()
        cols = [h["name"] for h in rep.get("columnHeaders", [])]
        for row in rep.get("rows", []):
            r = dict(zip(cols, row))
            vid = r.pop("video")
            if vid in videos:
                videos[vid]["last28d"] = r
    except Exception as e:
        print("[분석 리포트 실패, 건너뜀]", e)

    ytm.save("stats/videos.json", videos)
    print(f"통계 저장: 구독자 {ch.get('subscriberCount')}명, 영상 {len(videos)}개")


if __name__ == "__main__":
    main()
