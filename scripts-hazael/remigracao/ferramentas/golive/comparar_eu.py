#!/usr/bin/env python3
"""
comparar_eu.py — SOMENTE LEITURA. Compara a disposição (componentes, estilos, layout) das páginas do global2 Américas
(americas/mai/en, as páginas do mapa de links final) com as da Europa (eu/atd-europe/en). O conteúdo é de cada região;
o que se compara é COMO a página é montada.

Pedido do Hazael (25/09/2026): "do a read only pass comparing the global2 america and europe pages. First check if both
have equivalent pages. Then, I need you to make a detailed report comparing their layouts … the europe version is much
cleaner and better looking overall. I want you to check all pages and their europe counterparts to report the
differences in components used and layout."

Só GET, só no author (o cookie vai só para o base_url; o print bloqueia qualquer outro host).
  coleta  jcr:content.infinity.json das páginas da Europa (as das Américas vêm do cache da última coleta do
          links_vs_gwi), a structure dos templates dos dois sites e os rótulos dos estilos (policies) -> dados/eu/coleta.pkl
  censo   por página: tipo (template + seção), componentes, estilos, profundidade, fundos, títulos -> dados/eu/censo.json

    python3 comparar_eu.py coleta
    python3 comparar_eu.py censo
"""
import collections
import concurrent.futures as cf
import json
import pickle
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import links_vs_gwi as LV  # noqa: E402  (get com cookie só no author, CACHE da coleta)

AM = "/content/macnicaglobal2/americas/mai/en"
EU = "/content/macnicaglobal2/eu/atd-europe/en"
TESTE_EU = ("anion-test-folder", "testing-properties")          # pastas de teste da Europa: fora
PASTA = Path(__file__).resolve().parents[2] / "dados" / "eu"
COLETA = PASTA / "coleta.pkl"
TPL = "/conf/macnicaglobal2/settings/wcm/templates"


def json_de(path):
    r = LV.get(path)
    return r.json() if r.status_code == 200 else r.status_code


def coleta():
    PASTA.mkdir(parents=True, exist_ok=True)
    r = LV.get("/bin/querybuilder.json", params={"path": EU, "type": "cq:Page", "p.limit": "-1", "p.hits": "selective",
               "p.properties": "jcr:path jcr:content/deleted"})
    assert r.status_code == 200, r.status_code
    eu = [EU] + sorted(h["jcr:path"] for h in r.json()["hits"] if not (h.get("jcr:content") or {}).get("deleted")
                       and not h["jcr:path"][len(EU) + 1:].startswith(TESTE_EU) and h["jcr:path"] != EU)
    with cf.ThreadPoolExecutor(4) as ex:
        jcr = dict(zip(eu, ex.map(lambda p: json_de(f"{p}/jcr:content.infinity.json"), eu)))
    b = pickle.loads(LV.CACHE.read_bytes())
    am = [p for p in b["escopo"] if p.startswith(AM)]
    faltam = [p for p in am if not isinstance(b["jcr"].get(p), dict)]
    for p in faltam:
        b["jcr"][p] = json_de(f"{p}/jcr:content.infinity.json")
    r = LV.get("/bin/querybuilder.json", params={"path": "/conf/macnicaglobal2", "property": "cq:styleId",
               "property.operation": "exists", "p.limit": "-1", "p.hits": "selective",
               "p.properties": "jcr:path cq:styleId cq:styleLabel cq:styleClasses"})
    estilos = {}
    for h in r.json()["hits"]:
        m = re.search(r"/components/content/([^/]+)/", h["jcr:path"])
        estilos[h["cq:styleId"]] = {"comp": m.group(1) if m else "?", "rotulo": h.get("cq:styleLabel"),
                                    "classes": h.get("cq:styleClasses")}
    tpls = {}
    for t in ("mai-page-content", "mai-page-top", "mai-mae-product-page", "mai-technical-article-page",
              "atd-europe-page-content", "atd-europe-page-top", "atd-europe-mae-product-page", "atd-europe-technical-article-page"):
        tpls[t] = json_de(f"{TPL}/{t}/structure/jcr:content.infinity.json")
    dados = {"quando": b["quando"], "am": {p: b["jcr"][p] for p in am}, "eu": jcr, "estilos": estilos, "templates": tpls}
    COLETA.write_bytes(pickle.dumps(dados))
    ruins = [p for p, j in jcr.items() if not isinstance(j, dict)]
    print(f"Europa: {len(eu)} páginas ({len(ruins)} sem JSON: {ruins[:5]}); Américas: {len(am)} (relidas {len(faltam)}); "
          f"{len(estilos)} estilos; templates {[(t, isinstance(v, dict)) for t, v in tpls.items()]} -> {COLETA}")


# ---------------------------------------------------------------- censo
def tipo_de(site, rel, jc):
    """Tipo de página pelo template e pela seção — o que dá para comparar entre regiões com conteúdo diferente."""
    t = (jc.get("cq:template") or "").rsplit("/", 1)[-1]
    rt = (jc.get("sling:resourceType") or "").rsplit("/", 1)[-1]
    p = rel.split("/")
    if not rel:
        return "home"
    if p[0] == "about-us" and len(p) >= 3 and p[1] == "news-events":
        return "event" if p[2] in ("events-archive", "events") else "news"
    if p[0] == "about-us" and len(p) >= 2 and p[1] == "newsletter":
        return "newsletter issue"
    if p[0] == "products" and len(p) >= 2:
        prof = len(p) - (2 if p[1] in ("semiconductors", "boards-modules", "boards-and-modules") else 1)
        if len(p) == 2:
            return "product category"
        return {1: "supplier", 2: "product family / product"}.get(prof, "product")
    if p[0] == "solutions":
        return "solutions" if len(p) == 1 else "solution"
    return "other (landing, about, contact…)"


def componentes(j, prof=0, out=None):
    out = out if out is not None else []
    for k, v in j.items():
        if isinstance(v, dict) and k != "cq:responsive":
            rt = v.get("sling:resourceType") or ""
            if rt:
                out.append((prof, k, rt.split("/components/")[-1], v))
            componentes(v, prof + 1, out)
    return out


