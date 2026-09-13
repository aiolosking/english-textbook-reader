# -*- coding: utf-8 -*-
"""Publish a SELF-CONTAINED tap-read HTML to a no-account, short-lived public
link (default 72h = 3 days) and verify it actually serves as a web page.

Usage:
  python3 publish_anonymous.py <single-file.html> [--time 72h] [--tries 4]

Why single-file: an anonymous host serves ONE uploaded file; a multi-file site
(index.html + images/ + audio/) would 404 on its assets. Build the single-file
bundle first (build_single.py) so images+audio are inlined as data: URIs.

Primary host: litterbox.catbox.moe — no account, retention {1h,12h,24h,72h},
serves uploaded .html as Content-Type:text/html (renders, no download prompt).
It cannot be deleted and expires after the chosen window; warn the user.

This script does NOT trust "upload returned a URL" as success: it re-GETs the
URL and requires HTTP 200 + an HTML content-type before printing it. On any
failure it prints each attempt's status and exits non-zero (never claim a link
that was not verified live). No credentials are ever used or written.
"""
import os, subprocess, sys, time
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

API = "https://litterbox.catbox.moe/resources/internals/api.php"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
VALID_TIMES = ("1h", "12h", "24h", "72h")


def is_self_contained(path):
    """Cheap check: the HTML should not reference external images/ or audio/."""
    try:
        txt = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return True, ""
    bad = []
    for needle in ('src="images/', "src='images/", 'src="audio/', "src='audio/",
                   'href="images/', 'href="audio/'):
        if needle in txt:
            bad.append(needle)
    return (len(bad) == 0), ",".join(bad)


def curl_upload(path, t):
    cmd = ["curl", "-s", "--max-time", "120", "-A", UA,
           "-F", "reqtype=fileupload", "-F", "time=" + t,
           "-F", "fileToUpload=@" + path, API]
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "").strip()
    return out


def verify_url(url):
    """Return (ok, http_code, content_type)."""
    cmd = ["curl", "-s", "-o", os.devnull, "--max-time", "60", "-A", UA,
           "-w", "%{http_code} %{content_type}", url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    parts = (r.stdout or "").strip().split(" ", 1)
    code = parts[0] if parts else "000"
    ct = parts[1] if len(parts) > 1 else ""
    ok = (code == "200") and ("html" in ct.lower())
    return ok, code, ct


def main():
    ap = sys.argv[1:]
    if not ap:
        print("usage: publish_anonymous.py <single-file.html> [--time 72h] [--tries 4]")
        sys.exit(2)
    path = ap[0]
    t = "72h"
    tries = 4
    i = 1
    while i < len(ap):
        if ap[i] == "--time": t = ap[i + 1]; i += 2
        elif ap[i] == "--tries": tries = int(ap[i + 1]); i += 2
        else: i += 1

    if not os.path.exists(path):
        print("ERROR: file not found:", path)
        sys.exit(1)
    if t not in VALID_TIMES:
        print("ERROR: --time must be one of", VALID_TIMES, "(got %s)" % t)
        sys.exit(2)

    ok_self, bad = is_self_contained(path)
    if not ok_self:
        print("WARNING: file references external assets (%s)." % bad)
        print("         Anonymous hosts serve ONE file; run build_single.py first")
        print("         so images/audio are inlined, or the link will show no media.")

    size_mb = os.path.getsize(path) / (1024 * 1024)
    print("uploading %.2f MB to litterbox (no account, retention %s)..." % (size_mb, t))

    last = ""
    for n in range(1, tries + 1):
        resp = curl_upload(path, t)
        last = resp[:200]
        if resp.startswith("http://") or resp.startswith("https://"):
            url = resp.splitlines()[0].strip()
            vok, code, ct = verify_url(url)
            if vok:
                print("PUBLISHED:", url)
                print("verified: HTTP %s, Content-Type %s" % (code, ct))
                print("note: no-account link, expires after %s, cannot be deleted." % t)
                print("      Anyone can open it without login/download/same-WiFi.")
                return
            print("attempt %d: got URL but verification failed (HTTP %s, ct=%s): %s"
                  % (n, code, ct, url))
        else:
            print("attempt %d: upload failed -> %s" % (n, last.replace("\n", " ")[:120]))
        if n < tries:
            time.sleep(8)

    print("FAILED: could not publish anonymously after %d tries." % tries)
    print("last response:", last.replace("\n", " ")[:200])
    print("litterbox may be down/rate-limiting from this network. Options:")
    print("  - retry later (transient 5xx often clears);")
    print("  - or use an account host for a PERMANENT link (GitHub Pages / Netlify /")
    print("    Cloudflare Pages) — that needs a user-provided account/token, with consent.")
    print("Do NOT report a local URL, a preview, or an unverified upload as deployed.")
    sys.exit(1)


if __name__ == "__main__":
    main()
