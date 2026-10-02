# CLAUDE.md: AEM migration, GWI → macnicaglobal2

This repo migrates and fixes Macnica Americas pages in Adobe Experience Manager (AEM Cloud, author
`author-p53812-e590634.adobeaemcloud.com`):

- **GWI** `/content/macnicagwi/americas/mai/en/...`: the original site, where the production pages live today.
  **Read-only: it is NEVER written to.** It is the reference for every migrated page.
- **global2** `/content/macnicaglobal2/americas/mai/en/...`: where the migrated pages live, and where we work. It
  becomes production once all pages are done **and** each one has been individually approved by external verifiers.
- **copia-teste** `/content/copia-teste/...`: a staging copy from the remigration era (17–23/09). Its DAM is shared.

**How a migrated page relates to GWI.** Its content (text, images, links, tables, videos) matches GWI. Its layout
follows GWI's overall arrangement and ideas, adapted to global2's components wherever GWI's layout doesn't translate
directly, which happens a lot. It goes further than GWI only where a page standard requires it or the page clearly
looks better (e.g. images on the left of their text), and the report says so.

The rules below were agreed by the team, and several people run Claude in this repo. The rules apply to every
session, every subagent and every script. When you write a prompt for a subagent or a
workflow that can touch AEM, **copy the RULES section into that prompt.** Subagents don't inherit your judgment.