def censo():
    d = pickle.loads(COLETA.read_bytes())
    est = d["estilos"]
    linhas = []
    for site, base, pags in (("am", AM, d["am"]), ("eu", EU, d["eu"])):
        for p, jc in pags.items():
            if not isinstance(jc, dict):
                continue
            rel = p[len(base) + 1:] if p != base else ""
            cs = componentes(jc.get("root", {}))
            tipos = collections.Counter(rt.rsplit("/", 1)[-1] for _, _, rt, _ in cs)
            estilos = collections.Counter(f'{est.get(s, {}).get("comp", "?")}:{est.get(s, {}).get("rotulo", s)}'
                                          for _, _, _, v in cs for s in v.get("cq:styleIds", []) if s)
            titulos = collections.Counter(v.get("type") or "(default)" for _, _, rt, v in cs if rt.endswith("/title"))
            linhas.append({
                "site": site, "rel": rel, "tipo": tipo_de(site, rel, jc),
                "template": (jc.get("cq:template") or "").rsplit("/", 1)[-1],
                "page_rt": (jc.get("sling:resourceType") or "").rsplit("/", 1)[-1],
                "n": len(cs), "prof_max": max((pr for pr, *_ in cs), default=0),
                "comp": dict(tipos), "estilos": dict(estilos), "titulos": dict(titulos),
                "fundos": sorted({v.get("backgroundColor") for *_, v in cs if v.get("backgroundColor")}),
                "wrap": sum(1 for _, k, _, _ in cs if k.endswith("_wrap")),
                "xf": sorted({v.get("fragmentVariationPath", "").split("/site/")[-1] for *_, rt, v in cs
                              if rt.endswith("experiencefragment")}),
            })
    (PASTA / "censo.json").write_text(json.dumps(linhas, ensure_ascii=False, indent=0), encoding="utf-8")
    por = collections.defaultdict(list)
    for l in linhas:
        por[(l["tipo"], l["site"])].append(l)
    for tipo in sorted({t for t, _ in por}):
        a, e = por.get((tipo, "am"), []), por.get((tipo, "eu"), [])
        print(f"\n## {tipo}: Américas {len(a)} | Europa {len(e)}")
        for nome, ls in (("AM", a), ("EU", e)):
            if not ls:
                continue
            tp = collections.Counter(l["template"] for l in ls).most_common(3)
            uso = collections.Counter(c for l in ls for c in l["comp"])
            media = sum(l["n"] for l in ls) / len(ls)
            print(f"  {nome}: templates {tp}; componentes/página {media:.0f}; profundidade máx média "
                  f"{sum(l['prof_max'] for l in ls) / len(ls):.1f}; *_wrap/página {sum(l['wrap'] for l in ls) / len(ls):.1f}")
            print("     usa (% páginas): " + ", ".join(f"{c} {100 * n // len(ls)}%" for c, n in uso.most_common(14)))
            eu_est = collections.Counter(s for l in ls for s in l["estilos"])
            print("     estilos (% páginas): " + ", ".join(f"{s} {100 * n // len(ls)}%" for s, n in eu_est.most_common(10)))


# ---------------------------------------------------------------- equivalência
# página das Américas -> a da Europa com o MESMO papel (os nomes mudam: boards-modules x boards-and-modules…)
PARES = [
    ("", "", "Home"),
    ("products", "products", "Products"),
    ("products/semiconductors", "products/semiconductors", "Semiconductors"),
    ("products/boards-modules", "products/boards-and-modules", "Boards & Modules"),
    ("products/displays", "products/displays", "Displays"),
    ("products/ip-software", "products/ip-and-software", "IP & Software"),
    ("products/macnica-products", "products/macnica-products", "Macnica Products"),
    ("solutions", "solutions", "Solutions"),
    ("solutions/artificial-intelligence-of-things-aiot", "solutions/artificial-intelligence-of-things-aiot", "AIoT"),
    ("solutions/broadcast-proav-solutions", "solutions/broadcast-proav-solutions", "Broadcast & ProAV"),
    ("solutions/imaging-and-vision", "solutions/imaging-and-vision", "Imaging & Vision"),
    ("solutions/robotics-amrs", "solutions/robotics-amrs", "Robotics & AMRs"),
    ("services", "services", "Services"),
    ("services/design-services", "products-support/design-services", "Design Services"),
    ("about-us", "about-us", "About Us"),
    ("about-us/company-profile", "about-us/company", "Company"),
    ("about-us/careers", "about-us/career", "Careers"),
    ("about-us/locations", "about-us/locations", "Locations"),
    ("about-us/privacy-policy", "about-us/privacy-policy", "Privacy Policy"),
    ("about-us/terms-and-conditions", "about-us/terms-of-sales", "Terms (similar purpose)"),
    ("about-us/news-events", "about-us/news-events", "News & Events"),
    ("about-us/news-events/events-archive", "about-us/news-events/events", "Events list"),
    ("about-us/news-events/news-archive", "about-us/news-events/news", "News list"),
    ("contact/form", "contact-us", "Contact form"),
    ("error", "error", "Error page"),
    # o MESMO fornecedor/evento nas duas regiões
    ("products/boards-modules/ienso", "products/boards-and-modules/ienso", "iENSO (same supplier)"),
    ("products/boards-modules/mpression", "products/boards-and-modules/mpression", "Mpression (same supplier)"),
    ("products/semiconductors/namuga-advanced-camera-and-3d-sensing-solutions-for-intelligent-systems",
     "products/boards-and-modules/namuga", "Namuga (same supplier)"),
    ("products/semiconductors/namuga-advanced-camera-and-3d-sensing-solutions-for-intelligent-systems/namuga-vicon-lite",
     "products/boards-and-modules/namuga/namuga-vicon-lite", "Namuga Vicon Lite (same product)"),
    ("about-us/news-events/events-archive/ibc-2026", "about-us/news-events/events/ibc-2026", "IBC 2026 (same event)"),
    ("products/semiconductors/ambarella", "products/semiconductors/ambarella", "Ambarella (same supplier)"),
    ("products/semiconductors/infineon", "products/semiconductors/infineon", "Infineon (same supplier)"),
]
# mesmo TIPO de página, conteúdo diferente: a página de tamanho mediano de cada lado (censo, 25/09)
AMOSTRAS = [
    ("products/boards-modules/iei", "products/semiconductors/sony", "Supplier page (type sample)"),
    ("products/boards-modules/tq-systems/tq-embedded-arm-modules/boxpc-abox-6ulxl",
     "products/semiconductors/sony/sony-image-sensors/imx900-aqr", "Product page (type sample)"),
    ("products/semiconductors/altera/agilex/agilex-3-fpga-and-soc-overview",
     "products/semiconductors/canon/canon-li7030sa-cmos-sensor", "Product page 2 (type sample)"),
    ("products/boards-modules/ibase/ibase-ec-3200", "products/semiconductors/corning/corning-a-16f0",
     "Product page 3 (type sample)"),
    ("about-us/news-events/news-archive/2024-02-15-macnica-americas-welcomes-sebastien-dignard-as-president",
     "about-us/news-events/news/ai-solution-in-the-quality-control-for-the-textile-industry", "News article (type sample)"),
    ("about-us/news-events/news-archive/macnica-mep100-smartnic-named-nab-product-of-the-year",
     "about-us/news-events/press-releases/greenliant-expands-emmc-nandrive-portfolio-with-highest-endurance",
     "Press release (type sample)"),
]


