#!/usr/bin/env python3
"""
auditoria_padroes.py — auditoria SOMENTE LEITURA das páginas da whitelist do tracker, a 1400px, contra 4 critérios
definidos em 28/09/2026:

  1. CTA   — botões no fim da página (Contact Us, Sign Up, Request a Quote…) são Experience Fragment, não
             container com botões na própria página.
  2. TÍTULOS — hierarquia semântica: título da página = h1 (um só); seção = h2; subseção = h3…; sem pular nível.
  3. VÍDEO — vídeo dentro de flex container com 2+ itens (senão ocupa a largura toda da página sem margem);
             o ideal é o outro item ter o texto relacionado, ao lado do vídeo.
  4. TWI   — Text with Image com imagem à esquerda (Left): imageRatio sem vão entre imagem e texto, imagem não
             muito mais alta que o texto; texto bem mais alto que a imagem = candidato a Wrap.

Para o TWI a ferramenta SIMULA no navegador (só no DOM local, nada vai ao AEM) cada imageRatio de 5 a 60% e o
Wrap, e mede imagem/texto em cada um — a recomendação sai da medida, não de conta.

Mede com ?wcmmode=disabled (o que o visitante vê; ver aem-url-direta-do-author-e-modo-edicao), rola a página
inteira antes (imagem lazy) e abre todas as abas (cada painel é medido; ver pagina-com-abas-se-confere-aba-por-aba).

    set -a; . ../.env; set +a      # de scripts-hazael/
    python3 remigracao/ferramentas/auditoria_padroes.py coletar            # whitelist inteira (GET fresco)
    python3 remigracao/ferramentas/auditoria_padroes.py coletar --paginas /products/x /about-us/y
    python3 remigracao/ferramentas/auditoria_padroes.py analisar           # junta tudo em achados.json

Saída: remigracao/dados/auditoria_<data>/ (fora do git): whitelist.json, jcr/, paginas/<slug>.json, achados.json.
Só GET no author (cookie) e no tracker (token) — cada credencial só no seu host.
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests

_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, build_session, fetch_with_depth_fallback, parse_cookie_string  # noqa: E402

TRACKER = "https://site-migration-tracker.mdhw.dev/api"
MAI = "/content/macnicaglobal2/americas/mai/en"
DADOS = Path(__file__).resolve().parents[1] / "dados" / f"auditoria_{datetime.date.today():%d%m}"
LARGURA = 1400

# ─── sonda (roda na página) ────────────────────────────────────────────────────────────────────────────────
PROBE = r"""
async () => {
  const main = document.querySelector('.container.main') || document.querySelector('.root');
  const R = e => { if (!e) return null; const r = e.getBoundingClientRect();
    return {x: Math.round(r.x), y: Math.round(r.y + scrollY), w: Math.round(r.width), h: Math.round(r.height)}; };
  const T = e => ((e && (e.innerText || e.textContent)) || '').replace(/\s+/g, ' ').trim();
  const inXF = e => !!e.closest('.experiencefragment');
  const bg = e => { for (let n = e; n && n !== document.documentElement; n = n.parentElement) {
      const c = getComputedStyle(n).backgroundColor; if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') return c; }
    return 'rgb(255, 255, 255)'; };
  const topIdx = e => { const grid = main.querySelector(':scope > .cmp-container > .aem-Grid') || main;
    let n = e; while (n && n.parentElement !== grid) n = n.parentElement; return n ? [...grid.children].indexOf(n) : -1; };
  const ctx = e => { const fi = e.closest('.flexcontaineritem'); const tab = e.closest('.cmp-tabs__tabpanel');
    return {top: topIdx(e), flexItem: !!fi, tab: tab ? [...tab.parentElement.querySelectorAll(':scope > .cmp-tabs__tabpanel')].indexOf(tab) : null,
            card: !!e.closest('.cardlist,.list,.teaser'), bg: bg(e)}; };

  // abas: todos os painéis visíveis (medida por painel; o empilhamento só muda y, não largura)
  const st = document.createElement('style');
  st.textContent = '.cmp-tabs__tabpanel{display:block !important;visibility:visible !important}';
  document.head.appendChild(st);
  for (let y = 0; y < document.body.scrollHeight; y += 600) { scrollTo(0, y); await new Promise(r => setTimeout(r, 90)); }
  scrollTo(0, 0);
  const imgs = [...main.querySelectorAll('img')];
  imgs.forEach(i => { i.loading = 'eager'; });
  const t0 = Date.now();
  while (Date.now() - t0 < 12000 && imgs.some(i => !i.complete)) await new Promise(r => setTimeout(r, 200));

  const W = main.getBoundingClientRect().width;
  const out = {W: Math.round(W), scrollW: document.documentElement.scrollWidth, headings: [], comps: [], videos: [], twis: [],
               headerH1: [...document.querySelectorAll('.cmp-experiencefragment--header h1')].map(h => T(h))};

  // ── títulos ──
  main.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach(h => {
    if (h.closest('.cmp-experiencefragment--header,.cmp-experiencefragment--footer')) return;
    const comp = h.closest('.title,.textwithimage,.text,.tabs,.cardlist,.list,.teaser,.table,.experiencefragment,.accordion');
    const cs = getComputedStyle(h);
    out.headings.push({lv: +h.tagName[1], txt: T(h).replace(/\s*opens in a new tab/g, '').slice(0, 160), comp: comp ? comp.classList[0] : '?', inXF: inXF(h),
      vis: h.getClientRects().length > 0 && cs.visibility !== 'hidden' && cs.display !== 'none', fs: cs.fontSize, fw: cs.fontWeight,
      y: R(h).y, ...ctx(h)});
  });

  // ── componentes-folha em ordem (para o fim da página e para casar com o JCR) ──
  const NOMES = ['textwithimage', 'title', 'text', 'image', 'button', 'table', 'embed', 'experiencefragment', 'list',
                 'cardlist', 'downloadlist', 'carousel', 'anchorlink', 'form', 'teaser', 'tabs', 'separator'];
  const folhas = [];
  main.querySelectorAll('div').forEach(d => {
    const cl = d.classList; const nome = NOMES.find(n => cl.contains(n));
    if (!nome) return;
    if (nome !== 'experiencefragment' && d.parentElement.closest('.experiencefragment')) return;   // dentro de XF
    if (nome === 'image' && cl.contains('textwithimage')) return;
    if (['text', 'title', 'image', 'button'].includes(nome) && d.parentElement.closest('.textwithimage,.cardlist,.list,.teaser,.form,.downloadlist')) return;
    if (nome === 'form' && !d.querySelector('form')) return;
    const r = R(d); const tt = T(d).replace(/\s*opens in a new tab/g, ''); const it = {k: nome, txt: tt.slice(0, 200), n: tt.length, y: r.y, h: r.h, x: r.x, w: r.w, ...ctx(d)};
    if (nome === 'button') { const a = d.querySelector('a,button'); it.href = a ? a.getAttribute('href') : null; it.download = !!(a && (/\/content\/dam\//.test(a.getAttribute('href') || '') || a.hasAttribute('download'))) || /download/.test(d.className); it.cls = d.className.replace(/aem-GridColumn\S*/g, '').trim();
      it.btnBg = a ? getComputedStyle(a).backgroundColor : null; }
    if (nome === 'experiencefragment') { const x = d.querySelector('.cmp-experiencefragment'); it.xf = x ? x.className : '';
      it.botoes = [...d.querySelectorAll('a.cmp-button, .button a')].map(a => ({txt: T(a), href: a.getAttribute('href')})); }
    folhas.push(it);
  });
  out.comps = folhas;

  // ── vídeos ──
  const vids = [...main.querySelectorAll('iframe, video')].filter(v => /youtube|vimeo|youtu\.be|brightcove|wistia/i.test(v.src || v.getAttribute('data-src') || '') || v.tagName === 'VIDEO');
  vids.forEach(v => {
    const fi = v.closest('.flexcontaineritem'); const fc = fi ? fi.closest('.flexcontainer') : null;
    const itens = fc ? [...fc.querySelectorAll('.flexcontaineritem')].filter(i => i.parentElement.closest('.flexcontainer') === fc) : [];
    const rv = R(v);
    const outros = itens.filter(i => i !== fi).map(i => ({...R(i), txt: T(i).slice(0, 300), temImg: !!i.querySelector('img'),
      temVideo: !!i.querySelector('iframe,video'), lado: (() => { const r = R(i); return r.h > 0 && r.y < rv.y + rv.h && r.y + r.h > rv.y; })()}));
    const comp = v.closest('.embed,.text,.textwithimage');
    // texto antes/depois (para propor o que vai ao lado)
    const idx = folhas.findIndex(f => f.y >= rv.y - 2 && Math.abs(f.y - R(comp || v).y) < 3);
    const antes = folhas.filter(f => f.y + f.h <= rv.y && ['title', 'text', 'textwithimage'].includes(f.k)).slice(-2).map(f => ({k: f.k, txt: f.txt.slice(0, 200)}));
    const depois = folhas.filter(f => f.y >= rv.y + rv.h && ['title', 'text', 'textwithimage'].includes(f.k)).slice(0, 2).map(f => ({k: f.k, txt: f.txt.slice(0, 200)}));
    out.videos.push({src: (v.src || v.getAttribute('data-src') || '').slice(0, 120), comp: comp ? comp.classList[0] : '?', rect: rv,
      frac: +(rv.w / W).toFixed(2), emFlex: !!fc, nItens: itens.length,
      nItensComConteudo: itens.filter(i => T(i).length > 0 || i.querySelector('img,iframe,video')).length,
      outros, antes, depois, ...ctx(v)});
  });

  // ── Text with Image: medida atual + simulação de imageRatio (5–60%) e de Wrap ──
  const mede = (el) => { const it = el.querySelector('.cmp-textwithimage__item__image');
    const img = it && (it.querySelector('img.cmp-textwithimage__inner--pc') || it.querySelector('img'));
    const p = el.querySelector('.paragraph') || el.querySelector('.cmp-textwithimage__item:not(.cmp-textwithimage__item__image)');
    return {bloco: R(el), col: R(it), img: R(img), txt: R(p)}; };
  main.querySelectorAll('.textwithimage').forEach(w => {
    if (w.parentElement.closest('.experiencefragment')) return;
    const el = w.querySelector('.cmp-textwithimage'); if (!el) return;
    const it = el.querySelector('.cmp-textwithimage__item__image');
    const img = it && (it.querySelector('img.cmp-textwithimage__inner--pc') || it.querySelector('img'));
    const p = el.querySelector('.paragraph');
    const atual = mede(el);
    const reg = {left: w.classList.contains('left'), wrap: w.classList.contains('wrap'), vcenter: w.classList.contains('vert-center'),
      ratio: el.style.getPropertyValue('--textwithimage-image-ratio').trim(), nat: img ? [img.naturalWidth, img.naturalHeight] : null,
      src: img ? (img.getAttribute('src') || '').split('/').pop() : null, alt: img ? img.getAttribute('alt') : null,
      txt: T(p).slice(0, 240), nTxt: T(p).length, hs: p ? [...p.querySelectorAll('h1,h2,h3,h4,h5,h6')].map(h => h.tagName) : [],
      atual, sim: [], simWrap: null, ...ctx(w)};
    if (img && img.naturalWidth && !reg.wrap) {
      const orig = el.getAttribute('style');
      for (let r = 5; r <= 60; r++) { el.style.setProperty('--textwithimage-image-ratio', r + '%'); const m = mede(el);
        reg.sim.push([r, m.col.w, m.img.w, m.img.h, m.txt.h, m.txt.x - (m.img.x + m.img.w)]); }
      if (orig === null) el.removeAttribute('style'); else el.setAttribute('style', orig);
      w.classList.add('wrap'); const m = mede(el); reg.simWrap = {img: m.img, txt: m.txt, bloco: m.bloco}; w.classList.remove('wrap');
    } else if (img && reg.wrap) {
      const orig = el.getAttribute('style');
      w.classList.remove('wrap'); const sims = [];
      for (const r of [20, 30, 40]) { el.style.setProperty('--textwithimage-image-ratio', r + '%'); const m = mede(el); sims.push([r, m.col.w, m.img.w, m.img.h, m.txt.h, m.txt.x - (m.img.x + m.img.w)]); }
      if (orig === null) el.removeAttribute('style'); else el.setAttribute('style', orig);
      w.classList.add('wrap'); reg.simSemWrap = sims;
    }
    out.twis.push(reg);
  });
  st.remove();
  return out;
}
"""


# ─── tracker ──────────────────────────────────────────────────────────────────────────────────────────────
def tracker(lista):
    """GET fresco da whitelist/blacklist. Vai só o token do tracker, nunca o cookie do AEM."""
    tok = os.environ.get("MIGRATION_TRACKER_TOKEN", "").strip()
    if not tok:
        sys.exit("MIGRATION_TRACKER_TOKEN vazio no ambiente (set -a; . ../.env; set +a)")
    r = requests.get(f"{TRACKER}/{lista}", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    r.raise_for_status()
    return r.json()


def slug(aem_path):
    return aem_path[len(MAI):].strip("/").replace("/", "__") or "_home"


# ─── JCR: ordem dos componentes renderizados ──────────────────────────────────────────────────────────────
RENDERIZA = {"container", "flexcontainer", "flexcontaineritem", "responsivegrid", "tabs", "stickytabs", "carousel",
             "accordion"}


def nos_em_ordem(jcr):
    """(caminho relativo a jcr:content, tipo, nó) em ordem de documento, só dentro de root/containers."""
    saida = []

    def anda(no, cam):
        for k, v in no.items():
            if not isinstance(v, dict) or k in ("cq:responsive", "cq:featuredimage"):
                continue
            rt = str(v.get("sling:resourceType", "")).split("/")[-1]
            saida.append((f"{cam}/{k}", rt, v))
            if rt in RENDERIZA or k == "root":
                anda(v, f"{cam}/{k}")
    raiz = jcr.get("root")
    if isinstance(raiz, dict):
        anda(raiz, "root")
    return saida


def txt(v):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(v or ""))).strip()


# ─── coleta (1 processo por lote, 1 navegador por processo) ───────────────────────────────────────────────
def _coletar_lote(paginas, cookies_raw, base, saida):
    from playwright.sync_api import sync_playwright
    host = urlparse(base).hostname
    assert host and host.startswith("author-"), "cookie só vai para o author"
    cookies = parse_cookie_string(cookies_raw)
    feitos = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
        c = b.new_context(viewport={"width": LARGURA, "height": 1000})
        c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in cookies.items()])
        for pag in paginas:
            arq = Path(saida) / "paginas" / f"{slug(pag['aem_path'])}.json"
            if arq.exists():
                feitos.append((pag["aem_path"], "cache"))
                continue
            p = c.new_page()
            st = None
            try:
                resp = p.goto(f"{base}{pag['aem_path']}.html?wcmmode=disabled", wait_until="load", timeout=90000)
                st = resp.status if resp else None
                if st and st >= 400:
                    raise RuntimeError(f"HTTP {st}")
                p.wait_for_timeout(1200)
                r = p.evaluate(PROBE)
                r["status"] = st
                r["aem_path"] = pag["aem_path"]
                arq.write_text(json.dumps(r))
                feitos.append((pag["aem_path"], "ok"))
            except Exception as e:  # noqa: BLE001
                feitos.append((pag["aem_path"], f"erro: {e}"[:200]))
            finally:
                p.close()
        b.close()
    return feitos


def coletar(args):
    DADOS.mkdir(parents=True, exist_ok=True)
    (DADOS / "jcr").mkdir(exist_ok=True)
    (DADOS / "paginas").mkdir(exist_ok=True)
    wl, bl = tracker("whitelist"), tracker("blacklist")
    (DADOS / "whitelist.json").write_text(json.dumps(wl, indent=1))
    (DADOS / "blacklist.json").write_text(json.dumps(bl, indent=1))
    print(f"whitelist {wl['count']} páginas, blacklist {bl['count']} ({wl['generated_at']})")
    paginas = wl["pages"]
    if args.paginas:
        quer = {MAI + p if p.startswith("/") and not p.startswith("/content") else p for p in args.paginas}
        paginas = [p for p in paginas if p["aem_path"] in quer]
        fora = quer - {p["aem_path"] for p in paginas}
        if fora:
            print("fora da whitelist (não auditadas):", *sorted(fora), sep="\n  ")
    base = CONFIG["base_url"].rstrip("/")
    s, at = build_session(prompt_if_missing=False, verbose=False)
    for pag in paginas:
        arq = DADOS / "jcr" / f"{pag['aem_path'].replace('/', '__')}.json"
        if arq.exists() and not args.renovar:
            continue
        d, st = fetch_with_depth_fallback(s, base, pag["aem_path"] + "/jcr:content", "infinity", at)
        if d is None:
            print(f"  JCR {st}: {pag['aem_path']}")
            continue
        arq.write_text(json.dumps(d))
    if args.renovar:
        for pag in paginas:
            (DADOS / "paginas" / f"{slug(pag['aem_path'])}.json").unlink(missing_ok=True)
    # página com cq:redirectTarget nunca é vista (o visitante vai para o alvo): fora dos critérios, e não se abre
    # o site externo
    redirs = {}
    for pag in paginas:
        arq = DADOS / "jcr" / f"{pag['aem_path'].replace('/', '__')}.json"
        if arq.exists():
            alvo = json.loads(arq.read_text()).get("cq:redirectTarget")
            if alvo:
                redirs[pag["aem_path"]] = alvo
    antigos = json.loads((DADOS / "redirects.json").read_text()) if (DADOS / "redirects.json").exists() else {}
    (DADOS / "redirects.json").write_text(json.dumps({**antigos, **redirs}, indent=1))
    paginas = [p for p in paginas if p["aem_path"] not in redirs]
    if redirs:
        print(f"{len(redirs)} página(s) de redirect puladas (lista em redirects.json)")
    n = max(1, args.processos)
    lotes = [paginas[i::n] for i in range(n)]
    t0 = time.time()
    with ProcessPoolExecutor(n) as ex:
        fut = [ex.submit(_coletar_lote, l, os.environ["AEM_COOKIES"], base, str(DADOS)) for l in lotes if l]
        for f in as_completed(fut):
            for cam, st in f.result():
                if st not in ("ok", "cache"):
                    print(f"  {st}: {cam}")
    print(f"coleta: {len(list((DADOS / 'paginas').glob('*.json')))} páginas em {time.time() - t0:.0f}s -> {DADOS}")


# ─── análise ──────────────────────────────────────────────────────────────────────────────────────────────
CTA_GENERICO = re.compile(r"contact|request a quote|get a quote|quote|sign ?up|subscribe|newsletter|talk to|"
                          r"sales|inquir|more information|get in touch|reach out|ask an expert", re.I)
XF_CTA = {
    "products-contact-block": {"Contact Us for More Information": "/contact-us", "Request a Quote": "/request-a-quote"},
    "signup-and-contact-experience-fragment": {"Sign up": "constantcontact", "Contact us": "/contact-us"},
}
STYLE_LEFT, STYLE_WRAP = "1718154328384", "1718154382437"


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def analisar_pagina(aem_path, titulo_tracker):
    r = json.loads((DADOS / "paginas" / f"{slug(aem_path)}.json").read_text())
    jcr = json.loads((DADOS / "jcr" / f"{aem_path.replace('/', '__')}.json").read_text())
    nos = nos_em_ordem(jcr)
    por_tipo = {}
    for cam, rt, no in nos:
        por_tipo.setdefault(rt, []).append((cam, no))
    titulo = jcr.get("pageTitle") or jcr.get("jcr:title") or titulo_tracker
    ach = {"aem_path": aem_path, "titulo": titulo, "template": str(jcr.get("cq:template", "")).split("/")[-1],
           "W": r["W"], "scrollW": r["scrollW"], "cta": None, "titulos": None, "videos": [], "twis": []}

    # ── 2. títulos ──
    hs = [h for h in r["headings"] if not h["inXF"] and h["vis"] and h["txt"]]
    vazios = [h for h in r["headings"] if not h["inXF"] and h["vis"] and not h["txt"]]
    h1 = [h for h in hs if h["lv"] == 1]
    probs = []
    if len(h1) == 0:
        probs.append("sem h1 no conteúdo")
    if len(h1) > 1:
        probs.append(f"{len(h1)} h1 no conteúdo")
    if hs and hs[0]["lv"] != 1:
        probs.append(f"1º título é h{hs[0]['lv']}, não h1")
    if h1 and _norm(h1[0]["txt"]) != _norm(titulo) and _norm(titulo) not in _norm(h1[0]["txt"]) and _norm(h1[0]["txt"]) not in _norm(titulo):
        probs.append(f"h1 ≠ título da página ({titulo!r})")
    pulos = []
    for a, b in zip(hs, hs[1:]):
        if b["lv"] > a["lv"] + 1:
            pulos.append(f"h{a['lv']} '{a['txt'][:40]}' → h{b['lv']} '{b['txt'][:40]}'")
    if pulos:
        probs.append(f"{len(pulos)} pulo(s) de nível")
    if vazios:
        probs.append(f"{len(vazios)} título(s) vazio(s)")
    # subseção no mesmo nível da seção: título dentro de aba/item de flex/card com nível <= o do último título
    # de fora daquele bloco (ex.: abas com h2 "Carrier Boards" sob o h2 "Product Catalog") — candidato, não veredito
    mesmo_nivel = []
    fora = None
    for h in hs:
        dentro = h["tab"] is not None or h["flexItem"] or h["card"]
        if not dentro:
            fora = h
        elif fora and h["lv"] <= fora["lv"]:
            mesmo_nivel.append(f"h{h['lv']} '{h['txt'][:40]}' dentro de {'aba' if h['tab'] is not None else 'item de flex' if h['flexItem'] else 'card'} sob h{fora['lv']} '{fora['txt'][:40]}'")
    if mesmo_nivel:
        probs.append(f"{len(mesmo_nivel)} possível(is) subseção(ões) no nível da seção")
    # casar títulos do componente title com o JCR (ordem + texto; title sem jcr:title rende o título da página)
    tit_dom = [h for h in r["headings"] if h["comp"] == "title" and not h["inXF"]]
    tit_jcr = por_tipo.get("title", [])
    mapa = []
    for i, h in enumerate(tit_dom):
        cam, no = tit_jcr[i] if i < len(tit_jcr) else (None, {})
        esperados = [no.get("jcr:title") or no.get("text")] if (no.get("jcr:title") or no.get("text")) else [jcr.get("pageTitle"), jcr.get("jcr:title")]
        ok = cam and any(e and _norm(e)[:30] == _norm(h["txt"])[:30] for e in esperados)
        mapa.append({"lv": h["lv"], "txt": h["txt"][:80], "no": cam if ok else None,
                     "type": (no.get("type") or "(padrão da policy)") if ok else None})
    ach["titulos"] = {"problemas": probs, "pulos": pulos, "mesmo_nivel": mesmo_nivel, "headerH1": r.get("headerH1"),
                      "vazios": [f"h{h['lv']} vazio em {h['comp']}" for h in vazios],
                      "outline": [{k: h[k] for k in ("lv", "txt", "comp", "top", "flexItem", "tab", "card", "bg", "fs")} for h in hs],
                      "mapa_title": mapa}

    # ── 1. CTA no fim ──
    # bloco de CTA = os últimos blocos de 1º nível (top) só com botão/XF e texto curto; botão de download
    # (arquivo do DAM) é conteúdo, não CTA, e encerra a busca
    folhas = [c for c in r["comps"] if c["h"] > 0 or c["k"] == "experiencefragment"]
    grupos = []
    for c in folhas:
        if grupos and grupos[-1][0] == c["top"]:
            grupos[-1][1].append(c)
        else:
            grupos.append((c["top"], [c]))
    cauda = []
    for _, g in reversed(grupos):
        util = [c for c in g if not (c["k"] in ("anchorlink", "separator") or (c["k"] == "image" and c["h"] < 5)
                                     or (c["k"] in ("text", "title") and c.get("n", len(c["txt"])) == 0))]
        if not util:
            continue
        # o XF do formulário de evento (event-meeting-request-form) é conteúdo, não bloco de botões: encerra a busca
        # (em ibc-2025 ele fica no meio, numa faixa cinza, e os botões brancos vêm DEPOIS dele)
        cta = [c for c in util if (c["k"] == "button" and not c.get("download"))
               or (c["k"] == "experiencefragment" and "event-meeting-request-form" not in (c.get("xf") or ""))]
        resto = [c for c in util if c not in cta]
        if cta and all(c["k"] in ("text", "title") and c.get("n", len(c["txt"])) <= 200 for c in resto):
            cauda = util + cauda
        else:
            break
    botoes = [c for c in cauda if c["k"] == "button"]
    xfs = [c for c in cauda if c["k"] == "experiencefragment"]
    if botoes or xfs:
        btn_jcr = [(c, n) for c, n in por_tipo.get("button", [])]
        idx0 = len([c for c in folhas if c["k"] == "button"]) - len(botoes)
        det = []
        for j, b in enumerate(botoes):
            cam, no = btn_jcr[idx0 + j] if 0 <= idx0 + j < len(btn_jcr) else (None, {})
            ok = cam and _norm(no.get("jcr:title"))[:25] == _norm(b["txt"])[:25]
            det.append({"txt": b["txt"], "href": b.get("href"), "no": cam if ok else None, "linkURL": no.get("linkURL") if ok else None,
                        "generico": bool(CTA_GENERICO.search(b["txt"])), "bg": b["bg"], "btnBg": b.get("btnBg"), "top": b["top"]})
        ach["cta"] = {"botoes": det, "xfs": [{"xf": x.get("xf"), "botoes": x.get("botoes"), "bg": x["bg"]} for x in xfs],
                      "textos": [c["txt"] for c in cauda if c["k"] in ("text", "title")],
                      "ultimos": [f"{c['k']}: {c['txt'][:60]}" for c in folhas[-4:]]}

    # ── 3. vídeos ──
    for v in r["videos"]:
        lado = any(o["lado"] for o in v["outros"])
        texto_lado = any(o["lado"] and len(o["txt"]) > 30 for o in v["outros"])
        if not v["emFlex"] or v["nItensComConteudo"] < 2:
            st = "VIOLA: fora de flex container com 2+ itens"
        elif not lado:
            st = "VIOLA: flex com 2+ itens mas empilhado a 1400px"
        elif not texto_lado:
            st = "SUBÓTIMO: ao lado de algo que não é texto relacionado"
        else:
            st = "OK: texto ao lado"
        ach["videos"].append({**v, "status": st})

    # ── 4. Text with Image (Left) ──
    twi_jcr = por_tipo.get("textwithimage", [])
    for i, t in enumerate(r["twis"]):
        cam, no = twi_jcr[i] if i < len(twi_jcr) else (None, {})
        if cam and _norm(txt(no.get("text")))[:30] != _norm(t["txt"])[:30]:
            cam = None
        estilos = no.get("cq:styleIds") if cam else None
        rec = {"no": cam, "imageRatio_jcr": no.get("imageRatio") if cam else None, "styleIds": estilos,
               **{k: t[k] for k in ("left", "wrap", "vcenter", "ratio", "nat", "src", "alt", "txt", "nTxt", "hs", "top", "flexItem", "tab", "bg")}}
        a = t["atual"]
        rec["atual"] = {"col": a["col"]["w"] if a["col"] else None, "img": [a["img"]["w"], a["img"]["h"]] if a["img"] else None,
                        "txt_h": a["txt"]["h"] if a["txt"] else None,
                        "vao": (a["txt"]["x"] - (a["img"]["x"] + a["img"]["w"])) if a["img"] and a["txt"] else None,
                        "folga_col": (a["col"]["w"] - a["img"]["w"]) if a["img"] and a["col"] else None}
        if not t["left"]:
            rec["status"] = "fora do escopo (imagem não está à esquerda)"
            ach["twis"].append(rec)
            continue
        if t["wrap"]:
            rec["status"] = "OK: já faz wrap"
            rec["simSemWrap"] = t.get("simSemWrap")
            ach["twis"].append(rec)
            continue
        sim = t["sim"]  # [r, colW, imgW, imgH, txtH, vao]
        if not sim or not a["img"] or not a["img"]["w"]:
            rec["status"] = "sem imagem medível"
            ach["twis"].append(rec)
            continue
        # mesmos limiares na detecção e na recomendação: "muito mais alta" = passa do texto em max(60px, 25%);
        # "espaço vazio sob a imagem" = texto passa da imagem em max(120px, 50%)
        muito_alta = lambda ih, th: ih > th + max(60, 0.25 * th)   # noqa: E731
        vazio_sob = lambda ih, th: th > ih + max(120, 0.5 * ih)    # noqa: E731
        cheio = [s for s in sim if s[1] - s[2] <= 2]          # imagem preenche a coluna (sem folga)
        r_fit = max((s[0] for s in cheio), default=None)
        imgH, txtH = a["img"]["h"], a["txt"]["h"]
        folga = rec["atual"]["folga_col"]
        alta = muito_alta(imgH, txtH)
        baixa = vazio_sob(imgH, txtH)
        cand = [s for s in cheio if not muito_alta(s[3], s[4])]
        r_rec = max((s[0] for s in cand), default=None)       # a maior imagem sem vão e sem passar do texto
        s_rec = next((s for s in sim if s[0] == r_rec), None)
        wrap_rec = bool(s_rec and vazio_sob(s_rec[3], s_rec[4]))
        probs = []
        if r_rec is None:
            probs.append("texto curto demais: mesmo a 5% a imagem passa muito do texto — decidir à mão")
        # folga = coluna - imagem; a imagem fica CENTRADA na coluna, então o texto começa folga/2 além dos 40px do
        # gap. Até 40px de folga (≤20px a mais) é "menor"; os vãos das i-chips apontados na revisão tinham 75–150px.
        menor = []
        if folga is not None and folga > 40:
            probs.append(f"vão: coluna {a['col']['w']}px x imagem {a['img']['w']}px (natural {t['nat'][0]}px) — {folga}px de folga")
        elif folga is not None and folga > 20:
            menor.append(f"vão pequeno: {folga}px de folga na coluna (texto começa {folga // 2}px mais longe)")
        if alta:
            probs.append(f"imagem {imgH}px x texto {txtH}px (imagem muito mais alta)")
        if baixa:
            probs.append(f"texto {txtH}px x imagem {imgH}px (espaço vazio sob a imagem)")
        rec.update({"r_fit": r_fit, "r_rec": r_rec, "wrap_rec": wrap_rec,
                    "rec_medida": {"col": s_rec[1], "img": [s_rec[2], s_rec[3]], "txt_h": s_rec[4], "vao": s_rec[5]} if s_rec else None,
                    "simWrap": {"img": [t["simWrap"]["img"]["w"], t["simWrap"]["img"]["h"]], "bloco_h": t["simWrap"]["bloco"]["h"]} if t.get("simWrap") and t["simWrap"]["img"] else None,
                    "problemas": probs, "menor": menor,
                    "status": ("VIOLA: " + "; ".join(probs)) if probs else ("MENOR: " + "; ".join(menor)) if menor else "OK"})
        ach["twis"].append(rec)
    return ach


def analisar(args):
    wl = json.loads((DADOS / "whitelist.json").read_text())
    todos, falta = [], []
    redirs = json.loads((DADOS / "redirects.json").read_text()) if (DADOS / "redirects.json").exists() else {}
    for pag in wl["pages"]:
        if pag["aem_path"] in redirs:
            continue
        if not (DADOS / "paginas" / f"{slug(pag['aem_path'])}.json").exists():
            falta.append(pag["aem_path"])
            continue
        todos.append(analisar_pagina(pag["aem_path"], pag.get("title")))
    (DADOS / "achados.json").write_text(json.dumps(todos, indent=1, ensure_ascii=False))
    n = lambda f: sum(1 for a in todos if f(a))  # noqa: E731
    print(f"{len(todos)} páginas analisadas; {len(redirs)} redirect (fora dos critérios); {len(falta)} sem coleta")
    print("CTA no fim com botão fora de XF:", n(lambda a: a["cta"] and a["cta"]["botoes"]))
    print("títulos com problema:", n(lambda a: a["titulos"]["problemas"]))
    print("páginas com vídeo que viola:", n(lambda a: any(v["status"].startswith("VIOLA") for v in a["videos"])))
    print("páginas com TWI Left que viola:", n(lambda a: any(t["status"].startswith("VIOLA") for t in a["twis"])))
    for f in falta:
        print("  sem coleta:", f)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("coletar")
    c.add_argument("--paginas", nargs="*", help="caminhos relativos a mai/en (ou absolutos); padrão: whitelist inteira")
    c.add_argument("--processos", type=int, default=4)
    c.add_argument("--renovar", action="store_true", help="refaz JCR e render mesmo com cache")
    c.set_defaults(f=coletar)
    a = sub.add_parser("analisar")
    a.set_defaults(f=analisar)
    args = ap.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