**Our AEM accounts.** Only two accounts have access to AEM for this work, and they are the ones that count as "ours":
`bruno.jaques` and `valter.toffolo`. Scripts run with a cookie or token of one of them, and people also edit by hand
with them. Any other account (the Anion agency's, for example) is **not** ours: when filtering pages created or
modified by us, only those two count. And since people and scripts share them, `cq:lastModifiedBy` tells you which
of the two wrote, never whether a person or a script did. In code, use `aem_lib.contas_nossas()` / `eh_nossa()`
(both accounts by default; the call site, or `AEM_CONTAS_NOSSAS=valter|bruno|ambas`, can pick one). Never hard-code them.

Skills in `.claude/skills/` hold the how-to. Load the matching one before starting:

| Skill | Use it when |
|---|---|
| `tracker-lists` | before ANY AEM work pass; when you need the blacklist/whitelist or a page's approval status |
| `aem-operate` | reading or writing AEM: auth, endpoints, the write lock, backups, Sling POST patterns, assets, pitfalls |
| `aem-components` | looking up resourceTypes, style IDs, component properties, XFs, templates |
| `page-standards` | judging or changing how a page looks: headings, CTA XFs, videos, Text with Image, bands, gaps |
| `update-page-standards` | new feedback on how pages should look (e.g. from the external verifiers) must become a standard |
| `aem-verify-page` | checking that a page is correct (vs GWI, vs before, vs the standards), and reporting it |
| `session-handoff` | starting a session, resuming someone else's work, or handing work over when context runs out |

## RULES: follow them strictly, no exceptions

Decided on 25/09: *"those are **rules**, not suggestions or guidelines."* Several are also enforced in code by the
locked Session of `scripts-bruno/aem_lib.py`. That lock is a safety net, not permission. `EscritaProibida` is a stop
sign: never work around it.

1. **Never write to GWI.** No non-GET request against any URL containing `macnicagwi` (pages, DAM, XFs). Sling
   `:operation=copy` with a GWI source is a POST *on GWI*, so never use it. To copy a GWI asset, POST into the
   global2 folder with `<name>@CopyFrom=<GWI path>`. Reading GWI is fine.
2. **Never write to a blacklisted page.** The blacklist is the tracker's list of approved pages
   (`https://site-migration-tracker.mdhw.dev/api/blacklist`). No write, modify, move or delete on the page or its
   `jcr:content`. Reading is fine. Child pages are not protected unless they are on the list themselves.
3. **Fetch a FRESH blacklist before every AEM work pass**, and again right before each page in a long run: people
   approve pages while you work (37 → 86 in three days). Never use an old copy. If the GET fails, write nothing.
   An empty blacklist is a valid answer: no page is protected (on 02/10 the tracker was reset and review restarted
   from scratch). The tracker is the only list: `paginas_protegidas.txt` was retired on 02/10.
4. **Shared resources need explicit permission for each path.** Experience fragments, templates and policies
   (`/conf`), components (`/apps`), and anything else a protected page uses count as shared. The header and footer
   XFs reach every page. The only valid approval is *"You can edit \<exact path\>"*. "Go ahead", "you can proceed",
   "you can edit all of them" and approving a plan or batch do NOT count. In code, pass the path per run with
   `AEM_COMPARTILHADO_AUTORIZADO=<exact path>` on the command line, never in `.env`. If you're unsure whether
   something is shared, treat it as shared and ask. DAM assets and child pages shown on protected pages are an open
   question: ask.
5. **Back up the page before changing it:** the whole `jcr:content`, saved to disk before the first non-GET on that
   page. `aem_lib` does it automatically, into `scripts-hazael/remigracao/dados/backups_aem/auto/`. Outside
   `aem_lib` (curl, other Sessions) do it by hand. No backup, no write.
6. **Content = GWI; layout follows GWI, adapted.** Text, images, links, tables and videos must match GWI, errors
   included (a GWI error migrates as is). Layout follows GWI's arrangement and ideas, adapted to global2's
   components where it doesn't translate directly, and may go further when a standard requires it or the page looks
   better. Wrong or
   missing content you find is **reported and asked about**, never fixed silently. Some tasks say "just report"
   (i-chips, 28/09). Links that hard-code an old Macnica domain or point to dead GWI targets are decided case by
   case: ask.
7. **Page-level rules from the client direction (25/09):**
   - Contact/CTA buttons at the end of the page (XF or not) always sit on a **white** background.
   - A grey band always has inner padding: text and images never touch the grey/white edge.
   - **No width limit:** pages use the full window width. Don't copy Europe's 1000px column.
8. **Credentials stay in their lane.** The AEM cookie (`AEM_COOKIES` in `.env`) is personal: it goes only to the author
   host, and is never printed, logged or committed. The tracker token (`MIGRATION_TRACKER_TOKEN`) is the team's shared
   API bot token. It may be shared inside this private repository, but it goes only to the tracker, and you never
   print it in replies, logs or reports.
9. **"Read-only" means GET only.** When a task says read-only, send no non-GET anywhere and change no page. End the
   reply by saying that nothing was written to AEM.
10. **Scope:** "in macnicaglobal2" means the pages of the final link map, about 533 = tracker blacklist +
    whitelist. It does not mean the whole tree (5,096 pages). Sony, deepx, canon, design-gateway, the blog and
    Europe (`eu/atd-europe`) belong to the Anion agency: don't fix, create or migrate them. Leave links to their
    missing pages as they are.
11. **Node names are normalized** (`normalize_name()`: lower-case, collapsed hyphens), even when someone else's
    shell page uses GWI's capitals. Don't touch the other page: list the pair and ask.

Standing permission (25/09): reading and writing on AEM is allowed as long as the rules are followed. It covers
global2 page writes under rules 1–11. It does not cover shared resources (rule 4), content
changes nobody asked for (rule 6), or other people's sessions. A task declared read-only overrides it for that task.

**Never:**
- Use `aem_config.py` at the root: it has no lock.
- Run `scripts-hazael/aem_remigrar.py --executar` (or the old R1–R62 engine) on global2: it deletes
  `jcr:content/root` and wipes hand edits.
- Run `--executar` over a whole tree: only on the exact page list you dry-ran.
- Put `AEM_COMPARTILHADO_AUTORIZADO` in `.env` (it goes on the command line for one run only). Don't put the cookie
  value in a file, a prompt or a command line, or inline the tracker token in a command (read it from the environment).
- Say "nothing was written" without re-reading AEM.
- Judge gaps, anchors or popups inside `editor.html` or on the bare author URL.
- Treat the GWI JCR as the GWI page.

If a credential leaks (in a transcript, a log or a request to the wrong host), tell the user right away.

## GUIDELINES: use judgment; break one when the page gets better, and say why

Decided on 25/09: *"There are rules and there are guidelines. You should follow rules strictly, but guidelines can be
broken if it makes the page better."* Approved breaks: the Questa workflow diagram stayed full width, because at
36% its labels would be unreadable; the OpenCL logo went at 25%, because 36% would upscale and blur it. Look and
feel is **judged page by page, not applied by one rigid script.** Pages differ.

The first four are **page standards set on 28/09** ("should be…"; for videos, "need to be…"). The target is
fixed, but how you get there on each page is a judgment call:

- **Headings:** one h1 per page (the page title). Sections h2, subsections h3, and so on. No skipped levels.
- **End-of-page CTA buttons** (Contact Us, Request a Quote, Sign up…) come from an **Experience Fragment**, not
  buttons placed on the page. Existing XFs: `products-contact-block`, `signup-and-contact-experience-fragment`.
- **Videos** sit inside a Flex Container with at least 2 items, so they don't span the full page width on desktop.
  Best: the other item holds the video's related text, beside it. The text goes first or second as on the GWI page:
  on the side GWI puts it, or, when GWI stacks them, in GWI's reading order.
- **Text with Image, Left:** pick an `imageRatio` that leaves no gap between image and text and doesn't make the
  image much taller than the text at 1400px. If the text is much longer than the image, set **Wrap**.
- **Bands (faixas):** white title and introduction, then grey when the main content starts, back to white when the
  topic changes. Which group goes grey is decided per page. A band needs at least 2 blocks and at least ~200px.
- **Images on the left** of their text, via Text with Image. Width is per family: 36% (Holoscan), 25% (dev kits,
  OpenCL), 23% (i-chips). Never upscale an image past its natural width.
- **Gaps:** close big gaps (over ~125px; approved pages stay at or under ~121px), but blocks never touch.
- **Pilot first:** a NEW kind of structural change goes to one page first. When you designed the pattern yourself,
  show the pilot to the user and wait for an OK. When the user specified the exact pattern (i-chips, 28/09), check the
  pilot yourself, then continue.

`page-standards` has the measurements, the approved examples and the component mechanics behind each point.

## How we work

The flow every session follows: **plan → fresh blacklist → backup → targeted change → verify →
report.**

- **Change only what was planned.** Each write is a closed list of changes (node, property, expected current value).
  Afterwards, prove nothing else changed (see `aem-verify-page`). In link and content fixes, that means no layout
  change at all (24/09: *"don't break the layout nor change anything that isn't the targeted change"*). In a layout
  pass it means the content stays identical.
- **Before any AEM pass:** check the cookie. `.env` mtime plus one cheap GET; the cookie lasts ~8h and only the user
  can renew it. Then fetch the tracker lists. Then check that no other session or person is editing the same pages:
  an edit made *today* that isn't yours (a teammate by hand on one of our accounts, or any other account) means leave
  the page or ask. Older edits don't matter. The lock can enforce part of this: `AEM_BLOQUEAR_EDITADAS_MIN=N` (or
  `build_session(bloquear_editadas_min=N)`) refuses to write to a page edited in the last N minutes.