def equivalencia():
    d = pickle.loads(COLETA.read_bytes())
    b = pickle.loads(LV.CACHE.read_bytes())
    arvore_am = {h["jcr:path"] for h in b["g2"]}
    L = {(l["site"], l["rel"]): l for l in json.loads((PASTA / "censo.json").read_text(encoding="utf-8"))}
    out = []
    for a, e, nome in PARES:
        pa, pe = f"{AM}/{a}" if a else AM, f"{EU}/{e}" if e else EU
        la, le = L.get(("am", a)), L.get(("eu", e))
        out.append({"nome": nome, "am": a, "eu": e, "am_no_mapa": pa in d["am"], "am_existe": pa in arvore_am or pa in d["am"],
                    "eu_existe": pe in d["eu"], "am_n": la["n"] if la else None, "eu_n": le["n"] if le else None,
                    "eu_vazia": bool(le) and le["n"] <= 1, "am_vazia": bool(la) and la["n"] <= 1})
    (PASTA / "equivalencia.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for o in out:
        print(f"{o['nome'][:34]:34} AM {'mapa' if o['am_no_mapa'] else ('árvore' if o['am_existe'] else '—'):6} n={o['am_n']}  "
              f"EU {'sim' if o['eu_existe'] else '—':3} n={o['eu_n']}{'  (EU VAZIA)' if o['eu_vazia'] else ''}")


# ---------------------------------------------------------------- prints + medidas (1400px, fora do editor)
MEDIR = """() => {
  const main = document.querySelector('.container.main') || document.body, Y = scrollY;
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
                     return r.width > 2 && r.height > 2 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const box = e => { const r = e.getBoundingClientRect();
                     return {x: Math.round(r.left), y: Math.round(r.top + Y), w: Math.round(r.width), h: Math.round(r.height)}; };
  const raio = e => { for (let a = e, i = 0; a && i < 4; a = a.parentElement, i++) {
                        const r = getComputedStyle(a).borderTopLeftRadius; if (r && r !== '0px') return r; } return '0px'; };
  const textos = [...main.querySelectorAll('p, li, h1, h2, h3, h4, h5, h6, td, th')].filter(vis);
  const imgs = [...main.querySelectorAll('img')].filter(vis);
  const caixas = [...textos, ...imgs].map(box);
  const ps = textos.filter(e => e.tagName === 'P' && e.innerText.trim().length > 40);
  const larg = ps.map(e => e.getBoundingClientRect().width).sort((a, b) => a - b);
  const p0 = ps[0] ? getComputedStyle(ps[0]) : null;
  return {
    main: box(main), H: document.documentElement.scrollHeight,
    esquerda: caixas.length ? Math.min(...caixas.map(b => b.x)) : null,
    direita: caixas.length ? Math.max(...caixas.map(b => b.x + b.w)) : null,
    p_largura: larg.length ? Math.round(larg[Math.floor(larg.length / 2)]) : null,
    p_fonte: p0 ? `${p0.fontSize}/${p0.lineHeight} ${p0.fontFamily.split(',')[0]} ${p0.color}` : null,
    imgs: imgs.map(i => ({...box(i), nat: [i.naturalWidth, i.naturalHeight], raio: raio(i)})),
    titulos: [...main.querySelectorAll('h1, h2, h3, h4, h5, h6')].filter(vis).map(h => { const s = getComputedStyle(h);
      return {tag: h.tagName, txt: h.innerText.trim().slice(0, 70), size: s.fontSize, peso: s.fontWeight, cor: s.color,
              fonte: s.fontFamily.split(',')[0], ls: s.letterSpacing, align: s.textAlign, ...box(h)}; }),
    faixas: [...main.querySelectorAll('div')].filter(e => { const s = getComputedStyle(e), r = e.getBoundingClientRect();
      return s.backgroundColor !== 'rgba(0, 0, 0, 0)' && s.backgroundColor !== 'rgb(255, 255, 255)' && r.width > 600 && r.height > 40; })
      .map(e => ({cor: getComputedStyle(e).backgroundColor, ...box(e)})),
    botoes: [...main.querySelectorAll('.cmp-button, .link-button')].filter(vis).map(e => ({...box(e), txt: e.innerText.trim().slice(0, 40)})),
    abas: [...main.querySelectorAll('.cmp-tabs__tab')].filter(vis).length,
    texto: main.innerText.replace(/\\s+/g, ' ').length,
  };
}"""


def paginas_prints():
    eq = json.loads((PASTA / "equivalencia.json").read_text(encoding="utf-8"))
    ok = {(o["am"], o["eu"]) for o in eq if o["am_no_mapa"] and o["eu_existe"] and not o["eu_vazia"]}
    return [(a, e, n) for a, e, n in PARES if (a, e) in ok] + AMOSTRAS


def prints():
    import os
    from aem_lib import parse_cookie_string
    from playwright.sync_api import sync_playwright
    pasta = PASTA / "prints"
    pasta.mkdir(parents=True, exist_ok=True)
    host = LV.BASE.split("//", 1)[1]
    ck = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
    medidas = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        c = b.new_context(viewport={"width": 1400, "height": 1000})
        c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in ck.items()])
        pg = c.new_page()
        pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(LV.BASE) else r.abort())   # cookie só no author
        for a, e, nome in paginas_prints():
            for site, base, rel in (("am", AM, a), ("eu", EU, e)):
                chave = f"{site}:{rel}"
                if chave in medidas:
                    continue
                pg.goto(f"{LV.BASE}{base}{'/' + rel if rel else ''}.html?wcmmode=disabled", timeout=180000, wait_until="networkidle")
                pg.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important}")
                pg.evaluate("document.fonts.ready")
                pg.wait_for_timeout(2000)
                pg.evaluate("""() => document.querySelectorAll('body *').forEach(e => {
                    const p = getComputedStyle(e).position; if (p === 'fixed' || p === 'sticky') e.style.visibility = 'hidden'; })""")
                m = pg.evaluate(MEDIR)
                png = pasta / f"{site}__{(rel or 'home').replace('/', '__')}.png"
                pg.screenshot(path=str(png), full_page=True)
                m["png"] = png.name
                medidas[chave] = m
                print(f"{chave[:90]:90} H={m['H']} main={m['main']['h']} conteúdo {m['esquerda']}–{m['direita']} "
                      f"p={m['p_largura']} imgs={len(m['imgs'])} faixas={len(m['faixas'])} botões={len(m['botoes'])}")
        b.close()
    (PASTA / "medidas.json").write_text(json.dumps(medidas, ensure_ascii=False, indent=0), encoding="utf-8")


def recorte_main(site, rel, medidas):
    """O miolo da página (entre o header/breadcrumb e o footer, que são de cada site e comparados à parte)."""
    from PIL import Image
    m = medidas[f"{site}:{rel}"]
    im = Image.open(PASTA / "prints" / m["png"]).convert("RGB")
    return im.crop((0, m["main"]["y"], im.width, min(im.height, m["main"]["y"] + m["main"]["h"])))


