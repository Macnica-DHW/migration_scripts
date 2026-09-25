#!/usr/bin/env python3
"""
conteudo_faltando.py [--executar] [--so REL...] — conteúdo que o GWI mostra e a página do global2 não tem (a seção
"Content missing from the page" do global2_links_pending_<data>.html). Dry-run por padrão.

Pedido do Hazael (24/09/2026): "Work on the 'Content missing from the page' section of the pending pages. For pages that
need a grid, you can use …/solutions/imaging-and-vision.html as a reference" — a aba Suppliers/Partners: container >
flexcontainer "1 Column" (empilha só no celular) > 4 flexcontaineritem por linha > image com link (R59/R62).

Mudança ESTRUTURAL (nós entram e saem), então PILOTO em 1 página e mostrar ao Hazael antes das outras. Cada página é
uma lista fechada de operações (PAGINAS abaixo), com precondição conferida no dry-run E relida antes de gravar:
  asset   cópia do DAM do GWI para o do global2 (`<nome>@CopyFrom` com POST só na pasta do global2; sha1 e GET conferidos)
  props   grava propriedades num nó que existe (4º elemento opcional: valores que o nó TEM de ter agora)
  criar   cria um nó que não existe (na ordem dada; `:order` quando precisa de posição)
  apagar  apaga um nó que existe e está VAZIO (sem fileReference/linkURL/text/jcr:title) — placeholder
Conferência depois, a página inteira contra o backup:
  JCR     só mudam os nós declarados (e o carimbo da página);
  render  HTML normalizado idêntico ANTES da 1ª e DEPOIS da última diferença; o miolo é listado (texto que saiu/entrou);
  print   1400px, animação desligada, fixed/sticky escondidos: igual acima da mudança e igual no fim alinhado pelo rodapé.
Entrada com "feito" já foi gravada (fica como registro); "pagina" quando a chave não é o caminho (2ª passada).
Backup (jcr:content inteiro + render + print) ANTES de gravar, em dados/golive/backup_conteudo_<data>/. Trava da Session vale.

    python3 conteudo_faltando.py                          # dry-run: operações e precondições de cada página
    python3 conteudo_faltando.py --executar --so products
"""
import argparse
import datetime
import difflib
import html
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corrigir_links as C  # noqa: E402  (sessao com trava, ler, url, retrato, achatar, CARIMBO_PAGINA)
from aem_lib import parse_cookie_string  # noqa: E402

M = C.M
DADOS = C.DADOS
G2_DAM = "/content/dam/macnicaglobal2/americas/mai/en"
GWI_DAM = "/content/dam/macnicagwi/americas/mai/public/en"
RT = "macnicaglobal2/components/content/"
S_FLEX_1COL = "1719484596357"                                    # flexcontainer: 1 Column (sp-flex-direction-column)
S_CONT_PAD_SMALL, S_CONT_PAD_W0 = "1717498052331", "1717498055877"   # container: padding Small (altura) / No Padding (largura)
sessao = C.sessao


def img(ref, alt, link=None):
    """image do global2 com o alt autoral valendo na tela (R49: altValueFromDAM ausente vale true)."""
    d = {"sling:resourceType": RT + "image", "fileReference": ref, "alt": alt, "altValueFromDAM": "false",
         "isDecorative": "false", "titleValueFromDAM": "false", "displayPopupTitle": "false"}
    if link:
        d.update(linkURL=link, linkTarget="_self")
    return d


def texto(h):
    return {"sling:resourceType": RT + "text", "text": h, "textIsRich": "true"}


def card_produto(nome, alvo, foto, alt):
    """Card da landing /products como no GWI (imagetext com isHeading=false): nome em negrito, centrado, como link, EM
    CIMA da foto, e a foto também linkada. Link de texto com .html (sem ele: 302 -> 403); o image põe o .html sozinho."""
    return [("text_1", texto(f'<p style="text-align: center;"><b><a href="{M}/{alvo}.html">{nome}</a></b></p>')),
            ("image_1", img(f"{G2_DAM}/images/products/{foto}", alt, f"{M}/{alvo}"))]


