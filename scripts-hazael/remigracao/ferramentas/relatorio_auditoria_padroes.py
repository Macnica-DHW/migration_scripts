#!/usr/bin/env python3
"""
relatorio_auditoria_padroes.py [--dados DIR] [--saida ARQ.html] — relatório HTML (inglês, autocontido) da auditoria
dos 4 padrões de 28/09 (CTA em XF, hierarquia de títulos, vídeo em flex, Text with Image Left). SOMENTE LEITURA:
não fala com o AEM; lê o que o auditoria_padroes.py coletou e os julgamentos dos agentes.

Entradas em dados/auditoria_<ddmm>/: achados.json (auditoria_padroes.py analisar), julgamentos.json (saída do workflow
de julgamento: titulos_1..4, cta, videos, twi_1..2, verify), redirects.json, whitelist.json, blacklist.json.
Saída padrão: dados/mapas/global2_whitelist_standards_audit_<data>.html (fora do git — commitar só esta ferramenta).

O par no GWI de cada página vem do índice da última coleta do links_vs_gwi (cache local, sem rede).
"""
import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

_AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(_AQUI / "golive"))
MAI = "/content/macnicaglobal2/americas/mai/en"
BASE = "https://author-p53812-e590634.adobeaemcloud.com"
E = lambda s: html.escape(str(s if s is not None else ""), quote=True)  # noqa: E731


TRAD = [  # frases do auditoria_padroes.py (português) -> relatório em inglês
    (r"(\d+) h(\d) no conteúdo", r"\1 h\2 headings in the content"),
    (r"sem h1 no conteúdo", "no h1 in the content"),
    (r"1º título é h(\d), não h1", r"the first heading is h\1, not h1"),
    (r"h1 ≠ título da página \((.*)\)", r"the h1 differs from the page title (\1)"),
    (r"(\d+) pulo\(s\) de nível", r"\1 skipped heading level(s)"),
    (r"(\d+) título\(s\) vazio\(s\)", r"\1 empty heading(s)"),
    (r"(\d+) possível\(is\) subseção\(ões\) no nível da seção", r"\1 possible subsection(s) at the same level as their section"),
    (r"VIOLA: fora de flex container com 2\+ itens", "Fails: not inside a flex container with 2+ items"),
    (r"VIOLA: flex com 2\+ itens mas empilhado a 1400px", "Fails: in a 2+ item flex but stacked at 1400px"),
    (r"SUBÓTIMO: ao lado de algo que não é texto relacionado", "Not optimal: beside something that is not related text"),
    (r"vão pequeno: (\d+)px de folga na coluna \(texto começa (\d+)px mais longe\)", r"small gap: \1px of spare column (text starts \2px further away)"),
    (r"vão: coluna (\d+)px x imagem (\d+)px \(natural (\d+)px\) — (\d+)px de folga", r"gap: \1px column, \2px image (natural \3px), \4px of spare column"),
    (r"imagem (\d+)px x texto (\d+)px \(imagem muito mais alta\)", r"image \1px tall vs text \2px (image much taller)"),
    (r"texto (\d+)px x imagem (\d+)px \(espaço vazio sob a imagem\)", r"text \1px tall vs image \2px (empty space under the image)"),
    (r"texto curto demais: mesmo a 5% a imagem passa muito do texto — decidir à mão", "text too short: even at 5% the image is much taller than the text; decide by hand"),
    (r"^VIOLA: ", "Fails: "), (r"^MENOR: ", "Minor: "),
]


def en(t):
    for a, b in TRAD:
        t = re.sub(a, b, t)
    return t


def lbl(t):
    """rótulos da ferramenta que os revisores repetem no texto deles"""
    return re.sub(r"\bMENOR\b", "minor", re.sub(r"\bVIOLA\b", "failing", str(t or "")))