def lado_a_lado():
    """Américas à esquerda, Europa à direita, só o miolo, 700px cada; páginas longas em pedaços."""
    from PIL import Image, ImageDraw
    medidas = json.loads((PASTA / "medidas.json").read_text(encoding="utf-8"))
    pasta = PASTA / "lado_a_lado"
    pasta.mkdir(exist_ok=True)
    W, CORTE = 700, 2200
    for n, (a, e, nome) in enumerate(paginas_prints(), 1):
        ims = [recorte_main(s, r, medidas) for s, r in (("am", a), ("eu", e))]
        ims = [im.resize((W, max(1, round(im.height * W / im.width)))) for im in ims]
        alt = max(im.height for im in ims)
        for k, y in enumerate(range(0, alt, CORTE)):
            h = min(CORTE, alt - y)
            tela = Image.new("RGB", (2 * W + 20, h + 30), "white")
            dr = ImageDraw.Draw(tela)
            dr.text((6, 8), f"AMERICAS  /{a}"[:110], fill=(120, 0, 120))
            dr.text((W + 26, 8), f"EUROPE  /{e}"[:110], fill=(0, 70, 140))
            for i, im in enumerate(ims):
                tela.paste(im.crop((0, y, W, min(im.height, y + h))) if y < im.height else Image.new("RGB", (W, 1), "white"),
                           (i * (W + 20), 30))
            dr.line([(W + 10, 0), (W + 10, h + 30)], fill=(180, 180, 180), width=2)
            tela.save(pasta / f"{n:02d}_{k}.png")
        print(f"{n:02d} {nome}: {alt}px -> {len(range(0, alt, CORTE))} pedaço(s)")


# ---------------------------------------------------------------- relatório
def assinatura(v, est, prof=0):
    """Resumo de um bloco: componente[estilos] (filhos), com filhos iguais em sequência agrupados (4× teaser)."""
    rt = (v.get("sling:resourceType") or "").rsplit("/", 1)[-1]
    st = [est.get(s, {}).get("rotulo", "?") if s in est else f"«{s}»" for s in v.get("cq:styleIds", []) if s]
    ex = ""
    if rt == "title":
        ex = f" {v.get('type') or 'default'}"
    if rt == "experiencefragment":
        ex = " " + v.get("fragmentVariationPath", "").split("/site/")[-1].split("/")[0][:40]
    if v.get("backgroundColor"):
        ex += f" bg {v['backgroundColor']}"
    filhos = [assinatura(c, est, prof + 1) for k, c in v.items()
              if isinstance(c, dict) and k != "cq:responsive" and c.get("sling:resourceType") and not k == "spImage"]
    grup = []
    for f in filhos:
        if grup and grup[-1][0] == f:
            grup[-1][1] += 1
        else:
            grup.append([f, 1])
    corpo = ", ".join(f"{n}× {f}" if n > 1 else f for f, n in grup)
    return f"{rt}{'[' + ', '.join(st) + ']' if st else ''}{ex}" + (f" ({corpo})" if corpo and prof < 4 else (" (…)" if corpo else ""))


def blocos(jc, est):
    """Os blocos do miolo: filhos do container editável da página (root/container)."""
    raiz = (jc.get("root") or {}).get("container") or jc.get("root") or {}
    return [assinatura(v, est) for k, v in raiz.items() if isinstance(v, dict) and v.get("sling:resourceType")]


def img64(im, largura=1000):
    import base64
    import io
    from PIL import Image
    if im.width > largura:
        im = im.resize((largura, round(im.height * largura / im.width)), Image.LANCZOS)
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=70, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def links(site, rel):
    import html
    from urllib.parse import quote
    p = (AM if site == "am" else EU) + (f"/{rel}" if rel else "")
    nome = "Americas" if site == "am" else "Europe"
    ed = LV.BASE + "/editor.html" + quote(p, safe="/:") + ".html"
    return (LV._alink(f"{p}.html?wcmmode=disabled", f"{nome} page") + " "
            + f'<a href="{html.escape(ed, quote=True)}" target="_blank" rel="noopener">{nome} editor</a> ')


