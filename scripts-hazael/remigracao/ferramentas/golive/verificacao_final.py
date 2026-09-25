#!/usr/bin/env python3
"""
verificacao_final.py — conferência final (SÓ GET) de tudo o que foi gravado no global2 em 24–25/09/2026: consertos de link
(corrigir_links.py, grupos A/B/D/E/F), botões dos eventos (botao_evento.py, C), assets copiados do GWI e conteúdo
(conteudo_faltando.py, G). Para cada página:
  no lugar   cada mudança do manifesto continua no JCR (valor, href, nó criado/apagado/movido; asset com o sha1 do GWI);
  só isso    JCR de AGORA x backup de ANTES da 1ª gravação do dia: diferença só nos nós/propriedades declarados;
  carimbo    ninguém editou depois da nossa última gravação (cq:lastModified[By]);
  render     os links novos estão no HTML; alvos internos e do DAM respondem 200; âncora tem o id na página;
  tela       (páginas com print: conteúdo e eventos) print de agora x o 'depois' da gravação; imagens carregadas.

Pedido do Hazael (25/09/2026): "make a final verification pass on everything we have done today".

    python3 verificacao_final.py          # -> dados/golive/verificacao_final_<data>.json
"""
import datetime
import html
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import conteudo_faltando as CF  # noqa: E402  (PAGINAS, compara_prints, confere, no_de)
import corrigir_links as C  # noqa: E402

M, DADOS = C.M, C.DADOS
AUTO = {"jcr:lastModified", "jcr:lastModifiedBy", "jcr:created", "jcr:createdBy"}
HREF = re.compile(r'''href\s*=\s*(["'])(.*?)\1''', re.I | re.S)


def rel(pag):
    return pag[len(M) + 1:] if pag.startswith(M + "/") else ("" if pag == M else pag)


