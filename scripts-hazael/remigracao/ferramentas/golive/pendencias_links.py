#!/usr/bin/env python3
"""
pendencias_links.py [RELATORIO_JSON] — relatório HTML (em inglês, para mandar) do que AINDA falta nos links das páginas do
mapa final do macnicaglobal2, depois dos consertos de 24/09 (corrigir_links.py, grupos A/D/E).

OFFLINE: lê a coleta NOVA do links_vs_gwi.py (o JSON do relatório e o cache jcr_cache_links_vs_gwi.pkl) — nada de rede,
nada gravado. Cada achado da coleta é classificado pela tabela CLASSES abaixo (o diagnóstico feito à mão em 24/09);
achado que a tabela não conhece vai para "Not reviewed yet" — é para olhar, não para esconder. Por cima da comparação
com o GWI, confere o que ela não pega: link interno de TEXTO sem .html (403 no clique) e alvo interno inexistente.

Pedido do Hazael (24/09/2026): "Give me an HTML report of the pages that still need fixing after we fixed those 52 pages."

    python3 links_vs_gwi.py --saida global2_links_vs_gwi_<data>_pos     # coleta nova (só GET)
    python3 pendencias_links.py dados/mapas/global2_links_vs_gwi_<data>_pos.json
"""
import collections
import datetime
import html
import json
import pickle
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import links_vs_gwi as LV  # noqa: E402

M = "/content/macnicaglobal2/americas/mai/en"
NEWS, NL, EV = "about-us/news-events/news-archive", "about-us/newsletter", "about-us/news-events/events-archive"

CATS = {   # chave: (título, o que é preciso)
    "add": ("Add a link to an element that is already there",
            "The text, title or image is on the page but is not clickable; the GWI links it. Making it clickable does not change "
            "the layout (a linked title looks the same as an unlinked one)."),
    "event": ("Event website link",
              "The GWI shows the event name as a link to the event’s website; global2 dropped that line because it repeats the "
              "page title. Either link the page title (nothing looks different) or bring the line back (one line longer)."),
    "dest": ("Destination not in global2 yet",
             "The right destination is a page or file that does not exist in global2 yet; it has to be created or copied first."),
    "decide": ("Needs a decision",
               "The GWI link itself is wrong or points somewhere that should not be copied, or copying it would change more than "
               "the link."),
    "content": ("Content missing from the page",
                "The GWI page has content with these links that the global2 page does not have at all. Fixing it means adding "
                "blocks, which changes the layout."),
    "new": ("Not reviewed yet", "Found by today’s comparison but not in the list reviewed on 24/09 — to be looked at."),
}
EVENTOS = {"2015-04-14-nab-show-2015", "2015-09-12-ibc-2015", "2016-04-19-nab-show-2016", "2016-08-18-intel-isdf-2016",
           "2016-09-10-ibc-2016", "2017-09-16-ibc-2017", "2019-02-06-ise-2019", "2019-04-09-nab-show-2019",
           "2019-06-12-infocomm-2019"}

