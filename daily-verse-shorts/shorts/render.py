"""오늘의 말씀 쇼츠(1080x1920 mp4) + 썸네일(jpg) 렌더러.

날짜를 시드로 배경 색·빛 알갱이·배경음악이 매일 달라진다.
단독 실행(미리보기):
  python3 -m shorts.render --date 2026-11-23 --index 0 --out out/
"""
import argparse
import datetime as dt
import json
import math
import random
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
FONT_DIR = Path("/usr/share/fonts/opentype/noto")
SERIF = FONT_DIR / "NotoSerifCJK-Regular.ttc"
SERIF_BOLD = FONT_DIR / "NotoSerifCJK-Bold.ttc"
SANS = FONT_DIR / "NotoSansCJK-Regular.ttc"
SANS_BOLD = FONT_DIR / "NotoSansCJK-Bold.ttc"
KR = 1  # .ttc 안 한국어 글꼴 인덱스
WEEKDAY = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "주일"]

# 쇼츠 UI(오른쪽 버튼·아래 제목)에 가리지 않는 글자 영역
TEXT_LEFT, TEXT_RIGHT = 100, 900
TEXT_MAX_W = TEXT_RIGHT - TEXT_LEFT

# (위, 가운데, 아래, 빛 색) — 흰 글씨가 잘 읽히도록 모두 어두운 계열
PALETTES = [
    ("새벽", (16, 24, 48), (58, 72, 118), (226, 160, 120), (255, 214, 170)),
    ("숲", (10, 28, 26), (30, 74, 66), (196, 178, 112), (240, 226, 160)),
    ("바다", (8, 22, 46), (22, 70, 112), (96, 170, 190), (190, 236, 240)),
    ("노을", (34, 16, 44), (102, 52, 96), (232, 136, 110), (255, 190, 150)),
    ("밤하늘", (6, 8, 22), (22, 26, 64), (60, 62, 120), (200, 200, 255)),
    ("황금빛", (40, 22, 14), (110, 58, 30), (230, 170, 80), (255, 220, 150)),
]

END_BREAK = set("다라요냐꼬뇨까,")        # 문장이 끝나는 곳: 가장 좋은 줄바꿈 위치
SOFT_BREAK = set("니고며나면되사서여어아도")  # 연결 어미: 괜찮은 위치


def font(path, size):
    return ImageFont.truetype(str(path), size, index=KR)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ---------------- 줄바꿈 ----------------
def break_lines(text, fnt, max_w):
    """한국어 어절 단위 균형 줄바꿈. 연결 어미(…니, …고, …며) 뒤에서 끊기를 선호."""
    words = text.split()
    n = len(words)
    widths = {}

    def line_w(i, j):
        if (i, j) not in widths:
            widths[(i, j)] = fnt.getlength(" ".join(words[i:j]))
        return widths[(i, j)]

    INF = float("inf")
    best = [INF] * (n + 1)
    prev = [0] * (n + 1)
    best[0] = 0.0
    target = max_w * 0.82
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            w = line_w(i, j)
            if w > max_w:
                break
            is_last = j == n
            slack = max(0.0, target - w) / max_w
            cost = 0.0 if is_last and w > max_w * 0.35 else (slack ** 2) * 100
            if w > target:
                cost += ((w - target) / max_w) ** 2 * 60
            if not is_last:
                last_ch = words[j - 1][-1]
                cost += 0 if last_ch in END_BREAK else 5 if last_ch in SOFT_BREAK else 22
            if is_last and j - i == 1 and n > 2:
                cost += 40  # 마지막 줄 한 어절만 남는 것 방지
            cost += 2  # 줄 수가 쓸데없이 늘지 않게
            if best[i] + cost < best[j]:
                best[j] = best[i] + cost
                prev[j] = i
    if best[n] == INF:
        return None, INF
    lines, j = [], n
    while j > 0:
        i = prev[j]
        lines.append(" ".join(words[i:j]))
        j = i
    return lines[::-1], best[n]


def fit_text(text, path, sizes, max_w, max_h, leading):
    """글자 크기와 줄바꿈을 함께 고른다: 큰 글씨를 선호하되, 어색한 줄바꿈이면 한두 단계 줄인다."""
    sizes = list(sizes)
    best = None
    for size in sizes:
        f = font(path, size)
        lines, cost = break_lines(text, f, max_w)
        if not lines or len(lines) * size * leading > max_h:
            continue
        # 74px 이상은 "조금 더 큼" 정도의 가벼운 가산점, 그 아래로 줄어드는 건 크게 감점
        soft = min(sizes[0] - size, max(sizes[0] - 74, 0))
        score = cost + soft * 1.0 + max(0, min(74, sizes[0]) - size) * 3.0
        if best is None or score < best[0]:
            best = (score, f, size, lines)
    if best:
        return best[1], best[2], best[3]
    f = font(path, sizes[-1])
    return f, sizes[-1], break_lines(text, f, max_w)[0] or [text]


