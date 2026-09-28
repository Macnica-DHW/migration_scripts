---
name: tracker-lists
description: Fetch the site-migration-tracker blacklist (approved pages, which nobody may write to) and whitelist (unapproved pages you may work on), check a page's approval status, and pick the pages a task may touch. Use before ANY AEM work pass, before each page in a long run, when choosing which pages to work on, or when someone asks who approved what.
---

# Tracker lists: blacklist and whitelist

The tracker (`https://site-migration-tracker.mdhw.dev`) is where reviewers approve pages after checking them by
hand. It is the **source of truth** for which pages are frozen.

| Endpoint | What it holds | What you may do |
|---|---|---|
| `GET /api/blacklist` | pages approved (green check) by at least one person | **read only**, never write, move or delete |
| `GET /api/whitelist` | every other page of the site map, i.e. nobody has approved it yet | work on it, following the rules (backup first…) |

The two lists together are the site map: 533 pages on 28/09 (110 + 423). A page on neither list is outside the
scope: ask before touching it.

## Rules this skill serves (from CLAUDE.md)

- Fetch a **fresh** blacklist before every AEM work pass. Pages get approved during the day (37 → 86 between 25/09
  and 28/09), so fetch again right before each page in a long run. Never reuse a copy from earlier.
- If the GET fails (tracker down, no token, empty or inconsistent reply), **write nothing**. Reading can continue.
- Approvals can also be **withdrawn**: `altera-soc-courses` left the list on 27/09. Don't assume "once approved,
  always approved". Always use the live list.
- Child pages don't inherit protection. `news-archive` is approved; the news items under it are not.

## How to fetch

Auth header: `Authorization: Bearer $MIGRATION_TRACKER_TOKEN`, with the token from `.env`. Send the token **only**
to the tracker and the AEM cookie **only** to the author. Never print either one.

CLI (read-only; importing `aem_lib` loads `.env` on its own):

```bash
cd scripts-hazael
python3 remigracao/ferramentas/tracker.py resumo                       # counts per section + approvals per person
python3 remigracao/ferramentas/tracker.py status /products/boards-modules/iei /about-us/company-profile
python3 remigracao/ferramentas/tracker.py listar whitelist --prefixo /products/boards-modules
python3 remigracao/ferramentas/tracker.py listar blacklist --json /tmp/bl.json
```

`status` also flags pages listed in `paginas_protegidas.txt` (project root). The write lock refuses the **union**
of the tracker blacklist and that file. If the two disagree (for example, a page the tracker no longer lists is still
in the file), report it and ask. Never edit that file yourself.

In Python, writes go through the locked Session, which fetches the blacklist by itself:

```python
from aem_lib import build_session            # scripts-bruno/aem_lib.py
s, auth = build_session(prompt_if_missing=False)
s.blacklist.atual()   # tuple of protected aem_paths, or None if the tracker failed (then the Session refuses every write)
```

For the whitelist in code, reuse `baixar("whitelist")` from `ferramentas/tracker.py`.

## Response format

```json
{"count": 110, "generated_at": "2026-09-28T21:16:41Z", "description": "...",
 "pages": [{"aem_path": "/content/macnicaglobal2/americas/mai/en/about-us/glossary",
            "path": "/about-us/glossary", "title": "Glossary",
            "url": "https://author-…/…/glossary.html?wcmmode=disabled",
            "approved_by": [{"name": "<reviewer>", "approved_at": "2026-09-25T13:52:27.177Z"}]}]}
```

Whitelist entries have the same shape without `approved_by`. Always check `count == len(pages)`.

## Reading the data

- Approver names are tracker accounts, which have nothing to do with AEM accounts. In AEM, only `bruno.jaques` and
  `valter.toffolo` are ours, and people and scripts share them. So `cq:lastModifiedBy` never tells you which person
  or script made a write.
- The first 31 approvals share one timestamp (a bulk import): trust the name, not `approved_at`.
- "Which pages did a past session write that still aren't approved?" Take the automatic backups in
  `scripts-hazael/remigracao/dados/backups_aem/auto/<date_time>_<pid>/`, one per page per write run, and compare
  them with a fresh blacklist.
- The whitelist is a good work queue for read-only audits (`ferramentas/auditoria_padroes.py coletar` fetches it by
  itself). Before *writing*, re-check each page's status, because it may have been approved in the meantime.
