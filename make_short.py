"""
make_short.py - turns voiceover.mp3 into a vertical 9:16 YouTube Short with burned-in captions.

Run from n8n:  python C:\\n8n-shorts\\make_short.py
Inputs  (C:\\n8n-shorts):  voiceover.mp3, screen\\*.mp4 (your real screen recordings, used first),
                           backgrounds\\*.mp4 (stock B-roll, fills the gaps)
Outputs (C:\\n8n-shorts):  subs.ass, final_short.mp4
"""
import glob, json, math, os, random, shutil, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(BASE, "voiceover.mp3")
BG_DIR = os.path.join(BASE, "backgrounds")
SCREEN_DIR = os.path.join(BASE, "screen")  # 16:9 screen captures of the actual tools
SUBS = "subs.ass"  # relative on purpose: avoids Windows drive-letter escaping in the ffmpeg filter
OUT = os.path.join(BASE, "final_short.mp4")
W, H = 1080, 1920
WORDS_PER_CAPTION = 3


def find_tool(name):
    p = shutil.which(name)
    if p:
        return p
    local = os.environ.get("LOCALAPPDATA", "")
    for pattern in (
        os.path.join(local, "Microsoft", "WinGet", "Links", name + ".exe"),
        os.path.join(local, "Microsoft", "WinGet", "Packages", "*", "*", "bin", name + ".exe"),
        os.path.join("C:\\", "ffmpeg", "bin", name + ".exe"),
    ):
        hits = glob.glob(pattern)
        if hits:
            return hits[0]
    sys.exit(f"ERROR: {name} not found. Install with: winget install Gyan.FFmpeg")


FFMPEG, FFPROBE = find_tool("ffmpeg"), find_tool("ffprobe")


