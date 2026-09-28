---
name: session-handoff
description: Start a work session, resume what another session or person was doing, or hand work over when the context window is filling up. Covers the start-of-session checklist (git, other sessions, cookie, tracker, latest handoff), finding what a past session wrote (auto-backups, commits, transcripts), writing a HANDOFF note in notas/ and passing it to the next session, where durable knowledge must go so it isn't lost, and which docs and tools are stale. Use at the start of a session, when told to "continue" or "pick up" earlier work, and before the context runs out.
---

# Starting, resuming and handing over work

Knowledge gets lost between sessions when it lives only in chat, in `/tmp` scratchpads or in one person's memory.
Durable knowledge belongs in `CLAUDE.md`, in `.claude/skills/` and in versioned tools. Session state belongs in
`scripts-hazael/remigracao/notas/` (not versioned, but on disk for the next session).

## Start of a session (5 minutes, read-only)

```bash
git log --oneline -15; git status --short                   # unknown commits or files = another session/person
ps -eo pid,lstart,args | grep -E "[p]ython3 .*(ferramentas|golive|aem_)"   # someone writing right now? (bracket trick)
ls -t scripts-hazael/remigracao/notas/ | head               # latest HANDOFF-*, ONDE-PAREI*, PLANO-*
ls -la --time-style=+%F_%H:%M .env                          # cookie age (~8h life), then one GET: see aem-operate
cd scripts-hazael && python3 remigracao/ferramentas/tracker.py resumo    # fresh blacklist/whitelist counts
```

Then read the newest handoff or plan for the topic. Check that its "pending" items are still pending, using fresh
data (re-collect rather than trust a snapshot). Pages get approved, and people edit by hand.

## Resuming someone else's work

- **What did a past session write?** Every write run through `aem_lib` leaves one backup per page in
  `scripts-hazael/remigracao/dados/backups_aem/auto/<YYYY-MM-DD_HHMMSS>_<pid>/`. Older tools left theirs in
  `dados/golive/backup_*/` plus `manifesto*.jsonl`. Commits say `GRAVADO no AEM`. Compare those pages with a fresh
  blacklist to see which are approved (frozen) and which are still open.
- **Was it changed since?** GET `<page>/jcr:content.json` → `cq:lastModified[By]`. People and scripts share
  our two AEM accounts (`bruno.jaques`, `valter.toffolo`), so compare the timestamps with the backups and commits. Only edits made **today** by others
  block you.
- **What was said?** Session transcripts are JSONL files in the Claude config dir
  (`~/.claude*/projects/-home-<user>-projects-migration-scripts/*.jsonl`). Take the user's messages (`type=user`,
  text blocks) and the assistant's text replies; skip tool results. Sessions resumed from others repeat history, so
  dedupe by `uuid`. **Transcripts can contain secrets** (a token was once pasted into chat): never copy values out of
  them.
- **Scratchpad tools** from past sessions live in `/tmp/claude-*/…/scratchpad/` until the machine cleans `/tmp`. If
  one is worth keeping, move it into `scripts-hazael/remigracao/ferramentas/`, generalized and documented, and
  commit it (`NO CÓDIGO`). That's how `ferramentas/pagina/` came to exist.

## Handing over (context filling up, or end of day)

1. Write `scripts-hazael/remigracao/notas/HANDOFF-<topic>-<YYYY-MM-DD>.md`:
   - **State:** what's done, with commits, backup folders, and the pages written vs approved.
   - **In flight:** what's half-done, and exactly where to resume (page, step, command).
   - **Pending decisions:** numbered, each with a recommendation. Say which ones are still unanswered.
   - **Tools** used and how to run them. Paths only, never secrets.
   - **Traps** hit in this session that aren't in the skills yet.
   - **First task** for the next session.
2. If the next session is already open (the user told it to "wait for instructions"), find it with `ListAgents` and send
   the handoff path and the first task with `SendMessage`. Remind it of the rules: fresh blacklist, backup, never
   GWI, shared resources need "You can edit \<path\>".
3. If you learned something **durable** (a rule, a guideline, an AEM fact, a tool), put it in `CLAUDE.md` or the
   right skill. The per-user memory under `~/.claude*/` helps only that user, and a handoff note is read once.
4. Commit what should be committed (code, backups, manifests, skills) when asked. Handoffs, plans and reports stay out
   of git.

## Docs and tools that are stale (don't follow them blindly)

- `scripts-hazael/README.md`: its "Ordem recomendada" describes the 17–18/09 copia-teste cleanup, and it mentions a
  `--permitir-escrita-global2` flag that no longer exists.
- `remigracao/REGRAS-disposicao.md` stops at R62 (21/09). Later principles live in `page-standards` and in
  `notas/PLANO-altera-look-and-feel.md`. R36/R46/R50 (Text with Image sizing) and R53 (automatic bands) are superseded.
- `ROTEIRO-revisor.md` / `PROMPT-conferencia-visual.md` / `CONFERIDAS.md` target the copia-teste tree and "match
  GWI's layout". Still valid: read-only reviewers, 1400px, arrangement over width, and reporting a good page as good.
  Approval status now comes from the tracker.
- Tools hard-wired to the copia-teste tree (`jcr.py`, `prints.sh`, `faixas.py`, `lado.py`, `serie_twi.py`,
  `xf_lado_a_lado.py`, …) need a path option before use on global2. Go-live one-shots in `golive/` (staging,
  copying families, rewriting refs) are done: don't re-run them. **Never** run the remigration engine
  (`aem_remigrar.py`) on global2.

## Where things are

| What | Where |
|---|---|
| Rules, guidelines, workflow | `CLAUDE.md` |
| How-to | `.claude/skills/*/SKILL.md` |
| Current tools | `scripts-hazael/remigracao/ferramentas/` (`tracker.py`, `auditoria_padroes.py`, `pagina/`, `clicar_ancoras.py`, `golive/…`) |
| Session docs (not in git) | `scripts-hazael/remigracao/notas/` |
| Tool outputs, reports (not in git) | `scripts-hazael/remigracao/dados/` (`mapas/`, `auditoria_<ddmm>/`, `paginas/`) |
| AEM backups (in git) | `scripts-hazael/remigracao/dados/backups_aem/`, `dados/golive/backup_*` |
| Final link map (the scope) | `dados/mapas/global2_link_map_complete_<date>.html` (533 pages = tracker blacklist + whitelist) |
