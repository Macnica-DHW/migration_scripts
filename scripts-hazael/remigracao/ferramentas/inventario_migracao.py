#!/usr/bin/env python3
"""
inventario_migracao.py <secao>... [--render] — o que falta migrar do GWI para o global2. SOMENTE LEITURA.

Para cada seção (ex.: /technology /services /about-us) sob
/content/macnicagwi/americas/mai/en x /content/macnicaglobal2/americas/mai/en:

  1. lista as páginas dos dois lados e CASA os caminhos (nome exato, depois nome
     normalizado, depois sem diferença de maiúscula) — a Anion migra à mão e às
     vezes mantém o nome do GWI, às vezes não;
  2. lê o `jcr:content` de cada página: componentes de conteúdo, caracteres de
     texto, imagens, quem mexeu por último, `deleted` (soft-delete),
     redirecionamento, e no GWI se está PUBLICADA (página desativada na origem
     não é dívida de migração);
  3. com `--render`, abre os dois lados no Chrome (?wcmmode=disabled) e compara o
     TEXTO QUE SE VÊ (mesmo comparador do aem_fidelidade_render): o JCR da
     origem não é a página da origem, e a Anion monta com outros componentes —
     só a tela compara de verdade.

VEREDITO (coluna `status`)
  CRIAR       existe no GWI e não existe no global2
  MODIFICAR   existe, mas vazia (sem texto na tela) ou incompleta (falta texto do GWI)
  MIGRADA     existe e todo o texto do GWI está na tela do global2
  SO-GLOBAL2  existe só no global2 (página nova da Anion, renomeada ou movida)
Sem `--render` o veredito das que existem sai só do JCR (`?` no fim = palpite).

  python3 remigracao/ferramentas/inventario_migracao.py /technology /services /about-us --render
"""
import csv, json, os, re, sys
from pathlib import Path
_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import (CONFIG, build_session, crawl_tree, get_json, normalize_name,
                     parse_cookie_string)

G = "/content/macnicagwi/americas/mai/en"
D = "/content/macnicaglobal2/americas/mai/en"
ESTRUTURA = ("container", "responsivegrid", "resizablecontainer", "flexcontainer",
             "flexcontaineritem", "ghost", "pageproperties", "breadcrumb")
TEXTO = ("text", "jcr:title", "heading", "title", "description", "jcr:description")


def fatos(jc):
    """Números do jcr:content/root: componentes de conteúdo, texto, imagens."""
    comps, chars, imgs, tipos = 0, 0, 0, {}

    def anda(n):
        nonlocal comps, chars, imgs
        rt = str(n.get("sling:resourceType", "")).rsplit("/", 1)[-1]
        if rt and rt not in ESTRUTURA:
            comps += 1
            tipos[rt] = tipos.get(rt, 0) + 1
            for p in TEXTO:
                v = n.get(p)
                if isinstance(v, str):
                    chars += len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", v)).strip())
            if isinstance(n.get("fileReference"), str) and n["fileReference"]:
                imgs += 1
        for v in n.values():
            if isinstance(v, dict):
                anda(v)

    raiz = jc.get("root")
    if isinstance(raiz, dict):
        anda(raiz)
    return comps, chars, imgs, tipos


def ler(s, auth, base, caminho):
    jc, st = get_json(s, f"{base}{caminho}/jcr:content.infinity.json", auth)
    if not isinstance(jc, dict):          # HTTP 300: o AEM devolve a lista de profundidades
        jc, st = get_json(s, f"{base}{caminho}/jcr:content.50.json", auth)
    if not isinstance(jc, dict):
        return None
    comps, chars, imgs, tipos = fatos(jc)
    return {
        "titulo": jc.get("jcr:title", ""),
        "template": str(jc.get("cq:template", "")).rsplit("/", 1)[-1],
        "modificado": str(jc.get("cq:lastModified", ""))[4:21],
        "por": str(jc.get("cq:lastModifiedBy", "")).split("@")[0],
        "publicada": jc.get("cq:lastReplicationAction") or jc.get("cq:lastReplicationAction_publish", ""),
        "deleted": bool(jc.get("deleted") or jc.get("deletedBy")),
        "redirect": jc.get("cq:redirectTarget") or jc.get("redirectTarget") or "",
        "comps": comps, "chars": chars, "imgs": imgs,
        "tipos": " ".join(f"{k}={v}" for k, v in sorted(tipos.items(), key=lambda x: -x[1])[:6]),
    }


def casar(rels_g, rels_d):
    """{rel do GWI: rel do global2 | None}, e o que sobrou só no global2."""
    livres = set(rels_d)
    por_norm = {"/".join(normalize_name(x) for x in r.split("/")): r for r in rels_d}
    por_lower = {r.lower(): r for r in rels_d}
    pares = {}
    for r in rels_g:
        alvo = (r if r in livres else
                por_norm.get("/".join(normalize_name(x) for x in r.split("/"))) or
                por_lower.get(r.lower()))
        if alvo in livres:
            livres.discard(alvo)
            pares[r] = alvo
        else:
            pares[r] = None
    return pares, sorted(livres)


