---
name: aem-verify-page
description: Check that a macnicaglobal2 page is correct, and prove that a change touched only what it should. Covers pre-flight checks, rendering global2 and GWI at 1400px with wcmmode=disabled, comparing text/links/images/videos against GWI, before/after identity after a write, visual checks (bands, gaps, end buttons, tabs, anchors, FAQ spacing), link clicks, and the report reviewers use. Use after any write, when asked whether a page is right or matches GWI, when reviewing a page before approval, and in end-of-day verification.
---

# Verifying a page

"Verify" means proving three things. What changed is exactly what was planned. Nothing else changed. The page
meets the standards and still matches GWI. Automated checks catch content and structure. **Only looking at the
render catches disposition** (see the lessons below), so every verification ends with you looking at the
screenshots.

Tools (all read-only, run from `scripts-hazael/`) are in `remigracao/ferramentas/pagina/` (see its README):
`render.py`, `comparar_gwi.py`, `antes_depois.py`, `pixels.py`, and the edit helper `pagina.py` with `conferir()`.
Plus `aem_screenshot.py`, `remigracao/ferramentas/clicar_ancoras.py` and `remigracao/ferramentas/auditoria_padroes.py`.

## 0. Pre-flight (every time)

- The cookie is alive (`aem-operate`), and you have a fresh blacklist (`tracker-lists`). Verification is read-only,
  but you need both to know what you may fix.
- Who touched the page, and when: `jcr:content.json` → `cq:lastModified[By]`. An edit made **today** that isn't yours
  (a teammate by hand on one of our two accounts, or any other account) means re-read before judging. An older edit doesn't matter.
- Use the **live** state. A screenshot or report from earlier may predate a hand edit or a batch run.

## 1. Render what the visitor sees

- `…/<page>.html?wcmmode=disabled` at a **1400px** viewport. The bare author `.html` is edit mode: every container
  gets a 29px placeholder and the gaps inflate (Macnica & ADI measured 265 vs 120px). The editor's Preview equals
  `wcmmode=disabled`.
- Scroll the whole page first (lazy images), then wait for images. Open **every tab**: a page with tabs is checked tab
  by tab (imaging-and-vision once shipped with an empty third tab of 22 suppliers).
- `python3 remigracao/ferramentas/pagina/render.py <page> --lado g2 --etiqueta antes`, then `--lado gwi`. For a page
  renamed in global2 (`/technology`→`/solutions`, capitals, `europe`→`eu`), pass the absolute GWI path plus the
  global2 file name so the two renders pair up: `render.py /content/macnicagwi/…/technology/imaging-and-vision --lado gwi
  --nome solutions__imaging-and-vision`. The JSON has every tab panel. The PNG shows only the active tab, so check the
  other panels by clicking them.

## 2. Content vs GWI (rule: content = GWI)

`python3 remigracao/ferramentas/pagina/comparar_gwi.py <page>` compares both renders:
- **Text:** the visible blocks, in order. Expected, harmless differences: GWI's empty spacer paragraphs are gone;
  global2 adds a hidden "opens in a new tab" label; GWI's "Download Now · PDF FILE" box became a Title/Download
  table.
- **Links:** paired by text and order. Each internal target must return 200 as a visitor would click it (with
  `.html`; rich-text links without it give 403). Every DAM file must exist in the global2 DAM with the **same
  `dam:sha1`** as GWI's. `target=_blank` should match GWI.
- **Images and videos:** count and source. GWI page-property logos (`manufacturerlogo`…) aren't rendered by global2,
  by design. `fileReference`/`src` must not contain `macnicagwi` (an image served from the GWI DAM only works
  while GWI is up).
- Judge by what the **GWI page shows**, not by its JCR (flags hide content).
- Link and text comparators miss some defects: a page cloned from its sibling (x86 showing Layerscape content, mb991
  showing MI997), a supplierlist grid, a duplicated table. Put the screenshots side by side and **read the intro:
  is it the right product?**
- During a layout pass, content differences are **reported, not fixed**. Hard-coded Macnica domains and dead GWI
  links: ask.

## 3. After a write: only the planned change

1. Before the write, take a snapshot (render `--etiqueta antes`, screenshot). The backup JSON comes automatically
   from the lock.