def grade(base, cards, por_linha=4):
    """flexcontainer 1 Column com `por_linha` flexcontaineritem — o desenho da aba Suppliers/Partners da imaging-and-vision."""
    ops = [("criar", f"{base}/flexcontainer_1", {"sling:resourceType": RT + "flexcontainer", "cq:styleIds": [S_FLEX_1COL]})]
    for i, filhos in enumerate(cards, 1):
        item = f"{base}/flexcontainer_1/flexcontaineritem_{i}"
        ops.append(("criar", item, {"sling:resourceType": RT + "flexcontaineritem"}))
        ops += [("criar", f"{item}/{nome}", props) for nome, props in filhos]
    return ops


# ---------------------------------------------------------------- páginas (lista fechada)
PAGINAS = {
    "products": {
        "feito": "piloto 24/09 23:45, backup_conteudo_2026-09-24_234543",
        "gwi": "/content/macnicagwi/americas/mai/en/products",
        "o_que": "4 cards de categoria (em branco: 4 image sem imagem, larguras 2/2+1/3+4/2) -> grade de 4 (texto-link + foto "
                 "linkada), coluna 8+2 como o resto da página; banner (image vazio) -> products-banner.jpg do GWI",
        "assets": [(f"{GWI_DAM}/banners/products-banner.jpg", f"{G2_DAM}/images/products/products-banner.jpg")],
        "ops": [
            ("props", "root/container/image", img(f"{G2_DAM}/images/products/products-banner.jpg", "Products")),
            ("apagar", "root/container/container/image"),
            ("apagar", "root/container/container/image_1021195315"),
            ("apagar", "root/container/container/image_1899426112"),
            ("apagar", "root/container/container/image_66652080"),
            ("props", "root/container/container", {"cq:styleIds": [S_CONT_PAD_SMALL, S_CONT_PAD_W0]}),
            ("props", "root/container/container/cq:responsive/default", {"width": "8", "offset": "2"}),
        ] + grade("root/container/container", [
            card_produto("Semiconductors", "products/semiconductors", "iStock-1773543830.jpg", "Semiconductors"),
            card_produto("Boards &amp; Modules", "products/boards-modules", "Boards-generic.jpg", "mo"),  # alt do GWI (erro dele)
            card_produto("Displays", "products/displays", "TouchDisplay-generic.jpg", "Displays"),
            card_produto("IP and Software", "products/ip-software", "IP-Software.jpg", "IP & Software"),
        ]),
    },
    "products#padding": {
        "pagina": "products",
        "o_que": "piloto: o container da grade volta ao padding vertical PADRÃO (50px, o que tinha antes); fica só o 'sem "
                 "padding lateral', que alinha a grade com o texto. O 'Small' (30px) encolheu o vão até o rodapé (28px; GWI ~80)",
        "ops": [("props", "root/container/container", {"cq:styleIds": [S_CONT_PAD_W0]},
                 {"cq:styleIds": [S_CONT_PAD_SMALL, S_CONT_PAD_W0]})],
    },
}


# ---------------------------------------------------------------- precondições
CONTEUDO = ("fileReference", "linkURL", "text", "jcr:title", "fragmentVariationPath", "tableData")


def no_de(j, rel):
    for p in rel.split("/"):
        if not isinstance(j, dict) or p not in j:
            return None
        j = j[p]
    return j


def conferir(pag, cfg, jc):
    """Lista de problemas (vazia = pode gravar) contra o jcr:content lido agora."""
    prob = []
    criados = set()
    for op in cfg["ops"]:
        tipo, rel = op[0], op[1]
        no, pai = no_de(jc, rel), no_de(jc, rel.rsplit("/", 1)[0]) if "/" in rel else jc
        if tipo == "props" and no is None and rel.rsplit("/", 1)[0] not in criados:
            prob.append(f"props: {rel} não existe")
        elif tipo == "props" and len(op) > 3:
            prob += [f"props: {rel}.{k} = {no.get(k)!r}, esperado {v!r}" for k, v in op[3].items() if no.get(k) != v]
        elif tipo == "criar":
            if no is not None:
                prob.append(f"criar: {rel} já existe")
            if pai is None and rel.rsplit("/", 1)[0] not in criados:
                prob.append(f"criar: pai de {rel} não existe")
            criados.add(rel)
        elif tipo == "apagar":
            if no is None:
                prob.append(f"apagar: {rel} não existe")
            elif any(k in no for k in CONTEUDO) or any(isinstance(v, dict) and k != "cq:responsive" for k, v in no.items()):
                prob.append(f"apagar: {rel} NÃO está vazio")
        if C.motivo_bloqueio("POST", C.url(f"{M}/{pag}/jcr:content/{rel}"), {"a": "b"}):
            prob.append(f"página protegida ({rel})")
    for origem, destino in cfg.get("assets", []):
        st_d, _ = C.ler(destino, ".0.json")
        st_p, _ = C.ler(destino.rsplit("/", 1)[0], ".0.json")
        st_o, _ = C.ler(origem + "/jcr:content/metadata", ".json")
        if st_d != 404 or st_p != 200 or st_o != 200:
            prob.append(f"asset {destino[len(G2_DAM):]}: destino HTTP {st_d} (quero 404), pasta {st_p}, origem {st_o}")
    return prob


