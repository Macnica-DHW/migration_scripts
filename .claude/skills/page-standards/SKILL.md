---
name: page-standards
description: The look-and-feel standards for macnicaglobal2 pages, with the measurement behind each one and the examples approved or rejected in review. Covers the page-level rules (white end buttons, band padding, no width limit), the 28/09 standards (end-of-page CTA as Experience Fragment, heading hierarchy, video in a 2+ item flex, Text with Image Left ratio and wrap), and the guidelines (grey bands, white intro, image left and widths, gaps, structural cleanups). Use when auditing, proposing or making layout changes, or when judging whether a page looks right.
---

# Page standards: what a good global2 page looks like

Two kinds of standard (25/09): **rules** are followed strictly; **guidelines** can be broken when the page
gets better, as long as you say why in the report and the commit. The look is **judged page by page, not applied by
one rigid script**, because the pages differ. Start from the principles below, decide what fits each page, and
write "no change" when a page already follows them.

The starting point is always the **GWI page**, where the original production page lives (read-only). Content stays
equal to GWI. The layout follows GWI's arrangement and ideas, adapted to global2's components where GWI's layout
doesn't translate directly (often). The standards below say where a page goes further than GWI. Measure everything
at **1400px** with **`?wcmmode=disabled`**.

Standards change as the external verifiers review pages: record every change with `update-page-standards`, and check
the change log at the end of this file for what's current.

## Rules (no exceptions)

| Rule | How to check |
|---|---|
| Contact/CTA buttons at the end of the page (XF or not) sit on a **white** background | background of the last block before the footer (`pagina/pixels.py` → `fundo_botoes`; `auditoria_padroes.py` → `cta.botoes[].bg`) |
| A grey band has inner padding: nothing touches the grey/white edge | `pixels.py` → `faixas[].resp_topo/resp_base`. Approved pages: 37–50px. Exclude the fixed "Page Top" widget (x 1328–1411), which fakes 0px |
| No width limit: content uses the whole window (25px gutter) | no `fitcontainer` (1000px) style; screenshot 1400 wide (1412 = overflow) |
| Content = GWI (text, images, links, tables, videos) | `aem-verify-page` |

## Standards set on 28/09 ("should be…"; videos "need to be…")

Audit all four at once, read-only, from `scripts-hazael/`:
`python3 remigracao/ferramentas/auditoria_padroes.py coletar [--paginas …]` (fresh whitelist, JCR + render of each page;
redirect pages are skipped), then `… analisar` → `dados/auditoria_<ddmm>/achados.json`. For the HTML report, run
`python3 remigracao/ferramentas/relatorio_auditoria_padroes.py` → `dados/mapas/global2_whitelist_standards_audit_<date>.html`
(it adds per-page judgments when `dados/auditoria_<ddmm>/julgamentos.json` exists). The 28/09 run found, over 411
measured pages: 315 with heading problems (mostly every section title typed h1), 132 ending with the exact
products-contact-block buttons placed inline, 27 with the signup block inline, 17 videos outside a flex, and 195 Text
with Image blocks on 126 pages that are too tall or leave a gap.

### 1. End-of-page CTA buttons are an Experience Fragment
- **Target:** the closing block (Contact Us, Request a Quote, Sign up, Subscribe…) is an `experiencefragment`
  component, not `button` components on the page.
- **Which XF:** "Contact Us for More Information" + "Request a Quote" = `products-contact-block/master`. Newsletter
  "Sign up" + "Contact us" = `signup-and-contact-experience-fragment/master` (details in `aem-components`).