# (categoria, página rel, regex do texto do link, nota) — a 1ª que casar vale; "fora" = conferido, não é pendência
CLASSES = [
    ("add", f"{NEWS}/macnica-ships-mep100-smartnic-solution-as-ibc2024-approaches", r"^Files available for download",
     "The heading is on the page (a title); the GWI links it to the datasheet PDF."),
    ("add", "products/boards-modules/iei/iei-intelligent-body-temperature-monitoring-solution", r"^Download Brochure",
     "global2 shows it as an image of a “Download Brochure” button, without a link."),
    ("add", "products/boards-modules/iei/iei-smart-healthcare-panel-pcs-terminals-and-computing", r"^Line-up of Panel PC",
     "The heading is on the page (a title) without a link."),
    ("add", f"{EV}/2018-04-10-the-vision-show", r"visionshow\.org", "The URL is on the page as a title, without a link."),
    ("add", f"{EV}/2019-06-26-embedded-technologies-expo-conference", r"^Embedded Technologies Expo",
     "The event name is in the event details, without a link."),
    ("add", f"{EV}/2023-03-28-isc-west-2023", r"conta\.cc", "The URL is in the event details, without a link."),
    ("fora", f"{NL}/macnicas-medical-healthcare-solutions", r"^Learn More",
     "opens the blog post that exists in global2 under a longer name than the GWI’s (…-hospital-equipment; fixed 24/09)"),
    ("dest", "products", r"Linecard", "The linecard PDF is not in the global2 DAM; the link still opens the GWI’s file."),
    ("dest", "products/boards-modules/iei/iei-networking-servers", r"Networking & Servers Brochure",
     "The brochure PDF is not in the global2 DAM; the button opens its own page."),
    ("decide", f"{NEWS}/2016-02-16-macnica-demonstrates-video-transport-over-ip-interoperability-at", r"macnica-na\.com",
     "The GWI sends “www.macnica-na.com” to the Chinese APAC site (/apac/cytech/zh); global2 opens the Americas home page."),
    ("decide", f"{NEWS}/2018-02-13-macnica-americas-expands-value-added-services-for-displays", r"valueadd",
     "The GWI’s destination (macnica-value-add-services-for-displays) does not exist in the GWI either; global2 opens the "
     "Displays page."),
    ("decide", f"{NEWS}/ienso-to-showcase-generative-ai-at-the-edge-ces2025", r"submit your request",
     "The GWI links to a test page (/test-folder/CES-2025); in global2 the sentence is part of a title."),
    ("decide", "about-us/privacy-policy/privacy-policy-for-california-residents", r"zipteam",
     "In global2 the domain is inside a title (“Zipteam service ( www.zipteam.com )”); a link would make the whole line "
     "clickable, not just the domain."),
    ("content", "products", r".", "The four category cards (Semiconductors, Boards & Modules, Displays, IP & Software) are "
     "blank: four image components with no image, caption or link."),
    ("content", "products/boards-modules/connect-tech", r"Jetson AGX Xavier",
     "The tab text that lists the NVIDIA Jetson AGX Xavier is missing."),
    ("content", "products/boards-modules/iei/iei-smart-healthcare-panel-pcs-terminals-and-computing", r"FIT1|Surgical",
     "Two tables are missing: the FIT1 panel PCs and the 27\" surgical monitors."),
    ("content", "solutions/robotics-amrs", r"Robotics Solutions Brief",
     "The download button is missing, and the PDF is not in the global2 DAM."),
    ("content", "products/boards-modules/tq-systems/tq-embedded-arm-modules/mba8mp-ras314-single-board-computer", r"whitepaper",
     "The paragraph with the whitepaper link is missing, and the PDF is not in the global2 DAM."),
    ("content", "products/boards-modules/transcend", r"Memory Product Portfolio",
     "The button that jumps to the product portfolio (#productportfolio) is missing."),
    ("content", "products/boards-modules/tq-systems/tq-embedded-x86-modules", r".",
     "The contact block (Contact Us for More Information / Request a Quote) is missing."),
    ("content", "products/boards-modules", r"Request a Quote", "The contact block has no “Request a Quote” button."),
    ("content", "solutions/broadcast-proav-solutions/st-2110-at-scale-resources", r".",
     "The contact block with “Request Evaluation Kit” is missing."),
    ("content", "products/boards-modules/ibase/embedded-computing/mb991", r".",
     "The newsletter block (“Stay up to date on the latest news from Macnica Partners.” / Sign up) is missing."),
    ("fora", "products/boards-modules/ibase", r"EC-7100", "shown by a list on the page"),
    ("fora", "error", r"RETURN TO HOMEPAGE", "the button is right; the GWI’s second link goes to the APAC galaxy site"),
    ("fora", "products/semiconductors/analog-devices/analog-devices-lidar-development-kit", r".",
     "the GWI does not show its contact block either"),
    ("fora", "products/boards-modules/tq-systems/tq-embedded-arm-modules/tqma93xxla-embedded-cortex-a53-module", r"invisible",
     "invisible link (no text) on the GWI"),
    ("fora", "products/boards-modules/terasic/terasic-apollo-s10-som", r"^\(image\)",
     "the GWI links the images to files on the old www2.macnica.com site"),
    ("fora", f"{NEWS}/macnica-americas-introduces-100-gbps-mep100-smartnic-with-mac-compatibility", r"macnica\.com/mep100",
     "differs from the GWI on purpose: the GWI’s URL is dead (404), global2 opens the MEP100 page (24/09)"),
    ("fora", f"{NEWS}/2024-02-15-macnica-americas-welcomes-sebastien-dignard-as-president", r"Macnica Fuji",
     "kept as on the GWI (https://www.macnica.com/, on hold)"),
    ("fora", f"{NEWS}/ienso-to-showcase-generative-ai-at-the-edge-ces2025", r"^www\.macnica\.com",
     "kept as on the GWI (https://www.macnica.com/, on hold)"),
]


