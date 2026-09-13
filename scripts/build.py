# -*- coding: utf-8 -*-
"""Build a self-contained tap-to-read site from spec + alignment.

Usage:
  python3 build.py --spec spec.json --aligned aligned.json --material DIR \
                   --out OUT --template template.html [--audio RELPATH]

spec.json:
  {"meta":{"edition","grade","volume","unit","title","note"},
   "pages":[{"num":3,"file":"第03页.jpg","w":651,"h":921},...],
   "items":[{"id","page","sec","text","spot":[x,y,w,h]|null,"tag":null,
             "kind":"line|word|song|ann"},...],
   "order":[ids...]  (optional; defaults to items order)}
  spot is in PIXELS of the page image; converted to % so taps stay accurate
  at any scale.

Writes OUT/{index.html,data.js,images/,audio/,对应表.csv,使用说明.md}.
Items whose aligned unit is unmatched get file=null (no play button).
"""
import csv, json, os, shutil, subprocess, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def cut(audio, s, e, dst):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-ss", "%.3f" % s, "-to", "%.3f" % e, "-i", audio,
           "-c:a", "libmp3lame", "-b:a", "48k", "-ar", "24000", "-ac", "1", dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0


def _join_fields(parts):
    """拼接版本/年级/册次：纯中日韩文字段之间不加空格，其余用空格分隔。"""
    parts = [str(p).strip() for p in parts if str(p).strip()]
    if not parts:
        return ""
    cjk = lambda s: all("\u4e00" <= ch <= "\u9fff" for ch in s)
    return "".join(parts) if all(cjk(p) for p in parts) else " ".join(parts)