# o que vi em cada par (prints lado a lado a 1400px, 25/09) — em inglês, vai para o relatório
OBS = {
    "Products": [
        "Europe: title, short bold subtitle, two paragraphs, then 5 teaser cards (photo, ▸ title under it) in a 4-column row. No banner.",
        "Americas: everything in a narrower centred column (8 of 12); a large banner, a second heading in 29px letter-spaced bold, a blue "
        "text link to the linecard, then 4 small cards with the link text above the photo (the GWI's design, rebuilt on 24/09)."],
    "Boards & Modules": [
        "Europe: the whole page is one grey band — title, bold subtitle, text, 4 logo tiles of equal size (white boxes, logo centred, "
        "no caption), one centred Contact Us button.",
        "Americas: white page; title with a rule under it, a second large heading, 11 logos of very different visual size with captions "
        "in 3 rows of 4, two buttons side by side."],
    "Solutions": [
        "Europe: title, text, 4 teasers with rounded corners in one row, ▸ link titles, one Contact Us button — 656px tall.",
        "Americas: two h1 titles stacked, text, 6 photos 645px wide in rows of 2 with small captions, no button — 1,571px tall."],
    "AIoT": [
        "Same text on both sides.",
        "Europe opens with a hero (photo left, heading and text right); Americas with a thin banner strip and a 29px letter-spaced heading.",
        "Europe puts the Sense/Process/Deploy/Connect tabs in a lavender band, photos on the right, and uses text links (“View Sony "
        "Products”) where Americas has three large buttons and grey rules between suppliers.",
        "Europe shows the component-to-system diagram beside its text and the case study as image + text in one row, and ends with one "
        "button in a grey band; Americas stacks each of these and ends with two buttons."],
    "Broadcast & ProAV": [
        "Different content (Europe is built around the MEP100).",
        "Europe: hero (photo, title, text, Request a Demo button); alternating grey bands; a table with product images inside the cells; "
        "4 white feature cards on grey; one closing button.",
        "Americas: banner, long text with a video beside it, the FAQ as bold questions, a plain list of links, a rule, then tabs with "
        "large product photos and a button after each product."],
    "Imaging & Vision": [
        "Same text on both sides.",
        "Europe: hero (photo left; title, text and Contact Our Experts button right); the tabs sit in a grey band and each application is "
        "photo left + text right, with no rules between items and small dark group headings.",
        "Americas: banner strip, a link, a jump menu of 5 purple ▼ bars (Factory Automation, Professional Surveillance…), a grey rule "
        "after every item, bold purple group headings."],
    "Robotics & AMRs": [
        "Same text on both sides.",
        "Europe groups the page in bands (lavender intro, grey Capture/Process/Communicate), has one button in the intro and small "
        "section titles.",
        "Americas: two buttons in the intro (Download brief + Contact Us), 29px letter-spaced section titles, a jump menu of 3 purple ▼ "
        "bars before Capture/Process/Communicate."],
    "News & Events": [
        "Europe: one grey 1000px panel with a black heading and 3 cards (image + label).",
        "Americas: full width, 2 large cards with image, title and description."],
    "Events list": [
        "Same component (cardlist, “Two columns”). Europe turns on date and tags, lists newest first and shows All/Years filter buttons, "
        "inside a 1000px grey panel.",
        "Americas: sorted alphabetically by title, no date or tags; logos cropped by the image frame (Automate shows as “TOM”, Embedded "
        "Technologies cut off), several events without an image, a newsletter button above the list."],
    "News list": [
        "Same component. Europe: image, date, tags, newest first, filter buttons, 1000px grey panel.",
        "Americas: text only (featured image off), no date, sorted alphabetically by title — a 2016 story sits next to a 2025 one."],
    "Contact form": [
        "Different forms. Europe centres a short form (7 fields, consent checkbox, reCAPTCHA note) under a centred title; Americas has "
        "13 fields, left-aligned under a left title."],
    "Error page": [
        "Almost the same. Americas: a larger bold “404”, an extra “Not found” heading, an upper-case button; Europe: a small “404 / Page "
        "Not Found” and a title-case button."],
    "iENSO (same supplier)": [
        "Same text on both sides.",
        "Europe adds a photo beside the intro; tabs in a grey band with the photo on the right; “Why work with iENSO” in a lavender "
        "band; the closing heading with the diagram beside it and one button.",
        "Americas: no image in the intro; 29px letter-spaced tab headings with a large photo on the left; the diagram full width; two buttons."],
    "Mpression (same supplier)": [
        "Different content. Europe: hero image + text, 3 linked image cards in a grey band, a News/Updates item, a partner card in a "
        "lavender band.",
        "Americas: three long tables (P/N, Description, Images). The Images column shows nothing in the author: its images are "
        "hard-coded to https://www.macnica.com/… (some in the GWI DAM) — see “Found along the way”."],
    "Namuga (same supplier)": [
        "Same text; both open with a video + text hero.",
        "Europe: the Vicon Lite teaser and Target Applications in grey bands, the Solutions tabs in a lavender band, section photos "
        "smaller on the right, the diagram beside its list, one button.",
        "Americas: the same sections on white with 29px letter-spaced headings, larger photos, the diagram full width, two buttons."],
    "Namuga Vicon Lite (same product)": [
        "Same text (Europe even keeps “Macnica Americas is an authorized distributor … in North America”).",
        "Europe: a full-width banner under the title, no jump menu, small section headings, photos beside the text.",
        "Americas: a jump menu of 7 purple ▼ bars, 29px letter-spaced headings, each photo centred on its own row between sections."],
    "IBC 2026 (same event)": [
        "Europe: everything in a 1000px column; banner right under the title; dates and venue as one heading; the meeting form in a grey "
        "band; a “Get Updates After the Show” Subscribe button.",
        "Americas: full width; Location / Start Date / End Date as label lines; the banner after the text; a 29px letter-spaced heading; "
        "the form in a grey band; two buttons at the end."],
    "Ambarella (same supplier)": [
        "Mostly the same text.",
        "Europe: hero (video, title, text, Contact Our Experts); the FAQ as a collapsed accordion; News/Updates in a lavender band; "
        "“Why Choose” items photo-right in a grey band without rules; the SoCs as a 3-column grid (chip image, name, description).",
        "Americas: the FAQ open as bold questions; a jump menu of 3 purple ▼ bars; grey rules between items; larger photos."],
    "Infineon (same supplier)": [
        "Different text.",
        "Europe: hero (video + text), “A Leader in Power Systems” in grey, Key Markets, an acquisition story in a lavender band, "
        "News/Updates (2 dated links), then tabs and one Request a Quote button.",
        "Americas: hero (video, 29px letter-spaced heading, text), tabs in a grey band, no button."],
    "Supplier page (type sample)": [
        "Europe (Sony): hero in a lavender band, a grey band with the call to action as text links, News/Updates (4 dated links + Show "
        "more), sensor-family tabs in a lavender band, charts.",
        "Americas (IEI): text intro, video + text in a grey band, solution tabs, a resources table, two buttons."],
    "Product page (type sample)": [
        "Europe (Sony IMX900): a small product image beside a bold lead and text; Specifications and Related Documents in tabs inside a "
        "grey band, table centred; one Request a Quote button; Similar Products links.",
        "Americas (TQ ABox-6ULxL): a 29px letter-spaced subtitle beside the image, Features in a grey band, full-width Specifications and "
        "Ordering tables, a “TQ Embedded is known for” list, two buttons."],
    "Product page 2 (type sample)": [
        "Europe (Canon): product photo beside the heading and text; the Technical Specifications table in a grey band; two buttons.",
        "Americas (Altera Agilex 3 overview): text, a small two-column table, two buttons; no image."],
    "Product page 3 (type sample)": [
        "Europe (Corning): everything in a 1000px column; photo beside the text; a compact centred specifications table in a grey band; "
        "one button; Similar Products links.",
        "Americas (IBASE EC-3200): 29px letter-spaced subtitle, photo + text, Features in grey with an extra large photo, full-width "
        "Specifications and Ordering tables, About IBASE, two buttons."],
    "News article (type sample)": [
        "Europe: title, full-width hero image, text, grey and lavender bands with small headings, then Recent Posts (5 links) and a See "
        "All button.",
        "Americas: title, the dateline paragraph in a grey band, portrait photo left + text right, “About Macnica” in 29px letter-spaced "
        "type; no links to other posts."],
    "Press release (type sample)": [
        "Europe: title, full-width banner, PR number and date, bold and italic subtitles, body in a grey band, contacts, About sections "
        "in a grey band, a “Files available for download” table with a PDF icon.",
        "Americas: title, dateline + photo in a grey band, body, “About Macnica Americas” in 29px letter-spaced type, media contacts."],
}


