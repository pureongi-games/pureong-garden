# 처음 한 번만 하는 설정 (약 15~20분)

이 설정만 끝내면 그다음부터는 매일 아침 자동으로 만들어지고 올라갑니다.
막히는 화면이 있으면 캡처해서 Claude에게 보여 주세요.

---

## 1. Google Cloud 프로젝트 만들기

1. <https://console.cloud.google.com> 에 **유튜브 채널을 가진 구글 계정**으로 로그인
2. 위쪽 프로젝트 선택 → **새 프로젝트** → 이름 `daily-verse-shorts` → 만들기
3. 왼쪽 메뉴 **API 및 서비스 → 라이브러리**에서 아래 두 개를 찾아 각각 **사용** 누르기
   - `YouTube Data API v3`
   - `YouTube Analytics API`

## 2. 로그인 화면(OAuth) 설정

1. 왼쪽 메뉴 **Google 인증 플랫폼**(또는 *OAuth 동의 화면*) → **시작하기**
2. 앱 이름: `오늘의 말씀 자동 업로드`, 지원 이메일: 본인 이메일 → 대상: **외부** → 완료
3. **대상(Audience)** 메뉴 → **앱 게시(Publish app)** 를 눌러 상태를 **프로덕션**으로 바꾸기
   > ⚠️ 이걸 안 하면(테스트 상태) 7일마다 연결이 끊겨 업로드가 멈춥니다.
4. **클라이언트** 메뉴 → **클라이언트 만들기**
   - 애플리케이션 유형: **웹 애플리케이션**
   - 승인된 리디렉션 URI 에 정확히 입력: `https://developers.google.com/oauthplayground`
   - 만들기 → 나오는 **클라이언트 ID** 와 **클라이언트 보안 비밀번호** 를 메모장에 복사

## 3. 업로드 권한 토큰 받기 (설치 없이 브라우저에서)

1. <https://developers.google.com/oauthplayground> 접속
2. 오른쪽 위 ⚙️ 톱니바퀴 → **Use your own OAuth credentials** 체크 →
   2번에서 복사한 클라이언트 ID / 비밀번호 붙여넣기 → Close
3. 왼쪽 아래 **Input your own scopes** 칸에 아래 한 줄을 그대로 붙여넣기

   ```
   https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.force-ssl https://www.googleapis.com/auth/yt-analytics.readonly
   ```

4. **Authorize APIs** → 계정 선택 화면에서 **말씀 쇼츠를 올릴 채널**을 고르기
   - "Google에서 확인하지 않은 앱" 경고가 나오면 **고급 → (안전하지 않음)으로 이동 → 허용** (내가 만든 앱이라 괜찮습니다)
5. **Exchange authorization code for tokens** 버튼 → 나오는 **Refresh token** 을 복사

## 4. GitHub 저장소에 키 넣기

저장소 → **Settings → Secrets and variables → Actions → New repository secret** 에서 3개 추가

| 이름 | 값 |
|---|---|
| `YT_CLIENT_ID` | 2번의 클라이언트 ID |
| `YT_CLIENT_SECRET` | 2번의 클라이언트 보안 비밀번호 |
| `YT_REFRESH_TOKEN` | 3번의 Refresh token |

> 이 값들은 채팅창에 붙여넣지 말고 여기(GitHub Secrets)에만 넣어 주세요.

## 5. 유튜브 채널 전화번호 인증 (썸네일용)

<https://www.youtube.com/verify> 에서 전화번호 인증 → 이걸 해야 맞춤 썸네일이 적용됩니다.
(안 해도 업로드는 되고, 영상 화면이 썸네일로 쓰입니다.)

## 6. YouTube API 심사 신청 (영상 '공개'용)

심사를 안 받은 프로젝트는 자동 업로드 영상이 **비공개로 잠길 수 있습니다.**
첫 업로드 후 잠기면 GitHub 이슈로 알림이 오니, 그때 신청해도 됩니다.

- 신청서: <https://support.google.com/youtube/contact/yt_api_form>
- 답변 초안: [`docs/AUDIT_ANSWERS.md`](AUDIT_ANSWERS.md) — 그대로 복사해서 쓰면 됩니다.

---

## 끝! 확인하는 법

저장소 → **Actions → 오늘의 말씀 쇼츠 → Run workflow** 를 누르면 바로 한 편이 올라갑니다.
(먼저 `업로드 없이 영상만 만들어 보기` 를 체크하고 돌리면, 업로드 없이 결과 영상만 내려받아 볼 수 있어요.)