# ---------------------------------------------------------------- gravação
def payload(props):
    d = {"_charset_": "utf-8"}
    for k, v in props.items():
        if isinstance(v, list):
            d[k], d[f"{k}@TypeHint"] = v, "String[]"
        else:
            d[k] = v
    return d


def copiar_asset(origem, destino):
    pasta, nome = destino.rsplit("/", 1)
    assert destino.startswith(G2_DAM + "/") and "macnicagwi" not in pasta, destino           # só LÊ o GWI
    _, md_o = C.ler(origem + "/jcr:content/metadata", ".json")
    r = sessao.post(C.url(pasta), data={f"{nome}@CopyFrom": origem, "_charset_": "utf-8"}, timeout=300)
    st, j = C.ler(destino, ".2.json")
    _, md_d = C.ler(destino + "/jcr:content/metadata", ".json")
    rend = [k for k, v in ((j or {}).get("jcr:content", {}).get("renditions") or {}).items() if isinstance(v, dict)]
    g = sessao.get(C.url(destino), timeout=300, allow_redirects=False)
    ok = (r.status_code in (200, 201) and (j or {}).get("jcr:primaryType") == "dam:Asset"
          and (md_d or {}).get("dam:sha1") == (md_o or {}).get("dam:sha1") and g.status_code == 200
          and len(g.content) == int((md_o or {}).get("dam:size") or -1))
    print(f"   asset {destino[len(G2_DAM):]}: POST {r.status_code}; sha1 {'igual' if ok else (md_d or {}).get('dam:sha1')}; "
          f"GET {g.status_code} {len(g.content)} bytes; {len(rend)} renditions -> {'COPIADO' if ok else 'FALHOU'}")
    return ok


def aplicar(pag, op):
    tipo, rel = op[0], op[1]
    alvo = C.url(f"{M}/{pag}/jcr:content/{rel}")
    if tipo == "apagar":
        r = sessao.post(alvo, data={":operation": "delete"}, timeout=120)
    else:
        d = payload(op[2])
        if tipo == "criar":
            d.setdefault("jcr:primaryType", "nt:unstructured")
            if len(op) > 3:
                d[":order"] = op[3]
        r = sessao.post(alvo, data=d, timeout=120)
    return r.status_code


# ---------------------------------------------------------------- conferência
def prints(pags, pasta):
    """{pag: png} — página inteira a 1400px fora do editor."""
    from playwright.sync_api import sync_playwright
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
            png = pasta / f"{pag.replace('/', '__') or 'raiz'}.png"
            pg.screenshot(path=str(png), full_page=True)
            out[pag] = png
        b.close()
    return out


def compara_prints(pa, pd):
    """Linhas iguais no topo e no fim (alinhado pelo rodapé); o miolo é a região que mudou."""
    import numpy as np
    from PIL import Image
    a, d = np.array(Image.open(pa).convert("RGB")), np.array(Image.open(pd).convert("RGB"))
    w = min(a.shape[1], d.shape[1])
    a, d = a[:, :w], d[:, :w]
    n = min(len(a), len(d))
    topo = next((y for y in range(n) if not np.array_equal(a[y], d[y])), n)
    fim = next((k for k in range(1, n + 1) if not np.array_equal(a[-k], d[-k])), n + 1) - 1
    return {"altura": (len(a), len(d)), "igual_no_topo_ate": topo, "igual_no_fim_px": fim,
            "miolo_antes": (topo, len(a) - fim), "miolo_depois": (topo, len(d) - fim)}


def tokens(h):
    h = C.DL_RE.sub("", h)
    h = C.MODIFY_RE.sub(r"\1<data>", h)
    h = re.sub(r"\s+", " ", h)
    return [t for t in re.split(r"(<[^>]+>)", h) if t.strip()]