def classificar(rel, txt):
    for cat, pag, rx, nota in CLASSES:
        if rel == pag and re.search(rx, txt, re.I):
            return cat, nota
    if rel.startswith(EV + "/") and rel.split("/")[-1] in EVENTOS:
        return "event", "The event name above the details is not on the page; the page title is the same text."
    return "new", ""


def main():
    rel_json = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted(LV.MAPAS.glob("global2_links_vs_gwi_*_pos.json"))[-1]
    rel = json.loads(rel_json.read_text(encoding="utf-8"))
    b = pickle.loads(LV.CACHE.read_bytes())
    assert b["quando"] == rel["quando"], ("o cache não é desta coleta", b["quando"], rel["quando"])
    idx = LV.Indice(b)
    dam = {unquote(p) for p in b.get("dam_g2", [])}

    achados = []                                           # (rel, item)
    for r in rel["paginas"]:
        p = r["g2"][len(M) + 1:] if r["g2"] != M else ""
        for it in r["div"]:
            achados.append((p, {"txt": it["txt"], "agora": it["agora"], "deveria": it["deveria"], "gwi": it["gwi"],
                                "via": it["via"]}))
        for it in r["faltando"]:
            achados.append((p, {"txt": it["txt"], "agora": "", "deveria": it["deveria"], "gwi": it["href"], "via": it["via"]}))
        # o que a comparação não pega: link de texto sem .html (403 no clique) e alvo interno que não existe
        for ln in LV.links_de(b["jcr"][r["g2"]], "jcr:content", [], collections.Counter()):
            a = LV.alvo(ln["href"])
            h = html.unescape(ln["href"]).strip()
            if a["kind"] == "pagina" and a["site"] == "macnicaglobal2":
                q = idx.g2_n.get(LV.nrel(a["rel"])) if a["rel"] else None
                morto = not q or LV.Indice._morta(idx.g2[q])
                sem_html = not LV.PROP_LINK.search(ln["prop"]) and not re.split(r"[?#]", h, 1)[0].endswith(".html")
                if morto or sem_html:
                    achados.append((p, {"txt": ln["txt"], "agora": h, "deveria": "", "gwi": "", "via": "",
                                        "extra": "destination does not exist in global2" if morto else "no .html (403 when clicked)"}))
            elif a["kind"] == "dam" and a["site"] == "macnicaglobal2" and a["rel"].startswith(LV.DAM_G2) and a["rel"] not in dam:
                achados.append((p, {"txt": ln["txt"], "agora": h, "deveria": "", "gwi": "", "via": "",
                                    "extra": "file does not exist in the global2 DAM"}))

    # o IMX711 vem só do teste de alvo morto: entra em "dest" com a nota própria
    CLASSES.insert(0, ("fora", f"{NL}/macnica-technology-update-june-2026", r"IMX711",
                       "kept as is by decision (24/09): the Sony IMX711 page is not in global2’s Americas site yet; Sony "
                       "pages are the Anion’s"))
    por = collections.defaultdict(lambda: collections.defaultdict(list))
    fora, vistos = [], set()
    for p, it in achados:
        chave = (p, it["txt"], it["agora"], it["gwi"])
        if chave in vistos:
            continue
        vistos.add(chave)
        cat, nota = classificar(p, it["txt"])
        it["nota"] = nota
        if cat == "fora":
            fora.append((p, it))
        else:
            por[cat][p].append(it)

    quando = rel["quando"]
    n_links = {c: sum(len(v) for v in por[c].values()) for c in CATS}
    paginas = {p for c in por for p in por[c]}

    def titulo(p):
        jc = b["jcr"].get(f"{M}/{p}" if p else M) or {}
        return re.sub(r"\s+", " ", jc.get("pageTitle") or jc.get("jcr:title") or p.rsplit("/", 1)[-1]).strip()

    def editor(p):
        jc = b["jcr"].get(f"{M}/{p}" if p else M) or {}
        return (jc.get("cq:lastModifiedBy") or "").split("@")[0].replace(".", " ").title()

    def gwi_de(p):
        return idx.par(f"{M}/{p}" if p else M)

    def dd_link(u):
        if not u:
            return ""
        a = LV._alink(u, u[len(M):] if u.startswith(M + "/") else u)
        return a

    def item(cat, it):
        agora = (f'<dd class="agora">{dd_link(it["agora"])}</dd>' if it["agora"] else
                 f'<dd>{"(missing on the page)" if cat == "content" else "(not a link)"}</dd>')
        dev = it.get("deveria") or ""
        linhas = f"<dt>Now</dt>{agora}"
        if it.get("gwi"):
            linhas += f'<dt>GWI link</dt><dd>{dd_link(it["gwi"])}</dd>'
        if dev and cat in ("add", "event", "content") and dev != it.get("gwi"):
            linhas += f'<dt>Should be</dt><dd class="dev">{dd_link(dev)}</dd>'
        via = f' <span class="via">in the GWI’s {html.escape(it["via"].split("/site/")[-1].rsplit("/", 1)[0])} block</span>' if it["via"] else ""
        extra = f'<span class="nota">{html.escape(it["extra"])}</span>' if it.get("extra") else ""
        busca = html.escape(f"{it['txt']} {it['agora']} {it.get('gwi', '')}".lower(), quote=True)
        return (f'<div class="lk" data-p="{cat}" data-s="{busca}"><div class="t">“{html.escape(it["txt"])}”{via}{extra}</div>'
                f"<dl>{linhas}</dl></div>")

    corpo, nav = [], []
    for cat in CATS:
        if not por[cat]:
            continue
        tit, expl = CATS[cat]
        nav.append(f'<a href="#{cat}">{html.escape(tit)} ({n_links[cat]})</a>')
        corpo.append(f'<section class="sec"><h2 id="{cat}">{html.escape(tit)}<span class="n">{n_links[cat]} link'
                     f'{"s" if n_links[cat] != 1 else ""} on {len(por[cat])} page{"s" if len(por[cat]) != 1 else ""}</span></h2>'
                     f'<p class="intro">{html.escape(expl)}</p>')
        for p in sorted(por[cat]):
            its = por[cat][p]
            nota = next((i["nota"] for i in its if i["nota"]), "")
            w = gwi_de(p)
            corpo.append(f'<details class="pg" open><summary>{html.escape(titulo(p))}<span class="n">{len(its)} link'
                         f'{"s" if len(its) != 1 else ""} · last edited by {html.escape(editor(p))}</span></summary>'
                         f'<div class="abre">{LV._alink(f"{M}/{p}.html?wcmmode=disabled" if p else f"{M}.html?wcmmode=disabled", "global2 page")}'
                         + (LV._alink(f"{w}.html?wcmmode=disabled", "GWI page") if w else "")
                         + f'<span class="p">/{html.escape(p)}</span></div>'
                         + (f'<p class="oque">{html.escape(nota)}</p>' if nota else "")
                         + "".join(item(cat, it) for it in its) + "</details>")
        corpo.append("</section>")

    caixas = " ".join(f'<label><input type="checkbox" value="{c}" checked> {html.escape(CATS[c][0])} ({n_links[c]})</label>'
                      for c in CATS if n_links[c])
    linhas = "".join(f'<tr><td><a href="#{c}">{html.escape(CATS[c][0])}</a></td><td class="num">{n_links[c]}</td>'
                     f'<td class="num">{len(por[c])}</td></tr>' for c in CATS if n_links[c])
    fora_html = "".join(f"<li>/{html.escape(p)} — “{html.escape(it['txt'][:70])}”: {html.escape(it['nota'])}</li>"
                        for p, it in sorted(fora, key=lambda x: x[0]))
    css = LV.CSS + """
.intro{color:var(--mut);margin:0 0 10px}.oque{margin:8px 0 2px;font-size:14px}
.via{font-size:12px;color:var(--mut);font-weight:400;margin-left:6px}
.nota{display:inline-block;font-size:12px;font-weight:500;background:var(--badbg);color:var(--bad);border-radius:10px;padding:1px 8px;margin-left:8px}
.agora a{color:var(--bad)}.fora li{margin:3px 0}
"""
    pagina = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>global2 link fixes pending</title><style>{css}</style></head><body><main>
