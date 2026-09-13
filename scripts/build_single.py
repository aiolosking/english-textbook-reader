# -*- coding: utf-8 -*-
"""Bundle a built site into ONE self-contained HTML (images+audio as base64).

Usage:
  python3 build_single.py --out OUT [--single single.html]

OUT must contain index.html, data.js, images/, audio/. The template's
controller already prefers inline data URIs (it.d / pg.imgd) when present, so
the same index.html logic serves both the multi-file and single-file builds.
Useful for sharing one file or hosting on a single-file host.
"""
import base64, json, os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def b64(path, mime):
    with open(path, "rb") as f:
        return "data:" + mime + ";base64," + base64.b64encode(f.read()).decode("ascii")


def main():
    ap = sys.argv[1:]
    out = None
    single = None
    i = 0
    while i < len(ap):
        if ap[i] == "--out": out = ap[i+1]; i += 2
        elif ap[i] == "--single": single = ap[i+1]; i += 2
        else: i += 1
    if not out:
        print("usage: build_single.py --out OUT [--single single.html]")
        sys.exit(2)
    single = single or os.path.join(out, "单文件点读.html")

    raw = open(os.path.join(out, "data.js"), encoding="utf-8").read()
    data = json.loads(raw[raw.index("const DATA =") + len("const DATA ="):].rstrip().rstrip(";"))

    for pg in data["pages"]:
        pg["imgd"] = b64(os.path.join(out, "images", pg["file"]), "image/jpeg")
    n = 0
    for it in data["items"]:
        if it.get("file"):
            it["d"] = b64(os.path.join(out, "audio", it["file"]), "audio/mpeg")
            n += 1

    html = open(os.path.join(out, "index.html"), encoding="utf-8").read()
    tag = '<script src="data.js"></script>'
    if tag not in html:
        print("ERROR: data.js script tag not found in index.html")
        sys.exit(1)
    html = html.replace(tag, "<script>\nconst DATA = " +
                        json.dumps(data, ensure_ascii=False) + ";\n</script>")
    with open(single, "w", encoding="utf-8") as f:
        f.write(html)
    print("inlined clips:%d pages:%d size_MB:%.2f -> %s" %
          (n, len(data["pages"]), os.path.getsize(single) / 1e6, single))


if __name__ == "__main__":
    main()
