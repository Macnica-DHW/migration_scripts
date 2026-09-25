#!/usr/bin/env python3
"""
botao_evento.py [--executar] [--so REL...] — link do site do evento como BOTÃO nas 9 páginas de evento. Dry-run por padrão.

Pedido do Hazael (24/09/2026): "For the 'Event website link', use a button component … adding a button where the link
should be"; respostas: o anchorlink (a pílula "NAB Show 2015 ▼", menu de âncoras com href `#https://…`, quebrado — feito à
mão pelo Bruno em 23/09) é SUBSTITUÍDO pelo botão, no mesmo lugar; botão roxo "Fit to Text" + "Center", texto = o do link
no GWI, destino = o do GWI, abre em aba nova. IBC 2015 não tem anchorlink: o botão entra no mesmo lugar (1º do bloco do
evento, acima de Location/datas).

Mudança ESTRUTURAL (um nó sai, um entra), então a conferência é:
  JCR     antes x depois da página inteira: só pode sumir o anchorlink, aparecer o botão (na MESMA posição entre os irmãos)
          e mudar o carimbo da página (cq:lastModified[By]);
  render  HTML normalizado idêntico tirando o bloco do anchorlink (antes) e o do botão (depois);
  print   1400px, animação desligada: igual ACIMA do elemento e igual ABAIXO dele (alinhado pelo próximo elemento).
Backup (jcr:content inteiro + render + print) ANTES de gravar, em dados/golive/backup_botoes_<data>/. Trava da Session vale.

    python3 botao_evento.py                      # dry-run: o que sai e o que entra em cada página
    python3 botao_evento.py --executar --so 2015-04-14-nab-show-2015
"""
import argparse
import datetime
import html
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corrigir_links as C  # noqa: E402  (sessao com trava, retrato, achatar, normalizar)
from aem_lib import parse_cookie_string  # noqa: E402

M = C.M
EV = "about-us/news-events/events-archive"
DADOS = C.DADOS
POS = C.DADOS.parent / "mapas" / "global2_links_vs_gwi_2026-09-24_pos.json"
ESTILO = ["1723033446255", "1717669229626"]          # Width: Fit to Text; Display Position: Center (policy do button)
EVENTOS = {  # rel do evento -> bloco onde fica (o do anchorlink; IBC 2015 não tem)
    "2015-04-14-nab-show-2015": "container_evento", "2015-09-12-ibc-2015": "container_evento",
    "2016-04-19-nab-show-2016": "container_evento", "2016-08-18-intel-isdf-2016": "container_evento",
    "2016-09-10-ibc-2016": "container_evento", "2017-09-16-ibc-2017": "title_wrap_conteudo",
    "2019-02-06-ise-2019": "container_evento", "2019-04-09-nab-show-2019": "container_evento",
    "2019-06-12-infocomm-2019": "container_evento",
}
sessao = C.sessao


def filhos(no):
    return [k for k, v in no.items() if isinstance(v, dict) and k != "cq:responsive"]


def link_gwi(ev):
    """Texto e URL do link do site do evento no GWI (o 'faltando' da coleta pós-conserto)."""
    rel = json.loads(POS.read_text(encoding="utf-8"))
    r = next(r for r in rel["paginas"] if r["g2"] == f"{M}/{EV}/{ev}")
    f = [x for x in r["faltando"] if not x["via"] and x["href"].startswith("http")]
    assert len(f) == 1, (ev, f)
    return f[0]["txt"], f[0]["href"]


# ---------------------------------------------------------------- render: tirar o bloco trocado
def _corta_div(h, ini):
    """Remove o <div ...> que começa em `ini` até o </div> que fecha ele."""
    prof, i = 0, ini
    for m in re.finditer(r"<div\b|</div\s*>", h[ini:], re.I):
        prof += 1 if m.group(0).lower().startswith("<div") else -1
        if prof == 0:
            return h[:ini] + h[ini + m.end():]
    raise ValueError("div sem fechamento")


def sem_anchorlink(h):
    i = h.find('<div class="anchorlink')
    return _corta_div(h, i) if i >= 0 else h