def hook_text(text, limit=28):
    """제목·썸네일용 짧은 문구: 앞에서부터 어절 경계로 limit 글자까지."""
    if len(text) <= limit:
        return text.rstrip(",")
    words, out = text.split(), ""
    for w in words:
        nxt = (out + " " + w).strip()
        if len(nxt) > limit:
            break
        out = nxt
        if len(out) >= limit * 0.6 and w[-1] in "니라다요,":
            break
    out = out.rstrip(",")
    return out if out == text.rstrip(",") else out + "…"


# ---------------- 그림 재료 ----------------
def make_background(pal, seed):
    _, top, mid, low, _ = pal
    y = np.linspace(0, 1, H)[:, None]
    split = 0.58 + (seed % 7) * 0.01
    k1 = np.clip(y / split, 0, 1)
    k2 = np.clip((y - split) / (1 - split), 0, 1) ** 1.4
    col = np.array(top) * (1 - k1) + np.array(mid) * k1
    col = col * (1 - k2) + np.array(low) * k2
    img = np.repeat(col[:, None, :], W, axis=1)
    img += np.random.default_rng(seed).normal(0, 1.6, img.shape)  # 띠 현상 방지
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")


def make_glow(radius, color, strength):
    size = radius * 2
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.sqrt((xx - radius) ** 2 + (yy - radius) ** 2) / radius
    a = np.clip(1 - d, 0, 1) ** 2.2 * 255 * strength
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = a.astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def with_alpha(img, k):
    if k >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * k)))
    return out