2. **Stability test:** two reads with no change in between must give 0 differences. Otherwise your comparator is
   noisy.
3. After the write:
   - **JCR:** `jcr:content` now vs the backup differs only in the declared nodes and properties, plus the page stamp
     (`cq:lastModified[By]`, `jcr:lastModified[By]`) and AEM normalization (`rel="noopener noreferrer"`,
     `<br />`, entity variants, `\r\n`).
   - **Content:** `pagina.conferir()` (the in-order sequence of components with their content props must be
     identical), or `antes_depois.py <page>` (text, links, images, videos, headings: OK / CONFERIR). A deliberate
     merge (3 components → 1 Text with Image) is listed as intended.
   - **Render:** identical outside the changed stretch. Mask the data-layer `repo:modifyDate`.
   - **Screenshot:** pixel-identical above the change; below it, identical after aligning by the next element; the
     tail is blank. For stable prints, kill animations, wait for fonts, and hide fixed elements. 71–335 differing
     pixels of anti-aliasing after a sub-pixel shift is normal, but zoom in and **look** instead of accepting it
     blindly.
4. New links open (200). Copied files match GWI's sha1. Anchors land: click them with `clicar_ancoras.py <page>`, which
   works outside the editor, where `#` links do scroll.

## 4. Standards and visual checks

- `python3 remigracao/ferramentas/pagina/pixels.py <full-page print>` gives band heights and inner padding (37–50px on
  approved pages), gaps ≥100px (flag ≥125px), and the background behind the end buttons (it must be white).
- `auditoria_padroes.py coletar --paginas <page>` + `analisar` gives the headings outline and problems, the end CTA
  (inline buttons vs XF), videos (inside a 2+ item flex and side by side?), and Text with Image (gap, too tall,
  wrap, recommended ratio). The criteria are in `page-standards`.
- FAQ: every answer directly under its question (the migrator applied `margin-top:0` to only some answers).
- Anchors: every `href="#x"` has a matching `id` (ignore `#page-top`) **and** clicking scrolls to it.
- Tables: judge against GWI's render (GWI's own overflow isn't a defect). Buttons: a download button is never paired
  side by side with a normal one.
- **Look at the before/after side-by-side PNG yourself.** On 25/09 an automated pass accepted a button pair 13px out
  of line; only the screenshot showed it.

## 5. If you can't reproduce a reported defect

Measure across browsers (Chrome/Firefox), widths (900–1400), display scaling (100/125/150%) and modes (disabled /
editor Preview / Edit). If it still doesn't show, **don't write**. Ask for a screenshot, the browser and the zoom
level. The altera-soc-courses "missing top border" turned out to be a glitch in the reviewer's browser.

## 6. Report

For the team: English, concrete, self-contained HTML in `scripts-hazael/remigracao/dados/mapas/` when it's
meant to be shared. Commit the generator, not the HTML.
- For each page, three links: global2 `<page>.html?wcmmode=disabled`, the GWI counterpart (real path), and the
  editor `editor.html<page>.html`.
- What changed (before → after, with crops), why (rule or guideline, and any guideline broken, with the reason), how
  it was verified, what's still open. Keep "found, not changed" apart from "changed".
- End the reply by saying whether anything was written to AEM, and confirming nothing was written to GWI.
- End-of-day pass over everything written: `golive/verificacao_final.py` did this for 24–25/09 (every change still in
  place, nothing else differs from the pre-change backup, nobody edited since, links open, layout unchanged since
  the write). Adapt it to the day's manifest.

## Lessons: defects manual review found that our checks missed

1. A dead hard-coded GWI URL was copied as is (MEP100). **Open** copied public URLs, following redirects without the
   cookie.
2. Reviewers' "broken link" meant text links without `.html`. We had checked targets, not clicks.
3. Band on the wrong group (Stratix 10): a rule generalized from one family.
4. The first segment should have been white, and the big image should have been a Text with Image (Holoscan,
   Questa).
5. FAQ answers 1–2 had a gap, and 5 of 6 anchors were dead (Ambarella). We had compared against "before" and GWI,
   both of which had the same defects, and never clicked the anchors or compared the Q&A spacing.
6. i-chips intro titles stayed above the image and as h1: the first pass moved only the image.

False alarms that weren't defects: a gap seen only in the edit-mode URL, and a browser rendering glitch.
