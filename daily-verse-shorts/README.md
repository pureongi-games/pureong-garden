# 오늘의 말씀 쇼츠 자동화

매일 아침 성경 한 구절로 유튜브 쇼츠를 만들어 올리고, 채널을 관리합니다.

## 매일 자동으로 (GitHub Actions, 오전 5:40)
1. `data/verses.json` 에서 오늘의 구절 선택 (개역한글 444구절, 주제가 연달아 겹치지 않게)
2. 1080×1920 영상 + 썸네일 제작 — 배경색·빛·배경음악이 날마다 달라짐 (`shorts/render.py`)
3. 유튜브 업로드 → 썸네일 설정 → 재생목록 추가 (`shorts/daily.py`)
4. 댓글 처리: 스팸 숨김, 짧은 인사엔 답글, 위기 댓글엔 109 안내 + 주인에게 알림 (`shorts/comments.py`)
5. 조회수·시청 지속률·구독자 수집 (`shorts/analytics.py`)

## 매주 자동으로 (Claude)
성과를 보고 다음 구절 순서·제목 방식을 조정하고, 기도제목·질문 댓글에 답글을 쓰고,
`reports/` 에 주간 리포트를 남깁니다. → [`docs/WEEKLY_REVIEW.md`](docs/WEEKLY_REVIEW.md)

## 처음 설정
[`docs/SETUP.md`](docs/SETUP.md) — 한 번만, 약 15~20분.

## 바꾸고 싶을 때
- 앱 이름·링크·문구: `config.json`
- 앱 아이콘: `assets/app_icon.png` (정사각형 PNG)
- 미리보기: `python3 -m shorts.daily --dry-run --date 2026-12-01` → `out/` 폴더

## 출처
성경 본문: 개역한글(1961, 저작권 만료) — [crizin/bible-db](https://github.com/crizin/bible-db) 데이터셋에서 그대로 가져옴.
배경음악: 코드로 직접 합성(저작권 문제 없음). 글꼴: Noto Serif/Sans CJK (SIL OFL).
