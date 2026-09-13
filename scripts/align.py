# -*- coding: utf-8 -*-
"""Greedy sequential alignment of an ordered audio script onto ASR words.

Usage:
  python3 align.py --words words.json --script script.json --out aligned.json \
                   [--audio-duration SECONDS]

script.json:
  {"units":[{"id":..,"kind":"ann|line|word|song","text":"..",
             "fixed":[s,e]?, "skip":int?, "thresh":float?}, ...]}
  - kind "ann"  : spoken announcement / heading present in audio but not on page
  - kind "line" : a full sentence on the page
  - kind "word" : an isolated word / chip on the page (tight skip window)
  - kind "song" : sung verse; must supply "fixed":[start,end] (music has no silences)
  Units are matched IN ORDER against the word stream; the pointer only moves
  forward, so a mis-hear cannot reorder later matches.

aligned.json (the editable correspondence table):
  {id: {"kind","text","score","start","end","clip_start","clip_end","matched"}}
Clip bounds are clamped so a clip never bleeds into the previous/next unit:
  start = max(word_start-0.10, prev_end+0.01)
  end   = min(word_end +0.18, next_start-0.01)
"""
import json, re, sys
from difflib import SequenceMatcher

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CONTR = {
    "i'm": "i am", "don't": "do not", "can't": "can not", "isn't": "is not",
    "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "you're": "you are", "they're": "they are", "we're": "we are",
    "let's": "let us", "it's": "it is", "that's": "that is", "what's": "what is",
    "who's": "who is", "he's": "he is", "she's": "she is", "there's": "there is",
    "here's": "here is", "where's": "where is", "how's": "how is",
}


def expand_tokens(text):
    out = []
    for tok in str(text).lower().split():
        core = re.sub(r"[^a-z0-9']", "", tok)
        if core in CONTR:
            out.extend(CONTR[core].split())
        else:
            core = re.sub(r"[^a-z0-9]", "", core)
            if core:
                out.append(core)
    return out


def merged_stream(raw_words):
    """Expand contractions and merge split digit tokens (1 / -2 / -0)."""
    MW = []
    for w in raw_words:
        for t in expand_tokens(w["w"]):
            if t.isdigit() and MW and MW[-1]["t"].isdigit() and (w["s"] - MW[-1]["e"]) < 0.5:
                MW[-1]["t"] += t
                MW[-1]["e"] = w["e"]
            else:
                MW.append({"t": t, "s": w["s"], "e": w["e"]})
    return MW


def sim(a, b):
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    return 1.0 if SequenceMatcher(None, a, b).ratio() >= 0.6 else 0.0


def main():
    ap = sys.argv[1:]
    words_f = script_f = out_f = None
    dur = None
    i = 0
    while i < len(ap):
        if ap[i] == "--words": words_f = ap[i+1]; i += 2
        elif ap[i] == "--script": script_f = ap[i+1]; i += 2
        elif ap[i] == "--out": out_f = ap[i+1]; i += 2
        elif ap[i] == "--audio-duration": dur = float(ap[i+1]); i += 2
        else: i += 1
    if not (words_f and script_f and out_f):
        print("usage: align.py --words w.json --script s.json --out a.json [--audio-duration S]")
        sys.exit(2)

    raw = json.load(open(words_f, encoding="utf-8"))
    script = json.load(open(script_f, encoding="utf-8"))
    units = script["units"] if isinstance(script, dict) else script
    MW = merged_stream(raw)
    W = [m["t"] for m in MW]
    total = dur if dur else (MW[-1]["e"] + 1.0 if MW else 0.0)

    result = {}
    p = 0
    for u in units:
        kind = u.get("kind", "line")
        key = u["id"]
        if kind == "song" or u.get("fixed"):
            fx = u.get("fixed")
            if not fx:
                result[key] = {"kind": kind, "text": u.get("text", ""), "score": 0,
                               "start": None, "end": None,
                               "clip_start": None, "clip_end": None, "matched": False}
                continue
            a, b = fx
            result[key] = {"kind": kind, "text": u.get("text", ""), "score": 1.0,
                           "start": a, "end": b, "clip_start": a, "clip_end": b,
                           "matched": True, "fixed": True}
            # jump pointer past the fixed region so following units align after it
            nxt = [i2 for i2, w in enumerate(MW) if w["s"] >= b]
            p = nxt[0] if nxt else len(MW)
            continue
        tgt = expand_tokens(u.get("text", ""))
        n = len(tgt)
        if n == 0:
            result[key] = {"kind": kind, "text": "", "score": 0, "start": None,
                           "end": None, "clip_start": None, "clip_end": None, "matched": False}
            continue
        SKIP = u.get("skip", 3 if kind == "word" else 20)
        TH = u.get("thresh", 0.55)
        best = None
        for start in range(p, min(p + SKIP, len(W))):
            for ln in (n - 1, n, n + 1):
                if ln < 1 or start + ln > len(W):
                    continue
                win = W[start:start + ln]
                m = min(ln, n)
                sc = sum(sim(tgt[i], win[i]) for i in range(m)) / n
                if ln != n:
                    sc *= 0.9
                if best is None or sc > best[0]:
                    best = (sc, start, ln)
        if best and best[0] >= TH:
            sc, start, ln = best
            result[key] = {"kind": kind, "text": u.get("text", ""), "score": round(sc, 2),
                           "start": MW[start]["s"], "end": MW[start + ln - 1]["e"],
                           "clip_start": None, "clip_end": None, "matched": True}
            p = start + ln
        else:
            result[key] = {"kind": kind, "text": u.get("text", ""), "score": 0,
                           "start": None, "end": None,
                           "clip_start": None, "clip_end": None, "matched": False}

    # clamp clip bounds so clips never overlap / bleed
    ordered = [(k, v) for k, v in result.items() if v["start"] is not None]
    for i2, (k, v) in enumerate(ordered):
        if v.get("fixed"):
            continue
        prev_end = ordered[i2 - 1][1]["end"] if i2 > 0 else 0.0
        next_start = ordered[i2 + 1][1]["start"] if i2 + 1 < len(ordered) else total
        s = max(v["start"] - 0.10, prev_end + 0.01)
        e = min(v["end"] + 0.18, next_start - 0.01)
        v["clip_start"] = round(s, 3)
        v["clip_end"] = round(e, 3)

    json.dump(result, open(out_f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    miss = [k for k, v in result.items() if not v["matched"]]
    bad = [k for k, v in result.items()
           if v["matched"] and not v.get("fixed")
           and (v["clip_end"] is None or v["clip_end"] <= v["clip_start"])]
    print("units:%d matched:%d unmatched:%d bad_clamp:%d" %
          (len(units), len(ordered), len(miss), len(bad)))
    print("UNMATCHED:", miss)
    if bad:
        print("BAD_CLAMP:", bad)


if __name__ == "__main__":
    main()