def sem_botao(h, url):
    i = h.find(f'href="{html.escape(url, quote=True)}"')
    if i < 0:
        i = h.find(f'href="{url}"')
    ini = h.rfind('<div class="button', 0, i)
    return _corta_div(h, ini)


# ---------------------------------------------------------------- print + medidas
def prints(pags, pasta, url_botao=None):
    """{ev: (png, topo, topo_do_proximo)} — topo do anchorlink (antes) ou do botão (depois) e do elemento seguinte."""
    from playwright.sync_api import sync_playwright
    host = C.BASE.split("//", 1)[1]
    ck = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
    out = {}
    pasta.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        c = b.new_context(viewport={"width": 1400, "height": 1000})
        c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in ck.items()])
        pg = c.new_page()
        pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(C.BASE) else r.abort())
        for ev in pags:
            pg.goto(f"{C.BASE}{M}/{EV}/{ev}.html?wcmmode=disabled", timeout=180000, wait_until="networkidle")
            pg.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important}")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(3000)
            # botão de telefone, Page Top, reCAPTCHA: presos à janela, não andam com o conteúdo — no print de página
            # inteira viram diferença falsa quando o conteúdo desce (piloto NAB 2015, 24/09)
            pg.evaluate("""() => document.querySelectorAll('body *').forEach(e => {
                const p = getComputedStyle(e).position; if (p === 'fixed' || p === 'sticky') e.style.visibility = 'hidden'; })""")
            alvo = url_botao(ev) if url_botao else None
            medida = pg.evaluate("""(url) => {
                const y = e => Math.round(e.getBoundingClientRect().top + window.scrollY);
                let el = url ? [...document.querySelectorAll('a.link-button__anchor, a.cmp-button')].find(a => a.getAttribute('href') === url) : document.querySelector('.anchorlink');
                if (url && el) el = el.closest('.button');
                if (!el) {   // antes, sem anchorlink (IBC 2015): o botão vai entrar logo acima do texto Location/datas
                    const t = [...document.querySelectorAll('.text')].find(d => /Location\s*:/.test(d.textContent));
                    return t ? [y(t), y(t), 0] : null;
                }
                const prox = el.nextElementSibling;
                return [y(el), prox ? y(prox) : null, Math.round(el.getBoundingClientRect().height)];
            }""", alvo)
            png = pasta / f"{ev}.png"
            pg.screenshot(path=str(png), full_page=True)
            out[ev] = (png, medida)
        b.close()
    return out


def compara_prints(antes, depois):
    from PIL import Image, ImageChops
    (pa, ma), (pd, md) = antes, depois
    ia, idp = Image.open(pa).convert("RGB"), Image.open(pd).convert("RGB")
    W = min(ia.width, idp.width)
    topo_a, prox_a = ma[0], ma[1]                     # IBC 2015: topo == próximo (o texto Location/datas), altura 0
    topo_d, prox_d = md[0], md[1]
    topo = min(topo_a, topo_d)
    cima = ImageChops.difference(ia.crop((0, 0, W, topo)), idp.crop((0, 0, W, topo))).getbbox()
    resto_a, resto_d = ia.height - prox_a, idp.height - prox_d
    baixo = "alturas diferentes" if resto_a != resto_d else \
        ImageChops.difference(ia.crop((0, prox_a, W, ia.height)), idp.crop((0, prox_d, W, idp.height))).getbbox()
    return {"acima_igual": cima is None, "abaixo_igual": baixo is None, "cima": cima, "baixo": baixo,
            "altura": (ia.height, idp.height), "elemento": (ma, md)}