def carregar():
    """{pagina_rel: {"regs": [...], "ops": [(chave, cfg)], "quando": [...]}} + assets."""
    man = [json.loads(l) for l in (DADOS / "manifesto_links.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    pags, assets = {}, []
    for m in man:
        if m.get("tipo") == "asset":
            assets.append((m["origem"], m["destino"]))
            continue
        if m.get("status") != "gravado":
            continue
        p = pags.setdefault(rel(m["pagina"]), {"regs": [], "ops": [], "quando": []})
        p["quando"].append(m["quando"])
        if m.get("tipo") != "conteudo":
            p["regs"].append(m)
    for ch, cfg in CF.PAGINAS.items():
        if cfg.get("feito"):
            p = pags.setdefault(cfg.get("pagina", ch), {"regs": [], "ops": [], "quando": []})
            p["ops"].append((ch, cfg))
            assets += cfg.get("assets", [])
    return pags, sorted(set(assets))


def backups():
    """[(quando, pasta, {pagina_rel: jcr})] em ordem — o 1º que contém a página é o 'antes do dia'."""
    out = []
    for d in sorted(DADOS.glob("backup_*_2026-09-2*")):
        f = d / "jcr_content.json"
        if not f.exists():
            continue
        j = json.loads(f.read_text(encoding="utf-8"))
        if d.name.startswith("backup_botoes"):
            j = {f"about-us/news-events/events-archive/{k}": v for k, v in j.items()}
        out.append((d.name.split("_", 2)[2], d, j))
    return out


def permitido(no, k, regs, ops):
    if ("", k) in C.CARIMBO_PAGINA and no == "":
        return True
    for m in regs:
        if m["tipo"] == "botao":
            pai = m["no"].rsplit("/", 1)[0]
            if no.startswith(pai + "/button") or no.startswith(pai + "/anchorlink"):
                return True
        elif no == m["no"] and (k == m.get("prop") or k in AUTO):
            return True
    for _, cfg in ops:
        for op in cfg["ops"]:
            if op[0] in ("criar", "apagar", "remover", "mover") and (no == op[1] or no.startswith(op[1] + "/")):
                return True
            if op[0] == "mover" and (no == op[2] or no.startswith(op[2] + "/")):
                return True
            if op[0] == "props" and no == op[1] and (k in op[2] or k in AUTO):
                return True
    return False


def norm_html(v):
    """Sem o que não muda a tela: rel, entidades, <br /> x <br>, espaço (inclusive entre tags — o .json filtrado junta as linhas)."""
    v = re.sub(r"\s+", " ", html.unescape(re.sub(r'\s+rel="[^"]*"', "", str(v or "")))).replace("<br />", "<br>")
    return re.sub(r">\s+<", "><", v).strip()


def no_lugar(jc, regs, ops):
    """Problemas: mudança que não está mais no JCR."""
    prob, esperados = [], set()
    # registro substituído por um posterior no mesmo nó/propriedade (MEP100: A 19:53 -> E 20:17) não conta
    trocado = {id(m) for m in regs for m2 in regs if m2 is not m and m2["no"] == m["no"] and m2.get("prop") == m.get("prop")
               and m2["quando"] > m["quando"] and isinstance(m["para"], str) and m["para"] in str(m2.get("antes") or "")}
    for m in regs:
        if id(m) in trocado:
            continue
        no = CF.no_de(jc, m["no"])
        if m["tipo"] == "botao":
            ok = no and no.get("linkURL") == m["para"] and no.get("jcr:title") == m["txt"]
            esperados.add(m["para"])
        elif m["tipo"] == "prop":
            ok = no and no.get(m["prop"]) == m["para"]
            esperados.add(m["para"] + (".html" if m["para"].startswith(M) and not m["para"].endswith(".html") else ""))
        elif m["tipo"] == "href":
            ok = no and m["para"] in [html.unescape(h[1]) for h in HREF.findall(no.get(m["prop"]) or "")]
            esperados.add(m["para"])
        elif m["tipo"] == "ext":
            hs = [html.unescape(h[1]) for h in HREF.findall((no or {}).get(m["prop"]) or "")]
            ok = no and all(n in hs and v not in hs for v, n in m["para"])
            esperados |= {n for _, n in m["para"]}
        elif m["tipo"] == "wrap":
            alvo = HREF.search(m["para"])
            ok = no and alvo and alvo.group(2) in [html.unescape(h[1]) for h in HREF.findall(no.get(m["prop"]) or "")]
            if alvo:
                esperados.add(html.unescape(alvo.group(2)))
        else:
            ok = True
        if not ok:
            prob.append(f"{m['grupo']} {m['no']}: {str(m['para'])[:80]}")
    for ch, cfg in ops:
        for op in cfg["ops"]:
            no = CF.no_de(jc, op[1])
            if op[0] in ("apagar", "remover"):
                if no is not None and not any(o[0] == "criar" and o[1] == op[1] for c2 in ops for o in c2[1]["ops"]):
                    prob.append(f"{ch}: {op[1]} devia ter saído")
            elif op[0] == "mover":
                if CF.no_de(jc, op[2]) is None and not any(o[0] == "mover" and o[1] == op[2] for c2 in ops for o in c2[1]["ops"]):
                    prob.append(f"{ch}: {op[2]} (movido) não está lá")
            elif op[0] in ("criar", "props"):
                if no is None:
                    if not any(o[0] in ("remover", "mover") and (op[1] == o[1] or op[1].startswith(o[1] + "/"))
                               for c2 in ops for o in c2[1]["ops"]):
                        prob.append(f"{ch}: {op[1]} não existe")
                    continue
                for k, v in op[2].items():
                    if k == "sling:resourceType" and op[0] == "props":
                        continue
                    atual = no.get(k)
                    bate = (norm_html(atual) == norm_html(v)) if k == "text" else (atual == v)
                    tardio = [o for c2 in ops for o in c2[1]["ops"] if o[0] == "props" and o[1] == op[1] and k in o[2] and o is not op]
                    if not bate and not (tardio and atual == tardio[-1][2][k]):
                        prob.append(f"{ch}: {op[1]}.{k} = {str(atual)[:60]!r}")
                for k in ("linkURL",):
                    v = op[2].get(k)
                    if v:
                        esperados.add(v + (".html" if v.startswith(M) and not v.startswith("/content/dam") else ""))
                for h in HREF.findall(op[2].get("text") or ""):
                    esperados.add(html.unescape(h[1]))
    return prob, esperados


def alvo_ok(u, html_pag):
    if u.startswith("#"):
        return f'id="{u[1:]}"' in html_pag, "âncora"
    if u.startswith("/content/"):
        r = C.sessao.get(C.url(u.split("#")[0].split("?")[0]), timeout=120, allow_redirects=False, stream=True)
        r.close()
        return r.status_code == 200, f"HTTP {r.status_code}"
    return None, "externo (não requisitado)"


def prints_agora(pags, pasta):
    from playwright.sync_api import sync_playwright
    from aem_lib import parse_cookie_string
    host = C.BASE.split("//", 1)[1]
    ck = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
    pasta.mkdir(parents=True, exist_ok=True)
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        c = b.new_context(viewport={"width": 1400, "height": 1000})
        c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in ck.items()])
        pg = c.new_page()
        pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(C.BASE) else r.abort())
        for pag in pags:
            pg.goto(f"{C.BASE}{M}/{pag}.html?wcmmode=disabled", timeout=180000, wait_until="networkidle")
            pg.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important}")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(3000)
            pg.evaluate("""() => document.querySelectorAll('body *').forEach(e => {
                const p = getComputedStyle(e).position; if (p === 'fixed' || p === 'sticky') e.style.visibility = 'hidden'; })""")
            png = pasta / f"{pag.replace('/', '__')}.png"
            pg.screenshot(path=str(png), full_page=True)
            quebradas = pg.evaluate("""async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); }
                await new Promise(r => setTimeout(r, 1500));
                return [...document.querySelectorAll('main img, .root img')].filter(i => !i.closest('header,footer,.header,.footer') && i.getBoundingClientRect().width > 0
                        && (!i.complete || !i.naturalWidth)).map(i => (i.currentSrc || i.src).split('/').pop()); }""")
            out[pag] = (png, quebradas)
        b.close()
    return out