def duration(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def ts(t):
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def build_subs():
    from faster_whisper import WhisperModel

    import numpy as np

    # Decode with our own ffmpeg (16 kHz mono float) so faster-whisper never needs PyAV
    pcm = subprocess.run(
        [FFMPEG, "-v", "error", "-i", AUDIO, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True, check=True,
    ).stdout
    audio = np.frombuffer(pcm, dtype=np.float32)

    model = WhisperModel("base.en", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio, word_timestamps=True, vad_filter=True)
    words = [w for seg in segments for w in (seg.words or [])]
    if not words:
        sys.exit("ERROR: no words transcribed from voiceover.mp3")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial Black,92,&H00FFFFFF,&H0000FFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,2,60,60,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for i in range(0, len(words), WORDS_PER_CAPTION):
        chunk = words[i : i + WORDS_PER_CAPTION]
        end_limit = words[i + WORDS_PER_CAPTION].start if i + WORDS_PER_CAPTION < len(words) else chunk[-1].end + 0.3
        for j, wd in enumerate(chunk):
            start = wd.start
            end = chunk[j + 1].start if j + 1 < len(chunk) else end_limit
            parts = []
            for k, other in enumerate(chunk):
                txt = other.word.strip().upper().replace("{", "").replace("}", "")
                # active word highlighted in yellow and slightly bigger
                parts.append(r"{\c&H00FFFF&\fscx112\fscy112}" + txt + r"{\r}" if k == j else txt)
            lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{r'{\fad(40,0)}'}{' '.join(parts)}")
    with open(os.path.join(BASE, SUBS), "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")
    print(f"subs: {len(words)} words, {len(lines)} caption events")


SEG_LEN = 3.5          # seconds per B-roll cut
DARKEN = "eq=brightness=-0.07:contrast=1.05:saturation=1.1"  # keeps white captions readable
CLIP_EXTS = ("*.mp4", "*.mov", "*.mkv", "*.webm", "*.m4v")


def find_clips(folder):
    clips = []
    for ext in CLIP_EXTS:
        clips += glob.glob(os.path.join(folder, "**", ext), recursive=True)
    good = []
    for c in clips:
        try:
            d = duration(c)
            if d > 0.5:
                good.append((c, d))
        except Exception:
            print("skipping unreadable clip:", os.path.basename(c))
    return good


def broll_plan(screen, stock, total):
    """Cover the voiceover with cuts. Real screen recordings take the first (hook) cut and
    every other cut after it; stock B-roll fills the rest. Returns (path, start, len, loop, is_screen)."""
    n = max(1, math.ceil(total / SEG_LEN))
    pools = {True: [], False: []}
    sources = {True: screen, False: stock}
    plan = []
    for i in range(n):
        want_screen = bool(screen) and (i % 2 == 0 or not stock)
        if not pools[want_screen]:
            pools[want_screen] = sources[want_screen][:]
            random.shuffle(pools[want_screen])
        path, d = pools[want_screen].pop()
        seg = SEG_LEN if i < n - 1 else total - SEG_LEN * (n - 1) + 0.1
        start = random.uniform(0, max(0.0, d - seg - 0.1))
        plan.append((path, start, seg, d < seg + 0.1, want_screen))
    return plan


def render():
    dur = duration(AUDIO) + 0.4
    screen, stock = find_clips(SCREEN_DIR), find_clips(BG_DIR)
    vf_tail = f"subtitles={SUBS},format=yuv420p"
    if screen or stock:
        plan = broll_plan(screen, stock, dur)
        n_scr = sum(1 for p in plan if p[4])
        print(f"background: {len(plan)} cuts ({n_scr} screen recording, {len(plan) - n_scr} stock) from "
              f"{len(screen)} screen + {len(stock)} stock clip(s)")
        inputs, chains = [], []
        FG_W = int(W * 1.35)  # zoom screen captures so UI text stays readable on a phone
        for i, (path, start, seg, short, is_screen) in enumerate(plan):
            if short:
                inputs += ["-stream_loop", "-1"]
            inputs += ["-ss", f"{start:.2f}", "-t", f"{seg:.2f}", "-i", path]
            tail = f"setsar=1,fps=30,format=yuv420p,trim=duration={seg:.2f},setpts=PTS-STARTPTS[c{i}]"
            if is_screen:
                chains.append(
                    f"[{i}:v]split[a{i}][b{i}];"
                    f"[a{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=24:2,eq=brightness=-0.30[bg{i}];"
                    f"[b{i}]scale={FG_W}:-2,crop={W}:ih[fg{i}];"
                    f"[bg{i}][fg{i}]overlay=0:(H-h)/2-160,{tail}"
                )
            else:
                chains.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},{DARKEN},{tail}")
        concat = "".join(f"[c{i}]" for i in range(len(plan))) + f"concat=n={len(plan)}:v=1:a=0[bg]"
        vf = ";".join(chains + [concat, f"[bg]{vf_tail}[v]"])
        audio_idx = len(plan)
    else:
        print("background: none found in backgrounds\\ -> using animated gradient")
        inputs = ["-f", "lavfi", "-i", f"gradients=s={W}x{H}:c0=0x0f0c29:c1=0x302b63:c2=0x24243e:c3=0x6a00f4:n=4:speed=0.02:r=30:d={dur}"]
        vf = f"[0:v]setsar=1,{vf_tail}[v]"
        audio_idx = 1
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        *inputs, "-i", AUDIO,
        "-filter_complex", vf, "-map", "[v]", "-map", f"{audio_idx}:a",
        "-t", f"{dur:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT,
    ]
    subprocess.run(cmd, check=True, cwd=BASE)
    print(f"done: {OUT} ({duration(OUT):.1f}s, {os.path.getsize(OUT)//1024} KB)")


if __name__ == "__main__":
    os.chdir(BASE)
    if not os.path.exists(AUDIO):
        sys.exit("ERROR: voiceover.mp3 not found - run the Kokoro step first")
    os.makedirs(BG_DIR, exist_ok=True)
    build_subs()
    render()