def compara_render(ha, hd):
    ta, td = tokens(ha), tokens(hd)
    sm = difflib.SequenceMatcher(None, ta, td, autojunk=False)
    ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
    txt = lambda ts: C.texto(" ".join(t for t in ts if not t.startswith("<")))
    tags = lambda ts: sorted({re.match(r"<(\w+)", t).group(1) for t in ts if re.match(r"<\w", t)})
    saiu = [t for o in ops for t in ta[o[1]:o[2]]]
    entrou = [t for o in ops for t in td[o[3]:o[4]]]
    return {"blocos": len(ops), "igual_antes_do_1o": ops[0][1] if ops else len(ta), "igual_depois_do_ultimo": len(ta) - ops[-1][2] if ops else 0,
            "texto_saiu": txt(saiu), "texto_entrou": txt(entrou), "tags_saiu": tags(saiu), "tags_entrou": tags(entrou),
            "links_saiu": sorted(set(re.findall(r'href="([^"]*)"', " ".join(saiu)))),
            "links_entrou": sorted(set(re.findall(r'href="([^"]*)"', " ".join(entrou)))),
            "imgs_entrou": sorted(set(re.findall(r'src="([^"]*)"', " ".join(entrou))))}


def compara_jcr(ja, jd, cfg):
    fa, fd = C.achatar(ja), C.achatar(jd)
    declarados = [op[1] for op in cfg["ops"]]
    props_de = {op[1]: set(op[2]) | {f"{k}@TypeHint" for k in op[2]} for op in cfg["ops"] if op[0] == "props"}
    auto = {"jcr:lastModified", "jcr:lastModifiedBy", "jcr:created", "jcr:createdBy"}

    def previsto(no, k):
        if (no, k) in C.CARIMBO_PAGINA:
            return True
        for op in cfg["ops"]:
            rel = op[1]
            if op[0] in ("criar", "apagar") and (no == rel or no.startswith(rel + "/")):
                return True
            if op[0] == "props" and no == rel and (k in props_de[rel] or k in auto):
                return True
        return False
    fora = sorted(f"{no}.{k}" for no, k in set(fa) | set(fd) if fa.get((no, k)) != fd.get((no, k)) and not previsto(no, k))
    return fora, declarados


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--so", nargs="*", default=[])
    ap.add_argument("--testar-comparador", action="store_true", help="só GET: 2 leituras de cada página têm de dar 0 diferença")
    a = ap.parse_args()
    if a.testar_comparador:
        pags = sorted({cfg.get("pagina", ch) for ch, cfg in PAGINAS.items() if not a.so or ch in a.so})
        pasta = Path(os.environ.get("CF_TESTE", "/tmp")) / f"teste_comparador_{datetime.datetime.now():%H%M%S}"
        r1 = {p: C.retrato(f"{M}/{p}") for p in pags}
        p1 = prints(pags, pasta / "1")
        r2 = {p: C.retrato(f"{M}/{p}") for p in pags}
        p2 = prints(pags, pasta / "2")
        for p in pags:
            fora, _ = compara_jcr(r1[p][0], r2[p][0], {"ops": []})
            rr, pr = compara_render(r1[p][1], r2[p][1]), compara_prints(p1[p], p2[p])
            ok = not fora and rr["blocos"] == 0 and pr["igual_no_topo_ate"] == min(pr["altura"])
            print(f"{'OK ' if ok else 'DIFERENÇA'} /{p}: JCR {fora or 'igual'}; render {rr['blocos']} trechos; print {pr}")
        return
    lista = []
    for chave, cfg in PAGINAS.items():
        if a.so and chave not in a.so:
            continue
        pag = cfg.get("pagina", chave)
        if cfg.get("feito"):
            print(f"## {chave}: já gravado ({cfg['feito']})"); continue
        st, jc = C.ler(f"{M}/{pag}/jcr:content", ".infinity.json")
        assert st == 200, (pag, st)
        prob = conferir(pag, cfg, jc)
        print(f"## {chave} -> /{pag}  (última edição {jc.get('cq:lastModified', '')[:24]} por {jc.get('cq:lastModifiedBy', '')})\n   {cfg['o_que']}")
        for origem, destino in cfg.get("assets", []):
            print(f"   asset  {origem[len(GWI_DAM):]} -> {destino[len(G2_DAM):]}")
        for op in cfg["ops"]:
            extra = ""
            if op[0] in ("props", "criar"):
                extra = "; ".join(f"{k}={str(v)[:70]}" for k, v in op[2].items() if k != "sling:resourceType")
                extra = f"<{op[2].get('sling:resourceType', '').rsplit('/', 1)[-1]}> {extra}" if op[0] == "criar" else extra
            print(f"   {op[0]:6} {op[1]}  {extra}")
        print("   PULA: " + "; ".join(prob) if prob else "   precondições OK")
        if not prob:
            lista.append((pag, cfg, jc))
    assert len({x[0] for x in lista}) == len(lista), "a mesma página duas vezes na rodada: rodar as passadas separadas"
    if not a.executar:
        print(f"\n{len(lista)} páginas prontas (DRY-RUN: nada gravado)")
        return

    agora = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    pasta = DADOS / f"backup_conteudo_{agora}"
    pasta.mkdir(parents=True)
    retratos = {pag: C.retrato(f"{M}/{pag}") for pag, _, _ in lista}                                  # backup ANTES
    (pasta / "jcr_content.json").write_text(json.dumps({k: v[0] for k, v in retratos.items()}, ensure_ascii=False), encoding="utf-8")
    (pasta / "render.json").write_text(json.dumps({k: v[1] for k, v in retratos.items()}, ensure_ascii=False), encoding="utf-8")
    p_antes = prints([pag for pag, _, _ in lista], pasta / "prints_antes")
    print(f"backup: {len(lista)} páginas (jcr:content + render + print) -> {pasta}")

    feitos = []
    for pag, cfg, jc_plano in lista:
        st, jc = C.ler(f"{M}/{pag}/jcr:content", ".infinity.json")                                  # relido agora
        if C.achatar(jc) != C.achatar(jc_plano) or conferir(pag, cfg, jc):
            print(f"## /{pag}: MUDOU desde o plano — pulado"); continue
        print(f"## /{pag}")
        ok = all(copiar_asset(o, d) for o, d in cfg.get("assets", []))
        if not ok:
            print("   asset FALHOU — página não mexida"); continue
        codigos = []
        for op in cfg["ops"]:
            codigos.append(aplicar(pag, op))
            if codigos[-1] not in (200, 201):
                print(f"   {op[0]} {op[1]}: HTTP {codigos[-1]} — PAROU"); break
        print(f"   {len(codigos)} operações: HTTP {sorted(set(codigos))}")
        with open(DADOS / "manifesto_links.jsonl", "a") as f:
            f.write(json.dumps({"grupo": "G-conteudo", "pagina": f"{M}/{pag}", "tipo": "conteudo", "txt": cfg["o_que"],
                                "ops": [op[:2] for op in cfg["ops"]], "assets": cfg.get("assets", []), "quando": agora,
                                "status": "gravado" if all(c in (200, 201) for c in codigos) and len(codigos) == len(cfg["ops"]) else "falhou",
                                "http": codigos}, ensure_ascii=False) + "\n")
        feitos.append((pag, cfg))

    p_depois = prints([pag for pag, _ in feitos], pasta / "prints_depois")
    comp = []
    print("\n== antes x depois ==")
    for pag, cfg in feitos:
        jd, hd = C.retrato(f"{M}/{pag}")
        fora, _ = compara_jcr(retratos[pag][0], jd, cfg)
        rr = compara_render(retratos[pag][1], hd)
        pr = compara_prints(p_antes[pag], p_depois[pag])
        print(f"/{pag}: JCR fora do previsto {fora or 'nada'}\n   render: {rr['blocos']} trechos diferentes; saiu “{rr['texto_saiu'][:200]}” "
              f"{rr['tags_saiu']}; entrou “{rr['texto_entrou'][:300]}” {rr['tags_entrou']}\n   links que entraram {rr['links_entrou']}; "
              f"saíram {rr['links_saiu']}\n   imagens que entraram {rr['imgs_entrou']}\n   print: altura {pr['altura']}; igual até y={pr['igual_no_topo_ate']}; "
              f"igual nos últimos {pr['igual_no_fim_px']} px; miolo {pr['miolo_antes']} -> {pr['miolo_depois']}")
        comp.append({"pagina": pag, "jcr_fora": fora, "render": rr, "prints": pr})
    (pasta / "comparacao.json").write_text(json.dumps(comp, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