# ---------------------------------------------------------------- plano e gravação
def plano(so):
    out = []
    for ev, bloco in EVENTOS.items():
        if so and ev not in so:
            continue
        txt, url = link_gwi(ev)
        cont = f"{M}/{EV}/{ev}/jcr:content/root/container/{bloco}"
        st, j = C.ler(cont, ".infinity.json")
        assert st == 200, (ev, st)
        ordem = filhos(j)
        al = j.get("anchorlink")
        itens = [v for v in (al or {}).get("anchor", {}).values() if isinstance(v, dict)]
        out.append({"ev": ev, "bloco": bloco, "cont": cont, "txt": txt, "url": url, "ordem": ordem, "anchorlink": al,
                    "itens": itens, "botao_livre": "button" not in ordem})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--so", nargs="*", default=[])
    ap.add_argument("--reconferir-prints", metavar="PASTA", help="só GET: novo print 'depois' e compara com o 'antes' do backup")
    a = ap.parse_args()
    if a.reconferir_prints:
        pasta = Path(a.reconferir_prints)
        comp = json.loads((pasta / "comparacao.json").read_text(encoding="utf-8"))
        manif = [json.loads(l) for l in (DADOS / "manifesto_links.jsonl").read_text(encoding="utf-8").splitlines()]
        urls = {x["pagina"].rsplit("/", 1)[-1]: x["para"] for x in manif if x.get("tipo") == "botao" and x.get("status") == "gravado"}
        evs = [c["ev"] for c in comp]
        dep = prints(evs, pasta / "prints_depois_2", url_botao=lambda ev: urls[ev])
        for c in comp:
            pr = compara_prints((pasta / "prints_antes" / f"{c['ev']}.png", c["elemento"][0]), dep[c["ev"]])
            print(f"{c['ev']}: acima {'igual' if pr['acima_igual'] else pr['cima']}; abaixo {'igual' if pr['abaixo_igual'] else pr['baixo']}; "
                  f"elemento antes {pr['elemento'][0]} depois {pr['elemento'][1]}; altura {pr['altura']}")
            c["prints"] = {k: v for k, v in pr.items() if k != "elemento"}
            c["elemento"] = pr["elemento"]
            c["ok"] = not c["jcr_fora"] and c["render_igual"] and pr["acima_igual"] and pr["abaixo_igual"]
        (pasta / "comparacao.json").write_text(json.dumps(comp, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        return
    lista = plano(set(a.so))
    for x in lista:
        al = f"anchorlink “{x['itens'][0]['text']}” -> #{x['itens'][0]['linkId']}" if x["anchorlink"] else "sem anchorlink"
        print(f"## /{EV}/{x['ev']}  [{x['bloco']}: {' | '.join(x['ordem'])}]\n   sai: {al}\n"
              f"   entra: button “{x['txt']}” -> {x['url']} (aba nova, Fit to Text + Center), "
              f"{'no lugar do anchorlink' if x['anchorlink'] else 'antes de ' + x['ordem'][0]}")
        problema = [] if x["botao_livre"] else ["já existe um nó 'button' no bloco"]
        if x["anchorlink"] and len(x["itens"]) != 1:
            problema.append(f"anchorlink com {len(x['itens'])} itens")
        if C.motivo_bloqueio("POST", C.url(x["cont"] + "/button"), {"a": "b"}):
            problema.append("página protegida")
        if problema:
            print("   PULA:", "; ".join(problema))
        x["ok"] = not problema
    lista = [x for x in lista if x["ok"]]
    if not a.executar:
        print(f"\n{len(lista)} páginas (DRY-RUN: nada gravado)")
        return

    agora = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    pasta = DADOS / f"backup_botoes_{agora}"
    pasta.mkdir(parents=True)
    retratos = {x["ev"]: C.retrato(f"{M}/{EV}/{x['ev']}") for x in lista}                       # backup ANTES
    (pasta / "jcr_content.json").write_text(json.dumps({k: v[0] for k, v in retratos.items()}, ensure_ascii=False), encoding="utf-8")
    (pasta / "render.json").write_text(json.dumps({k: v[1] for k, v in retratos.items()}, ensure_ascii=False), encoding="utf-8")
    p_antes = prints([x["ev"] for x in lista], pasta / "prints_antes")
    print(f"backup: {len(lista)} páginas (jcr:content + render + print) -> {pasta}")

    urls = {x["ev"]: x["url"] for x in lista}
    resultado = []
    for x in lista:
        ev, cont = x["ev"], x["cont"]
        st, j = C.ler(cont, ".infinity.json")                         # relido agora: tem de estar como no plano
        if filhos(j) != x["ordem"] or (x["anchorlink"] and j.get("anchorlink", {}).get("anchor") != x["anchorlink"]["anchor"]):
            print(f"## {ev}: MUDOU desde o plano — pulado"); continue
        dados = {"jcr:primaryType": "nt:unstructured", "sling:resourceType": "macnicaglobal2/components/content/button",
                 "jcr:title": x["txt"], "linkURL": x["url"], "linkTarget": "_blank",
                 "cq:styleIds": ESTILO, "cq:styleIds@TypeHint": "String[]", "_charset_": "utf-8",
                 ":order": "before anchorlink" if x["anchorlink"] else f"before {x['ordem'][0]}"}
        r1 = sessao.post(C.url(cont + "/button"), data=dados, timeout=120)
        r2 = sessao.post(C.url(cont + "/anchorlink"), data={":operation": "delete"}, timeout=120) if x["anchorlink"] else None
        st, j2 = C.ler(cont, ".infinity.json")
        esperado = [("button" if k == "anchorlink" else k) for k in x["ordem"]] if x["anchorlink"] else ["button"] + x["ordem"]
        bt = j2.get("button", {})
        no_ok = (filhos(j2) == esperado and bt.get("jcr:title") == x["txt"] and bt.get("linkURL") == x["url"]
                 and bt.get("linkTarget") == "_blank" and bt.get("cq:styleIds") == ESTILO)
        print(f"## {ev}: botão HTTP {r1.status_code}" + (f", anchorlink apagado HTTP {r2.status_code}" if r2 else "")
              + f"; ordem {filhos(j2)} {'OK' if no_ok else 'NÃO CONFERE'}")
        linha = {"grupo": "C-botao", "pagina": f"{M}/{EV}/{ev}", "no": cont[len(f'{M}/{EV}/{ev}/jcr:content/'):] + "/button",
                 "tipo": "botao", "txt": x["txt"], "para": x["url"], "saiu": x["anchorlink"], "quando": agora,
                 "status": "gravado" if no_ok else "falhou"}
        with open(DADOS / "manifesto_links.jsonl", "a") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
        resultado.append((x, no_ok))

    # ---- depois: página inteira contra o backup
    p_depois = prints([x["ev"] for x, _ in resultado], pasta / "prints_depois", url_botao=lambda ev: urls[ev])
    comp = []
    print("\n== antes x depois ==")
    for x, no_ok in resultado:
        ev = x["ev"]
        jcr_a, html_a = retratos[ev]
        jcr_d, html_d = C.retrato(f"{M}/{EV}/{ev}")
        base = f"root/container/{x['bloco']}"
        fa, fd = C.achatar(jcr_a), C.achatar(jcr_d)
        fora = sorted(f"{no}.{k}" for no, k in set(fa) | set(fd) if fa.get((no, k)) != fd.get((no, k))
                      and not no.startswith((f"{base}/anchorlink", f"{base}/button")) and (no, k) not in C.CARIMBO_PAGINA)
        ra = C.normalizar(sem_anchorlink(html_a) if x["anchorlink"] else html_a)
        rd = C.normalizar(sem_botao(html_d, x["url"]))
        render_igual = ra == rd
        pr = compara_prints(p_antes[ev], p_depois[ev])
        ok = no_ok and not fora and render_igual and pr["acima_igual"] and pr["abaixo_igual"]
        print(f"{'OK ' if ok else 'DIFERENÇA'} /{EV}/{ev}: JCR fora do previsto {fora or 'nada'}; render sem o bloco "
              f"{'igual' if render_igual else 'DIFERENTE'}; print acima {'igual' if pr['acima_igual'] else pr['cima']}, "
              f"abaixo {'igual' if pr['abaixo_igual'] else pr['baixo']} (altura {pr['altura'][0]} -> {pr['altura'][1]})")
        if not render_igual:
            i = next((i for i in range(min(len(ra), len(rd))) if ra[i] != rd[i]), min(len(ra), len(rd)))
            print(f"     render: …{ra[max(0, i - 100):i + 150]}…\n          ≠ …{rd[max(0, i - 100):i + 150]}…")
        comp.append({"ev": ev, "ok": ok, "jcr_fora": fora, "render_igual": render_igual,
                     "prints": {k: v for k, v in pr.items() if k != "elemento"}, "elemento": pr["elemento"]})
    (pasta / "comparacao.json").write_text(json.dumps(comp, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"{sum(c['ok'] for c in comp)}/{len(comp)} páginas conferidas")


if __name__ == "__main__":
    main()