def main():
    ap = sys.argv[1:]
    spec_f = aligned_f = mat = out = tpl = None
    audio_rel = None
    i = 0
    while i < len(ap):
        if ap[i] == "--spec": spec_f = ap[i+1]; i += 2
        elif ap[i] == "--aligned": aligned_f = ap[i+1]; i += 2
        elif ap[i] == "--material": mat = ap[i+1]; i += 2
        elif ap[i] == "--out": out = ap[i+1]; i += 2
        elif ap[i] == "--template": tpl = ap[i+1]; i += 2
        elif ap[i] == "--audio": audio_rel = ap[i+1]; i += 2
        else: i += 1
    if not (spec_f and aligned_f and mat and out and tpl):
        print("usage: build.py --spec s.json --aligned a.json --material DIR --out OUT --template t.html [--audio rel]")
        sys.exit(2)

    spec = json.load(open(spec_f, encoding="utf-8"))
    aligned = json.load(open(aligned_f, encoding="utf-8"))
    meta = spec.get("meta", {})
    pages_spec = spec["pages"]
    items_spec = spec["items"]
    order = spec.get("order") or [it["id"] for it in items_spec]

    # locate the source audio
    def _dur(p):
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
        try:
            return float(r.stdout.strip() or 0)
        except Exception:
            return 0.0

    audio = None
    if audio_rel:
        audio = os.path.join(mat, audio_rel)
    else:
        # 材料目录里可能已有上一次构建切出的片段，按“时长最长”挑源音频，别把片段当源
        out_abs = os.path.abspath(out)
        cands = []
        for root, _d, files in os.walk(mat):
            for fn in files:
                if fn.lower().endswith((".mp3", ".wav", ".m4a", ".aac")):
                    p = os.path.abspath(os.path.join(root, fn))
                    if p == out_abs or p.startswith(out_abs + os.sep):
                        continue
                    cands.append(p)
        if cands:
            cands.sort(key=lambda p: os.path.getsize(p), reverse=True)
            scored = sorted(((_dur(p), p) for p in cands[:3]), reverse=True)
            audio = scored[0][1]
            print("source audio: %s (%.1fs, %d candidate(s))"
                  % (audio, scored[0][0], len(cands)))
    if not audio or not os.path.exists(audio):
        print("ERROR: source audio not found under " + mat)
        sys.exit(1)

    img_dir = os.path.join(out, "images")
    aud_dir = os.path.join(out, "audio")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(aud_dir, exist_ok=True)

    # copy page images
    for pg in pages_spec:
        src = os.path.join(mat, pg["file"])
        if not os.path.exists(src):
            print("WARN missing image: " + pg["file"])
            continue
        shutil.copyfile(src, os.path.join(img_dir, os.path.basename(pg["file"])))

    # items + clips
    items = []
    fail = []
    rows = []
    bypage = {pg["num"]: pg for pg in pages_spec}
    for it in items_spec:
        a = aligned.get(it["id"])
        has = bool(a) and a.get("matched") and a.get("kind") in ("line", "word", "song") \
            and a.get("clip_start") is not None and a.get("clip_end") is not None
        fname = None
        clip = None
        if has:
            fname = it["id"] + ".mp3"
            dst = os.path.join(aud_dir, fname)
            ok = cut(audio, a["clip_start"], a["clip_end"], dst)
            if not ok:
                fail.append(it["id"])
                fname = None
                has = False
            else:
                clip = [a["clip_start"], a["clip_end"]]
        items.append({"id": it["id"], "page": it["page"], "sec": it.get("sec", ""),
                      "text": it.get("text", ""), "tag": it.get("tag"),
                      "file": fname, "clip": clip})
        rows.append([it["id"], it["page"], it.get("sec", ""), it.get("text", ""),
                     it.get("kind", ""), os.path.basename(audio) if has else "",
                     a.get("start") if a else "", a.get("end") if a else "",
                     a.get("clip_start") if a else "", a.get("clip_end") if a else "",
                     a.get("score") if a else "",
                     ("已核对" if has else ("固定切分" if (a and a.get("fixed")) else "未匹配/无音频"))])

    # pages with % hotspots
    pages = []
    for pg in pages_spec:
        spots, ids = [], []
        for it in items_spec:
            if it["page"] != pg["num"]:
                continue
            ids.append(it["id"])
            sp = it.get("spot")
            if sp and pg.get("w") and pg.get("h"):
                x, y, w, h = sp
                spots.append({"id": it["id"],
                              "x": round(x / pg["w"] * 100, 3),
                              "y": round(y / pg["h"] * 100, 3),
                              "w": round(w / pg["w"] * 100, 3),
                              "h": round(h / pg["h"] * 100, 3)})
        pages.append({"num": pg["num"], "file": os.path.basename(pg["file"]),
                      "w": pg.get("w"), "h": pg.get("h"), "spots": spots, "items": ids})

    data = {"pages": pages, "items": items, "order": order}
    with open(os.path.join(out, "data.js"), "w", encoding="utf-8") as f:
        f.write("const DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")

    # index.html：用 spec meta 填充模板占位符（模板不含任何示例教材的固定书名）
    title = meta.get("title") or " ".join(filter(None, [
        meta.get("edition", ""), meta.get("grade", ""), meta.get("volume", ""),
        meta.get("unit", "")])) or "英语点读"
    note = meta.get("note", "")
    unit = (meta.get("unit") or "").strip()
    unit_name = title.split(unit, 1)[1].strip(" ·-—") if unit and unit in title else ""
    header_title = (unit + " " + unit_name).strip() if unit_name else (unit or title)
    header_sub = meta.get("subtitle") or _join_fields([
        meta.get("edition", ""), meta.get("grade", ""), meta.get("volume", "")]) or "英语点读"
    footer_extra = ("<br>" + meta["footer"]) if meta.get("footer") else ""
    with open(tpl, encoding="utf-8") as f:
        html = f.read()
    for k, v in (("{{PAGE_TITLE}}", title + " · 英语点读"),
                 ("{{HEADER_TITLE}}", header_title + " · 点读"),
                 ("{{HEADER_SUB}}", header_sub),
                 ("{{FOOTER_EXTRA}}", footer_extra)):
        html = html.replace(k, v)
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    with open(os.path.join(out, "对应表.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "页码", "section", "文字", "kind", "原音频",
                    "起始s", "结束s", "切片起s", "切片止s", "匹配分", "状态"])
        w.writerows(rows)

    with open(os.path.join(out, "使用说明.md"), "w", encoding="utf-8") as f:
        f.write("# %s · 点读使用说明\n\n" % title)
        f.write("- 打开 index.html（或单文件版）即可点读；点击课本图中气泡/单词或右侧句子播放原声并高亮。\n")
        f.write("- 控制：整课连播 / 暂停继续 / 单句重复 / 跟读（读完停顿数秒）/ 停止；切换句子自动停旧音。\n")
        f.write("- 无音频的句子标\"无音频\"，不提供播放按钮。\n")
        if note:
            f.write("\n> %s\n" % note)
        f.write("\n音频为配套录音按句切分；对应关系见 对应表.csv。\n")

    nclip = sum(1 for it in items if it["file"])
    print("pages:%d items:%d clips:%d cut_fail:%d" % (len(pages), len(items), nclip, len(fail)))
    if fail:
        print("CUT_FAIL:", fail)
    print("out:", os.path.abspath(out))


if __name__ == "__main__":
    main()