- **Re-read the live page right before writing,** and keep hand edits. People edit pages in AEM while sessions run,
  with the same two accounts the scripts use, so `cq:lastModifiedBy` can't tell a person from a script. Use the
  backups, manifests and timestamps.
- **Measure before you attribute a cause.** Render with `?wcmmode=disabled` at **1400px**. A direct author `.html`
  is edit mode, and its placeholders inflate gaps. Mobile is out of scope unless asked.
- **If a command is blocked** by the permission classifier or the lock: stop, re-read AEM with GET to confirm what
  was or wasn't written (a denied command may have partly run), then ask. Never route around it.
- **If you can't reproduce a reported defect,** don't write. Ask for a screenshot, browser and zoom.
- **Decisions:** give numbered options with a recommendation. Answers often come in bulk. Leave unanswered items
  alone, and don't take on work the user said they'll do themselves.
- **Do what was asked, at the size asked.** "Generate a list" means generate it, not also check every link in it.
  Offer extra checks in one line instead.
- **A screenshot the user sends may predate a write:** check the live page before "fixing" what it shows.

## Reporting

- Reply in English. Be concrete: what the reader will see on the page, and why it matters. Avoid internal jargon.
  A visible hole or breakage is the first item of a report, with its size, never a footnote. Say when a page is
  good; don't invent defects. Warn about known side effects *before* recommending something.
- In every reply that follows AEM work, say whether anything was written to AEM, and confirm nothing was written to
  GWI.
- Reports meant to be shared are **self-contained HTML in English**, written to `scripts-hazael/remigracao/dados/mapas/`.
  Give each page three links: global2 (`<page>.html?wcmmode=disabled`), its GWI counterpart (the real GWI path, even if
  renamed), and the global2 editor. Include before/after, what was done, how it was verified, what's still open,
  and a filter box. Keep them readable at 1400px and 390px with no horizontal scroll.

## Git and files

- Branch `migration` (named `migration/semiconductors-remigration` until 28/09). Commit only when asked. No co-author trailer. Pushing is the
  user's decision. Never push `backup/antes-da-limpeza-2026-09-25`.
- Commit messages are in Portuguese and say what happened in AEM: **`GRAVADO no AEM (dd/mm)`**,
  **`NO CÓDIGO, nada gravado no AEM`** or **`SOMENTE LEITURA`**.
- Versioned: code; lasting docs (READMEs, `REGRAS-disposicao.md`, `ROTEIRO-revisor.md`…); tool inputs;
  **all AEM backups** (`dados/backups_aem/`, `dados/golive/backup_*`); write manifests;
  `.claude/` (skills, shared settings).
- Not versioned: `.env`; tool outputs in `scripts-hazael/remigracao/dados/` (maps, reports, renders, screenshots);
  session docs in `scripts-hazael/remigracao/notas/` (handoffs, plans); `.claude/settings.local.json`. Never
  `git add -f` an ignored path. For a report, commit the tool that generates it, not the HTML.
- Several sessions may share this branch. An unknown commit or a stale file means another actor: check
  `git log`/`ps` before committing.

## Layout of the repo

- `scripts-bruno/aem_lib.py`: shared library. `build_session()` returns the **locked Session** (fresh blacklist,
  GWI block, shared-resource block, automatic backup). Every tool that writes must use it.
- `scripts-hazael/`: post-migration tools. Its README is partly out of date: see `session-handoff` for what's stale.
  `remigracao/ferramentas/` holds the current tools: `tracker.py`, `auditoria_padroes.py` (+
  `relatorio_auditoria_padroes.py`), `pagina/`, `clicar_ancoras.py`, `golive/`.
- `scripts-hazael/aem_screenshot.py`: full-page render (`--full --publicado` = 1400px, `?wcmmode=disabled`).
- `scripts-luiza/`: has its own Session, **not** covered by the lock. Don't change it.
- `.env` (from `.env.example`): `AEM_BASE_URL`, `AEM_COOKIES` (personal login-token, ~8h), `MIGRATION_TRACKER_TOKEN` (the
  team's shared tracker bot token).