class Particles:
    def __init__(self, seed, color, n):
        rng = random.Random(seed)
        self.items = []
        for _ in range(n):
            r = rng.choice([5, 6, 8, 10, 14])
            self.items.append(dict(
                x=rng.uniform(0, W), y=rng.uniform(0, H),
                vy=rng.uniform(8, 26), vx=rng.uniform(-4, 4),
                phase=rng.uniform(0, 6.28), speed=rng.uniform(0.6, 1.6),
                sprite=make_glow(r, color, rng.uniform(0.35, 0.8)),
            ))

    def draw(self, frame, t):
        for p in self.items:
            x = (p["x"] + p["vx"] * t + 14 * math.sin(t * 0.5 + p["phase"])) % W
            y = (p["y"] - p["vy"] * t) % H
            tw = 0.55 + 0.45 * math.sin(t * p["speed"] + p["phase"])
            s = with_alpha(p["sprite"], tw)
            frame.alpha_composite(s, (int(x) - s.width // 2, int(y) - s.height // 2))


def text_layer(text, fnt, fill, shadow=0.55, spacing=0):
    bbox = fnt.getbbox(text)
    w = int(fnt.getlength(text) + spacing * max(len(text) - 1, 0)) + 40
    h = bbox[3] + 40
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if spacing:
        x = 20
        for ch in text:
            d.text((x, 20), ch, font=fnt, fill=fill)
            x += fnt.getlength(ch) + spacing
    else:
        d.text((20, 20), text, font=fnt, fill=fill)
    if shadow:
        sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        sh.putalpha(layer.getchannel("A").point(lambda v: int(v * shadow)))
        sh = sh.filter(ImageFilter.GaussianBlur(9))
        out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        out.alpha_composite(sh, (0, 4))
        out.alpha_composite(layer)
        layer = out
    return layer


def app_icon(cfg, size):
    """앱 아이콘(동그랗게) — 파일이 없으면 십자가 아이콘을 그린다."""
    path = ROOT / cfg["app"].get("icon", "")
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    if path.is_file():
        icon = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        out.paste(icon, (0, 0), mask)
        return out
    d = ImageDraw.Draw(out)
    d.ellipse((0, 0, size - 1, size - 1), fill=(255, 250, 240, 255))
    c, navy, s = size // 2, (70, 84, 130), size / 140
    d.rounded_rectangle((c - 7 * s, c - 44 * s, c + 7 * s, c + 44 * s), int(4 * s), fill=navy)
    d.rounded_rectangle((c - 30 * s, c - 22 * s, c + 30 * s, c - 8 * s), int(4 * s), fill=navy)
    return out


# ---------------- 배경음악(합성 앰비언트, 저작권 걱정 없음) ----------------
PROGRESSIONS = [
    [[0, 7, 16, 19], [-3, 4, 12, 16], [-7, 0, 9, 16], [-5, 2, 11, 14]],   # I vi IV V
    [[0, 7, 16, 19], [-7, 0, 9, 16], [-3, 4, 12, 16], [-5, 2, 11, 14]],   # I IV vi V
    [[-7, 0, 9, 16], [0, 7, 16, 19], [-5, 2, 11, 14], [-3, 4, 12, 16]],   # IV I V vi
]


def make_music(path, seconds, seed, sr=44100):
    rng = random.Random(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    base = 48 + rng.choice([-3, -2, 0, 2, 3, 5])
    hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    prog = rng.choice(PROGRESSIONS)
    seg = seconds / len(prog)
    for i, ch in enumerate(prog):
        start, end = i * seg - 1.0, (i + 1) * seg + 1.0
        env = np.clip((t - start) / 1.8, 0, 1) * np.clip((end - t) / 1.8, 0, 1)
        for off in ch:
            f = hz(base + off)
            for det in (-0.6, 0.6):
                out += env * np.sin(2 * np.pi * (f + det) * t) * 0.05
            out += env * np.sin(2 * np.pi * 2 * f * t) * 0.008
    pent = [0, 2, 4, 7, 9, 12]
    for k in np.arange(1.5, seconds - 2, rng.uniform(1.2, 1.7)):
        m = base + 24 + rng.choice(pent)
        st, ln = int(k * sr), int(2.5 * sr)
        tt = np.arange(min(ln, n - st)) / sr
        out[st:st + len(tt)] += np.sin(2 * np.pi * hz(m) * tt) * np.exp(-tt * 2.2) * 0.07
    ir_len = int(2.2 * sr)
    ir = np.random.default_rng(seed).normal(0, 1, ir_len) * np.exp(-np.arange(ir_len) / sr * 2.6)
    ir /= np.abs(ir).sum() / 6
    nfft = 1 << (n + ir_len - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(out, nfft) * np.fft.rfft(ir, nfft), nfft)[:n]
    mix = (out * 0.7 + wet * 0.35) * np.clip(t / 1.0, 0, 1) * np.clip((seconds - t) / 1.8, 0, 1)
    mix /= max(np.abs(mix).max(), 1e-9) / 0.5
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.stack([pcm, pcm], axis=1).tobytes())


# ---------------- 썸네일 ----------------
def render_thumbnail(verse, date, cfg, pal, seed, out_path):
    img = make_background(pal, seed)
    glow = make_glow(620, pal[4], 0.7)
    img.alpha_composite(glow, (W // 2 - 620, 1420 - 620))
    Particles(seed, (255, 240, 210), 30).draw(img, 3.0)

    label = text_layer("오늘의 말씀", font(SANS_BOLD, 60), (255, 230, 196), spacing=12)
    img.alpha_composite(label, (W // 2 - label.width // 2, 250))
    d = ImageDraw.Draw(img)
    d.rectangle((W // 2 - 60, 362, W // 2 + 60, 366), fill=(255, 226, 190, 220))
    dl = text_layer(f"{date.month}월 {date.day}일 {WEEKDAY[date.weekday()]}", font(SANS, 44), (225, 230, 248))
    img.alpha_composite(dl, (W // 2 - dl.width // 2, 385))

    hook = hook_text(verse["text"], 34)
    f, size, lines = fit_text(hook, SERIF_BOLD, range(112, 72, -4), 920, 660, 1.45)
    lh = int(size * 1.45)
    top = 930 - (lh * len(lines)) // 2
    for i, line in enumerate(lines):
        tl = text_layer(line, f, (255, 255, 255), shadow=0.7)
        img.alpha_composite(tl, (W // 2 - tl.width // 2, top + i * lh))
    ref = text_layer(verse["ref"], font(SERIF_BOLD, 58), (255, 222, 180))
    img.alpha_composite(ref, (W // 2 - ref.width // 2, top + lh * len(lines) + 40))

    img.convert("RGB").save(out_path, "JPEG", quality=88, optimize=True)
    return out_path


# ---------------- 영상 ----------------
def render(verse, date, cfg, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = date.toordinal()
    pal = PALETTES[seed % len(PALETTES)]  # 날마다 바뀜, 연속으로 같은 색 없음
    bg = make_background(pal, seed)
    glow = make_glow(520, pal[4], 0.55)
    parts = Particles(seed, (255, 240, 210), 40 + seed % 12)

    label = text_layer("오늘의 말씀", font(SANS_BOLD, 40), (255, 236, 210), spacing=10)
    date_l = text_layer(f"{date.month}월 {date.day}일 {WEEKDAY[date.weekday()]}", font(SANS, 34), (220, 226, 245))
    rule = Image.new("RGBA", (90, 3), (255, 226, 190, 200))

    vf, vsize, lines = fit_text(verse["text"], SERIF, range(86, 56, -2), TEXT_MAX_W, 920, 1.68)
    line_layers = [text_layer(l, vf, (255, 255, 255)) for l in lines]
    line_h = int(vsize * 1.68)
    block_h = line_h * len(lines)
    verse_top = 950 - block_h // 2 - 30
    ref_l = text_layer(verse["ref"], font(SERIF_BOLD, 44), (255, 222, 180))
    ref_y = verse_top + block_h + 46
    tr_l = text_layer(cfg.get("translation_label", ""), font(SANS, 28), (205, 210, 230))

    end = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    end.alpha_composite(make_glow(150, (255, 230, 190), 0.9), (W // 2 - 150, 560))
    end.alpha_composite(app_icon(cfg, 140), (W // 2 - 70, 640))
    rows = [(cfg["app"]["name"], font(SANS_BOLD, 64), (255, 255, 255), 900)]
    for k, line in enumerate(cfg["app"].get("tagline", [])):
        rows.append((line, font(SANS, 42), (232, 236, 250), 1010 + k * 60))
    rows.append((cfg["app"].get("store_line", ""), font(SANS, 34), (255, 222, 180), 1010 + len(cfg["app"].get("tagline", [])) * 60 + 70))
    for txt, f, col, y in rows:
        if txt:
            tl = text_layer(txt, f, col)
            end.alpha_composite(tl, (W // 2 - tl.width // 2, y - tl.height // 2))

    t_label, t_lines, step = 0.0, 0.5, 0.6
    t_ref = t_lines + step * len(lines) + 0.4
    read_time = max(5.5, len(verse["text"].replace(" ", "")) * 0.13)
    t_end = t_ref + read_time
    total = round(t_end + 4.0, 2)

    wav = out_dir / "music.wav"
    mp4 = out_dir / "short.mp4"
    make_music(wav, total, seed)
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(wav),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(mp4),
    ], stdin=subprocess.PIPE)

    for i in range(int(total * FPS)):
        t = i / FPS
        fr = bg.copy()
        fr.alpha_composite(with_alpha(glow, 0.8 + 0.2 * math.sin(t * 0.8)), (W // 2 - 520, 1500 - 520))
        parts.draw(fr, t)

        out_k = 1 - ease((t - t_end) / 0.9)
        if out_k > 0:
            k = ease((t - t_label) / 0.35) * out_k
            if k > 0:
                fr.alpha_composite(with_alpha(label, k), (W // 2 - label.width // 2, 300))
                fr.alpha_composite(with_alpha(rule, k), (W // 2 - 45, 392))
                fr.alpha_composite(with_alpha(date_l, k), (W // 2 - date_l.width // 2, 410))
            for j, ll in enumerate(line_layers):
                k = ease((t - t_lines - j * step) / 0.8)
                if k > 0:
                    dy = int((1 - k) * 24)
                    fr.alpha_composite(with_alpha(ll, k * out_k), (W // 2 - ll.width // 2, verse_top + j * line_h + dy))
            k = ease((t - t_ref) / 0.9) * out_k
            if k > 0:
                fr.alpha_composite(with_alpha(ref_l, k), (W // 2 - ref_l.width // 2, ref_y))
                fr.alpha_composite(with_alpha(tr_l, k * 0.9), (W // 2 - tr_l.width // 2, ref_y + 70))

        k = ease((t - t_end - 0.5) / 0.9)
        if k > 0:
            fr.alpha_composite(with_alpha(end, k), (0, int((1 - k) * 20)))
        ff.stdin.write(fr.convert("RGB").tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg 인코딩 실패")
    wav.unlink(missing_ok=True)

    thumb = render_thumbnail(verse, date, cfg, pal, seed, out_dir / "thumbnail.jpg")
    return {"video": mp4, "thumbnail": thumb, "seconds": total, "palette": pal[0], "lines": lines}


def load_cfg():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--index", type=int, default=0, help="data/verses.json 의 몇 번째 구절")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    verses = json.loads((ROOT / "data/verses.json").read_text(encoding="utf-8"))
    res = render(verses[a.index], dt.date.fromisoformat(a.date), load_cfg(), a.out)
    print(res)