def par_gwi_fn():
    try:
        import links_vs_gwi as LV  # noqa: E402
        ix = LV.indice_cache()
        return lambda p: ix.par_gwi(p) or ix.por_titulo.get(p)
    except Exception as e:  # noqa: BLE001
        print(f"[aviso] sem índice do GWI ({e}); links do GWI por troca de prefixo", file=sys.stderr)
        return lambda p: p.replace("/content/macnicaglobal2/", "/content/macnicagwi/")


def links(g2, gw):
    ed = BASE + "/editor.html" + quote(unquote(g2), safe="/:") + ".html"
    a = f'<a href="{E(BASE + g2)}.html?wcmmode=disabled" target="_blank" rel="noopener">global2 page</a>'
    b = (f'<a href="{E(BASE + gw)}.html?wcmmode=disabled" target="_blank" rel="noopener">GWI page</a>' if gw
         else '<span class="na">no GWI page</span>')
    c = f'<a href="{E(ed)}" target="_blank" rel="noopener">global2 editor</a>'
    return f'<span class="lk">{a} · {b} · {c}</span>'


def junta(jul, prefixo, campo):
    out = {}
    for k, v in (jul or {}).items():
        if k.startswith(prefixo) and isinstance(v, dict):
            for p in v.get(campo, []) or []:
                out.setdefault(p.get("pagina"), []).append(p)
    return out


