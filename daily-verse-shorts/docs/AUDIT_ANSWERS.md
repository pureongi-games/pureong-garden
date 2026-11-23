# YouTube API 심사 신청서 답변 초안

신청서(영어): <https://support.google.com/youtube/contact/yt_api_form>
`[대괄호]` 부분만 채워서 복사해 넣으세요. 신청서 항목은 바뀔 수 있으니, 없는 항목은 건너뛰면 됩니다.

---

**Organization / developer name:** [앱 개발자 이름 또는 회사명]

**Google Cloud project number:** [Google Cloud 콘솔 첫 화면 '프로젝트 번호']

**API client name:** Daily Verse Shorts (internal automation)

**Website / app link:** [플레이스토어 또는 앱스토어 링크]

**Which API services do you use?** YouTube Data API v3, YouTube Analytics API

**Describe your API client and how it uses YouTube API Services:**

> This is a private, internal automation tool used only by the owner of a single YouTube channel
> ([채널 이름], [채널 URL]). Once a day it renders a short vertical video showing one Bible verse
> (Korean Revised Version 1961, public domain) and uploads it to the owner's own channel with
> `videos.insert`, sets the custom thumbnail with `thumbnails.set`, and adds it to the channel's own
> playlist. It reads the channel's own statistics (`channels.list`, `videos.list`, YouTube Analytics
> `reports.query`) to decide which topics to post next, and it manages comments on the channel's own
> videos (`commentThreads.list`, `comments.insert` for replies, `comments.setModerationStatus` to hold spam).
>
> There are no other users: the tool runs as a scheduled GitHub Actions job with the channel owner's
> own OAuth credentials. It does not access any other channel's data, does not store YouTube data beyond
> the channel's own aggregate statistics, and does not display YouTube data to third parties.

**Expected daily quota usage:** About 3,000 units/day (1 upload, 1 thumbnail, 1 playlist insert, up to
25 comment replies, a few moderation calls and list calls). The default 10,000 units is sufficient.

**Why do you need the audit?** Videos uploaded by our API project are restricted to private. We need
uploads to be public on our own channel.

---

> 신청서에서 화면 녹화(screencast)나 사용 화면 설명을 요구하면 Claude에게 말해 주세요.
> 자동 업로드가 돌아가는 모습을 정리해서 보여 줄 자료를 만들어 드립니다.