def main():
    args = sys.argv[1:]
    render = "--render" in args
    saida = "remigracao/dados/inventario_migracao.csv"
    if "--output" in args:
        i = args.index("--output")
        saida = args[i + 1]
        del args[i:i + 2]
    secoes = [a for a in args if a.startswith("/")]
    if not secoes:
        sys.exit(__doc__)
    s, auth = build_session(prompt_if_missing=False, verbose=False)
    base = CONFIG["base_url"]
    if "author-" not in base:                       # o cookie só vai para o author
        sys.exit(f"[erro] base_url inesperada: {base}")

    linhas = []
    for sec in secoes:
        sec = "/" + sec.strip("/")
        pg = sorted(crawl_tree(s, base, G + sec, auth, only_pages=True, quiet=True))
        pd = sorted(crawl_tree(s, base, D + sec, auth, only_pages=True, quiet=True))
        pares, so_d = casar([p[len(G):] for p in pg], [p[len(D):] for p in pd])
        print(f"  {sec}: GWI {len(pg)} páginas, global2 {len(pd)}; "
              f"sem par no global2 {sum(1 for v in pares.values() if v is None)}, só no global2 {len(so_d)}")
        for rg, rd in pares.items():
            linhas.append({"secao": sec, "gwi": rg, "global2": rd or "",
                           "g": ler(s, auth, base, G + rg), "d": ler(s, auth, base, D + rd) if rd else None})
        for rd in so_d:
            linhas.append({"secao": sec, "gwi": "", "global2": rd, "g": None,
                           "d": ler(s, auth, base, D + rd)})

    if render:
        import aem_fidelidade_render as FR
        from playwright.sync_api import sync_playwright
        cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
        host = base.split("//", 1)[1].rstrip("/")
        with sync_playwright() as pw:
            nav = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                                     args=["--no-sandbox", "--disable-dev-shm-usage"])
            ctx = nav.new_context(viewport={"width": 1400, "height": 1000})
            ctx.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"}
                             for k, v in cookies.items()])
            pag = ctx.new_page()
            alvo = [l for l in linhas if l["gwi"] and l["global2"]]
            for i, l in enumerate(alvo, 1):
                try:
                    uo = FR.extrair(pag, base, G + l["gwi"], 1500)
                    ud = FR.extrair(pag, base, D + l["global2"], 1500)
                    falt, sobr, _fora, _tl = FR.comparar(uo, ud)
                    vis_o = [u for u in uo if not FR.e_ruido(u.get("txt", ""))]
                    vis_d = [u for u in ud if not FR.e_ruido(u.get("txt", ""))]
                    l["r"] = {"un_gwi": len(vis_o), "un_g2": len(vis_d),
                              "faltando": len(falt), "sobrando": len(sobr),
                              "amostra": " ¦ ".join(re.sub(r"\s+", " ", u.get("txt", ""))[:70] for u in falt[:4])}
                except Exception as e:              # página que não abre é achado, não aborto
                    l["r"] = {"erro": str(e)[:120]}
                print(f"    [{i:3}/{len(alvo)}] {l['gwi'][:70]:70} {l['r']}"[:230])
            nav.close()

    for l in linhas:
        g, d, r = l["g"], l["d"], l.get("r")
        if not l["gwi"]:
            st = "SO-GLOBAL2"
        elif not l["global2"]:
            st = "CRIAR"
        elif d and d["deleted"]:
            st = "MODIFICAR"; l["motivo"] = "soft-delete no global2 (invisível no console)"
        elif r and "erro" not in r:
            if r["un_g2"] == 0 or (d and d["comps"] == 0):
                st = "MODIFICAR"; l["motivo"] = "VAZIA: nenhum texto de conteúdo na tela do global2"
            elif r["faltando"] == 0:
                st = "MIGRADA"
            else:
                pct = 100 * r["faltando"] // max(1, r["un_gwi"])
                st = "MODIFICAR"; l["motivo"] = f"INCOMPLETA: faltam {r['faltando']} de {r['un_gwi']} unidades de texto ({pct}%)"
        else:
            if d is None or d["comps"] == 0:
                st = "MODIFICAR?"; l["motivo"] = "JCR sem componente de conteúdo"
            elif g and d["chars"] < 0.6 * g["chars"]:
                st = "MODIFICAR?"; l["motivo"] = f"JCR com {d['chars']} caracteres contra {g['chars']} no GWI"
            else:
                st = "MIGRADA?"
        l["status"] = st

    Path(saida).parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["secao", "status", "motivo", "gwi", "global2", "gwi_publicada", "gwi_redirect",
                    "gwi_comps", "gwi_chars", "gwi_imgs", "g2_comps", "g2_chars", "g2_imgs",
                    "g2_modificado", "g2_por", "g2_template", "un_gwi", "un_g2", "faltando",
                    "sobrando", "amostra_faltando", "gwi_tipos", "g2_tipos"])
        for l in linhas:
            g, d, r = l["g"] or {}, l["d"] or {}, l.get("r") or {}
            w.writerow([l["secao"], l["status"], l.get("motivo", ""), l["gwi"], l["global2"],
                        g.get("publicada", ""), g.get("redirect", ""), g.get("comps", ""),
                        g.get("chars", ""), g.get("imgs", ""), d.get("comps", ""), d.get("chars", ""),
                        d.get("imgs", ""), d.get("modificado", ""), d.get("por", ""),
                        d.get("template", ""), r.get("un_gwi", ""), r.get("un_g2", ""),
                        r.get("faltando", ""), r.get("sobrando", ""), r.get("amostra", r.get("erro", "")),
                        g.get("tipos", ""), d.get("tipos", "")])
    json.dump(linhas, open(saida.replace(".csv", ".json"), "w"), indent=1, ensure_ascii=False, default=str)

    from collections import Counter
    print()
    for sec in secoes:
        c = Counter(l["status"] for l in linhas if l["secao"] == "/" + sec.strip("/"))
        print(f"  {sec:14} " + "  ".join(f"{k}={v}" for k, v in sorted(c.items())))
    print(f"\n  CSV: {saida}")


if __name__ == "__main__":
    main()
