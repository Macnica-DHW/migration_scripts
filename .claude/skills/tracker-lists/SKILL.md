---
name: tracker-lists
description: Fetch the site-migration-tracker blacklists (approved pages, which nobody may write to) and whitelists (unapproved pages you may work on) of both trackers, MAI (americas/mai/en) and DHW (americas/dhw), check a page's approval status, and pick the pages a task may touch. Use before ANY AEM work pass, before each page in a long run, when choosing which pages to work on, or when someone asks who approved what.
---

# Tracker lists: blacklist and whitelist

A tracker is where reviewers approve pages after checking them by hand. Since 15/10 there are **two trackers, one
per site**. Each is the **source of truth** for which of its pages are frozen:

| Tracker | Site | Site map |
|---|---|---|
| `https://site-migration-tracker.mdhw.dev` | MAI: `/content/macnicaglobal2/americas/mai/en/...` | the final link map, 533 pages |
| `https://dhw-site-migration-tracker.mdhw.dev` | DHW: every page under `/content/macnicaglobal2/americas/dhw` | 321 pages on 15/10 |

Both answer the same endpoints, with the same token:

| Endpoint | What it holds | What you may do |
|---|---|---|
| `GET /api/blacklist` | pages approved (green check) by at least one person | **read only**, never write, move or delete |
| `GET /api/whitelist` | every other page of that tracker's site map, i.e. nobody has approved it yet | work on it, following the rules (backup first…) |

A tracker's two lists together are its site map. MAI: 533 pages on 28/09 (110 + 423). On 02/10 the MAI tracker was
reset after talks with Anion and review restarted from scratch (0 + 533). DHW opened on 15/10 with 0 + 321. A page
on neither list of its site's tracker is outside the scope: ask before touching it. CLAUDE.md rule 10 still defines
the scope as MAI's 533 pages, so **ask before DHW work** until the rules say otherwise.

The trackers are the **only** lists. `paginas_protegidas.txt`, a local list the write lock used to add on top of the
tracker, was retired on 02/10: ignore it in old notes and git history.

## Rules this skill serves (from CLAUDE.md)

- Fetch a **fresh** blacklist before every AEM work pass. Pages get approved during the day (37 → 86 between 25/09
  and 28/09), so fetch again right before each page in a long run. Never reuse a copy from earlier.
- If the GET fails (tracker down, no token, inconsistent reply), **write nothing**. Reading can continue. An
  **empty** blacklist is a valid reply: no page is protected.
- Approvals can also be **withdrawn**: `altera-soc-courses` left the list on 27/09. Don't assume "once approved,
  always approved". Always use the live list.
- Child pages don't inherit protection. `news-archive` is approved; the news items under it are not.
- **Both trackers count.** The locked Session (`aem_lib`) fetches both blacklists and protects their union. If
  either tracker fails, the Session writes nothing at all, on either site. Outside `aem_lib` (curl, other
  Sessions), check the blacklist of the page's own site yourself.

## How to fetch

Auth header: `Authorization: Bearer $MIGRATION_TRACKER_TOKEN`, with the token from `.env` (the same token works on
both trackers). Send the token **only** to the trackers and the AEM cookie **only** to the author. Never print either
one.

CLI, **MAI tracker only** (read-only; importing `aem_lib` loads `.env` on its own):

```bash
cd scripts-hazael
python3 remigracao/ferramentas/tracker.py resumo                       # counts per section + approvals per person
python3 remigracao/ferramentas/tracker.py status /products/boards-modules/iei /about-us/company-profile
python3 remigracao/ferramentas/tracker.py listar whitelist --prefixo /products/boards-modules
python3 remigracao/ferramentas/tracker.py listar blacklist --json /tmp/bl.json
```

`tracker.py` knows only the MAI tracker: its API URL and its relative paths are MAI's, so it reports every DHW page as
on neither list. For DHW, read the DHW tracker directly (read-only):

```bash
python3 - <<'EOF'
import os, sys, requests
sys.path.insert(0, "scripts-bruno"); import aem_lib              # loads .env
h = {"Authorization": f"Bearer {os.environ['MIGRATION_TRACKER_TOKEN'].strip()}"}
for lista in ("blacklist", "whitelist"):
    d = requests.get(f"https://dhw-site-migration-tracker.mdhw.dev/api/{lista}", headers=h, timeout=30).json()
    assert d["count"] == len(d["pages"]), "inconsistent reply: treat as no list"
    print(lista, d["count"], *(p["aem_path"] for p in d["pages"][:5]), sep="\n  ")
EOF
```

In Python, writes go through the locked Session, which fetches both blacklists by itself:

```python
from aem_lib import build_session            # scripts-bruno/aem_lib.py
s, auth = build_session(prompt_if_missing=False)
s.blacklist.atual()   # tuple of protected aem_paths from BOTH trackers (empty = none protected), or None if either tracker failed (then the Session refuses every write)
```

`aem_lib.BLACKLIST_URLS` lists the trackers. `MIGRATION_TRACKER_BLACKLIST_URLS` (separated by `;`) replaces the
list for one run. The old single-URL `MIGRATION_TRACKER_BLACKLIST_URL` is refused: while it is set, nothing writes.

For the MAI whitelist in code, reuse `baixar("whitelist")` from `ferramentas/tracker.py`. For DHW, GET it as above.

## Response format

```json
{"count": 110, "generated_at": "2026-09-28T21:16:41Z", "description": "...",
 "pages": [{"aem_path": "/content/macnicaglobal2/americas/mai/en/about-us/glossary",
            "path": "/about-us/glossary", "title": "Glossary",
            "url": "https://author-…/…/glossary.html?wcmmode=disabled",
            "approved_by": [{"name": "<reviewer>", "approved_at": "2026-09-25T13:52:27.177Z"}]}]}
```

Whitelist entries have the same shape without `approved_by`. Always check `count == len(pages)`.

`path` is relative and means different things on each tracker. MAI's is relative to
`/content/macnicaglobal2/americas/mai/en` (`/about-us/glossary`). DHW's is relative to
`/content/macnicaglobal2/americas`, so it starts with `/dhw` (`/dhw/pt/quem-somos`; the site root is `/dhw`). Use
`aem_path`, which is absolute on both, whenever you match pages.

## Reading the data

- Approver names are tracker accounts, which have nothing to do with AEM accounts. In AEM, only `bruno.jaques` and
  `valter.toffolo` are ours, and people and scripts share them. So `cq:lastModifiedBy` never tells you which person
  or script made a write. Both trackers use the same accounts.
- The first 31 MAI approvals share one timestamp (a bulk import): trust the name, not `approved_at`.
- "Which pages did a past session write that still aren't approved?" Take the automatic backups in
  `scripts-hazael/remigracao/dados/backups_aem/auto/<date_time>_<pid>/`, one per page per write run, and compare
  them with fresh blacklists.
- The whitelist is a good work queue for read-only audits (`ferramentas/auditoria_padroes.py coletar` fetches the
  MAI one by itself). Before *writing*, re-check each page's status, because it may have been approved in the
  meantime.
- DHW has its own copy of the TQ-Systems families (`/dhw/tq-systems/...`), separate from MAI's
  `/products/boards-modules/tq-systems/...`. An approval on one tracker says nothing about the other site's copy.
