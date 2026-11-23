"""매일 실행: 새 댓글 처리.

- 스팸(링크·홍보·연락처)        → '검토 대기'로 숨김 (지워지지 않음, 스튜디오에서 되돌릴 수 있음)
- 짧은 인사(아멘, 감사합니다…)  → 따뜻한 답글 자동 작성
- 위기 신호(죽고 싶다 등)       → 상담전화 109 안내 답글 + GitHub 이슈로 주인에게 즉시 알림
- 그 밖의 댓글(질문·기도제목…)  → data/comments/inbox.jsonl 에 모아 두고, 주간 검토 때
                                  Claude가 정성 들인 답글을 data/comments/replies.json 에 써 두면
                                  다음 실행 때 올라감
"""
import hashlib
import re

from . import youtube as ytm
from .render import load_cfg

MAX_REPLIES_PER_RUN = 25

SPAM = re.compile(
    r"https?://|www\.|\.com\b|\.kr\b|텔레그램|카톡|카카오톡|오픈채팅|오픈톡|수익|부업|투자|코인|리딩방|재테크|대출|"
    r"맞구독|구독\s*늘|조회수\s*늘|무료\s*상담|문의\s*주|01[016-9][-\s.]?\d{3,4}[-\s.]?\d{4}",
    re.I,
)
CRISIS = re.compile(r"죽고\s*싶|자살|극단적\s*선택|살기\s*싫|사라지고\s*싶|끝내고\s*싶|자해|살고\s*싶지\s*않")
SIMPLE_WORDS = re.compile(r"아멘|감사|할렐루야|은혜|좋아요|좋네요|축복|사랑합니다|믿습니다|주님|예수님|힘이\s*됩니다|위로")
EMOJI_ONLY = re.compile(r"^[\s\W_]+$")
# 기도제목·아픔·고민은 짧아도 정성 답글 대상
NEEDS_CARE = re.compile(r"기도\s*부탁|기도해\s*주|아프|아파|힘들|수술|병원|투병|슬프|우울|외롭|고민|걱정|불안|돌아가셨|천국\s*가")

SIMPLE_REPLIES = [
    "아멘🙏 오늘 하루도 말씀 안에서 평안하세요.",
    "함께 아멘으로 받습니다. 은혜 가운데 승리하는 하루 되세요 🙏",
    "댓글 감사합니다! 오늘도 주님의 사랑이 가득하길 기도할게요.",
    "아멘! 이 말씀이 오늘 하루의 힘이 되길 바랍니다 🌿",
    "감사합니다 🙏 내일 아침에도 말씀으로 만나요.",
    "할렐루야! 함께 말씀을 나눌 수 있어 기쁩니다.",
    "아멘 🙏 말씀과 함께 평안한 하루 보내세요.",
    "마음 나눠 주셔서 감사해요. 오늘도 주님이 함께하십니다 🌿",
]
CRISIS_REPLY = (
    "많이 힘드시죠. 이렇게 마음을 나눠 주셔서 정말 고맙습니다. "
    "혼자 견디지 마시고 지금 자살예방상담전화 109(24시간, 무료)에 연락해 이야기를 나눠 주세요. "
    "당신의 생명은 무엇보다 소중합니다. 당신을 위해 기도하겠습니다 🙏"
)


def classify(text):
    t = text.strip()
    if CRISIS.search(t):
        return "crisis"
    if SPAM.search(t):
        return "spam"
    if "?" in t or "？" in t:
        return "inbox"
    if NEEDS_CARE.search(t):
        return "inbox"
    core = re.sub(r"[\s\W_]+", "", t)
    if (len(core) <= 25 and SIMPLE_WORDS.search(t)) or (EMOJI_ONLY.match(t) and len(t) <= 12):
        return "simple"
    return "inbox"


def pick_reply(comment_id):
    h = int(hashlib.sha1(comment_id.encode()).hexdigest(), 16)
    return SIMPLE_REPLIES[h % len(SIMPLE_REPLIES)]


def reply(yt, thread_id, text):
    yt.comments().insert(part="snippet", body={"snippet": {"parentId": thread_id, "textOriginal": text}}).execute()


def main():
    if not ytm.has_credentials():
        print("유튜브 키 미설정 → 댓글 처리 생략")
        return
    cfg = load_cfg().get("comments", {})
    yt = ytm.youtube()
    state = ytm.load("state.json", {"posted": {}})
    cstate = ytm.load("comments/state.json", {"handled": []})
    handled_list = cstate["handled"]
    handled = set(handled_list)
    me = ytm.channel_id(yt, state)
    ytm.save("state.json", state)
    sent = 0

    # 1) 주간 검토에서 Claude가 써 둔 답글 올리기
    queue = ytm.load("comments/replies.json", [])
    remaining = []
    for item in queue:
        if sent >= MAX_REPLIES_PER_RUN:
            remaining.append(item)
            continue
        try:
            reply(yt, item["thread_id"], item["text"])
            ytm.append_jsonl("comments/sent.jsonl", [{**item, "kind": "reviewed"}])
            sent += 1
        except Exception as e:
            print("[답글 실패]", item.get("thread_id"), e)
    ytm.save("comments/replies.json", remaining)

    # 2) 새 댓글 처리
    res = yt.commentThreads().list(
        part="snippet", allThreadsRelatedToChannelId=me, maxResults=100, order="time", textFormat="plainText",
    ).execute()
    inbox, stats = [], {"spam": 0, "simple": 0, "crisis": 0, "inbox": 0}
    for th in res.get("items", []):
        tid = th["id"]
        top = th["snippet"]["topLevelComment"]
        sn = top["snippet"]
        if tid in handled or sn.get("authorChannelId", {}).get("value") == me:
            continue
        text = sn.get("textOriginal") or sn.get("textDisplay", "")
        kind = classify(text)
        stats[kind] += 1
        try:
            if kind == "spam" and cfg.get("hide_spam", True):
                yt.comments().setModerationStatus(id=top["id"], moderationStatus="heldForReview").execute()
            elif kind == "crisis":
                reply(yt, tid, CRISIS_REPLY)
                ytm.notify_owner(
                    "⚠️ 도움이 필요해 보이는 댓글이 있어요",
                    f"영상: https://youtube.com/shorts/{sn.get('videoId')}\n\n> {text}\n\n"
                    "자살예방상담전화 109 안내 답글은 자동으로 달았습니다. 직접 한 번 더 살펴봐 주세요.",
                )
            elif kind == "simple" and cfg.get("auto_reply_simple", True) and sent < MAX_REPLIES_PER_RUN:
                reply(yt, tid, pick_reply(tid))
                sent += 1
            elif kind in ("inbox", "simple"):
                inbox.append({"thread_id": tid, "video_id": sn.get("videoId"), "author": sn.get("authorDisplayName"),
                              "text": text, "published": sn.get("publishedAt")})
        except Exception as e:
            print("[댓글 처리 실패]", tid, kind, e)
            continue
        handled.add(tid)
        handled_list.append(tid)

    if inbox:
        ytm.append_jsonl("comments/inbox.jsonl", inbox)
    cstate["handled"] = handled_list[-3000:]  # 오래된 것부터 버림
    ytm.save("comments/state.json", cstate)
    print("댓글 처리:", stats, f"답글 {sent}개")


if __name__ == "__main__":
    main()
