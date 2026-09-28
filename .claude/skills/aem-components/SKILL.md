---
name: aem-components
description: Reference for macnicaglobal2 components on the AEM author. Covers resourceTypes, every style ID (cq:styleIds) with its label and CSS class, component properties (title type, textwithimage imageRatio, embed, button, container backgroundColor, experiencefragment), the CTA experience fragments, page-level properties and templates. Use when reading a JCR tree, deciding which property or style produces an effect, writing a node, or explaining why something renders the way it does.
---

# macnicaglobal2 components: reference

Every resourceType is `macnicaglobal2/components/content/<name>`. Style IDs live in
`/conf/macnicaglobal2/settings/wcm/policies/.../<name>/policy_*/cq:styleGroups/item*/cq:styles/item*`. This table was
read on 28/09. Refresh it with a GET of `/conf/macnicaglobal2/settings/wcm/policies.infinity.json` if something looks
off.

Before saying "the component can't do X", read its dialog
(`/apps/macnicaglobal2/components/content/<c>/_cq_dialog.infinity.json`, plus the super-type's dialog under `/libs`)
and grep the repo. A policy is not a dialog: dialog fields don't show up in `cq:styleIds`. That mistake happened
twice.

## Style IDs

`cq:styleIds` is a `String[]` with one slot per style group (the empty string = nothing picked in that group). Write it
as a list of tuples plus `cq:styleIds@TypeHint=String[]` (see `aem-operate`). A write **replaces** the whole array.
Watch out: 175 components on 163 Americas pages have the ID saved digit by digit (`["1","7","1","7",…]`), so their
style isn't applied.

| Component | ID | Label | Class | Notes |
|---|---|---|---|---|
| container | 1717498050826 / 1717498051666 / **1717498052331** / **1717498056876** | Top/Bottom padding Large / Medium / **Small** / **No Padding** | `container-padding-height_*`, `-height0` | vertical padding of a section ("TBs", "TB0"). Default is ~50px |
| container | **1717498053499** / 1717498054232 / 1717498054937 / **1717498055877** | Left/Right padding **Large** / Medium / Small / **No Padding** | `container-padding-width_*`, `-width0` | "LR" group |
| container | 1717410661180 | 1000px | `fitcontainer` | **don't use**: rule "no width limit" |
| flexcontainer | 1718800456497 / 1718800457369 / 1718800525141 / 1718800458698 | gap Large / Small / Medium / No Spacing | `flex-gap_*`, `flex-gap0` | |
| flexcontainer | **1719484596357** / 1719484597737 | 1 Column / 2 Columns | `sp-flex-direction-column[2]` | affects **phones only** (stacking); desktop is always side by side |
| textwithimage | **1718154328384** | Left | `left` | image left of the text (slot 1) |
| textwithimage | **1718154382437** | Wrap | `wrap` | text flows around/below the image (slot 2), see below |
| textwithimage | 1783061491236 / 1783061500464 | Vertical Center / Bottom | `vert-center` / `vert-bottom` | slot 3 |
| title | 1718280235037 … 1718280239865 | Heading 1 … Heading 6 | `heading1`…`heading6` | **visual size only**; the semantic level is the `type` property. "Heading 2" (1718280235888) has class `heading1` (policy slip) |
| title | 1717668061877 / 1717668062802 | Black / White | | colour |
| title | 1717668077776 / 1717668092148 | Ball / Back Line | | decoration |
| title | 1717668113714 / 1717668114416 | Center / Right | | alignment |
| button | 1722936853890 / 1723033446255 | Fixed Minimum Width / Fit to Text | | desktop min-width is 550px either way |
| button | **1717669229626** / 1717669230937 | Center / Right | | "Right" has no phone variant (a Right+Left pair turns into a staircase at 376–1049px) |
| button | 1717669222081 | White | `white` | |
| image | **1717565101174** | Expand to Fit Width | `large` | image = column width (like GWI's resizableimage) |
| image | 1726800547211 / 1726800548797 / 1726800549719 | Left / Center / Right | | |
| embed | 1719541568246 | YouTube | `youtube-width_full` | the video fills its column |
| table | 1722937999485 / 1722858778108 / 1722939215525 / 1722858697098 | Black / No Background / No Rounded Corner / No Frame | | second table policy: 1722940227649 / 1722860212196 / 1722940243721 / 1722860210955 |
| list | 1717649397305 / 1717648336486 | 2 Columns / Ranking | | theme adds `.cmp-list__list{margin:55px 0}` |
| cardlist | 1776056731771 / 1776056736854 / 1776056741289 | One column / Two columns / Slim | | |
| teaser | 1719301722473 / 1726809542533 | Rounded Corners / Full Size Display | | Europe uses rounded teasers |
| anchorlink | 1718759835935 / …836834 / …837531 / 1718861445028 | 4 / 5 / 10 Columns / Small text | | |

## Components and the properties that matter

**Page (`jcr:content`)**: `jcr:title`, `pageTitle` (what an empty Title shows as the h1), `navTitle`, `cq:template`
(`mai-page-content`, `mai-mae-product-page`, `mai-technical-article-page`, `mai-page-top`), `deleted`/`deletedBy`
(soft delete), `cq:redirectTarget`, `hideInNav`, `showInLists` (a cardlist only lists children that have it),
`cq:lastModified[By]`, `cq:lastReplicationAction_publish`. `manufacturerlogo`, `productlinelogo` and
`cq:featuredimage` exist, but **the global2 template doesn't render them** (GWI does).

**Structure.** `root` (responsivegrid) › `container` (the main container) › first-level sections (`container`)
› components. Only `root` and containers render. **Column widths live in `cq:responsive/default/{width,offset}`**,
not on the component. There is no margin between components: vertical spacing comes from the container padding
styles.

**container**: `backgroundColor` = `rgb(247,247,247)` (grey band, written without spaces). Other band colours seen:
lavender `rgb(245,243,249)`, `#ebebeb`. Paint the **first-level section**, so the band spans the full width. Remove it
with `backgroundColor@Delete`. `layout=responsiveGrid`.

**flexcontainer › flexcontaineritem**: the two-column (or n-column) layout. The items sit side by side on desktop, and
"1 Column" only stacks them on phones. The standard wrapper for a video beside its text.

**title**: `jcr:title`, `type` (`h1`…`h6`; empty = the policy default, which renders as **h1**), `id` (anchor
target, which lands correctly under the 85px fixed header), `linkURL` (the heading becomes a link and looks
unchanged). An empty `jcr:title` shows the page's title. **Theme sizes at 1400px: h1 25px, h2 29px (bigger than
h1!), h3 22px, h4 18px.** To fix the semantic level without changing the look, change `type` and pick the matching
"Heading N" style.

**text**: `text` (HTML) + `textIsRich="true"`. Headings inside rich text (`<h2>`…) are real headings and count in
the page outline. GWI `<hr />` "spacers" are content: keep them.

**textwithimage** ("Text with Image" / "Image with text"): `fileReference`, `alt`, `altValueFromDAM="false"`,
`isDecorative`, `text` (rich text; a raw `<h2>` as the first line renders exactly like a Title h2: 29px/600/purple),
`imageRatio` (dialog "Image Width (%)"), `linkURL`, `cq:styleIds` (3 slots: position, wrap, vertical). Measured CSS
at ≥1050px:
- **Not wrapped:** a flex row with a 40px gap. The image column width = `imageRatio`% (default 50%), the text takes
  the rest. The `<img>` is `max-width:100%`, **never upscaled**, and **centered** in its column. An asset narrower
  than the column leaves empty space on both sides of the image.
- **Wrap:** the image floats (left with the Left style) at its **natural width, capped at 48%** of the block.
  **`imageRatio` is ignored** in this mode. The text flows beside it and continues below.
- There is no size style (unlike `image`). The image comes from `<page>/_jcr_content/<node>.coreimg.<ext>`. Read
  `tiff:ImageWidth` from the asset metadata before picking a ratio.

**image**: `fileReference`, `alt`, `altValueFromDAM="false"` (**always** write it; missing means true, and the DAM alt
wins), `isDecorative`, `linkURL`/`linkTarget`, `jcr:title` (caption). Expand to Fit Width = column width.

**embed**: `type` = `embeddable` (`embeddableResourceType=core/wcm/components/embed/v1/embed/embeddable/youtube`,
`youtubeVideoId`) or `url` (`url=https://www.youtube.com/watch?v=…`). With the YouTube style it fills its column, so
outside a flex container it spans the whole page width. The iframe loads lazily: scroll before measuring.

**button**: `jcr:title`, `linkURL`, `linkTarget`, `cq:styleIds`. Adds `.html` to internal links itself.
`linkURL="#id"` is fine. A linkURL pointing to a DAM file renders the **download variant** (51px tall, 14px text,
icon over the last letter). Don't pair it side by side with a normal 57px button: stack them. The desktop min-width
is 550px.

**experiencefragment**: `fragmentVariationPath`. The page-end CTA fragments under
`/content/experience-fragments/macnicaglobal2/americas/mai/en/site/`:

| XF | Content |
|---|---|
| `products-contact-block/master` | flex: **Contact Us for More Information** (→ `/contact-us`, which redirects to `/contact/form`) · **Request a Quote** (→ `/request-a-quote`) |
| `signup-and-contact-experience-fragment/master` | flex: "Stay up to date on the latest news from Macnica Partners." + **Sign up** (Constant Contact) · "For more information:" + **Contact us** |
| `event-meeting-request-form/master` | the event meeting request form (not a button block) |
| `popups` | popups used by forms |

All of these are **shared resources** (rule 4: "You can edit \<path\>" for each change). The masters are built on
`components/page`, so an embed injects a second `<html>/<head>/<body>` (with a second canonical/og:url) into the
host page. That defect is known and open, waiting on a team decision (notas/PLANO-go-live.md). Mention it before recommending
a new embed. Find every embedder with querybuilder `property=fragmentVariationPath&property.value=<xf>/master`.
About 90px of space above the contact buttons comes from inside `products-contact-block`, so it can't be trimmed
without permission.

**tabs**: `item_N` children with `cq:panelTitle` (and an optional `id`). Inactive panels are hidden: check each one.

**anchorlink** (the purple ▼ "jump menu"): `anchor/*` items with `text` + `linkId`. The target must be an `id` on a
**title** component. It can't hold an external URL (it renders `#https://…`); use a button instead.

**list / cardlist**: `listFrom=children` + `parentPage` lists soft-deleted children too. A cardlist only shows
children with `showInLists=true`, and it renders text without logos.