def relatorio():
    import datetime
    import html
    from PIL import Image
    d = pickle.loads(COLETA.read_bytes())
    est = d["estilos"]
    L = json.loads((PASTA / "censo.json").read_text(encoding="utf-8"))
    eq = json.loads((PASTA / "equivalencia.json").read_text(encoding="utf-8"))
    med = json.loads((PASTA / "medidas.json").read_text(encoding="utf-8"))
    e_ = html.escape
    pares = paginas_prints()

    # ---- números para o resumo (render dos 25 pares)
    def rend(site):
        ps = [v for k, v in med.items() if k.startswith(site + ":")]
        grandes = [sum(1 for h in v["titulos"] if h["tag"] in ("H1", "H2")) for v in ps]
        imgs = [i for v in ps for i in v["imgs"]]
        dois = sum(1 for v in ps if len(v["botoes"]) >= 2 and len({b["y"] for b in v["botoes"]}) < len(v["botoes"]))
        faixas = collections.Counter(f["cor"] for v in ps for f in {(f["y"], f["h"], f["cor"]): f for f in v["faixas"]}.values())
        return {"n": len(ps), "grandes": sum(grandes) / len(ps), "redondas": sum(1 for i in imgs if i["raio"] != "0px"),
                "imgs": len(imgs), "dois": dois, "faixas": faixas}
    ra, re_ = rend("am"), rend("eu")
    cen = {s: [l for l in L if l["site"] == s] for s in ("am", "eu")}
    pct = lambda s, f: 100 * sum(1 for l in cen[s] if f(l)) // len(cen[s])
    usa = lambda comp: (lambda l: comp in l["comp"])
    est_ = lambda rot: (lambda l: rot in l["estilos"])

    # ---- 1. padrões
    padroes = [
        ("One big heading per page",
         "The page title is the only large heading (h1, 25px, letter-spaced); sections use h3 (22px) and h4 (18px), no letter-spacing.",
         "Section titles are h1/h2 too. In this theme h2 is 29px with 2.9px letter-spacing — larger than the page title.",
         f"Large headings (h1+h2) per page: Americas {ra['grandes']:.1f}, Europe {re_['grandes']:.1f} (the 25 compared pairs). "
         f"Across all pages: h1+h2 per page {sum(l['titulos'].get('h1', 0) + l['titulos'].get('h2', 0) for l in cen['am']) / len(cen['am']):.1f} "
         f"vs {sum(l['titulos'].get('h1', 0) + l['titulos'].get('h2', 0) for l in cen['eu']) / len(cen['eu']):.1f}.",
         "title: type h3 for sections, h4 for sub-sections"),
        ("A hero at the top",
         "Solution, supplier and product pages open with image + title + text (+ one button) side by side.",
         "A thin banner strip or large photo, then a large heading, then text.",
         "AIoT, Imaging & Vision, Ambarella, iENSO, Infineon, Broadcast, product pages.",
         "textwithimage (Left) or a flexcontainer with image + title/text/button"),
        ("Teaser cards",
         "Links to child pages are teaser cards — same-size image, ▸ purple title under it, rounded corners on landing pages "
         f"(the teaser is used on {', '.join('/' + (l['rel'] or '(home)') for l in cen['eu'] if 'teaser' in l['comp'])}).",
         f"Plain image + small caption, or a text link above a photo; photos up to 645px wide; {ra['redondas']} rounded images.",
         "Solutions, Products, Boards & Modules (logo tiles), home.",
         "teaser + style “Rounded Corners”, 4 per row in a flexcontainer"),
        ("Colour bands group the sections",
         "Sections alternate white, light grey (#f7f7f7), lavender (rgb 245,243,249) and mid grey (#ebebeb); no rules between items.",
         "White and light grey only; horizontal rules separate items.",
         "Bands in the samples — Europe: " + ", ".join(f"{c} ×{n}" for c, n in re_["faixas"].most_common(4))
         + "; Americas: " + ", ".join(f"{c} ×{n}" for c, n in ra["faixas"].most_common(3)) + ".",
         "container backgroundColor (the lavender is rgb(245,243,249))"),
        ("One call to action",
         "One centred button per page or section; secondary actions are text links (“View Sony Products”, “Learn more”).",
         "Two buttons side by side at the end (Contact Us for More Information + Request a Quote) and a large button after each item.",
         f"Pages with two buttons side by side: Americas {ra['dois']} of {ra['n']}, Europe {re_['dois']} of {re_['n']}.",
         "button (Center); text links in the text component"),
        ("Detail folded into tabs and accordions",
         "Product specifications and documents sit in tabs (tabs on "
         f"{sum(1 for l in cen['eu'] if l['tipo'] == 'product' and 'tabs' in l['comp'])} of {sum(1 for l in cen['eu'] if l['tipo'] == 'product')} "
         "product pages); FAQs are a collapsed accordion.",
         "Specification and ordering tables at full length one after the other; FAQs open.",
         "Product pages, Ambarella.",
         "tabs, accordion"),
        ("No jump menus",
         "Sections simply follow each other.",
         "Rows of purple ▼ bars (anchor jump menus) above the sections.",
         "Imaging & Vision (5 bars), Robotics (3), Ambarella (3), Vicon Lite (7).",
         "— (remove the options/anchorlink bars)"),
        ("Lists that read like a news feed",
         "News and events lists: image, date, tags, newest first, All/Years filter, in a 1000px grey panel.",
         "News list: text only, no date, alphabetical by title. Events list: alphabetical, cropped logos, some without image.",
         "Same cardlist component and style on both sides — only the options differ.",
         "cardlist: showFeaturedImage, showArticleDate, showTags on; order by date, descending"),
        ("Ways onward",
         "Articles end with Recent Posts + See All; product pages with Similar Products; supplier pages carry News/Updates.",
         "Articles and product pages end with the contact buttons only.",
         "News/press samples, product samples, Ambarella, Infineon, Sony.",
         "list / cardlist of related pages"),
        ("A 1000px column for reading pages",
         f"Lists, events and product specification tables sit in a 1000px column (container style “1000px” on "
         f"{pct('eu', est_('container:1000px'))}% of pages); landing and solution pages are full width like Americas.",
         "Full width everywhere (the 18/09 decision to drop the 1000px margin).",
         "Events list, News list, IBC 2026, Corning.",
         "container style “1000px” — conflicts with the 18/09 no-margin decision: your call"),
    ]
    t_padroes = "".join(f"<tr><td><b>{e_(a)}</b></td><td>{e_(b)}</td><td>{e_(c)}</td><td>{e_(dd)}</td><td><code>{e_(x)}</code></td></tr>"
                        for a, b, c, dd, x in padroes)

    # ---- 2. equivalência
    def st_am(o):
        return "in our link map" if o["am_no_mapa"] else ("exists, outside our link map" if o["am_existe"] else "—")
    t_eq = "".join(
        f'<tr><td><b>{e_(o["nome"])}</b></td><td><div class="p">/{e_(o["am"])}</div>{e_(st_am(o))}'
        + (f' · {o["am_n"]} components' if o["am_n"] is not None else "") + f'</td><td><div class="p">/{e_(o["eu"])}</div>'
        + ('<span class="x">empty page</span> (one empty container)' if o["eu_vazia"] else (f'{o["eu_n"]} components' if o["eu_existe"] else "—"))
        + "</td><td>" + ("compared below" if any(a == o["am"] and e == o["eu"] for a, e, _ in pares) else "not compared") + "</td></tr>"
        for o in eq)
    com_par = {(o["am"], "am") for o in eq} | {(o["eu"], "eu") for o in eq}
    grupo = lambda r: "/".join(r.split("/")[:3 if r.startswith("about-us/news-events/") else 2])
    so_am = collections.Counter(grupo(l["rel"]) for l in cen["am"] if (l["rel"], "am") not in com_par and l["rel"].startswith((
        "about-us/newsletter", "about-us/partner-with", "about-us/glossary", "contact/", "request-a-quote", "services/automotive",
        "services/imaging", "solutions/medical", "solutions/networking", "solutions/smartcity", "about-us/tariff", "terms-conditions")))
    so_eu = collections.Counter(grupo(l["rel"]) or "(home)" for l in cen["eu"] if (l["rel"], "eu") not in com_par and (l["rel"].startswith((
        "about-us/certificates", "about-us/legal-notice", "products-support/suppliers", "products-support/products", "resources", "search",
        "about-us/news-events/press-releases")) or l["rel"] in ("products-support", "")))
    tipos = sorted({l["tipo"] for l in L})
    t_tipos = "".join(f"<tr><td>{e_(t)}</td><td class='n'>{sum(1 for l in cen['am'] if l['tipo'] == t)}</td>"
                      f"<td class='n'>{sum(1 for l in cen['eu'] if l['tipo'] == t)}</td></tr>" for t in tipos)

    # ---- 3. censo por tipo
    COMPS = ["teaser", "textwithimage", "image", "tabs", "accordion", "cardlist", "list", "table", "button", "flexcontainer",
             "experiencefragment", "embed", "options", "anchorlink"]
    linhas_c = []
    for t in [t for t in tipos if any(l["tipo"] == t for l in cen["am"]) and any(l["tipo"] == t for l in cen["eu"])]:
        a = [l for l in cen["am"] if l["tipo"] == t]
        b = [l for l in cen["eu"] if l["tipo"] == t]
        p = lambda ls, f: f"{100 * sum(1 for l in ls if f(l)) // len(ls)}%"
        grandes = lambda ls: f"{sum(l['titulos'].get('h1', 0) + l['titulos'].get('h2', 0) for l in ls) / len(ls):.1f}"
        celula = lambda ls: (f"<b>{len(ls)}</b> pages · {sum(l['n'] for l in ls) / len(ls):.0f} components/page · h1+h2 per page "
                             f"{grandes(ls)} · colour band {p(ls, lambda l: bool(l['fundos']))} · 1000px {p(ls, est_('container:1000px'))}<br>"
                             + ", ".join(f"{c} {p(ls, usa(c))}" for c in COMPS if any(c in l["comp"] for l in ls)))
        linhas_c.append(f"<tr><td><b>{e_(t)}</b></td><td>{celula(a)}</td><td>{celula(b)}</td></tr>")

    # ---- 4. header e footer
    m_am, m_eu = med["am:products"], med["eu:products"]
    ia, ie = Image.open(PASTA / "prints" / m_am["png"]), Image.open(PASTA / "prints" / m_eu["png"])
    cab = [ia.crop((0, 0, 1400, m_am["main"]["y"])), ie.crop((0, 0, 1400, m_eu["main"]["y"]))]
    rod = [ia.crop((0, m_am["main"]["y"] + m_am["main"]["h"], 1400, ia.height)), ie.crop((0, m_eu["main"]["y"] + m_eu["main"]["h"], 1400, ie.height))]
    fig = lambda t, im: f'<figure><figcaption>{e_(t)}</figcaption><img src="{img64(im, 1000)}" alt="{e_(t)}" loading="lazy"></figure>'

    # ---- 5. par a par
    corpo = []
    for n, (a, e, nome) in enumerate(pares, 1):
        ma, me = med[f"am:{a}"], med[f"eu:{e}"]
        def resumo(m):
            g = sum(1 for h in m["titulos"] if h["tag"] in ("H1", "H2"))
            return (f"page body {m['main']['h']:,}px tall · {g} large heading{'s' if g != 1 else ''} · {len(m['imgs'])} images"
                    f"{' (' + str(sum(1 for i in m['imgs'] if i['raio'] != '0px')) + ' rounded)' if any(i['raio'] != '0px' for i in m['imgs']) else ''}"
                    f" · {len({(f['y'], f['h']) for f in m['faixas']})} colour bands · {len(m['botoes'])} buttons"
                    + (f" · {m['abas']} tabs" if m["abas"] else ""))
        pedacos = sorted((PASTA / "lado_a_lado").glob(f"{n:02d}_*.png"), key=lambda p: int(p.stem.split("_")[1]))
        imgs = "".join(f'<img class="lado" src="{img64(Image.open(p), 1100)}" alt="{e_(nome)}, part {k + 1}" loading="lazy">'
                       for k, p in enumerate(pedacos[:3]))
        if len(pedacos) > 3:
            imgs += f'<p class="nota">(first {3 * 2200 * 2:,}px of {len(pedacos) * 2200 * 2:,}px shown)</p>'
        ba = "".join(f"<li>{e_(s)}</li>" for s in blocos(d["am"][f"{AM}/{a}" if a else AM], est))
        be = "".join(f"<li>{e_(s)}</li>" for s in blocos(d["eu"][f"{EU}/{e}" if e else EU], est))
        corpo.append(
            f'<details class="pg" id="par{n}" open><summary>{n}. {e_(nome)}</summary>'
            f'<div class="abre">{links("am", a)} {links("eu", e)}</div>'
            f'<ul class="obs">' + "".join(f"<li>{e_(o)}</li>" for o in OBS.get(nome, [])) + "</ul>"
            f'<table class="med"><tr><th>Americas</th><td>{e_(resumo(ma))}</td></tr><tr><th>Europe</th><td>{e_(resumo(me))}</td></tr></table>'
            f'{imgs}<details class="arv"><summary>Components, block by block</summary><div class="duas"><div><b>Americas</b><ol>{ba}</ol></div>'
            f'<div><b>Europe</b><ol>{be}</ol></div></div></details></details>')

    # ---- 6. achados
    partidos = sum(1 for p, jc in d["am"].items() if isinstance(jc, dict) for *_, v in componentes(jc.get("root", {}))
                   if any(s and s not in est for s in v.get("cq:styleIds", [])))
    pags_part = sum(1 for p, jc in d["am"].items() if isinstance(jc, dict)
                    and any(any(s and s not in est for s in v.get("cq:styleIds", [])) for *_, v in componentes(jc.get("root", {}))))
    vazias = [o for o in eq if o["eu_vazia"]]
    fora = [o for o in eq if not o["am_no_mapa"] and o["am_existe"]]
    achados = [
        ("Americas: style IDs saved digit by digit",
         f"{partidos} components on {pags_part} pages (almost all under /products/boards-modules) have their style stored as single digits "
         "(e.g. 1, 7, 1, 7, 4, 9, 8, 0, 5, 3, 4, 9, 9 instead of 1717498053499 = container side padding “Large”), so the style is not "
         "applied. None of them was written by us; most have no editor stamp (created by a script)."),
        ("Americas: the Mpression tables' images are hard-coded to the public site",
         "The Images column of the three Mpression tables points to https://www.macnica.com/content/dam/… — some into the GWI DAM, some "
         "into the global2 DAM on the public domain. They do not show in the author screenshots (external hosts blocked); whether they "
         "load on the public site was not checked."),
        ("Americas: news and events lists sorted by title",
         "Both lists use orderBy = title, ascending, with no date shown — the newest item is not first. Europe sorts by date, newest "
         "first, with dates and tags."),
        ("Americas: event logos cropped, some events without image",
         "The events list crops wide logos to the card frame (Automate reads “TOM”) and shows empty space for events without a "
         "featured image (IBC 2015, IBC 2016, Collaborative Robots…)."),
        ("Theme: h2 is larger than h1",
         "h1 renders at 25px/500 with 2.5px letter-spacing, h2 at 29px/600 with 2.9px letter-spacing. Any section title set as h2 "
         "outranks the page title visually. Europe avoids h2 almost completely."),
        ("Americas: news, events and newsletters built on the product-page template",
         "They use mai-mae-product-page (Europe uses the article template). The templates are structurally identical today, so "
         "nothing shows; it matters only if the article template changes."),
        (f"Europe: {len(vazias)} counterpart pages are empty",
         "; ".join(f"/{o['eu']}" for o in vazias) + " — each is a single empty container created by admin in January 2026."),
        ("Europe: Americas text on Europe pages",
         "Europe's Namuga Vicon Lite and Ambarella pages still say “Macnica Americas …” (copied from the Americas pages). Europe's "
         "content, not ours — for information."),
        (f"Not compared: {len(fora)} Americas pages outside our link map",
         "; ".join(f"/{o['am'] or '(home)'}" for o in fora) + " exist in the Americas tree but are not in the final link map (not ours). "
         "Say if you want them compared."),
    ]
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    css = LV.CSS + """
h2{scroll-margin-top:12px}.tabela{overflow-x:auto;margin:0 0 14px}.tabela table{min-width:760px}td{vertical-align:top}
td.n{text-align:right}.x{color:var(--bad);font-weight:600}.obs{margin:6px 0 8px;padding-left:20px}.obs li{margin:0 0 4px}
table.med{margin:6px 0 10px;font-size:13px}table.med th{text-align:left;padding-right:10px;white-space:nowrap}
img.lado{width:100%;height:auto;border:1px solid var(--lin);border-radius:4px;display:block;margin:0 0 6px}
.duas{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}.duas ol{font-size:12px;padding-left:18px;overflow-wrap:anywhere}
details.arv{margin:6px 0 4px}details.arv>summary{cursor:pointer;color:var(--acc);font-size:14px}
figure{margin:0 0 10px}figcaption{font-size:12px;color:var(--mut);margin:0 0 3px}figure img{width:100%;height:auto;border:1px solid var(--lin)}
nav.toc{margin:4px 0 18px;display:flex;flex-wrap:wrap;gap:4px 16px}nav.toc a{white-space:nowrap}.abre a{white-space:nowrap}
.achado li{margin:0 0 10px}table.padroes td:last-child{min-width:200px}code{font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere}
"""
    pagina = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Americas vs Europe layout</title><style>{css}</style></head><body><main>