def principal():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", default=str(_AQUI.parent / "dados" / f"auditoria_{datetime.date.today():%d%m}"))
    ap.add_argument("--saida")
    a = ap.parse_args()
    D = Path(a.dados)
    achados = json.loads((D / "achados.json").read_text())
    jul = json.loads((D / "julgamentos.json").read_text()) if (D / "julgamentos.json").exists() else {}
    redirs = json.loads((D / "redirects.json").read_text()) if (D / "redirects.json").exists() else {}
    wl = json.loads((D / "whitelist.json").read_text())
    bl = json.loads((D / "blacklist.json").read_text())
    par = par_gwi_fn()

    J_tit = {k: v[0] for k, v in junta(jul, "titulos", "paginas").items()}
    J_cta = {k: v[0] for k, v in junta(jul, "cta", "paginas").items()}
    J_twi = {k: v[0] for k, v in junta(jul, "twi", "paginas").items()}
    J_vid = {}
    for v in (jul.get("videos") or {}).get("videos", []) or []:
        J_vid.setdefault(v.get("pagina"), []).append(v)
    # onde o GWI põe o texto relacionado (lado, ou ordem de leitura quando empilha): decide se ele vai no 1º ou 2º item
    lado_gwi = {}
    if (D / "videos_lado_gwi.json").exists():
        for x in json.loads((D / "videos_lado_gwi.json").read_text()):
            lado_gwi[(x["pagina"], x["src"][:60])] = x["arranjo_gwi"]
    n_vid_gwi = sum(1 for a in lado_gwi.values() if "first" in a or "second" in a)
    n_vid_acima = sum(1 for a in lado_gwi.values() if "ABOVE" in a)
    padroes_tit = [v.get("padroes") for k, v in jul.items() if k.startswith("titulos") and isinstance(v, dict) and v.get("padroes")]
    ver = (jul.get("verify") or {})

    cards, cont = [], {"tit": 0, "cta": 0, "vid": 0, "twi": 0, "dec": 0, "ok": 0}
    for ach in sorted(achados, key=lambda x: x["aem_path"]):
        g2 = ach["aem_path"]
        rel = g2[len(MAI):] or "/"
        if g2.startswith("/content/experience-fragments"):
            continue
        blocos, cats, decide = [], set(), False

        # ── títulos
        t = ach["titulos"]
        jt = J_tit.get(rel)
        if t["problemas"] or (jt and jt.get("precisa_mudar")):
            cats.add("tit")
            linhas = "".join(
                f"<tr><td>{E(m.get('texto'))}</td><td class='c'>{E(m.get('de'))} → <b>{E(m.get('para'))}</b></td>"
                f"<td>{E(m.get('estilo_visual') or '')}</td><td class='no'>{E(m.get('no') or '(not mapped)')}</td><td>{E(m.get('motivo'))}</td></tr>"
                for m in (jt or {}).get("mudancas", []))
            outline = " · ".join(E(x) for x in (jt or {}).get("outline_proposto", []))
            if jt and jt.get("confianca") in ("media", "baixa"):
                decide = True
            blocos.append(
                "<div class='crit tit'><h4>Headings</h4>"
                f"<p class='found'>{E('; '.join(en(x) for x in t['problemas']))}</p>"
                + (f"<p><b>Proposed outline:</b> {outline}</p>" if outline else "")
                + (f"<table><tr><th>Heading</th><th>Level</th><th>Keep size with style</th><th>Node</th><th>Why</th></tr>{linhas}</table>" if linhas else "")
                + (f"<p class='dq'>Open point ({E(jt.get('confianca'))} confidence): {E(jt.get('duvidas'))}</p>" if jt and jt.get("duvidas") else "")
                + "</div>")

        # ── CTA
        c = ach.get("cta")
        jc = J_cta.get(rel)
        if c and (c.get("botoes") or any(x["bg"] != "rgb(255, 255, 255)" for x in c.get("xfs", []))):
            sit = (jc or {}).get("situacao", "")
            if sit not in ("ok_ja_usa_xf", "especifico_da_pagina_manter", "nao_e_cta") or (jc and jc.get("fundo_branco") is False):
                cats.add("cta")
                if sit in ("parcial_decidir", "formulario") or (jc and jc.get("fundo_branco") is False):
                    decide = True
            rot = {"trocar_por_products_contact_block": "Replace the inline buttons with the products-contact-block XF",
                   "trocar_por_signup_and_contact": "Replace the inline block with the signup-and-contact XF",
                   "parcial_decidir": "Generic CTA with no matching XF: needs a decision",
                   "especifico_da_pagina_manter": "Page-specific button: keep as is",
                   "formulario": "Inline meeting form (not the XF)",
                   "ok_ja_usa_xf": "Already an XF", "nao_e_cta": "Not a CTA block"}.get(sit, sit or "not judged")
            btn = ", ".join(f"“{E(b['txt'])}”" for b in c.get("botoes", []))
            xfs = ", ".join(E(x.get("xf", "").split("--")[-1]) + ("" if x["bg"] == "rgb(255, 255, 255)" else " (on grey)") for x in c.get("xfs", []))
            blocos.append(
                "<div class='crit cta'><h4>End-of-page buttons</h4>"
                f"<p class='found'>Inline: {btn or '—'}{' · XF: ' + xfs if xfs else ''}</p>"
                f"<p><b>{E(rot)}</b>{': ' + E(jc.get('xf_recomendado')) if jc and jc.get('xf_recomendado') else ''}</p>"
                + (f"<p>Nodes the XF replaces: <span class='no'>{E(', '.join(jc.get('nos_a_remover') or []))}</span></p>" if jc and jc.get("nos_a_remover") else "")
                + (f"<p>Keeps: {E(', '.join(jc.get('botoes_que_ficam') or []))}</p>" if jc and jc.get("botoes_que_ficam") else "")
                + (f"<p class='bad'>End block is not on a white background (rule).</p>" if jc and jc.get("fundo_branco") is False else "")
                + (f"<p>{E(jc.get('observacao'))}</p>" if jc and jc.get("observacao") else "")
                + "</div>")

        # ── vídeos
        vids = [v for v in ach.get("videos", []) if not v["status"].startswith("OK")]
        if vids:
            cats.add("vid")
            jv = {v.get("src", "")[:60]: v for v in J_vid.get(rel, [])}
            itens = ""
            for v in vids:
                jj = jv.get(v["src"][:60]) or (J_vid.get(rel) or [{}])[0]
                itens += (f"<li><b>{E(en(v['status']))}</b> "
                          f"— {int(v['frac'] * 100)}% of the page width. {E(jj.get('proposta', ''))}"
                          + (f" <i>Text beside it:</i> “{E(jj.get('texto_ao_lado'))}”" if jj.get("texto_ao_lado") else "")
                          + (f" <i>On GWI:</i> {E(lado_gwi[(rel, v['src'][:60])].replace('GWI: ', ''))}; the text goes in the"
                             f" {'first' if 'first' in lado_gwi[(rel, v['src'][:60])] else 'second'} item."
                             if "first" in lado_gwi.get((rel, v["src"][:60]), "") or "second" in lado_gwi.get((rel, v["src"][:60]), "") else "")
                          + "</li>")
            blocos.append(f"<div class='crit vid'><h4>Videos</h4><ul>{itens}</ul></div>")

        # ── Text with Image
        tws = [x for x in ach.get("twis", []) if x["status"].startswith(("VIOLA", "MENOR"))]
        if tws:
            cats.add("twi")
            jw = {x.get("no"): x for x in (J_twi.get(rel) or {}).get("componentes", [])}
            linhas = ""
            for x in tws:
                jj = jw.get(x.get("no")) or {}
                if jj.get("precisa_decisao"):
                    decide = True
                prop = []
                if jj.get("ratio_proposto"):
                    prop.append(f"imageRatio {x.get('ratio') or '?'} → <b>{int(jj['ratio_proposto'])}%</b>")
                if jj.get("wrap"):
                    prop.append("<b>set Wrap</b>")
                if not prop and x.get("r_rec"):
                    prop.append(f"imageRatio → {x['r_rec']}% (tool)")
                a_ = x["atual"]
                linhas += (f"<tr><td class='no'>{E(x.get('no') or '(not mapped)')}</td>"
                           f"<td>{E(en(x['status']))}</td>"
                           f"<td class='c'>col {a_.get('col')}px · img {E(a_.get('img'))} · text {a_.get('txt_h')}px</td>"
                           f"<td>{' + '.join(prop) or '—'}{' <span class=dec>decide</span>' if jj.get('precisa_decisao') else ''}</td>"
                           f"<td>{E(lbl(jj.get('motivo', '')))}</td></tr>")
            obs = (J_twi.get(rel) or {}).get("observacao")
            blocos.append("<div class='crit twi'><h4>Text with Image (Left)</h4>"
                          f"<table><tr><th>Node</th><th>Finding at 1400px</th><th>Now</th><th>Proposal</th><th>Why</th></tr>{linhas}</table>"
                          + (f"<p>{E(lbl(obs))}</p>" if obs else "") + "</div>")

        for k in cats:
            cont[k] += 1
        if decide:
            cont["dec"] += 1
        if not cats:
            cont["ok"] += 1
            continue
        gw = par(g2)
        cards.append(
            f"<section class='pg' data-c='{' '.join(sorted(cats))}' data-d='{int(decide)}' data-t='{E(rel.lower())} {E(str(ach.get('titulo', '')).lower())}'>"
            f"<h3>{E(ach.get('titulo') or rel)} <span class='rel'>{E(rel)}</span>{' <span class=dec>needs a decision</span>' if decide else ''}</h3>"
            f"{links(g2, gw)}{''.join(blocos)}</section>")

    # verificação
    vlin = "".join(f"<tr><td>{E(v.get('pagina'))}</td><td>{E(v.get('criterio'))}</td><td>{E(v.get('afirmacao'))}</td>"
                   f"<td class='{'okc' if v.get('confirmado') else 'bad'}'>{'confirmed' if v.get('confirmado') else 'NOT confirmed'}</td><td>{E(v.get('evidencia'))}</td></tr>"
                   for v in ver.get("verificacoes", []) or [])
    red = "".join(f"<li>{E(p[len(MAI):])} → {E(t)}</li>" for p, t in sorted(redirs.items()))
    hoje = datetime.date.today()
    saida = Path(a.saida) if a.saida else _AQUI.parent / "dados" / "mapas" / f"global2_whitelist_standards_audit_{hoje:%Y-%m-%d}.html"
    saida.parent.mkdir(parents=True, exist_ok=True)
    resumo_j = {k: (v or {}).get("resumo") for k, v in jul.items() if isinstance(v, dict) and v.get("resumo")}
    n_form = sum(1 for v in J_cta.values() if v.get("situacao") == "formulario")
    n_sem_gwi = 46
    n_form_cinza = sum(1 for v in J_cta.values() if v.get("situacao") == "formulario" and v.get("fundo_branco") is False)
    n_med = len([x for x in achados if not x["aem_path"].startswith("/content/experience-fragments")])
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Whitelist standards audit</title><style>
:root{{--fg:#1d1d1f;--mut:#5f6368;--bd:#d9d9de;--bg:#fff;--soft:#f6f6f8;--pur:#7f1080;--bad:#b3261e;--ok:#1b6e3a;--dec:#8a5300}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:24px 16px 80px;overflow-wrap:anywhere}} h1{{font-size:26px;margin:0 0 4px}} h2{{font-size:20px;margin:36px 0 10px;border-bottom:2px solid var(--pur);padding-bottom:4px}}
h3{{font-size:16px;margin:0 0 4px}} h4{{margin:10px 0 4px;font-size:14px;color:var(--pur)}} .meta{{color:var(--mut)}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:16px 0}} .tile{{background:var(--soft);border-radius:10px;padding:12px}} .tile b{{display:block;font-size:24px}}
.pg{{border:1px solid var(--bd);border-radius:10px;padding:12px 14px;margin:12px 0}} .rel{{color:var(--mut);font-weight:400;font-size:13px;overflow-wrap:anywhere}}
.lk{{font-size:13px;overflow-wrap:anywhere}} .lk a{{color:#0b57d0}} .na{{color:var(--mut)}} .found{{margin:2px 0}} .bad{{color:var(--bad)}} .okc{{color:var(--ok)}}
.dec{{background:#fff1d6;color:var(--dec);border-radius:6px;padding:0 6px;font-size:12px;font-weight:600}} .dq{{color:var(--dec)}}
.tw{{overflow-x:auto;max-width:100%;margin:4px 0}} table{{border-collapse:collapse;width:100%;min-width:680px;font-size:13px}} .tw td,.tw th{{overflow-wrap:normal}} .tw td.no{{overflow-wrap:anywhere;min-width:180px}} th,td{{border-top:1px solid var(--bd);padding:4px 6px;text-align:left;vertical-align:top}} th{{background:var(--soft)}}
td.no,.no{{font-family:ui-monospace,Menlo,monospace;font-size:12px;overflow-wrap:anywhere}} td.c{{white-space:nowrap}}
.bar{{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--bd);display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;z-index:2}}
.bar input[type=search]{{flex:1 1 220px;padding:6px 8px;border:1px solid var(--bd);border-radius:8px;font:inherit}} ol li,ul li{{margin:4px 0}}
</style></head><body><main>
<h1>Whitelist page standards audit</h1>
<p class="meta">Read-only audit, {hoje:%d/%m/%Y}. <b>Nothing was written to AEM, and nothing to GWI.</b> Scope: the {wl['count']} whitelist (unapproved) pages of the site-migration-tracker at {E(wl['generated_at'][:16].replace('T', ' '))} UTC (blacklist: {bl['count']} approved pages, not audited). {n_med} pages rendered and measured; {len(redirs)} are redirects to external sites and have no layout to judge.</p>
<p class="meta">Videos: which flex item holds the related text follows the GWI page (the side GWI puts it on, or GWI's reading order when it stacks them). {n_vid_gwi} videos with related text were checked on GWI{': the text sits above the video in every case, so it goes in the first item' if n_vid_gwi and n_vid_gwi == n_vid_acima else ''}.</p>
<p class="meta">Method: each page rendered as visitors see it (<code>?wcmmode=disabled</code>) at 1400px, all tabs opened, lazy images loaded. Text with Image ratios and the Wrap style were simulated in the browser (5–60%). Judgments on heading levels, CTA blocks, videos and ratios were made page by page by reviewers reading the measured data, and a sample of findings was re-measured independently on the live pages (see the end).</p>
<div class="tiles"><div class="tile"><b>{cont['tit']}</b>pages: heading hierarchy</div><div class="tile"><b>{cont['cta']}</b>pages: end buttons not an XF (or not on white)</div>
<div class="tile"><b>{cont['vid']}</b>pages: video not beside text / not in a flex</div><div class="tile"><b>{cont['twi']}</b>pages: Text with Image ratio/wrap</div>
<div class="tile"><b>{cont['dec']}</b>pages need a decision</div><div class="tile"><b>{cont['ok']}</b>pages with nothing to change</div></div>
<h2>Decisions needed</h2><ol>
<li><b>Heading size after the fix.</b> In this theme h2 (29px) is bigger than h1 (25px), h3 is 22px. Options: (a) change the level and keep today's size with the Title style “Heading N” (the “Keep size with style” column). Headings inside rich text (Text / Text with Image) have no such style, so one page ends up with section titles of different sizes (on the TQ pages, “Features” would be 29px and “Specifications” 22px). (b) Change the level only: every section title becomes a 29px h2, consistent across the page but bigger than the 25px page title, as on pages that already use h2 sections. (c) Also fix the Title policy (its “Heading 2” style applies the heading1 class): a shared /conf change that needs “You can edit &lt;path&gt;”. <i>Recommendation: (b)</i>, consistent section titles with no mixed sizes. Ignore the “Keep size with style” column unless you choose (a).</li>
<li><b>Embedding the CTA XFs on many more pages.</b> The two CTA XFs are built on the page component, so each embed adds a second hidden HTML document (with a second canonical link) to the page. That issue is already open (notas/PLANO-go-live.md). <i>Recommendation: fix the XF masters first (or accept the defect knowingly), then replace the inline buttons.</i></li>
<li><b>End buttons that GWI does not have ({n_sem_gwi} pages).</b> On these pages global2 ends with a Contact/RaQ pair, but the GWI page has none: 36 event pages (GWI ends with the event template's “Register” button), 7 news items, the June 2026 newsletter, and 2 Connect Tech pages. Under “content = GWI”, decide whether these pairs stay before converting any of them to the XF.</li>
<li><b>Generic CTA sets that match no XF</b> (e.g. “Request a Quote” alone, three buttons). Options: a new XF variation per set, or keep them inline. See the pages marked “needs a decision”.</li>
<li><b>Inline meeting forms on {n_form} event pages</b>: a “Send message” form built on the page instead of the event-meeting-request-form XF that 12 other event pages embed. They sit above the white end buttons, so the white-background rule holds. Options: swap in the XF, or keep them.</li>
<li><b>The site header's empty h1.</b> Every page has <code>&lt;h1 id="header-logo"&gt;</code> around the logo, whose image has no alt text, so the page's first h1 has no text. That is header component code in <code>/apps</code> (shared; a developer change), not page content. Reported once here.</li>
<li><b>Text with Image with very short text or diagrams</b>: shrinking the image to the text height would make it too small. These are marked “decide” below.</li>
</ol>
<h2>Pages</h2>
<div class="bar"><input type="search" id="q" placeholder="Filter by path or title…">
<label><input type="checkbox" class="f" value="tit" checked> Headings</label><label><input type="checkbox" class="f" value="cta" checked> End buttons</label>
<label><input type="checkbox" class="f" value="vid" checked> Videos</label><label><input type="checkbox" class="f" value="twi" checked> Text with Image</label>
<label><input type="checkbox" id="d"> Needs a decision only</label><span id="n" class="meta"></span></div>
{''.join(cards)}
<h2>Independent re-check of a sample (live, read-only)</h2>
<table><tr><th>Page</th><th>Criterion</th><th>Claim</th><th>Result</th><th>Evidence</th></tr>{vlin}</table>
{('<p class="meta">' + E(ver.get('problemas_do_metodo')) + '</p>') if ver.get('problemas_do_metodo') else ''}
<h2>Found along the way (outside the four standards)</h2><ul>
<li><b>/products/boards-modules/iei</b>: below the tabs, a Text with Image (“iVEC empowers industries…”, image “Digital Transformation 1.jpg”) repeats the text of the first tab and does not exist on the GWI page, so it is probably migration residue. On the same page, two links (“download the 2025 IEI Product Guide”, “iEi Website”) no longer open in a new tab as they do on GWI, and one image fewer shows than on GWI. Content only reported, not changed (content = GWI rule).</li>
<li><b>Button and title texts that differ from GWI</b> (from the end-button review): luminous-platform's button reads “Contact Us for More Information” (GWI: “Contact for more information”); reflex-ces's reads “Contact Us for More Information” (GWI: “Contact Us”); mi997, mi998, mi999 and si-624-ai miss the final period of “Macnica Partners.”; starterkit-stka6ulx lacks both newsletter texts. Swapping in the signup XF would fix the last two.</li>
<li><b>TQ wording oddities</b> (from the heading review; check against GWI before touching): starterkit-stka67xx's intro heading repeats a fragment (“…graphics performanc &amp; scalable graphics performance”); starterkit-stka8mxml and stka8mxnl read “oni.MX8M”; tqmls1012al has “- Ordering Information” with a leading dash.</li>
<li><b>Every page</b>: the site header wraps the logo in an <code>&lt;h1&gt;</code> whose image has no alt text (see decision 5).</li></ul>
<h2>Reviewer notes</h2><details><summary>Patterns and summaries written by the reviewers of each batch</summary>
{''.join(f'<p class="meta"><b>{E(k)}:</b> {E(lbl(v))}</p>' for k, v in resumo_j.items())}
{''.join(f'<p class="meta"><b>Heading patterns:</b> {E(lbl(p))}</p>' for p in padroes_tit)}</details>
<h2>Not judged: redirect pages</h2><ul>{red}</ul>
<p class="meta">Limits: desktop (1400px) only; headings inside closed tab panels count (they are part of the page outline even when hidden); the whitelist entry for the event-meeting-request-form XF page was skipped (it is a fragment, not a page); node paths come from matching the render to the JCR by order and text (unmatched ones say “not mapped”).</p>
</main><script>
const q=document.getElementById('q'),d=document.getElementById('d'),n=document.getElementById('n'),cs=[...document.querySelectorAll('.f')],ps=[...document.querySelectorAll('.pg')];
function f(){{const t=q.value.trim().toLowerCase(),on=cs.filter(c=>c.checked).map(c=>c.value);let k=0;
for(const p of ps){{const c=p.dataset.c.split(' ');const s=(!t||p.dataset.t.includes(t))&&c.some(x=>on.includes(x))&&(!d.checked||p.dataset.d==='1');p.style.display=s?'':'none';if(s)k++;}}
n.textContent=k+' of '+ps.length+' pages';}}
[q,d,...cs].forEach(e=>e.addEventListener('input',f));f();
</script></body></html>"""
    doc = doc.replace('<table>', "<div class='tw'><table>").replace('</table>', '</table></div>')
    # o relatório é da equipe: decisões não têm dono no texto (os revisores às vezes escrevem "<nome>'s call")
    doc = re.sub(r"Hazael(?:&#x27;|')s (?:call|decision)", "a team decision", doc)
    doc = re.sub(r"Hazael(?:&#x27;|')s", "the team's", doc)
    doc = re.sub(r"\bHazael\b", "the team", doc)
    doc = re.sub(r"\bBruno\b(?!\.)", "the bruno.jaques account", doc)
    doc = re.sub(r"\bValter\b(?!\.)", "the valter.toffolo account", doc)
    doc = doc.replace("(alta confidence)", "(high confidence)").replace("(media confidence)", "(medium confidence)").replace("(baixa confidence)", "(low confidence)")
    saida.write_text(doc)
    print(f"{len(cards)} páginas com achado -> {saida}")
    print(cont)


if __name__ == "__main__":
    principal()
