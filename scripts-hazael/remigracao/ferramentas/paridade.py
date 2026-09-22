#!/usr/bin/env python3
"""
paridade.py <mapa.json> — paridade de CONTEÚDO entre cada página do mapa (mapa_links.py) e a sua origem no GWI.
SOMENTE LEITURA: só GET no author (render com ?wcmmode=disabled e `.0.json` dos alvos de link). Nada gravado.

Pedido do Hazael (22/09/2026): revisar as 114 páginas de /content/copia-teste/americas/mai/en/about-us contra o
GWI. Compara O QUE O VISITANTE VÊ a 1400px, com o comparador do aem_fidelidade_render (texto por contenção,
ruído de chrome filtrado) e, por cima dele, o que texto não pega:
  imagens   contagem (≥40px) dos dois lados; imagem quebrada no destino (naturalWidth 0)
  links     link da origem sem correspondente no destino (externo: mesma URL; interno: mesmo nome de nó);
            alvo interno morto no destino (GET .0.json ≠ 200); href do destino apontando para o GWI
  embeds    iframe/video/embed/object da origem que não está no destino
  forms     formulário da origem que não está no destino
  tabelas, h1, altura da página — só informação
Página cuja origem é REDIRECT (cq:redirectTarget) não é aberta na origem (o 301 sai do author): veredito
ORIGEM-REDIRECT e só a descrição do destino. Disposição (layout) NÃO é julgada aqui — só conteúdo.

VEREDITO   OK = nada faltando/sobrando/quebrado;  VER = pelo menos um motivo;  ORIGEM-REDIRECT;  ERRO
Saída: dados/mapas/<mapa>_paridade.{html,json} + resumo na tela (com as diferenças RECORRENTES agrupadas por
texto, para separar o sistemático do pontual antes de abrir página por página).

    python3 remigracao/ferramentas/paridade.py remigracao/dados/mapas/copia-teste_about-us.json
    python3 remigracao/ferramentas/paridade.py <mapa.json> --so Careers glossary      # só essas rels
    python3 remigracao/ferramentas/paridade.py <mapa.json> --paralelo 3 --espera 2500
"""
import argparse
import collections
import datetime
import html
import json
import os
import re
import sys
from multiprocessing import get_context
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
import aem_fidelidade_render as FR  # noqa: E402
from aem_lib import CONFIG, build_session, normalize_name, parse_cookie_string  # noqa: E402

DADOS = Path(__file__).resolve().parents[1] / "dados" / "mapas"
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE     # cookie só vai para o author
HOST = BASE.split("//", 1)[1]
CHROME = "/usr/bin/google-chrome"

JS_METRICAS = """
() => {
  // Nenhum dos dois sites tem <main>. Conteúdo da página: destino = .responsivegrid.main (header/footer são XFs irmãos);
  // GWI = .subsidiary-page-content (header e footer são XFs DENTRO dele: #xf-header, .cmp-experiencefragment--footer).
  const FORA = ['header','footer','nav','aside','[class*="header__"]','[class*="footer__"]','[class*="breadcrumb"]',
    '[class*="navigation"]','[class*="megamenu"]','[class*="mega-menu"]','[role="navigation"]','[role="banner"]',
    '[role="contentinfo"]','[id*="copyright"]','[class*="socialmedia"]','[class*="social-media"]','[class*="cookie"]',
    '[class*="modal"]','[class*="drawer"]','.aem-GridColumn--default--hide','#xf-header','[class*="experiencefragment--header"]',
    '[class*="experiencefragment--footer"]','[id*="footer"]','[class*="subsidiary-footer"]','[class*="subsidiary-header"]',
    '[class*="header-xf"]','.grecaptcha-badge'].join(',');
  const alvo = document.querySelector('.responsivegrid.main') || document.querySelector('.subsidiary-page-content')
            || document.querySelector('main') || document.body;
  // XF de conteúdo (signup-and-contact do GWI, bloco de contato do destino, form de inscrição de evento): contado à parte
  const XF = '.cmp-experiencefragment, .experiencefragment';
  const ok = el => !el.closest(FORA) && !el.closest(XF);
  const txt = el => (el.textContent || '').replace(/\\s+/g, ' ').trim();
  const xfs = [...alvo.querySelectorAll(XF)].filter(x => !x.closest(FORA) && !x.parentElement.closest(XF)).map(x => ({
    nome: ([...x.classList].find(c => /^cmp-experiencefragment--/.test(c)) || x.id || 'xf').replace('cmp-experiencefragment--', ''),
    forms: x.querySelectorAll('form').length, embeds: x.querySelectorAll('iframe,video').length,
    links: [...x.querySelectorAll('a[href]')].map(a => txt(a).slice(0, 60)).filter(Boolean).slice(0, 8),
    texto: txt(x).slice(0, 160)}));
  const imgs = [...alvo.querySelectorAll('img')].filter(ok).map(i => {
    const r = i.getBoundingClientRect();
    return {src: i.currentSrc || i.src || '', nw: i.naturalWidth, w: Math.round(r.width), h: Math.round(r.height), alt: i.getAttribute('alt') || ''};
  });
  const links = [...alvo.querySelectorAll('a[href]')].filter(ok).map(a => ({href: a.getAttribute('href') || '', txt: txt(a).slice(0, 80), target: a.getAttribute('target') || ''}));
  const embeds = [...alvo.querySelectorAll('iframe,video,embed,object')].filter(ok).map(e => (e.getAttribute('src') || e.getAttribute('data-src') || e.querySelector('source')?.getAttribute('src') || e.tagName.toLowerCase()).slice(0, 160));
  const forms = [...alvo.querySelectorAll('form')].filter(ok).length;
  const tabelas = [...alvo.querySelectorAll('table')].filter(ok).length;
  const h1 = [...alvo.querySelectorAll('h1')].filter(ok).map(txt);
  const hs = {}; ['h1','h2','h3','h4'].forEach(t => { hs[t] = [...alvo.querySelectorAll(t)].filter(ok).length; });
  const bg = [];
  alvo.querySelectorAll('*').forEach(e => { if (!ok(e)) return; const b = getComputedStyle(e).backgroundImage;
    if (b && b !== 'none' && /url\\(/.test(b)) { const m = b.match(/url\\("?([^")]+)"?\\)/); if (m && !/data:/.test(m[1])) bg.push(m[1]); } });
  return {imgs, links, embeds, forms, tabelas, h1, hs, bg, xfs, altura: document.documentElement.scrollHeight, url: location.href};
}
"""