<h1>global2 — Americas vs Europe: how the pages are built</h1>
<p class="sub">A read-only comparison of the global2 Americas pages (americas/mai/en — the {len(cen['am'])} pages of our final link map) with
the Europe pages (eu/atd-europe/en — {len(cen['eu'])} pages, test folders excluded), made on {agora}. Content differs by region; what is
compared is how the pages are built: components, styles, headings, bands, buttons and layout. Nothing was changed. Sources: the stored
content of every page (component census) and 1400px screenshots of {len(pares)} page pairs, measured in the browser. Videos and anything
hosted outside the AEM author do not load in the screenshots (the grey boxes with an icon are embedded videos). Links open in the AEM
author; you must be logged in.</p>
<div class="resumo">
<div><b>{len(cen['am'])} / {len(cen['eu'])}</b><span>pages: Americas (link map) / Europe</span></div>
<div><b>{len(eq)}</b><span>role-matched pairs ({sum(1 for o in eq if o['eu_vazia'])} with an empty Europe page)</span></div>
<div><b>{len(pares)}</b><span>pairs compared side by side</span></div>
<div><b>same</b><span>templates, components, styles and theme on both sites</span></div></div>
<nav class="toc"><a href="#padroes">1. What makes Europe cleaner</a><a href="#equivalencia">2. Equivalent pages</a><a href="#censo">3. Components by page type</a>
<a href="#moldura">4. Templates, header, footer</a><a href="#pares">5. Page by page</a><a href="#achados">6. Found along the way</a></nav>

