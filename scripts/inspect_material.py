# -*- coding: utf-8 -*-
"""Inspect an English-textbook material directory.

Usage:
  python3 inspect_material.py <material_dir> [--write inspect.json]

Prints a concise JSON report: readme text, image list (with pixel size),
audio list (with duration), and best-guess edition/grade/unit/page-range.
Never modifies the material directory.
"""
import json, os, re, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
AUD_EXT = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")

EDITIONS = ["北师大", "北师", "人教版", "人教", "外研", "外研社", "译林", "牛津", "沪教", "教科版", "冀教", "湘少", "赣旅", "重大", "闽教", "湘鲁"]
GRADES = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级",
          "七年级", "八年级", "九年级", "高一", "高二", "高三"]


def probe(path, want):
    """Return width/height for images or duration for audio via ffprobe."""
    sel = "width,height" if want == "img" else "duration"
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams",
             "v:0" if want == "img" else "a:0",
             "-show_entries", "stream=" + sel if want == "img" else "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=60)
        parts = [x.strip() for x in r.stdout.split() if x.strip()]
        if want == "img" and len(parts) >= 2:
            return int(parts[0]), int(parts[1])
        if want == "aud" and parts:
            return round(float(parts[0]), 2)
    except Exception:
        pass
    return None


def guess(text):
    g = {}
    for e in EDITIONS:
        if e in text:
            g["edition"] = e if e != "北师" else "北师大"
            break
    for gr in GRADES:
        if gr in text:
            g["grade"] = gr
            break
    if "上册" in text:
        g["volume"] = "上册"
    elif "下册" in text:
        g["volume"] = "下册"
    m = re.search(r"(Unit|MODULE|Module|Starter|starter)\s*([0-9]+)", text)
    if m:
        g["unit"] = m.group(1) + " " + m.group(2)
    m2 = re.search(r"第\s*([0-9]+)\s*单元", text)
    if m2 and "unit" not in g:
        g["unit"] = "第" + m2.group(1) + "单元"
    return g


def main():
    if len(sys.argv) < 2:
        print("usage: inspect_material.py <material_dir> [--write inspect.json]")
        sys.exit(2)
    d = sys.argv[1]
    write = None
    if "--write" in sys.argv:
        write = sys.argv[sys.argv.index("--write") + 1]
    if not os.path.isdir(d):
        print("ERROR: not a directory: " + d)
        sys.exit(1)

    readme = []
    images, audios = [], []
    haystack = []
    for root, _dirs, files in os.walk(d):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            low = fn.lower()
            if low.endswith((".txt", ".md")) and any(k in fn for k in ("说明", "readme", "README", "usage")):
                try:
                    t = open(p, encoding="utf-8", errors="replace").read()
                    readme.append({"file": os.path.relpath(p, d), "text": t[:1500]})
                    haystack.append(t)
                except Exception:
                    pass
            elif low.endswith(IMG_EXT):
                wh = probe(p, "img")
                images.append({"file": os.path.relpath(p, d),
                               "w": wh[0] if wh else None, "h": wh[1] if wh else None})
                haystack.append(fn)
            elif low.endswith(AUD_EXT):
                du = probe(p, "aud")
                audios.append({"file": os.path.relpath(p, d), "duration": du})
                haystack.append(fn)

    def pkey(x):
        m = re.findall(r"\d+", os.path.basename(x["file"]))
        return (int(m[0]) if m else 0, x["file"])
    images.sort(key=pkey)

    nums = [int(m[0]) for x in images for m in [re.findall(r"\d+", os.path.basename(x["file"]))] if m]
    report = {
        "dir": os.path.abspath(d),
        "readme": readme,
        "images": images,
        "image_count": len(images),
        "page_range": [min(nums), max(nums)] if nums else None,
        "audio": audios,
        "audio_count": len(audios),
        "guess": guess(" ".join(haystack)),
        "warnings": [],
    }
    if not images:
        report["warnings"].append("no page images found")
    if not audios:
        report["warnings"].append("no audio found")
    for a in audios:
        if a["duration"] is None:
            report["warnings"].append("cannot read duration: " + a["file"])
    for im in images:
        if im["w"] is None:
            report["warnings"].append("cannot read size: " + im["file"])

    out = json.dumps(report, ensure_ascii=False, indent=1)
    print(out)
    if write:
        open(write, "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
