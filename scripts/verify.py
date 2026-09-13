# -*- coding: utf-8 -*-
"""Verify a built tap-to-read site.

Usage:
  python3 verify.py --out OUT [--audio SRC.mp3] [--asr N] [--model small]

Structural checks (always, fast):
  - every item with a clip has an existing non-empty audio file
  - clip_end > clip_start and duration sane (0.05s .. 60s)
  - clips never overlap when sorted by clip_start (no bleed into neighbours)
  - clips lie inside [0, source audio duration]
  - every hotspot rect is within its page bounds (0..100 %)
  - every page image file referenced by data.js exists

Optional ASR spot-check (--asr N): re-transcribe up to N clips with
faster-whisper and compare against the item text; prints OK/BAD counts and the
BAD list. Isolated single words often garble in ASR — treat those as
"not machine-confirmable", not as proven errors.

Exit 0 when no structural anomaly; non-zero otherwise.
"""
import json, os, re, subprocess, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def dur(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", path],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip())
    except Exception:
        return None


def norm_text(t):
    return re.sub(r"[^a-z0-9]", "", str(t).lower())


def main():
    ap = sys.argv[1:]
    out = None
    audio = None
    n_asr = 0
    model = "small"
    i = 0
    while i < len(ap):
        if ap[i] == "--out": out = ap[i+1]; i += 2
        elif ap[i] == "--audio": audio = ap[i+1]; i += 2
        elif ap[i] == "--asr": n_asr = int(ap[i+1]); i += 2
        elif ap[i] == "--model": model = ap[i+1]; i += 2
        else: i += 1
    if not out:
        print("usage: verify.py --out OUT [--audio src.mp3] [--asr N] [--model small]")
        sys.exit(2)

    raw = open(os.path.join(out, "data.js"), encoding="utf-8").read()
    data = json.loads(raw[raw.index("const DATA =") + len("const DATA ="):].rstrip().rstrip(";"))
    items = {it["id"]: it for it in data["items"]}
    problems = []

    # images exist
    for pg in data["pages"]:
        if not os.path.exists(os.path.join(out, "images", pg["file"])):
            problems.append("missing image " + pg["file"])
        for sp in pg["spots"]:
            if not (0 <= sp["x"] <= 100 and 0 <= sp["y"] <= 100 and
                    0 <= sp["w"] <= 100 and 0 <= sp["h"] <= 100 and
                    sp["x"] + sp["w"] <= 100.001 and sp["y"] + sp["h"] <= 100.001):
                problems.append("spot out of bounds %s" % sp["id"])

    # clips
    clips = []
    for it in data["items"]:
        if not it.get("file"):
            continue
        p = os.path.join(out, "audio", it["file"])
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            problems.append("missing/empty clip " + it["id"])
            continue
        d = dur(p)
        s, e = it["clip"]
        if d is None or d <= 0.05 or d > 60:
            problems.append("bad duration %s %s" % (it["id"], d))
        if e <= s:
            problems.append("non-positive clip %s" % it["id"])
        clips.append((s, e, it["id"], p))
    clips.sort()
    for a, b in zip(clips, clips[1:]):
        if b[0] < a[1] - 0.001:
            problems.append("overlap %s/%s" % (a[2], b[2]))
    if audio and os.path.exists(audio):
        total = dur(audio)
        if total:
            for s, e, iid, _p in clips:
                if s < -0.001 or e > total + 0.001:
                    problems.append("clip outside source %s" % iid)

    print("STRUCTURAL problems:%d" % len(problems))
    for p in problems[:40]:
        print("  -", p)

    ok = bad = skipped = 0
    badlist = []
    if n_asr > 0:
        from difflib import SequenceMatcher
        try:
            from faster_whisper import WhisperModel
            m = WhisperModel(model, device="cpu", compute_type="int8")
        except Exception as ex:
            print("ASR unavailable:", ex)
            m = None

        def toks(s):
            return re.findall(r"[a-z0-9]+", str(s).lower())

        def fuzzy_in(w, hset, hlist):
            if w in hset:
                return True
            return any(SequenceMatcher(None, w, h).ratio() >= 0.6 for h in hlist)

        if m:
            for s, e, iid, p in clips[:n_asr]:
                it = items[iid]
                segs, _ = m.transcribe(p, language="en")
                heard = " ".join(x.text.strip() for x in segs).lower()
                if it.get("kind") == "song":
                    skipped += 1
                    continue
                wt = toks(it["text"])
                ht = toks(heard)
                if not wt:
                    skipped += 1
                    continue
                hset, hlist = set(ht), ht
                hit = sum(1 for w in set(wt) if fuzzy_in(w, hset, hlist))
                score = hit / len(set(wt))
                if score >= 0.5:
                    ok += 1
                else:
                    bad += 1
                    badlist.append((iid, it["text"], heard[:40], round(score, 2)))
            print("ASR OK:%d BAD:%d SKIPPED:%d" % (ok, bad, skipped))
            for b in badlist[:40]:
                print("  MISMATCH", b)
            if bad:
                print("note: low scores are often proper-noun/isolated-word mis-hears,")
                print("      i.e. NOT machine-confirmable rather than proven wrong; audition them.")

    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