<h1>global2 links still to fix</h1>
<p class="sub">Pages of the macnicaglobal2 link map (Americas / MAI / EN) that still have link problems after the fixes of 24/09
(see global2_link_fixes_2026-09-24.html). Based on a fresh comparison of the {len(rel['paginas'])} pages with their GWI pages, {html.escape(quando)}.
Links open in the AEM author in a new tab; you must be logged in.</p>
<div class="resumo">
<div><b>{sum(n_links.values())}</b><span>links still to fix</span></div>
<div><b>{len(paginas)}</b><span>pages</span></div>
<div><b>{n_links['add'] + n_links['event']}</b><span>can be fixed without adding content (links on existing elements)</span></div>
<div><b>{n_links['content']}</b><span>need content that is missing from the page</span></div></div>
<table><thead><tr><th>What is needed</th><th class="num">Links</th><th class="num">Pages</th></tr></thead><tbody>{linhas}</tbody></table>
<div class="barra"><input id="q" type="search" placeholder="Filter by link text or path…" autocomplete="off"> {caixas}
<nav>{' '.join(nav)}</nav></div>
{''.join(corpo)}
<footer><p><b>Checked, no action needed</b> ({len(fora)}):</p><ul class="fora">{fora_html}</ul>
<p>Paths are relative to <code>{M}</code>. “Now” is where the global2 link goes today; “GWI link” is the matching link on
the GWI page. Only GET requests were made for this report; nothing was changed.</p></footer>
</main><script>{LV.JS}</script></body></html>
"""
    saida = LV.MAPAS / f"global2_links_pending_{quando[:10]}.html"
    saida.write_text(pagina, encoding="utf-8")
    print(f"{sum(n_links.values())} links em {len(paginas)} páginas: {n_links}; fora {len(fora)} -> {saida}")
    for p, its in por["new"].items():
        for it in its:
            print(f"  NOVO /{p}: “{it['txt'][:60]}” agora={it['agora'][-70:]} gwi={it.get('gwi', '')[-70:]} {it.get('extra', '')}")


if __name__ == "__main__":
    main()
