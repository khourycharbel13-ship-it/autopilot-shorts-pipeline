"""
fetch_broll.py - downloads free vertical (9:16) tech B-roll from Pexels into C:\\n8n-shorts\\backgrounds\\

API key (free, from https://www.pexels.com/api/) - use ONE of these:
  1) put the key alone in a text file:  C:\\n8n-shorts\\pexels_key.txt
  2) or set an environment variable:     PEXELS_API_KEY=your_key

Usage:
  python fetch_broll.py              -> tops the folder up to 15 clips (skips if already >= 15)
  python fetch_broll.py --min 25     -> tops up to 25 clips
  python fetch_broll.py --force 15   -> downloads 15 new clips even if the folder is full
"""
import argparse, glob, json, os, sys, time, urllib.parse, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
BG_DIR = os.path.join(BASE, "backgrounds")
KEY_FILE = os.path.join(BASE, "pexels_key.txt")
CREDITS = os.path.join(BG_DIR, "_pexels_credits.txt")
QUERIES = ["coding", "matrix code", "cybersecurity", "dark office typing", "server room"]
UA = "n8n-shorts-broll/1.0 (+local automation)"
MAX_MB = 60  # skip giant files


def get_key():
    k = os.environ.get("PEXELS_API_KEY", "").strip()
    if not k and os.path.exists(KEY_FILE):
        k = open(KEY_FILE, encoding="utf-8-sig").read().strip()
    # tolerate labels like "PEXELS-KEY: abc..." or quotes: keep the longest letters/digits run
    import re
    runs = re.findall(r"[A-Za-z0-9]{20,}", k)
    return max(runs, key=len) if runs else k


def api(key, query, page=1, per_page=15):
    q = urllib.parse.urlencode({"query": query, "orientation": "portrait", "size": "medium", "per_page": per_page, "page": page})
    req = urllib.request.Request(f"https://api.pexels.com/videos/search?{q}", headers={"Authorization": key, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def best_file(video):
    """Pick a portrait HD mp4, closest to 1080x1920 without going far above it."""
    files = [f for f in video.get("video_files", [])
             if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")
             and f["height"] > f["width"] and f["height"] >= 1280]
    if not files:
        return None
    return min(files, key=lambda f: abs(f["height"] - 1920) + (2000 if f["height"] > 2600 else 0))


def download(url, dest):
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        size = int(r.headers.get("Content-Length") or 0)
        if size and size > MAX_MB * 1024 * 1024:
            raise ValueError(f"too large ({size // 1048576} MB)")
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=15, help="top the folder up to this many clips")
    ap.add_argument("--force", type=int, default=0, help="download this many new clips regardless")
    a = ap.parse_args()

    os.makedirs(BG_DIR, exist_ok=True)
    have = [p for p in glob.glob(os.path.join(BG_DIR, "*.mp4"))]
    need = a.force if a.force else max(0, a.min - len(have))
    print(f"backgrounds: {len(have)} clip(s) present, downloading {need}")
    if need == 0:
        return

    key = get_key()
    if not key:
        print(f"WARNING: no Pexels key found. Put it in {KEY_FILE} (or set PEXELS_API_KEY). Skipping download.")
        return  # exit 0 so the pipeline still renders with whatever clips exist

    existing_ids = {os.path.basename(p).split("_")[1] for p in have if os.path.basename(p).startswith("pexels_")}
    per_query = -(-need // len(QUERIES))  # ceil
    got, credits = 0, []
    for query in QUERIES:
        if got >= need:
            break
        taken, page = 0, 1
        while taken < per_query and got < need and page <= 3:
            try:
                data = api(key, query, page=page)
            except Exception as e:
                print(f"  [{query}] API error: {e}")
                break
            videos = data.get("videos", [])
            if not videos:
                break
            for v in videos:
                if taken >= per_query or got >= need:
                    break
                vid = str(v["id"])
                if vid in existing_ids:
                    continue
                f = best_file(v)
                if not f:
                    continue
                slug = query.replace(" ", "-")
                dest = os.path.join(BG_DIR, f"pexels_{vid}_{slug}.mp4")
                try:
                    download(f["link"], dest)
                except Exception as e:
                    print(f"  [{query}] skip {vid}: {e}")
                    continue
                existing_ids.add(vid)
                taken += 1
                got += 1
                credits.append(f"{os.path.basename(dest)}  |  {v.get('user', {}).get('name', '?')}  |  {v.get('url', '')}")
                print(f"  [{query}] {got}/{need}  {f['width']}x{f['height']}  {os.path.getsize(dest) // 1024} KB  -> {os.path.basename(dest)}")
            page += 1
            time.sleep(0.3)

    if credits:
        with open(CREDITS, "a", encoding="utf-8") as c:
            c.write("\n".join(credits) + "\n")
    total = len(glob.glob(os.path.join(BG_DIR, "*.mp4")))
    print(f"downloaded {got} clip(s); backgrounds now has {total}")


if __name__ == "__main__":
    main()
