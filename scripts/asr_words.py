# -*- coding: utf-8 -*-
"""Word-level ASR timestamps for the source recording (faster-whisper, CPU).

Usage:
  python3 asr_words.py <audio> --out words.json [--model small] [--reuse existing.json]

Caches results next to --out as words.<sha16>.<model>.json so re-runs on an
unchanged audio file are instant. --reuse <file> skips ASR entirely and just
normalises an existing word list (use when a prior transcription of the SAME
audio already exists). Output: [{"w":token,"s":start,"e":end}, ...]
"""
import hashlib, json, os, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def norm(segs_words):
    out = []
    for w in segs_words:
        t = (w.get("word") or w.get("w") or "").strip()
        if not t:
            continue
        s = w.get("start", w.get("s"))
        e = w.get("end", w.get("e"))
        if s is None or e is None:
            continue
        out.append({"w": t, "s": round(float(s), 3), "e": round(float(e), 3)})
    return out


def main():
    ap = sys.argv[1:]
    if not ap:
        print("usage: asr_words.py <audio> --out words.json [--model small] [--reuse f.json]")
        sys.exit(2)
    audio = ap[0]
    model = "small"
    out = "words.json"
    reuse = None
    i = 1
    while i < len(ap):
        if ap[i] == "--model":
            model = ap[i + 1]; i += 2
        elif ap[i] == "--out":
            out = ap[i + 1]; i += 2
        elif ap[i] == "--reuse":
            reuse = ap[i + 1]; i += 2
        else:
            i += 1

    if reuse:
        raw = json.load(open(reuse, encoding="utf-8"))
        words = norm(raw) if isinstance(raw, list) else norm(raw.get("words", []))
        json.dump(words, open(out, "w", encoding="utf-8"), ensure_ascii=False)
        print("reused %s -> %d words -> %s" % (reuse, len(words), out))
        return

    key = os.path.join(os.path.dirname(os.path.abspath(out)) or ".",
                       "words.%s.%s.json" % (sha16(audio), model))
    if os.path.exists(key):
        words = json.load(open(key, encoding="utf-8"))
        json.dump(words, open(out, "w", encoding="utf-8"), ensure_ascii=False)
        print("cache hit %s -> %d words -> %s" % (key, len(words), out))
        return

    try:
        from faster_whisper import WhisperModel
    except Exception as ex:
        print("ERROR: faster-whisper not installed (%s). pip install faster-whisper" % ex)
        sys.exit(3)

    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _info = m.transcribe(audio, word_timestamps=True, language="en")
    words = []
    for seg in segs:
        for w in (seg.words or []):
            t = (w.word or "").strip()
            if t:
                words.append({"w": t, "s": round(float(w.start), 3), "e": round(float(w.end), 3)})
    json.dump(words, open(key, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(words, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print("transcribed %s (%s) -> %d words -> %s (cache %s)" % (audio, model, len(words), out, key))


if __name__ == "__main__":
    main()
