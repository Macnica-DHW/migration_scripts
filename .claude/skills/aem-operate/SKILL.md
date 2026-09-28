---
name: aem-operate
description: How to read from and write to the AEM author safely in this repo. Covers the cookie and its ~8h lifetime, GET endpoints (infinity.json, HTTP 300 fallback, querybuilder, DAM metadata, dialogs, policies), the locked Session in aem_lib (fresh blacklist, GWI block, shared-resource block, automatic backup), Sling POST patterns (set/delete props, cq:styleIds arrays, create/move/order/delete nodes, @CopyFrom assets), Playwright rendering, and the pitfalls that cost hours. Use for any AEM GET or write, and before writing or changing a tool that talks to AEM.
---

# Operating AEM safely

Read the RULES in `CLAUDE.md` first. This skill covers *how*; the rules cover *whether*.

## Hosts and paths

| What | Where |
|---|---|
| Author (the only AEM host) | `https://author-p53812-e590634.adobeaemcloud.com` (`CONFIG["base_url"]` in `aem_lib`) |
| global2 Americas (where we work) | `/content/macnicaglobal2/americas/mai/en` |
| GWI (read only) | `/content/macnicagwi/americas/mai/en`; DAM `/content/dam/macnicagwi/americas/mai/public/en` |
| global2 DAM | `/content/dam/macnicaglobal2/americas/mai/en/...` (file names lower-cased/renamed) |
| XFs (shared) | `/content/experience-fragments/macnicaglobal2/americas/mai/en/site/<name>/master` |
| Europe (Anion's, read only for us) | `/content/macnicaglobal2/eu/atd-europe/en` |
| Components / policies | `/apps/macnicaglobal2/components/content/<c>`, `/conf/macnicaglobal2/settings/wcm/policies` |

Renamed pairs you'll meet: GWI `/technology/...` is global2 `/solutions/...`; GWI names can have capitals
(`iENSO-to-Showcase-…`), which global2 lower-cases; `europe` becomes `eu`; Sony is nested under the Anion's tree;
`/contact-us` redirects to `/contact/form`.

## Authentication: the cookie

- `.env` → `AEM_COOKIES` holds the browser's `login-token`. **It lasts about 8 hours** and only the user can
  renew it: log in to AEM, then in F12 → Network, pick a 200 request to the author → Copy as cURL, and paste the value
  after `-b` into `.env`. Basic auth doesn't work (Adobe IMS).
- Check it before any pass, and again before long runs:
  ```bash
  ls -la --time-style=+%F_%H:%M .env; date
  python3 - <<'EOF'
  import sys; sys.path.insert(0, "scripts-bruno"); import aem_lib as L
  s, a = L.build_session(prompt_if_missing=False, verbose=False)
  print(L.get_json(s, L.CONFIG["base_url"] + "/libs/granite/security/currentuser.json", a)[1])   # 200 = ok, 401 = expired
  EOF
  ```
  If it returns 401, ask the user to renew it. Keep doing offline work meanwhile. Tell them roughly when the new one
  will expire (mtime + 8h).
- The cookie goes **only** to the author. In Playwright, add cookies for the author host only. A route that aborts
  every other host is even safer: `pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(BASE) else r.abort())`.
- `aem_lib` loads `.env` when imported. Standalone scripts that read `os.environ["AEM_COOKIES"]` need
  `set -a; . ./.env; set +a` first. That prints a harmless `command not found: Americas`, because of an unquoted
  value on line 48.

## Reading (GET only)

Use `aem_lib`: `s, auth = build_session(prompt_if_missing=False, verbose=False)`, then
`get_json(s, url, auth)` → `(json, status)`. For content subtrees use
`fetch_with_depth_fallback(s, base, path, "infinity", auth)`, which handles the HTTP 300 case.

| Need | GET |
|---|---|
| whole page content | `<page>/jcr:content.infinity.json` (HTTP 300 on big pages → the fallback picks the deepest `.N.json` allowed) |
| page props (title, stamp, soft delete, redirect) | `<page>/jcr:content.json`: `jcr:title`, `pageTitle` (drives the h1), `cq:lastModified[By]`, `deleted`, `cq:redirectTarget`, `hideInNav`, `cq:lastReplicationAction_publish` |
| child pages | `<page>.1.json` (or `.2.json` to also see each child's `jcr:content`) |
| a node exists? name free? | `<node>.json` → 200 / 404 |
| what visitors see | `<page>.html?wcmmode=disabled`. **Never** the bare `.html`: that is edit mode, with 29px placeholders per container |
| DAM asset facts | `<asset>/jcr:content/metadata.json` → `dam:sha1`, `dam:size`, `tiff:ImageWidth`, `tiff:ImageLength`; renditions at `<asset>/jcr:content/renditions.1.json` |
| component fields | `/apps/macnicaglobal2/components/content/<c>/_cq_dialog.infinity.json` (+ the `sling:resourceSuperType` dialog under `/libs`) |
| style IDs | `/conf/macnicaglobal2/settings/wcm/policies.infinity.json`; walk `cq:styleGroups/*/cq:styles/*` (see `aem-components`) |
| queries | `/bin/querybuilder.json`, e.g. every page embedding an XF: `path=<mai/en>&property=fragmentVariationPath&property.value=<xf>/master&p.limit=-1`; pages edited today: `type=cq:PageContent&daterange.property=cq:lastModified&daterange.lowerBound=<date>T00:00:00.000-03:00` |

Read these gotchas before trusting what you read:
- **A node's own `.json` filters HTML** (`<br />`, `&#34;`, adds `rel`). Take raw text (especially GWI text you'll
  copy) from the page's `jcr:content.infinity.json`. GWI text uses `\r\n`, global2 uses `\n`.
- **Only `root` and its containers render.** A sibling node outside that tree never shows up on screen.
- **The GWI JCR isn't the GWI page.** Flags (`isText`, `isButton`, `isHeading`) and the template hide content.
  Judge "what GWI shows" from its render (`.html?wcmmode=disabled`).
- **Soft-deleted pages** (`jcr:content/deleted`) vanish from the console but keep their name. `list` components
  with `listFrom=children` still show them as duplicates.
- **querybuilder** can lag after writes, returned an empty 200 once (25/09), and `nodename` is case-sensitive.
  Fall back to folder listings plus `dam:sha1`.
- `cq:lastModified` comes back in GMT, while query bounds are written in -03:00.

## Writing: always through the locked Session

`scripts-bruno/aem_lib.build_session()` returns a `requests.Session` whose non-GET calls pass through
`travar_session`:

1. **GWI:** any non-GET to a URL containing `macnicagwi` raises `EscritaProibida`. So do `@MoveFrom` out of GWI and
   `:operation=copy` with a GWI source.
2. **Protected pages:** the fresh tracker blacklist (re-fetched when older than 300 s) ∪ `paginas_protegidas.txt`.
   Blocked: writes to the page or its `jcr:content`, delete/move of the page or an ancestor, `:dest` into it, and
   `@MoveFrom` out of it. If the tracker fails, **every** write is refused (it fails closed).
3. **Shared structures:** everything under `/content/experience-fragments`, `/conf` and `/apps` is blocked, unless the
   user said "You can edit \<exact path\>" and you pass it for that single run:
   `AEM_COMPARTILHADO_AUTORIZADO=<exact path> python3 ...` (paths separated by `;`, at least 6 levels deep; refused
   if it's set in `.env`).
4. **Automatic backup (rule 5):** before the Session's first non-GET on a page, it saves that page's whole
   `jcr:content` to `scripts-hazael/remigracao/dados/backups_aem/auto/<YYYY-MM-DD_HHMMSS>_<pid>/<path with __>.json`
   (for a delete/move of the page node itself, the whole subtree). If the backup fails (HTTP 300/500, network), the
   write doesn't happen. `s.backups` maps each page to its backup file. These backups get committed.

5. **Optional: pages edited in the last N minutes.** `build_session(bloquear_editadas_min=N)`, or
   `session.bloquear_editadas_min = N`, or `AEM_BLOQUEAR_EDITADAS_MIN=N` on the command line. Before the Session's
   first write on a page, it looks at the newest `cq:lastModified` / `jcr:lastModified` / `jcr:created` anywhere in
   that page's `jcr:content`. If it's younger than N minutes, by **any** account, the write is refused (someone may be
   working on it) and no backup is saved. The Session's own later writes to that page don't count. It's off by
   default. Turn it on whenever other people or sessions may be editing the same family. If it refuses a page that
   your own earlier run just wrote, rerun with a smaller N. `Pagina(..., bloquear_editadas_min=N)` also warns about
   it during the dry-run.

`EscritaProibida` means **stop and ask**. Not covered by the lock: `scripts-luiza/` (its own Session), raw
curl, and anything done by hand in the AEM UI. With those, apply the rules yourself: fresh blacklist, manual
backup, no GWI.

For per-page edits, use the helper `scripts-hazael/remigracao/ferramentas/pagina/pagina.py` (class `Pagina`). It
refuses protected pages, can refuse a page that changed since your snapshot, dry-runs by default (`executar=False`),
and has `conferir()` for the after-check. See that folder's README.

### Sling POST recipes

Every write is `s.post(BASE + <node path>, data=..., timeout=60)`. 200 = updated, 201 = created. Any other status:
stop the page and report. Add `"_charset_": "utf-8"` when sending text.

```python
# set properties
s.post(url, data={"linkURL": "/content/macnicaglobal2/americas/mai/en/…", "_charset_": "utf-8"})
s.post(url, data={"text": html, "textIsRich": "true"})
s.post(url, data={"backgroundColor": "rgb(247,247,247)"})           # grey band on a first-level container
s.post(url, data={"backgroundColor@Delete": ""})                     # remove a property (back to white)

# multi-value: send a LIST of tuples (repeated key) + TypeHint; the array is REPLACED, so re-send every slot
s.post(url, data=[("cq:styleIds", "1718154328384"), ("cq:styleIds", ""), ("cq:styleIds", ""),
                  ("cq:styleIds@TypeHint", "String[]")])             # textwithimage: Left in slot 1 of 3

# create a node at a position (first confirm <node>.json is 404)
s.post(parent + "/container_new", data=[("jcr:primaryType", "nt:unstructured"),
       ("sling:resourceType", "macnicaglobal2/components/content/container"),
       ("cq:styleIds", ""), ("cq:styleIds", "1717498056876"), ("cq:styleIds@TypeHint", "String[]"),
       (":order", "after container_2")])

# move, then position; delete (check <node>.1.json has no child nodes before deleting a container)
s.post(src, data={":operation": "move", ":dest": "<absolute destination path incl. node name>"})
s.post(dest, data={":order": "before experiencefragment_1"})
s.post(node, data={":operation": "delete"})

# copy a GWI asset: the POST goes to the global2 FOLDER; GWI is only read by the server
s.post(g2_folder, data={f"{name}@CopyFrom": "/content/dam/macnicagwi/…/file.pdf", "_charset_": "utf-8"}, timeout=300)
```

Rules of thumb for writes:
- **Sling POST merges; it doesn't replace.** Writing a subtree over an existing one leaves both. Delete first, or
  write property by property.
- **Re-read right before writing** and compare with the state you planned against. If it changed (for example,
  someone edited it by hand), re-plan on top of the live state and keep those edits.
- **Precondition every change:** the current value must be the expected "from" value, otherwise skip (`PULA`).
  After the write, re-read and require that only the planned properties changed (plus the stamp).
- A write stamps the **page**: `cq:lastModified[By]` becomes the account whose cookie or token ran the write
  (`valter.toffolo` or `bruno.jaques`, our two accounts), and the data-layer `repo:modifyDate` changes too. Allow for that noise in comparisons. When the page was someone else's, say so in the report.
- AEM normalizes rich text on save: it adds `rel="noopener noreferrer"` to `target=_blank` links and turns `<br>` into
  `<br />`. Normalize both sides before comparing, or you'll report false failures.
- Rich-text links need `.html` (`/content/…/page.html`); without it, a click gives 302 → trailing slash → 403.
  Buttons, images and titles add `.html` themselves.
- New `image`/`textwithimage` nodes need `altValueFromDAM="false"` (and `isDecorative="false"`). When the flag is
  missing it behaves as true, and the DAM alt replaces yours.
- Before copying an asset, look for the same `dam:sha1` already in the global2 DAM and reuse it if found. After
  copying, check `dam:sha1` = GWI's, that the binary GET is 200 with the right size, and that renditions appear a few
  seconds later.
- Batch writers: dry-run by default, a closed hand-reviewed list, `--executar` only with the exact dry-run list
  (`--paginas`/`--so`). Keep a manifest (`dados/golive/manifesto*.jsonl`) of what was written.
- A new *kind* of structural change (create/delete/move nodes, change resourceType) runs on **one pilot page**
  first and is shown to the user before the rest.

## Rendering and measuring (Playwright)

```python
from aem_lib import CONFIG, parse_cookie_string       # importing loads .env
from playwright.sync_api import sync_playwright
host = CONFIG["base_url"].split("//", 1)[1]
b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
c = b.new_context(viewport={"width": 1400, "height": 1000})
c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in parse_cookie_string(os.environ["AEM_COOKIES"]).items()])
pg = c.new_page(); pg.goto(f"{CONFIG['base_url']}{path}.html?wcmmode=disabled", wait_until="load", timeout=90000)
```

- Scroll the whole page before measuring, because lazy images shift everything below them. Wait for `img.complete`.
- Page content lives in `.container.main`, between `.cmp-experiencefragment--header` and `--footer`. The header XF
  holds an empty `<h1>` on every page, so ignore it when counting headings.
- Tabs hide inactive panels. Measure each panel, either by clicking each `.cmp-tabs__tab` or by forcing
  `.cmp-tabs__tabpanel{display:block}` in your local DOM.
- Full-page screenshots: `cd scripts-hazael && python3 aem_screenshot.py <path> -o out.png --full --publicado`. For
  pixel-stable prints, kill animations (`*{animation:none!important;transition:none!important}`), wait for
  `document.fonts.ready`, and hide fixed/sticky elements (Page Top, phone button, reCAPTCHA).
- A 1412px-wide screenshot at a 1400px viewport = horizontal overflow (the 12px come from the header/footer on
  every page).
- Measure only at **1400px** unless asked. Anchor links never scroll inside `editor.html`; test them outside it
  (`ferramentas/clicar_ancoras.py`).
- Changing the local DOM to simulate something (a CSS variable, a class) is fine: it never reaches AEM.
  `ferramentas/auditoria_padroes.py` simulates `imageRatio` this way.

## Our accounts, in code

Only `bruno.jaques` and `valter.toffolo` are ours (see CLAUDE.md). Don't hard-code them. Use `aem_lib`:

```python
from aem_lib import contas_nossas, eh_nossa
contas_nossas()                  # both (default), or what AEM_CONTAS_NOSSAS says
contas_nossas("valter")          # just one; also "bruno", "ambas", "valter,bruno" or full e-mails
eh_nossa(jc.get("cq:lastModifiedBy"), contas_nossas("bruno"))
```

The call site decides which accounts count. A script can also leave it to whoever runs it:
`AEM_CONTAS_NOSSAS=valter python3 …`. An unknown name raises an error, so a typo never quietly means "nobody". The
go-live tools (`golive/_comum.py` → `NOSSAS`, plus `direto.py`, `canonical_secoes.py`, `lista_links.py`) already
work this way.

## Environment pitfalls

- zsh doesn't word-split `$VAR`: pass multiple paths as separate arguments or as an array.
- Chrome fails when `TMPDIR` is a long path. Set a short one.
- In a Python heredoc, JS strings with `\\n` get mangled. Put probes in files.
- If an auto-mode permission check blocks a command, **stop**. Re-read AEM with GET to see whether anything was
  written (a denied command may have partly run), then ask. Never route around it.
