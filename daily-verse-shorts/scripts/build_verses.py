"""말씀 목록(data/verses.json) 생성기 — 개발용, 매일 실행에는 필요 없음.

구절 '위치'만 여기서 고르고, 본문은 개역한글(1961, 퍼블릭 도메인) 데이터셋에서 그대로 가져온다.
데이터: https://github.com/crizin/bible-db (bible.sqlite, source='krv')

  python3 scripts/build_verses.py path/to/bible.sqlite
"""
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

MAX_CHARS = 115  # 쇼츠 한 화면에 편하게 읽히는 길이

REFS = {
    "위로": """
        PSA 23:1  PSA 23:4  PSA 34:18  PSA 46:1  PSA 55:22  PSA 147:3  PSA 30:5  PSA 42:11
        PSA 56:3  PSA 73:26  PSA 94:19  PSA 116:7  PSA 34:4  PSA 9:9  PSA 86:7  PSA 119:50
        PSA 119:71  PSA 126:5  PSA 138:7  ISA 40:1  ISA 41:13  ISA 43:2  ISA 46:4  ISA 49:15
        ISA 66:13  LAM 3:22-23  MAT 5:4  MAT 11:28  JHN 14:1  JHN 14:18  JHN 16:33  2CO 4:16
        2CO 12:9  1PE 5:7  REV 21:4  ISA 42:3  ISA 54:10  PSA 31:24  ISA 35:4
    """,
    "평안": """
        PSA 4:8  PSA 29:11  PSA 46:10  PSA 62:1  PSA 62:5  PSA 91:1  PSA 119:165  PSA 127:2
        PRO 14:30  ISA 26:3    ISA 32:17  JHN 14:27  ROM 5:1  ROM 8:6  ROM 15:13
        PHP 4:6-7  COL 3:15  2TH 3:16  NUM 6:24-26  MAT 11:29    PSA 131:2
    """,
    "사랑": """
        JHN 3:16  JHN 13:34  JHN 15:9  JHN 15:12  JHN 15:13  ROM 5:8  ROM 8:38-39  ROM 12:10
        ROM 13:10  1CO 13:4  1CO 13:7  1CO 13:13  1CO 16:14  EPH 4:32  COL 3:14  1PE 4:8
        1JN 3:1  1JN 3:18  1JN 4:7  1JN 4:10  1JN 4:11  1JN 4:16  1JN 4:18  1JN 4:19
        JER 31:3  ZEP 3:17  ISA 43:4  DEU 6:5  MAT 22:39  LUK 6:31  PRO 10:12  PRO 17:17
        DEU 7:9  PSA 36:7  ISA 49:16
    """,
    "소망": """
        JER 29:11  ROM 8:18  ROM 8:28  ROM 15:4  PSA 39:7  PSA 42:5  PSA 62:5  PSA 71:5
        PSA 130:5  PSA 146:5  PRO 23:18  ISA 40:31  ISA 43:18-19  LAM 3:25  LAM 3:26  MIC 7:7
        HEB 10:23  1PE 1:3  REV 21:5  JOB 8:7  JOB 23:10  ROM 5:3-4  ROM 5:5  ROM 12:12
        2CO 4:17  2CO 4:18  PHP 1:6  PHP 3:13-14  HEB 6:19  ISA 60:1  HAG 2:9  PSA 27:13
    """,
    "믿음": """
        HEB 11:1  HEB 11:6  MRK 9:23  MRK 11:24  MAT 17:20  MAT 21:22  ROM 10:17  ROM 1:16
        2CO 5:7  GAL 2:20  EPH 2:8  JAS 1:6  1JN 5:4  JHN 11:25  JHN 20:29  JHN 1:12
        ACT 16:31    MRK 5:36  LUK 1:37  LUK 1:45  1PE 1:8  PRO 3:5-6  PSA 37:5
        PSA 56:4  PSA 112:7  JHN 14:6  ROM 10:10  HEB 12:2  1TI 6:12  2TI 4:7
    """,
    "감사": """
        1TH 5:16-18  PSA 100:4  PSA 107:1  PSA 118:1  PSA 136:1  PSA 103:2  PSA 9:1  PSA 92:1
        1CH 16:34  COL 3:17  COL 4:2  EPH 5:20  PHP 4:11  1TI 6:6  2CO 9:15  PSA 50:23
        PSA 69:30  PSA 95:2  PSA 116:12  PSA 118:24  HAB 3:17-18  1CO 15:57  JAS 1:17
    """,
    "기도": """
        JER 33:3  JER 29:12-13  MAT 7:7  MAT 6:6  MAT 18:20  MAT 26:41  LUK 11:9  
        JHN 14:13-14  JHN 16:24  ROM 8:26  ROM 12:12  EPH 6:18      JAS 5:16
        JAS 1:5  1JN 5:14  PSA 145:18  PSA 50:15  PSA 5:3  PSA 141:2  ISA 65:24  2CH 7:14
        PSA 66:20  MRK 11:25  JAS 4:8
    """,
    "인도하심": """
        PSA 23:2  PSA 23:3  PSA 32:8  PSA 37:23-24  PSA 48:14  PSA 73:24  PSA 119:105  PSA 139:9-10
        PSA 143:8  PSA 143:10  PSA 16:11  PSA 25:4-5  PSA 31:3  PRO 16:3  PRO 16:9  PRO 19:21
        PRO 20:24  ISA 30:21  ISA 48:17  ISA 58:11  JER 10:23  GEN 28:15  EXO 33:14  DEU 31:8
        JHN 10:27  JHN 8:12  ISA 42:16  PSA 121:7-8  PSA 121:3  PSA 121:1-2
    """,
    "용기": """
        JOS 1:9  DEU 31:6  ISA 41:10  PSA 27:1  PSA 27:14  PSA 118:6  PSA 18:2  PSA 28:7
          ISA 12:2  EXO 14:14  1CH 16:11  2TI 1:7  EPH 6:10  PHP 4:13  ROM 8:31
        ROM 8:37  HEB 13:6    ZEC 4:6    ISA 40:29  ISA 40:28  NAM 1:7
        PSA 3:3  2SA 22:33  HAB 3:19    2CH 20:15
    """,
    "지혜": """
        PRO 1:7  PRO 9:10  PRO 4:23  PRO 3:13  PRO 2:6  PRO 15:1  PRO 16:24  PRO 16:32
        PRO 17:22  PRO 18:10  PRO 12:25  PRO 15:13  PRO 22:6  PRO 27:17  PRO 3:27  PRO 11:25
        PRO 24:16  PRO 28:13  PRO 31:30  PRO 4:18  ECC 3:1  ECC 3:11  ECC 4:9  ECC 12:1
        ECC 12:13  PSA 90:12  PSA 111:10  JAS 1:19  JAS 1:22  JAS 3:17  COL 3:23  MIC 6:8
        1SA 16:7  PRO 8:17  PRO 13:20  PRO 14:29
    """,
    "은혜": """
        EPH 2:10  2CO 5:17  ROM 3:24  ROM 6:23  ROM 8:1  TIT 3:5  1JN 1:9  ISA 1:18
        ISA 43:25  ISA 44:22  ISA 53:5  PSA 103:8  PSA 103:12  PSA 86:5  PSA 51:10  PSA 32:1
        JHN 1:16  JHN 10:11  JHN 10:10  MRK 10:45  LUK 19:10  1CO 15:10  2CO 8:9  HEB 4:16
        ACT 4:12  JHN 3:17  JHN 6:35  JHN 6:37  JHN 15:5  JHN 15:16  PSA 84:11  NUM 23:19
          PSA 68:19  2CO 9:8  PHP 4:19
    """,
    "기쁨": """
        PHP 4:4    PSA 16:11  PSA 30:11  PSA 37:4  PSA 126:3  PSA 34:8  PSA 63:3
        PSA 90:14  PSA 118:24  JHN 15:11  JHN 16:22  ROM 12:15  ROM 14:17  GAL 5:22-23  1PE 1:8
        ISA 61:10  ISA 12:3  HAB 3:18  PSA 4:7  PRO 17:22  LUK 2:10  LUK 15:7  PSA 5:11
    """,
    "찬양": """
        PSA 150:6  PSA 103:1  PSA 34:1  PSA 34:3  PSA 96:1  PSA 95:1  PSA 100:1-2  PSA 104:33
        PSA 113:3  PSA 117:1-2  PSA 145:3  PSA 146:2  PSA 8:1  PSA 19:1  PSA 63:4  PSA 59:16
        PSA 89:1  PSA 92:4  PSA 147:1  REV 4:11  ISA 6:3  EXO 15:2  1CH 29:11  PSA 29:2
        PSA 57:9  PSA 86:12  JHN 4:24  ROM 11:36  ROM 12:1  HEB 13:15  PSA 139:14  REV 1:8
    """,
    "말씀": """
        PSA 119:105  PSA 119:11  PSA 119:103  PSA 119:130  PSA 119:9  PSA 119:18  PSA 19:7  PSA 1:1-2
        PSA 1:3  ISA 40:8  ISA 55:11  MAT 4:4  MAT 24:35  JHN 1:1  JHN 8:31-32  JHN 6:63
        2TI 3:16  HEB 4:12  1PE 1:24-25  JOS 1:8  DEU 8:3  JER 15:16  LUK 11:28  COL 3:16
          PRO 30:5  PSA 18:30  PSA 33:4  ROM 15:4  JHN 15:7
    """,
    "섬김": """
        MAT 5:14  MAT 5:16  MAT 5:9  MAT 5:7  MAT 5:8  MAT 5:3  MAT 5:6  MAT 6:33
        MAT 6:34  MAT 7:12  MAT 25:40  MAT 28:20  MRK 16:15  ACT 1:8  ACT 20:35  ROM 12:2
        ROM 12:21  GAL 5:13  GAL 6:2  GAL 6:9  GAL 6:10  EPH 4:2  EPH 4:29  PHP 2:3
        PHP 2:4  COL 3:2  COL 3:12  COL 3:13  1TH 5:11  HEB 10:24  HEB 13:16  1PE 4:10
        JAS 4:10  1PE 5:6  LUK 9:23  LUK 16:10  1CO 10:31  1CO 3:16  JHN 13:35  3JN 1:2
        PSA 133:1  PSA 37:3  JOS 24:15  RUT 1:16  MAT 5:44  LUK 6:36  LUK 6:38  1TI 4:12
    """,
}