- **Not CTAs:** download buttons (links to DAM files) are content, and so are page-specific actions (an event's
  "Register now", a supplier's website). The fix must keep the same links. If the page's buttons differ from every
  XF (other text, target or number of buttons), report it: a new XF or variation is a shared resource (rule 4) and
  a team decision.
- Swapping inline buttons for an XF is a **structural** change on a page, not an XF edit. Pilot one page first.
  Mention the known "second document inside the page" defect of these XFs. The XF block must still sit in a white
  section.

### 2. Heading hierarchy
- **Target:** exactly one **h1** (the page title), sections **h2**, subsections **h3**, then h4… No skipped levels
  (h2 → h4), no heading used only for size, no empty headings.
- Headings come from the Title component (`type`) **and** from rich text (`<h2>` inside `text` or `textwithimage`).
  Both count.
- A Title with no `type` renders the policy default, which is **h1**. Many migrated pages have 2–4 h1s, because GWI
  used h1 for section titles.
- **Theme sizes:** h1 25px < **h2 29px**, h3 22px, h4 18px. Demoting an h1 section title to h2 makes it *bigger*,
  and demoting a card title from h2 to h3 makes it smaller. When the visual size should stay, set the Title's
  "Heading N" style (`heading1`…`heading6`, which only change size) along with the new `type`. Note that the style
  labelled "Heading 2" applies the class `heading1`.
- Sub-items (cards in a flex row, tab panels under a section heading, FAQ questions) are one level below their
  section. Europe does the same: one big title, h3/h4 inside sections.
- The header XF contains an empty `<h1>` on every page. That's shared and site-wide: report it once, and don't fix it
  per page.
- i-chips precedent (28/09): intro titles typed h1 (as in GWI) became `<h2>` inside the Text with Image, so the
  page title is the only h1.

### 3. Videos inside a Flex Container with 2+ items
- **Why:** there's no width limit and the YouTube embed style fills its column, so a lone video spans the whole
  1400px.
- **Target:** the `embed` sits in a `flexcontaineritem` of a `flexcontainer` with **at least 2 items that have
  content**, rendered **side by side** at 1400px.
- **Best:** the other item holds the video's **related text** (usually the heading and paragraph right before or
  after it in GWI). **The text goes first or second as on the GWI page:** on the side GWI puts it, or, when GWI
  stacks text and video, in GWI's reading order (text above the video in GWI → text in the first item). Example of
  the structure: `/altera` (Agilex 3 heading and text first, video second, about half width).
- Judgment call already accepted: i-chips leaf demo videos with no text of their own stayed as they were (medium
  width, empty column).

### 4. Text with Image, image position Left
Mechanics (measured): the image column is `imageRatio`% wide, and the image is **centered** in it at no more than its
natural width, with a 40px gap before the text. **Wrap** ignores `imageRatio`: the image floats at min(natural, 48%)
and the text flows around it.
- **No gap:** the image must fill its column. If the column is wider than the asset (`tiff:ImageWidth`), lower the
  ratio. Never upscale an asset.
- **Not much taller than the text:** at 1400px the image shouldn't pass the text height by more than
  max(60px, 25%).
- **Much more text than image** (text taller than the image by more than max(120px, 50%)) leaves empty space under
  the image. Set **Wrap** (style `1718154382437`), and check the resulting image size (it may grow up to 48%).
- `auditoria_padroes.py` simulates every ratio from 5 to 60% and the Wrap in the local DOM, then recommends the
  **largest ratio that has no gap and doesn't make the image too tall**. Treat it as a starting point:
  - **series:** consecutive Text with Image blocks (tabs, "Why choose" lists) should share one ratio, so the text
    starts at the same x;
  - **legibility:** diagrams and screenshots with small labels shouldn't shrink (Questa: kept full width);
  - **family precedent:** 36% Holoscan, 25% dev kits and OpenCL, 23% i-chips;
  - a very short text (1–2 lines) beside a big image may need a different layout, not a tiny image. Ask.

## Guidelines (judgment; examples approved in review)

- **Bands (faixas):** the page starts white (title + introduction), goes grey (`rgb(247,247,247)` on a
  **first-level** section, so it spans the full width) when the main content starts, and returns to white when the
  topic changes. Which group goes grey is decided per page. Stratix 10: the Applications blocks grey, the tables,
  links and buttons white. Dev kits: the Specs table grey. N1: bands alternate between major sections. A band holds
  at least 2 blocks and is at least ~200px tall. End buttons are never inside it.
- **The first segment after the title is the introduction and stays white.** If the text under the title is just a
  tagline, the first real section is the intro (Questa: "Overview" white).