<h2 id="padroes">1. What makes the Europe pages look cleaner</h2>
<p class="intro">Both sites use the same templates (identical structure: header, breadcrumb, one editable area, footer), the same
component library, the same 62 styles and the same theme (fonts, colours, heading sizes). Everything below is a choice of how the page
is built — it can be done on the Americas pages with what already exists, without development.</p>
<div class="tabela"><table class="padroes"><thead><tr><th>Pattern</th><th>Europe</th><th>Americas today</th><th>Evidence</th><th>With</th></tr></thead>
<tbody>{t_padroes}</tbody></table></div>

<h2 id="equivalencia">2. Equivalent pages</h2>
<p class="intro">Only 15 pages share the same path; the two trees name things differently (boards-modules / boards-and-modules,
company-profile / company, events-archive / events…). Pages were matched by role. Supplier and product pages match only where both
regions carry the same supplier (Ambarella, iENSO, Infineon, Mpression, Namuga); the rest are compared by page type (section 3 and the
type samples in section 5).</p>
<div class="tabela"><table><thead><tr><th>Role</th><th>Americas</th><th>Europe</th><th></th></tr></thead><tbody>{t_eq}</tbody></table></div>
<p><b>Only in Americas:</b> {e_(", ".join(f"/{k} ({v})" for k, v in so_am.most_common()))}.<br>
<b>Only in Europe:</b> {e_(", ".join(f"/{k or '(home)'} ({v})" for k, v in so_eu.most_common()))}.</p>
<div class="tabela"><table><thead><tr><th>Page type</th><th>Americas</th><th>Europe</th></tr></thead><tbody>{t_tipos}</tbody></table></div>

<h2 id="censo">3. Components by page type (all pages)</h2>
<p class="intro">Share of pages of each type that use a component; “h1+h2 per page” counts large headings; “colour band” = pages with
at least one container background; “1000px” = pages using the 1000px container style.</p>
<div class="tabela"><table><thead><tr><th>Type</th><th>Americas</th><th>Europe</th></tr></thead><tbody>{"".join(linhas_c)}</tbody></table></div>

<h2 id="moldura">4. Templates, header and footer</h2>
<p class="intro">The four templates of each site have the same structure; only the header and footer fragments differ. They appear on
every page, so a change there changes every page. Europe's header has 5 menu items on one line, no utility row and a “Home” breadcrumb;
Americas' has a utility row (Glossary, FAQ, Terms), 6 menu items — one of them three lines long — and “Technology Solutions &amp;
Innovation Partner” as the first breadcrumb.</p>
<div class="duas">{fig("Americas header", cab[0])}{fig("Europe header", cab[1])}</div>
<div class="duas">{fig("Americas footer", rod[0])}{fig("Europe footer", rod[1])}</div>

<h2 id="pares">5. Page by page</h2>
<p class="intro">Americas on the left, Europe on the right; only the page body (header and footer in section 4). Each pair has the page
and editor links for both sides, what differs, the measurements, the screenshots and the component outline.</p>
{"".join(corpo)}

<h2 id="achados">6. Found along the way (nothing changed)</h2>
<ul class="achado">{"".join(f"<li><b>{e_(t)}.</b> {e_(x)}</li>" for t, x in achados)}</ul>
<footer><p>Paths are relative to {AM} and {EU}. Tool: ferramentas/golive/comparar_eu.py (coleta, censo, equivalencia, prints,
lado_a_lado, relatorio); data in dados/eu/.</p></footer>
</main></body></html>"""
    saida = LV.MAPAS / f"global2_americas_vs_europe_layout_{datetime.date.today().isoformat()}.html"
    saida.write_text(pagina, encoding="utf-8")
    print(f"{len(pares)} pares, {len(eq)} equivalências -> {saida} ({saida.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    {"coleta": coleta, "censo": censo, "equivalencia": equivalencia, "prints": prints,
     "lado_a_lado": lado_a_lado, "relatorio": relatorio}[sys.argv[1]]()