def parse_ref(tok):
    m = re.fullmatch(r"([1-3]?[A-Z]{2,3}) (\d+):(\d+)(?:-(\d+))?", tok)
    if not m:
        return None
    book, ch, v1, v2 = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    return book, ch, v1, int(v2) if v2 else v1


def main(db_path):
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    books = {code: (num, name) for num, code, name in c.execute("select book, code, name_kr from books")}
    seen, out, problems = set(), [], []
    for theme, block in REFS.items():
        toks = re.findall(r"[1-3]?[A-Z]{2,3}(?: \d+:\d+(?:-\d+)?)?", block)
        for tok in toks:
            r = parse_ref(tok)
            if not r:
                continue
            book, ch, v1, v2 = r
            key = (book, ch, v1, v2)
            if key in seen:
                continue
            num, name = books[book]
            rows = c.execute(
                "select canon_verse, text from verses where source='krv' and book=? and canon_chapter=? "
                "and canon_verse between ? and ? order by canon_verse",
                (num, ch, v1, v2),
            ).fetchall()
            if len(rows) != v2 - v1 + 1:
                problems.append(f"{tok}: 본문 없음/누락")
                continue
            text = " ".join(t.strip() for _, t in rows)
            text = re.sub(r"\s+", " ", text)
            if len(text) > MAX_CHARS:
                problems.append(f"{tok}: 너무 김({len(text)}자)")
                continue
            seen.add(key)
            vref = f"{v1}" if v1 == v2 else f"{v1}-{v2}"
            out.append({
                "id": f"{book}.{ch}.{vref}",
                "ref": f"{name} {ch}:{vref}",
                "theme": theme,
                "text": text,
            })

    # 같은 주제가 연달아 나오지 않도록 주제를 번갈아 섞는다(고정 시드 → 매번 같은 순서).
    rng = random.Random(2026)
    pools = {}
    for v in out:
        pools.setdefault(v["theme"], []).append(v)
    for p in pools.values():
        rng.shuffle(p)
    ordered, last = [], None
    while any(pools.values()):
        cands = sorted((t for t, p in pools.items() if p and t != last), key=lambda t: -len(pools[t]))
        if not cands:
            cands = [t for t, p in pools.items() if p]
        pick = cands[0] if rng.random() < 0.6 or len(cands) == 1 else rng.choice(cands[:4])
        ordered.append(pools[pick].pop())
        last = pick

    # 처음 2주는 많이 검색되는 대표 구절로 시작 (검색 유입·첫인상)
    featured = ["JHN.3.16", "PSA.23.1", "ISA.41.10", "PHP.4.13", "JER.29.11", "MAT.11.28", "ROM.8.28",
                "PRO.3.5-6", "ISA.40.31", "1TH.5.16-18", "JOS.1.9", "PSA.46.1", "1CO.13.4", "PHP.4.6-7"]
    by_id = {v["id"]: v for v in ordered}
    head = [by_id[i] for i in featured if i in by_id]
    ordered = head + [v for v in ordered if v["id"] not in set(featured)]

    Path("data/verses.json").write_text(json.dumps(ordered, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(ordered)}개 구절 저장 → data/verses.json")
    for p in problems:
        print("  제외:", p)


if __name__ == "__main__":
    main(sys.argv[1])