- **Big image + related text → Text with Image,** image on the left (GWI often puts it on the right; the client
  accepted left). Holoscan banner + intro at 36%.
- **Gaps (vãos):** close gaps over ~125px (approved pages stay at or under ~121px), but blocks never touch.
  Usual causes: an XF alone in a nested section (~157px), a list at the end of a band (the list's 55px margin; give
  it its own section with No Padding), empty spacer sections. Fixes: move the end XF into the previous white section
  or its own "No Padding" section, and delete empty containers. The ~90px above the contact buttons is inside the
  shared XF and stays.
- **Structural cleanups accepted when the content stays identical:** keep a heading in the same section as its
  content, remove empty spacer containers, flatten nested sections so a band can run full width, move images left.
  GWI `<hr />` dividers are content and stay. Contact buttons stay where GWI has them (mid-page on the ADI landing).
- **Download buttons** (DAM file) are 51px tall and render differently: stack them, never pair them with a normal
  button.
- **Anchor menus:** the `id` goes on the target **title** (it lands under the fixed header). Click-test with
  `ferramentas/clicar_ancoras.py`. An anchorlink can't hold an external URL: an event website link becomes a
  **button** with GWI's text and URL (the NAB 2015 pilot, approved).
- **FAQ:** every answer sits directly under its question (`style="margin-top: 0;"` on all answers, not just some).
- **Grids** (GWI supplierlist, cards): rebuild them like `/solutions/imaging-and-vision` (Suppliers/Partners tab):
  container › flexcontainer "1 Column" › 4 items per row › image with link.
- **Links:** internal targets use the global2 page, and rich-text links end in `.html`. When a GWI link hard-codes a
  Macnica domain or is dead, ask (MEP100 and Agilex 3 were repointed to global2 pages after asking). Links to the
  global portal `https://www.macnica.com/` were **deferred** (24/09: "Let's skip this for now"), since global2 has
  no portal page yet. Approved precedents: iENSO "submit your request here" goes to the contact form, and
  the whole Zipteam heading is linked.

## How to run a look-and-feel pass

1. Fresh tracker lists (`tracker-lists`). Only whitelist pages, one family at a time. Avoid families someone is
   editing today.
2. Learn from the approved pages first. Diff the hand-edited, approved pages against their earlier state to
   extract the principles (`notas/PLANO-altera-look-and-feel.md` did this for Altera).
3. Per page: measure (`auditoria_padroes.py`, `pixels.py`, screenshots), decide, and write a closed list of changes.
   Record "no change" pages.
4. Pilot a new pattern on one page. If you designed the pattern, show it and wait for an OK. If the user specified it,
   check the pilot yourself and continue. Then go page by page: re-read, backup (automatic), write, check
   (`aem-verify-page`), and look at the before/after side by side.
5. Report per page: what changed, why (rule or guideline, and any guideline you broke), how you checked it, and
   what's still open. Keep decisions as numbered options with a recommendation.

## Change log

Newest first. Each entry: date, source (team, or the external verifiers), what changed, and what it supersedes.
Maintained with `update-page-standards`.

- **28/09**, team: videos. The related text goes first or second as on the GWI page (side or reading order), not
  always second. The page-level framing is stated: content = GWI, and layout follows GWI adapted to global2's
  components.
- **28/09**, team: four page standards: end-of-page CTA as an XF; heading hierarchy (one h1, h2 sections, h3
  subsections); videos in a 2+ item flex, ideally beside related text; Text with Image Left with no gap, image not
  much taller than the text, Wrap when the text is much longer. The i-chips pattern: intro title as `<h2>` inside the
  Text with Image, image 23%. **Supersedes** fixed per-family ratios as hard numbers: the ratio is now fitted to the
  asset and the text.
- **25/09**, team (client direction): rules are strict, guidelines can be broken when the page gets better. White end
  buttons, band inner padding, no width limit (rules). Band placement is an open per-page guideline: white intro, grey
  main content, white on topic change. **Supersedes** the automatic band placement of 21/09. Big image + related text
  becomes a Text with Image with the image on the left. Videos go medium-sized beside text. Close big gaps without
  blocks touching.
