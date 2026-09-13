# Authoring spec.json (pages, items, hotspots)

## Meta block

`meta` drives the on-page branding — build.py substitutes it into the template
placeholders `{{PAGE_TITLE}}`, `{{HEADER_TITLE}}`, `{{HEADER_SUB}}` and
`{{FOOTER_EXTRA}}`; the template itself contains no textbook names.

- `edition` / `grade` / `volume` / `unit`: publisher edition, grade, volume,
  unit, exactly as the material shows them. Joined they are the fallback title.
- `title`: full name used for the document title and 使用说明.md heading, e.g.
  `人教版八年级上册 Unit 1 Happy Holiday`. The part after `unit` becomes the
  header heading (`Unit 1 Happy Holiday · 点读`).
- `note`: caveats recorded in 使用说明.md (edition is a network display version,
  which pages have no audio, wording differences between print and recording…).
- `subtitle` (optional): short line under the header. Default is
  edition+grade+volume joined (no space between CJK fields).
- `footer` (optional): extra footer line, rendered after a `<br>`.

Never label audio as publisher-official unless the material proves it. When the
recording is third-party or unverified, say so in `subtitle` or `footer` — that
text is the reader's only on-page warning.

## Page entries

One entry per textbook page image actually provided:
`{"num":3,"file":"第03页.jpg","w":651,"h":921}` — `w`/`h` are the image's pixel
size (from inspect_material.py). `num` is the printed page number used in labels.

## Item entries

One item per tappable English string, in reading order:
`{"id":"p5_s6","page":5,"sec":"Lesson 1 / Enjoy the Story","text":"A monkey? But I'm a doctor, not a vet.","spot":[x,y,w,h],"tag":null,"kind":"line"}`

- `id`: stable slug, e.g. `p<page>_<block>_<n>`. Must match the script.json id
  for anything spoken.
- `sec`: grouping heading shown in the side list (lesson / activity name).
- `text`: the exact English as printed (book spelling; contractions as printed).
- `kind`: `line` sentence · `word` isolated word/chip · `song` sung verse.
- `tag`: `null` for body; `"答案"` for exercise answers (amber badge); any other
  short label for notes/annotations.
- `spot`: PIXEL rect `[x,y,w,h]` of the tappable region in the page image, or
  `null` for list-only items (no on-image hotspot).

## Choosing hotspot rects

- Speech bubbles: the bubble box (include tail if it is part of the bubble).
- Word chips / phonics grids / puzzle words: the individual word cell.
- Long paragraphs read aloud as one clip: one rect over the paragraph, or split
  into proportional sub-rects if the recording speaks them separately.
- Song verses: one rect per verse block.
- Keep rects inside the printed ink; a little padding is fine, overlap between
  two tappable rects is not.

## Verifying hotspot alignment (do this before build)

Render an overlay and eyeball it:
```
ffmpeg -y -i 第NN页.jpg -vf "drawbox=x=X:y=Y:w=W:h=H:color=red@0.8:t=2[,drawbox=...]" _overlay_NN.jpg
```
Open `_overlay_NN.jpg`; every red box must sit on its intended bubble/word.
Fix pixel values in spec.json and re-render until correct. Because build.py
converts pixels to percentages of `w`/`h`, correct pixels stay correct at any
display scale or screen size.

## Distinguishing content types

- Body text / dialogue: normal items.
- Exercise prompts & blanks: items if spoken; else list-only (`spot:null`).
- Printed or handwritten ANSWERS: `tag:"答案"`; include as spoken items only if
  the recording reads them; otherwise they appear in the list with a 无音频
  badge and no play button.
- Headings/section titles that are SPOKEN (e.g. "Lesson 1 Enjoy the story"):
  put them in script.json as `ann` units (they consume audio time) but do NOT
  make them page items.