SCROLL = "async()=>{for(let y=0;y<document.body.scrollHeight;y+=700){scrollTo(0,y);await new Promise(r=>setTimeout(r,80));}scrollTo(0,0);}"


def _t(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _chave_link(href):
    """(tipo, chave) para casar link da origem com o do destino. None = não é link de conteúdo."""
    h = (href or "").strip()
    if not h or h.startswith(("#", "javascript:")):
        return None, None
    if re.match(r"^(mailto|tel):", h, re.I):
        return "ext", h.lower()
    if re.match(r"^https?://", h, re.I):
        u = urlparse(h)
        if u.netloc.endswith("adobeaemcloud.com") or (u.netloc.lower() in ("www.macnica.com", "macnica.com") and u.path.startswith("/americas/")):
            h = u.path                                   # site público do GWI: o destino reescreve para /content/…, casa pelo nó
        else:
            return "ext", re.sub(r"/+$", "", h.split("?")[0].split("#")[0].lower())
    p = unquote(h.split("?")[0].split("#")[0])
    p = re.sub(r"\.html$", "", p).rstrip("/")
    return "int", normalize_name(p.rsplit("/", 1)[-1]) if p else None


def links_faltando(origem, destino):
    """Links da origem sem correspondente no destino (externo: mesma URL; interno: mesmo nome de nó)."""
    chaves_d = collections.Counter(_chave_link(ln["href"]) for ln in destino)
    faltam, vistos = [], collections.Counter()
    for ln in origem:
        k = _chave_link(ln["href"])
        if k[0] is None or k[1] is None:
            continue
        vistos[k] += 1
        if chaves_d[k] < vistos[k] and not any(x["href"] == ln["href"] for x in faltam):
            faltam.append({"href": ln["href"][:160], "txt": ln["txt"]})
    return faltam


def _nome(src):
    return unquote(src.split("?")[0].rsplit("/", 1)[-1])[:70]


def _lado(pag, path, espera):
    unidades = FR.extrair(pag, BASE, path, espera)
    pag.evaluate(SCROLL)
    pag.wait_for_timeout(800)
    return unidades, pag.evaluate(JS_METRICAS)


def _imgs_visiveis(m):
    return [i for i in m["imgs"] if (i["w"] >= 40 and i["h"] >= 40) or i["nw"] >= 40]


def comparar_par(pag, sessao, existe, e, espera):
    r = {"rel": e["rel"], "path": e["path"], "origem": e["origem"], "titulo": e["titulo"], "motivos": [], "erro": ""}
    try:
        jc = sessao.get(BASE + quote(unquote(e["path"]), safe="/:") + "/jcr:content.json", timeout=60, allow_redirects=False)
        jc = jc.json() if jc.status_code == 200 else {}
        r["jcr"] = {"jcr:title": jc.get("jcr:title"), "jcr:description": jc.get("jcr:description"), "pageTitle": jc.get("pageTitle"),
                    "navTitle": jc.get("navTitle"), "cq:template": (jc.get("cq:template") or "").rsplit("/", 1)[-1]}
        ud, md = _lado(pag, e["path"], espera)
        if not md["url"].startswith(BASE + "/"):
            raise RuntimeError(f"destino navegou para fora do author: {md['url'][:80]}")
        r["destino"] = {"unidades": sum(1 for u in ud if not FR.e_ruido(u["txt"])), "imagens": [_nome(i["src"]) for i in _imgs_visiveis(md)],
                        "imagens_quebradas": [_nome(i["src"]) for i in md["imgs"] if i["nw"] == 0 and "/content/" in i["src"]],
                        "links": len(md["links"]), "embeds": md["embeds"], "forms": md["forms"], "tabelas": md["tabelas"],
                        "h1": md["h1"], "bg": [_nome(b) for b in md["bg"]], "altura": md["altura"], "xfs": md["xfs"], "hs": md.get("hs")}
        # alvos internos mortos e referências ao GWI no destino
        mortos, gwi = [], []
        for ln in md["links"]:
            h = ln["href"]
            if re.search(r"macnicagwi|www\.macnica\.com", h, re.I):
                gwi.append({"href": h[:160], "txt": ln["txt"]})
            if h.startswith("/content/"):
                p = unquote(h.split("?")[0].split("#")[0])
                p = re.sub(r"\.html$", "", p).rstrip("/")
                if p not in existe:
                    rr = sessao.get(BASE + quote(p, safe="/:") + ".0.json", timeout=60, allow_redirects=False)   # só author
                    existe[p] = rr.status_code
                if existe[p] != 200:
                    mortos.append({"href": p[:160], "txt": ln["txt"], "status": existe[p]})
        r["links_mortos"], r["links_gwi"] = mortos, gwi
        if e.get("origem_redirect"):
            r["veredito"] = "ORIGEM-REDIRECT"
            r["origem_redirect"] = e["origem_redirect"]
            r["motivos"].append(f"origin is a redirect to {e['origem_redirect']}; destination shows a full page "
                                f"({r['destino']['unidades']} text units, {len(r['destino']['imagens'])} images)")
        else:
            uo, mo = _lado(pag, e["origem"], espera)
            if not mo["url"].startswith(BASE + "/"):
                raise RuntimeError(f"origem navegou para fora do author: {mo['url'][:80]}")
            r["origem_dados"] = {"unidades": sum(1 for u in uo if not FR.e_ruido(u["txt"])), "imagens": [_nome(i["src"]) for i in _imgs_visiveis(mo)],
                                 "links": len(mo["links"]), "embeds": mo["embeds"], "forms": mo["forms"], "tabelas": mo["tabelas"],
                                 "h1": mo["h1"], "bg": [_nome(b) for b in mo["bg"]], "altura": mo["altura"], "xfs": mo["xfs"], "hs": mo.get("hs")}
            falt, sobr, fora, tit = FR.comparar(uo, ud)
            r["faltando"] = [{"tag": u["tag"], "txt": _t(u["txt"])[:600]} for u in falt]
            r["sobrando"] = [{"tag": u["tag"], "txt": _t(u["txt"])[:600]} for u in sobr]
            r["ordem"] = fora
            r["titulos_lista"] = [{"origem": _t(u["txt"])[:80], "destino": _t(v["txt"])[:80]} for u, v in tit]
            r["links_origem"] = [{"href": ln["href"][:300], "txt": ln["txt"]} for ln in mo["links"]]
            r["links_destino"] = [{"href": ln["href"][:300], "txt": ln["txt"]} for ln in md["links"]]
            r["links_faltando"] = links_faltando(r["links_origem"], r["links_destino"])
            r["embeds_faltando"] = [x for x in mo["embeds"] if x not in md["embeds"]]
        if "veredito" not in r:
            classificar(r)

    except Exception as ex:                                     # noqa: BLE001
        r["veredito"], r["erro"] = "ERRO", repr(ex)[:300]
    return r


# ---------------------------------------------------------------- classificação (offline; `--relatorio-de` refaz sem navegar)

CONHECIDOS_SOBRANDO = {"contact us for more information", "request a quote"}          # bloco de contato do XF do global2
ALVO_GOLIVE = re.compile(r"/contact/form$|/request-a-quote$|/products/ip-software/")     # decisão de go-live já registrada
EXT_ARQ = re.compile(r"\.(pdf|zip|docx?|xlsx?|pptx?|png|jpe?g)$", re.I)
CABECALHO_EVENTO = re.compile(r"^(location|start date|end date|date|time|venue|booth)\b|^register$", re.I)    # template do GWI (event-details-page)


def _chrome_download(u):
    """dt/dd do componente `download` do global2 (Filename / Size / application/pdf / 1 MB / nome-do-arquivo.pdf)."""
    n = FR.norm(u["txt"])
    return u["tag"] in ("dt", "dd") and (n in ("filename", "size", "format") or n.startswith("application ") or n.startswith("application/")
                                         or re.fullmatch(r"\d+(\.\d+)? ?(b|kb|mb|gb)", n) or EXT_ARQ.search(u["txt"]))


def classificar(r):
    """Preenche r['motivos'] (o que é para ver) e r['conhecidos'] (ruído catalogado) e dá o veredito."""
    r["motivos"], r["conhecidos"] = [], []
    if "links_origem" in r:                                    # recalcula com a regra atual de casamento
        r["links_faltando"] = links_faltando(r["links_origem"], r["links_destino"])
    jcr = r.get("jcr") or {}
    tit, desc = FR.norm(jcr.get("jcr:title") or ""), FR.norm(jcr.get("jcr:description") or "")
    d, o = r.get("destino") or {}, r.get("origem_dados")
    if o is not None:
        falt = [u for u in r.get("faltando", [])]
        sobr, conh_s = [], collections.Counter()
        for u in r.get("sobrando", []):
            n = FR.norm(u["txt"])
            if n in CONHECIDOS_SOBRANDO:
                conh_s["contact block of the global2 XF"] += 1
            elif _chrome_download(u):
                conh_s["download component labels (Filename/Size/type)"] += 1
            elif (u["tag"] == "h1" and n == tit) or (u["tag"] == "p" and desc and (n == desc or (len(n) >= 200 and desc.startswith(n[:200])))):
                conh_s["page title/description printed by the template"] += 1
            else:
                sobr.append(u)
        r["sobrando_ver"], r["faltando_ver"] = sobr, falt
        r["conhecidos"] += [f"{n}× {k}" for k, n in conh_s.items()]
        # h1 diferente = conteúdo de OUTRA página (vidtrans-2017 mostrava "IBC 2016")
        h1o = [FR.norm(x) for x in o.get("h1", []) if x.strip()]
        h1d = [FR.norm(x) for x in d.get("h1", []) if x.strip()]
        if h1o and h1d and not any(a == b or a in b or b in a for a in h1o[:1] for b in h1d):
            r["motivos"].append(f"h1 differs: origin '{o['h1'][0][:50]}', destination '{d['h1'][0][:50]}'")
        ho, hd = o.get("hs") or {}, d.get("hs") or {}
        if ho and hd and hd.get("h1", 0) > max(1, ho.get("h1", 0)) + 1:
            r["motivos"].append(f"headings: destination has {hd['h1']} h1 (origin {ho['h1']}) — sub-headings or paragraphs promoted to h1")
        evento = [u for u in falt if CABECALHO_EVENTO.search(u["txt"])]
        resto = [u for u in falt if u not in evento]
        if evento:
            r["motivos"].append(f"event header from the GWI template missing ({len(evento)}: location, dates, Register)")
        if resto:
            r["motivos"].append(f"{len(resto)} text unit(s) of the origin missing")
        if sobr:
            r["motivos"].append(f"{len(sobr)} text unit(s) only on the destination")
        if len(d["imagens"]) < len(o["imagens"]):
            r["motivos"].append(f"images: origin {len(o['imagens'])}, destination {len(d['imagens'])}")
        if r.get("links_faltando"):
            r["motivos"].append(f"{len(r['links_faltando'])} link(s) of the origin without a counterpart")
        if r.get("embeds_faltando"):
            r["motivos"].append(f"{len(r['embeds_faltando'])} embed(s) of the origin missing")
        if o["forms"] > d["forms"]:
            r["motivos"].append(f"forms: origin {o['forms']}, destination {d['forms']}")
        xo, xd = [x["nome"] for x in o.get("xfs", [])], [x["nome"] for x in d.get("xfs", [])]
        if xo or xd:
            r["conhecidos"].append(f"XFs — origin: {', '.join(xo) or 'none'}; destination: {', '.join(xd) or 'none'}")
        xf_form = [x for x in o.get("xfs", []) if x["forms"]]
        if xf_form and not any(x["forms"] for x in d.get("xfs", [])):
            r["motivos"].append(f"form inside origin XF ({', '.join(x['nome'] for x in xf_form)}) with no form on the destination")
    if d.get("imagens_quebradas"):
        r["motivos"].append(f"{len(d['imagens_quebradas'])} broken image(s) on the destination")
    mortos = [m for m in r.get("links_mortos", []) if not ALVO_GOLIVE.search(m["href"])]
    conh_m = len(r.get("links_mortos", [])) - len(mortos)
    if conh_m:
        r["conhecidos"].append(f"{conh_m}× dead link to /contact/form, /request-a-quote or ip-software (go-live decision)")
    r["links_mortos_ver"] = mortos
    if mortos:
        r["motivos"].append(f"{len(mortos)} dead internal link(s) on the destination")
    if r.get("links_gwi"):
        r["motivos"].append(f"{len(r['links_gwi'])} link(s) on the destination pointing to the GWI")
    r["veredito"] = "VER" if r["motivos"] else "OK"


def trabalhar(args):
    pares, espera, idx = args
    from playwright.sync_api import sync_playwright
    sessao, _ = build_session(prompt_if_missing=False, verbose=False)
    cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
    existe, out = {}, []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1400, "height": 1000})
        ctx.add_cookies([{"name": k, "value": v, "domain": HOST, "path": "/"} for k, v in cookies.items()])
        pag = ctx.new_page()
        for i, e in enumerate(pares, 1):
            r = comparar_par(pag, sessao, existe, e, espera)
            out.append(r)
            print(f"  [{idx}:{i:3}/{len(pares)}] {r['veredito']:15} {e['rel'][:70]:70} {'; '.join(r['motivos'])[:90]}{' ' + r['erro'][:80] if r['erro'] else ''}", flush=True)
        nav.close()
    return out