def main():
    agora = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    pags, assets = carregar()
    bks = backups()
    res = {"quando": agora, "paginas": {}, "assets": []}
    for origem, destino in assets:                                  # assets: sha1 = GWI, processado
        st, md_d = C.ler(destino + "/jcr:content/metadata", ".json")
        _, md_o = C.ler(origem + "/jcr:content/metadata", ".json")
        _, rd = C.ler(destino + "/jcr:content/renditions", ".1.json")
        n = len([k for k, v in (rd or {}).items() if isinstance(v, dict)])
        ok = st == 200 and (md_d or {}).get("dam:sha1") == (md_o or {}).get("dam:sha1") and n > 1
        res["assets"].append({"destino": destino, "ok": ok, "renditions": n})
        print(f"{'OK ' if ok else 'PROBLEMA'} asset {destino.rsplit('/', 1)[-1]}: sha1 {'= GWI' if ok else '?'}; {n} renditions")
    com_print = []
    for pag, info in sorted(pags.items()):
        jc, hp = C.retrato(f"{M}/{pag}" if pag else M)
        prob, esperados = no_lugar(jc, info["regs"], info["ops"])
        base = next(((q, d, j[pag]) for q, d, j in bks if pag in j), None)
        fora = []
        if base:
            fa, fd = C.achatar(base[2]), C.achatar(jc)
            fora = sorted(f"{n}.{k}" for n, k in set(fa) | set(fd) if fa.get((n, k)) != fd.get((n, k))
                          and not permitido(n, k, info["regs"], info["ops"]))
        ultima = max(info["quando"])
        lm = jc.get("cq:lastModified", "")
        lm_dt = datetime.datetime.strptime(lm[4:24], "%b %d %Y %H:%M:%S").replace(tzinfo=datetime.timezone.utc) if lm else None
        nossa = datetime.datetime.strptime(ultima, "%Y-%m-%d_%H%M%S").astimezone(datetime.timezone.utc)
        depois = lm_dt and (lm_dt - nossa).total_seconds() > 1800
        editor = (jc.get("cq:lastModifiedBy") or "").split("@")[0]
        hrefs = {html.unescape(h[1]) for h in HREF.findall(hp)}
        falta_html = sorted(u for u in esperados if u not in hrefs and not u.startswith("#"))
        alvos = {u: alvo_ok(u, hp) for u in esperados}
        mortos = sorted(f"{u} ({s})" for u, (ok, s) in alvos.items() if ok is False)
        ok = not prob and not fora and not depois and not falta_html and not mortos
        res["paginas"][pag] = {"ok": ok, "no_lugar": prob, "fora_do_declarado": fora, "base": base[1].name if base else None,
                               "ultima_nossa": ultima, "lastModified": lm, "lastModifiedBy": editor, "editada_depois": bool(depois),
                               "links_fora_do_html": falta_html, "alvos": {u: s for u, (o, s) in alvos.items()}, "alvos_mortos": mortos,
                               "grupos": sorted({m["grupo"] for m in info["regs"]} | ({"G"} if info["ops"] else set()))}
        print(f"{'OK ' if ok else 'PROBLEMA'} /{pag} [{','.join(res['paginas'][pag]['grupos'])}] "
              + ("" if ok else f"no_lugar={prob} fora={fora[:6]} depois={editor if depois else '-'} html={falta_html} mortos={mortos}"))
        if info["ops"] or any(m["grupo"] == "C-botao" for m in info["regs"]):
            com_print.append(pag)
    # tela: print de agora x o 'depois' da última gravação da página
    pasta = DADOS / f"verificacao_final_{agora}"
    atuais = prints_agora(com_print, pasta / "prints")
    for pag in com_print:
        arq = pag.replace("/", "__")
        ev = pag.rsplit("/", 1)[-1]
        cands = [d / "prints_depois" / f"{arq}.png" for d in sorted(DADOS.glob("backup_conteudo_*"))] + \
                [d / n / f"{ev}.png" for d in sorted(DADOS.glob("backup_botoes_*")) for n in ("prints_depois", "prints_depois_2")]
        ref = [c for c in cands if c.exists()]
        png, quebradas = atuais[pag]
        pr = CF.compara_prints(ref[-1], png) if ref else None
        igual = pr and pr["altura"][0] == pr["altura"][1] and pr["igual_no_topo_ate"] == pr["altura"][0]
        r = res["paginas"][pag]
        r["tela"] = {"referencia": str(ref[-1].relative_to(DADOS)) if ref else None, "igual": bool(igual), "comparacao": pr,
                     "imagens_quebradas": quebradas}
        if not igual or quebradas:
            r["ok"] = False
        print(f"{'OK ' if igual and not quebradas else 'TELA'} /{pag}: print {'igual ao do depois' if igual else pr}; imagens quebradas {quebradas or 0}")
    out = DADOS / f"verificacao_final_{agora[:10]}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    n_ok = sum(r["ok"] for r in res["paginas"].values())
    print(f"\n{n_ok}/{len(res['paginas'])} páginas OK; assets {sum(a['ok'] for a in res['assets'])}/{len(res['assets'])} -> {out}")


if __name__ == "__main__":
    main()
