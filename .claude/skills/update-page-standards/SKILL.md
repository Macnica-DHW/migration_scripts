---
name: update-page-standards
description: Turn new feedback about how migrated pages should look into the written standards. The feedback might come from the external verifiers who approve pages, from the team, or from a correction during review. Covers capturing the feedback, classifying it (rule, guideline or one-page fix), checking it against the existing standards and against what global2's components can do, updating page-standards (and CLAUDE.md when needed), making it measurable in the audit tool, and keeping a dated change log. Use whenever the user relays verifier feedback, says "from now on pages should…", or corrects a layout decision in a way that applies beyond one page.
---

# Updating the page standards

`page-standards` is the single written source for how a migrated global2 page should look. It has to keep up with
what the external verifiers say while they approve pages one by one. Every page must pass their review before global2
becomes production. A standard left only in chat is lost at the next session, so every durable piece of feedback
goes through this procedure.

This is a **documentation** task. It changes no page in AEM: applying a new standard to pages is a separate pass,
under the usual rules (fresh blacklist, backup, verify). Don't mix the two in one step.

## 1. Capture the feedback exactly

- Write it down **verbatim**, with the date (dd/mm) and the kind of source: "external verifiers", "team", or "review
  of page X". Don't name individuals. The shared docs never attribute decisions to a person.
- Note the pages it came from (global2 path and GWI path) and what exactly was wrong or right on them. A screenshot
  description or measurement helps: "the video spans 96% of the width", "the band touches the text".
- If the feedback is ambiguous about its **scope** (this page, this family, all pages), ask. One question with
  options is enough.

## 2. Classify it

| Kind | Meaning | Where it goes |
|---|---|---|
| **Rule** | followed strictly, no exceptions (e.g. "end buttons always on white") | the Rules table of `page-standards` **and** the RULES list in `CLAUDE.md` |
| **Standard** | a fixed target, reached by judgment per page (e.g. the 28/09 heading hierarchy) | a numbered section of `page-standards`, and a one-line bullet in `CLAUDE.md` → Guidelines |
| **Guideline** | a default that can be broken when the page gets better, saying why (e.g. band placement) | the Guidelines list of `page-standards` |
| **One-page fix** | applies only to that page | not a standard: record it where the work is tracked (report or handoff) |

Wording like "always" or "never" usually means a rule, and "should" or "ideally" usually means a standard or
guideline. If you can't tell, ask the user instead of guessing: a rule applied as a guideline, or the reverse, causes
wrong writes later.

## 3. Check it against what exists

- **Conflicts:** read `page-standards`, the guidelines in `CLAUDE.md` and the change log. If the new feedback
  contradicts an existing standard, the newer one wins. Say so in the change log ("supersedes …") and rewrite the old
  text; don't leave both. If the conflict looks unintended, ask before overwriting.
- **GWI:** the standard must fit the principle that content = GWI and layout follows GWI, adapted to global2's
  components. If the feedback asks for a *content* change (text, links, images), it isn't a layout standard: raise it
  with the user as a content question.
- **Feasibility in global2:** check that the components can do it before writing the standard. Read the dialog
  (`_cq_dialog`), the policy styles and the site CSS (see `aem-components`), and measure on a real page at 1400px
  with `?wcmmode=disabled`. If it needs a shared resource (XF, policy, template, component code), write it down as
  such: the change then needs "You can edit \<path\>" or developer work.
- **Precedents:** look for pages already approved that follow or break the new standard (`tracker-lists` → blacklist;
  read those pages). If approved pages contradict it, tell the user: approved pages are frozen, and a new standard
  doesn't reopen them by itself.

## 4. Write it into the standards

In `.claude/skills/page-standards/SKILL.md`, give each standard:
- **Target:** what a correct page has, in terms of what the reader sees.
- **Why:** the reason, when known.
- **How to check:** viewport, mode, thresholds in px or %, the tool or the manual check.
- **GWI relation:** whether it follows GWI or deliberately departs from it, and in which cases.
- **Examples:** approved and rejected pages, with paths.
- **Exceptions and judgment calls** already accepted.

Update the frontmatter `description` of `page-standards` if the list of topics changes, so the skill still triggers.
Update `CLAUDE.md` only with the short version (a rule line, or a one-line guideline bullet), because it is loaded in
every session. Update `aem-components` if you learned a component mechanic, and `aem-verify-page` if the check is
manual.

## 5. Make it measurable when possible

If a script can check the standard, extend `scripts-hazael/remigracao/ferramentas/auditoria_padroes.py`: the probe
(`PROBE`) measures, `analisar_pagina` decides, and `relatorio_auditoria_padroes.py` shows it. Test on 3–5 pages that
include at least one that passes and one that fails, all read-only. Compare with the page as you see it before
trusting the numbers. If it can't be automated, add it to the manual checks in `aem-verify-page`.

## 6. Log it

Add an entry at the top of the **Change log** at the end of `page-standards`: date, source kind, what changed, and what
it supersedes. The log shows what's current and why earlier pages may follow an older standard.

## 7. Report back

Tell the user:
- the classification you chose, especially when it was a judgment call;
- the files changed (`page-standards`, `CLAUDE.md`, the tools);
- whether the standard is now measurable;
- optionally, a read-only estimate of how many whitelist pages it affects (`auditoria_padroes.py` for measurable
  standards).

Don't start changing pages until the user asks for that pass. Commit only when asked. The skills and CLAUDE.md are
versioned, so the update reaches everyone who uses the repo.