# ---------------------------------------------------------------- HTML

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1f23;--mut:#6a6f78;--lin:#e4e1d8;--acc:#0b5cad;--vis:#6b3fa0;--card:#fff;--ok:#1b7f3b;--ver:#b3261e;--red:#8a6d00}
@media (prefers-color-scheme:dark){:root{--bg:#15171b;--fg:#e8e6e1;--mut:#9aa0aa;--lin:#2b2f36;--acc:#7db7f5;--vis:#c3a2ee;--card:#1c1f24;--ok:#5fc07a;--ver:#f28b82;--red:#e0c060}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:32px 16px 80px}
h1{font-size:26px;margin:0 0 4px}
.sub{color:var(--mut);margin:0 0 16px}
.barra{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--lin);z-index:2;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.barra input[type=search]{flex:1 1 260px;padding:8px 10px;border:1px solid var(--lin);border-radius:6px;background:var(--card);color:var(--fg);font:inherit}
.barra nav a{margin-right:12px;white-space:nowrap}
.barra label{white-space:nowrap;color:var(--mut)}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}a:visited{color:var(--vis)}
h2{font-size:21px;margin:36px 0 8px;scroll-margin-top:64px}
h2 .n,summary .n{color:var(--mut);font-weight:400;font-size:14px;margin-left:6px}
details{background:var(--card);border:1px solid var(--lin);border-radius:8px;margin:8px 0;padding:0 14px}
summary{cursor:pointer;padding:10px 0;font-weight:600;font-size:15px}
details[open]>summary{border-bottom:1px solid var(--lin)}
.badge{display:inline-block;font-size:11px;font-weight:700;padding:1px 7px;border-radius:10px;margin-right:8px;vertical-align:middle;color:#fff}
.OK .badge{background:var(--ok)}.VER .badge{background:var(--ver)}.ORIGEM-REDIRECT .badge{background:var(--red)}.ERRO .badge{background:#555}
.p{display:block;color:var(--mut);font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere;font-weight:400}
.x{font-size:12px;color:var(--mut);margin-left:8px}
.x a,.x a:visited{color:var(--mut);text-decoration:underline dotted}
.mot{font-weight:400;color:var(--ver);font-size:13px;margin-left:8px}
.ORIGEM-REDIRECT .mot{color:var(--red)}
table{border-collapse:collapse;font-size:13px;margin:10px 0}
td,th{border:1px solid var(--lin);padding:3px 10px;text-align:left}th{color:var(--mut);font-weight:600}
h4{margin:14px 0 4px;font-size:14px}
ul{margin:0 0 8px;padding-left:20px}li{padding:2px 0}
.tag{color:var(--mut);font:12px ui-monospace,Menlo,Consolas,monospace;margin-right:6px}
.oculto{display:none}
body.so-ver details.OK{display:none}
.resumo{display:flex;gap:18px;flex-wrap:wrap;margin:14px 0}
.resumo div{background:var(--card);border:1px solid var(--lin);border-radius:8px;padding:8px 14px}
.resumo b{font-size:20px;display:block}
footer{margin-top:48px;color:var(--mut);font-size:13px;border-top:1px solid var(--lin);padding-top:12px}
"""

JS = """
const q=document.getElementById('q');
q.addEventListener('input',()=>{const t=q.value.trim().toLowerCase();
  document.querySelectorAll('details.pg').forEach(d=>{d.classList.toggle('oculto',!!t&&!(d.dataset.t||'').includes(t))});});
document.getElementById('sover').addEventListener('change',e=>document.body.classList.toggle('so-ver',e.target.checked));
"""


def _a(href, texto):
    return f'<a href="{html.escape(href, quote=True)}" target="_blank" rel="noopener">{html.escape(texto)}</a>'


def _link(path):
    return BASE + quote(unquote(path), safe="/:") + ".html?wcmmode=disabled"


def _editor(path):
    return BASE + "/editor.html" + quote(unquote(path), safe="/:") + ".html"


def _lista(itens, fmt):
    return "<ul>" + "".join(f"<li>{fmt(x)}</li>" for x in itens) + "</ul>"


def _pagina_html(r):
    cls = r["veredito"]
    partes = [f'<details class="pg {cls}"{" open" if cls != "OK" else ""} data-t="{html.escape((r["titulo"] + " " + r["rel"]).lower(), quote=True)}">']
    mot = html.escape("; ".join(r["motivos"]) or r["erro"])
    conh = html.escape("; ".join(r.get("conhecidos") or []))
    partes.append(f'<summary><span class="badge">{cls}</span>{html.escape(r["titulo"] or r["rel"])}'
                  f'<span class="mot">{mot}</span>{f"<span class=x>known: {conh}</span>" if conh else ""}<span class="p">/{html.escape(r["rel"])}</span></summary>')
    partes.append(f'<p class="x">{_a(_link(r["path"]), "page")} · {_a(_editor(r["path"]), "edit")} · '
                  + (_a(_link(r["origem"]), "origin") if r["origem"] else "no origin") + "</p>")
    d, o = r.get("destino"), r.get("origem_dados")
    if d:
        def cel(k, f=lambda v: v):
            return f"<td>{html.escape(str(f(o.get(k))) if o else '—')}</td><td>{html.escape(str(f(d.get(k))))}</td>"
        partes.append("<table><tr><th></th><th>origin</th><th>destination</th></tr>"
                      f"<tr><th>text units</th>{cel('unidades')}</tr>"
                      f"<tr><th>images (≥40px)</th>{cel('imagens', len)}</tr>"
                      f"<tr><th>links</th>{cel('links')}</tr>"
                      f"<tr><th>embeds (iframe/video)</th>{cel('embeds', len)}</tr>"
                      f"<tr><th>forms</th>{cel('forms')}</tr>"
                      f"<tr><th>tables</th>{cel('tabelas')}</tr>"
                      f"<tr><th>h1</th>{cel('h1', lambda v: ' | '.join(x[:60] for x in (v or [])[:6]) + (' …' if len(v or []) > 6 else ''))}</tr>"
                      f"<tr><th>headings h1/h2/h3/h4</th>{cel('hs', lambda v: '/'.join(str(v.get(t, 0)) for t in ('h1', 'h2', 'h3', 'h4')) if v else '—')}</tr>"
                      f"<tr><th>page height (px)</th>{cel('altura')}</tr></table>")
    if r.get("origem_redirect"):
        partes.append(f'<p class="x">origin redirects to {html.escape(r["origem_redirect"])}</p>')
    if r.get("faltando_ver"):
        partes.append(f"<h4>Missing on the destination ({len(r['faltando_ver'])})</h4>"
                      + _lista(r["faltando_ver"], lambda u: f'<span class="tag">{u["tag"]}</span>{html.escape(u["txt"])}'))
    if r.get("sobrando_ver"):
        partes.append(f"<h4>Only on the destination ({len(r['sobrando_ver'])})</h4>"
                      + _lista(r["sobrando_ver"], lambda u: f'<span class="tag">{u["tag"]}</span>{html.escape(u["txt"])}'))
    if r.get("titulos_lista"):
        partes.append("<h4>List items with the same target and a different label</h4>"
                      + _lista(r["titulos_lista"], lambda t: f'{html.escape(t["origem"])} → {html.escape(t["destino"])}'))
    if r.get("links_faltando"):
        partes.append(f"<h4>Links of the origin without a counterpart ({len(r['links_faltando'])})</h4>"
                      + _lista(r["links_faltando"], lambda l: f'{html.escape(l["txt"] or "(no text)")} <span class="p">{html.escape(l["href"])}</span>'))
    if r.get("embeds_faltando"):
        partes.append("<h4>Embeds of the origin missing</h4>" + _lista(r["embeds_faltando"], lambda s: html.escape(s)))
    if d and d["imagens_quebradas"]:
        partes.append("<h4>Broken images on the destination</h4>" + _lista(d["imagens_quebradas"], lambda s: html.escape(s)))
    if r.get("links_mortos_ver"):
        partes.append("<h4>Dead internal links on the destination</h4>"
                      + _lista(r["links_mortos_ver"], lambda l: f'{html.escape(l["txt"] or "(no text)")} <span class="p">{html.escape(l["href"])} → HTTP {l["status"]}</span>'))
    if r.get("links_gwi"):
        partes.append("<h4>Links on the destination pointing to the GWI</h4>"
                      + _lista(r["links_gwi"], lambda l: f'{html.escape(l["txt"] or "(no text)")} <span class="p">{html.escape(l["href"])}</span>'))
    if d and (d["embeds"] or (o and o["embeds"])):
        partes.append("<h4>Embeds</h4><p class=\"x\">origin: " + html.escape(" | ".join(o["embeds"]) if o else "—")
                      + "<br>destination: " + html.escape(" | ".join(d["embeds"]) or "—") + "</p>")
    xfs = [(lado, x) for lado, dd in (("origin", o), ("destination", d)) if dd for x in dd.get("xfs", [])]
    if xfs:
        partes.append("<h4>Experience fragments inside the content</h4>"
                      + _lista(xfs, lambda lx: f'<span class="tag">{lx[0]}</span>{html.escape(lx[1]["nome"])} — forms {lx[1]["forms"]}, embeds {lx[1]["embeds"]}, links: {html.escape(", ".join(lx[1]["links"]) or "—")}'))
    if r["erro"]:
        partes.append(f'<p class="mot">{html.escape(r["erro"])}</p>')
    partes.append("</details>")
    return "".join(partes)


def _grupo(m):
    """Motivo sem os números e sem o detalhe, para contar por tipo."""
    m = re.sub(r"^h1 differs:.*", "h1 differs (origin shows pageTitle, destination shows jcr:title)", m)
    m = re.sub(r"^origin is a redirect to \S+;.*", "origin is a redirect; destination shows a full page", m)
    m = re.sub(r"^headings:.*", "headings: sub-headings or paragraphs promoted to h1", m)
    m = re.sub(r"\(\d+: ", "(", m)
    return re.sub(r"^\d+ ", "", re.sub(r"\b\d+\b", "N", m)) if not m.startswith(("event", "form", "images", "headings")) else re.sub(r"\b\d+\b", "N", m)


def recorrentes(res, chave):
    c = collections.defaultdict(list)
    for r in res:
        for u in r.get(chave + "_ver") or []:
            c[FR.norm(u["txt"])].append(r["rel"])
    return sorted(((k, v) for k, v in c.items() if len(v) > 1), key=lambda kv: -len(kv[1]))


def montar_html(res, meta):
    por_ver = collections.Counter(r["veredito"] for r in res)
    ramos = collections.OrderedDict()
    for r in res:
        ramos.setdefault(r["rel"].split("/")[0] if "/" in r["rel"] else "(root level)", []).append(r)
    nav, corpo = [], []
    for ramo, itens in ramos.items():
        idr = "r-" + re.sub(r"[^a-z0-9]+", "-", ramo.lower())
        n_ver = sum(1 for r in itens if r["veredito"] != "OK")
        nav.append(f'<a href="#{idr}">{html.escape(ramo)} ({n_ver}/{len(itens)})</a>')
        corpo.append(f'<h2 id="{idr}">{html.escape(ramo)}<span class="n">{len(itens)} pages, {n_ver} to review</span></h2>')
        corpo += [_pagina_html(r) for r in itens]
    rec = []
    for chave, rotulo in (("faltando", "Missing on the destination"), ("sobrando", "Only on the destination")):
        lst = recorrentes(res, chave)
        if lst:
            rec.append(f"<h4>{rotulo} — same text on more than one page ({len(lst)})</h4><ul>"
                       + "".join(f'<li><b>{len(v)}×</b> {html.escape(k[:160])} <span class="p">{html.escape(", ".join(v[:4]))}{"…" if len(v) > 4 else ""}</span></li>' for k, v in lst[:40])
                       + "</ul>")
    motivos = collections.Counter(_grupo(m) for r in res for m in r["motivos"])
    resumo = "".join(f"<div><b>{por_ver.get(k, 0)}</b>{k}</div>" for k in ("OK", "VER", "ORIGEM-REDIRECT", "ERRO"))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(meta['nome'])} — content parity</title><style>{CSS}</style></head><body><main>
<h1>{html.escape(meta['nome'])} — content parity with the origin</h1>
<p class="sub"><code>{html.escape(meta['raiz'])}</code> against <code>{html.escape(meta['origem'])}</code>, rendered at 1400px outside the editor.
Text is compared by containment after filtering site chrome (menu, footer, breadcrumb, cookie bar); images, links, embeds and forms are counted
per side inside the main content. Layout is not judged here. {len(res)} pages. Generated {meta['quando']}.</p>
<div class="resumo">{resumo}</div>
<details open><summary>Recurring differences<span class="n">group first, then open pages</span></summary>{''.join(rec) or '<p class="x">none</p>'}
<h4>Reasons, by number of pages</h4><ul>{''.join(f'<li><b>{n}×</b> {html.escape(m)}</li>' for m, n in motivos.most_common())}</ul></details>
<div class="barra"><input id="q" type="search" placeholder="Filter by title or path…" autocomplete="off">
<label><input id="sover" type="checkbox"> only pages to review</label><nav>{''.join(nav)}</nav></div>
{''.join(corpo)}
<footer>Read-only: every request was a GET to the AEM author. OK means no text missing or extra, no broken image, no missing link/embed/form,
no dead internal link. Verify a VER page by opening the two links side by side; the comparator has known blind spots (see aem_fidelidade_render.py).</footer>
</main><script>{JS}</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mapa", help="JSON gerado pelo mapa_links.py")
    ap.add_argument("--so", nargs="*", default=None, metavar="REL", help="só estas rels (prefixo também vale)")
    ap.add_argument("--paralelo", type=int, default=3, help="navegadores em paralelo (padrão 3)")
    ap.add_argument("--espera", type=int, default=2500, help="ms de espera após o load (padrão 2500)")
    ap.add_argument("--saida", default=None, help="nome dos arquivos em dados/mapas (padrão: <mapa>_paridade)")
    ap.add_argument("--relatorio-de", default=None, metavar="JSON", help="não navega: reclassifica e regrava HTML/JSON a partir deste JSON")
    a = ap.parse_args()
    if a.relatorio_de:
        j = json.loads(Path(a.relatorio_de).read_text(encoding="utf-8"))
        res, meta = j["paginas"], j["meta"]
        for r in res:
            if r["veredito"] not in ("ORIGEM-REDIRECT", "ERRO"):
                classificar(r)
        nome = a.saida or Path(a.relatorio_de).stem
        (DADOS / f"{nome}.html").write_text(montar_html(res, meta), encoding="utf-8")
        (DADOS / f"{nome}.json").write_text(json.dumps({"meta": meta, "sem_origem": j.get("sem_origem", []), "paginas": res},
                                                       ensure_ascii=False, indent=1), encoding="utf-8")
        resumo(res, nome)
        return
    mapa = json.loads(Path(a.mapa).read_text(encoding="utf-8"))
    paginas = [e for e in mapa["paginas"] if not e.get("deleted")]
    if a.so is not None:
        paginas = [e for e in paginas if any(e["rel"] == s or e["rel"].startswith(s.rstrip("/") + "/") for s in a.so)]
    sem_origem = [e for e in paginas if not e.get("origem")]
    paginas = [e for e in paginas if e.get("origem")]
    nome = a.saida or (Path(a.mapa).stem + "_paridade")
    print(f"{len(paginas)} pares (origem = GWI), {len(sem_origem)} sem origem (fora), {a.paralelo} navegadores")

    n = max(1, min(a.paralelo, len(paginas)))
    lotes = [(paginas[i::n], a.espera, i + 1) for i in range(n)]
    if n == 1:
        res = trabalhar(lotes[0])
    else:
        with get_context("spawn").Pool(n) as pool:
            res = [r for lote in pool.map(trabalhar, lotes) for r in lote]
    quando = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta = {"nome": Path(a.mapa).stem, "raiz": mapa["raiz"]["path"], "origem": mapa.get("origem") or "", "quando": quando}
    anterior = DADOS / f"{nome}.json"
    if a.so is not None and anterior.exists():                # funde: as rels refeitas substituem as antigas
        j = json.loads(anterior.read_text(encoding="utf-8"))
        refeitas = {r["rel"] for r in res}
        res += [r for r in j["paginas"] if r["rel"] not in refeitas]
        meta = dict(j["meta"], quando=f"{j['meta']['quando']} (+{len(refeitas)} pages redone {quando})")
        print(f"fundido com {anterior.name}: {len(refeitas)} refeitas, {len(res)} no total")
    res.sort(key=lambda r: r["rel"])
    DADOS.mkdir(parents=True, exist_ok=True)
    (DADOS / f"{nome}.html").write_text(montar_html(res, meta), encoding="utf-8")
    (DADOS / f"{nome}.json").write_text(json.dumps({"meta": meta, "sem_origem": [e["rel"] for e in sem_origem], "paginas": res},
                                                   ensure_ascii=False, indent=1), encoding="utf-8")

    resumo(res, nome)


def resumo(res, nome):
    por = collections.Counter(r["veredito"] for r in res)
    print("\nveredito:", dict(por))
    motivos = collections.Counter(_grupo(m) for r in res for m in r["motivos"])
    for m, k in motivos.most_common():
        print(f"    {k:4d}  {m}")
    conh = collections.Counter(re.sub(r"^\d+× ", "", c) for r in res for c in r.get("conhecidos") or [])
    print("conhecido (não conta):")
    for m, k in conh.most_common(12):
        print(f"    {k:4d}  {m}")
    for chave, rotulo in (("faltando", "FALTANDO recorrente"), ("sobrando", "SOBRANDO recorrente")):
        lst = recorrentes(res, chave)
        if lst:
            print(f"\n{rotulo} (texto igual em mais de uma página): {len(lst)}")
            for k, v in lst[:25]:
                print(f"    {len(v):4d}×  {k[:110]}")
    for r in res:
        if r["veredito"] == "ERRO":
            print(f"ERRO  {r['rel']}  {r['erro']}")
    print(f"\n{DADOS / (nome + '.html')}\n{DADOS / (nome + '.json')}")


if __name__ == "__main__":
    main()
