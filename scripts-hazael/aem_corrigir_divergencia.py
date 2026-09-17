#!/usr/bin/env python3
"""
Corrige páginas do GLOBAL2 cujo conteúdo DIVERGE do GWI de origem.

A REGRA (definida pelo time em 17/09/2026)
O GWI é a fonte da verdade. Se o conteúdo do GWI está errado, o problema
é do GWI — migra-se fielmente assim mesmo. Se o GLOBAL2 diverge do GWI,
o erro é NOSSO e tem que ser corrigido. Layout pode (e deve) diferir;
conteúdo, não.

O QUE ISTO ACHOU
Várias páginas de tq-systems carregam texto de OUTRA página. Exemplo:
mba8mpxl-single-board-computer tinha o h1 e o parágrafo de introdução do
boxpc-abox-6ulxl, com a imagem e o alt corretos. O texto
"Extended temperature range for challenging environments..." (que é do
boxpc-abox-6ulxl no GWI) aparecia em 4 páginas diferentes.

Não é padronização de conteúdo: das 131 páginas com bloco Features, 115
têm texto DISTINTO. A repetição é acidente de copiar-e-colar em poucas
páginas, não política editorial.

O QUE CORRIGE (só dois campos, nada mais)
  1. textwithimage/text  -> <h1>{heading do GWI}</h1> + {intro do GWI}
  2. o text do bloco de Features -> <h3>Features</h3> + {lista do GWI}

A conversão é 1-para-1 do vocabulário antigo para o novo; o HTML interno
(<p>, <ul><li>) vem do GWI sem alteração, só com os links reescritos
para o prefixo do destino, como faz o aem_migrate.py.

O QUE NÃO TOCA
- O heading genérico "Features": no GWI cada página tem um título
  próprio ("TQMxE41S SMARC 2.1 Specs & Features"), e no destino as 131
  páginas usam "Features". Isso é LAYOUT novo, aplicado de forma
  consistente — não é conteúdo divergente.
- Imagem, alt, tabelas, Specifications, Ordering, botões.

IDEMPOTENTE: página cujo texto já bate com o GWI (cobertura >= --limiar)
é pulada e reportada como "ok".

COMO RODAR
  python3 aem_corrigir_divergencia.py --destino /content/macnicaglobal2/.../tq-systems \
                                      --origem  /content/macnicagwi/.../tq-systems
  # depois de conferir o CSV:
  python3 aem_corrigir_divergencia.py --destino ... --origem ... --executar \
      --permitir-escrita-global2 /content/macnicaglobal2/.../tq-systems
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from urllib.parse import urljoin
from aem_lib import (CONFIG, HEADING_TYPES, TITLE_TYPES, build_session, crawl_tree,
                     fetch_with_depth_fallback, get_json, list_child_nodes,
                     normalize_name, post_node, print_header, rewrite_links_in_html,
                     session_expired, write_csv)

TAG_RE = re.compile(r"<[^>]+>")


def plano(v):
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", v or "")).strip() if isinstance(v, str) else ""


def cobertura(origem, destino):
    """Fração das palavras da origem que aparecem no destino."""
    pal = plano(origem).lower().split()
    if not pal:
        return 1.0
    alvo = plano(destino).lower()
    return sum(1 for w in pal if w in alvo) / len(pal)


def ler_gwi(jcr):
    """(heading_plano, intro_html, features_html) da página do GWI."""
    achados = {"h": None, "t": None, "f": None}

    def walk(node):
        for _, ch in list_child_nodes(node):
            rt = ch.get("sling:resourceType", "")
            if (rt in HEADING_TYPES or rt in TITLE_TYPES) and achados["h"] is None:
                achados["h"] = plano(ch.get("text") or ch.get("jcr:title") or "")
            elif rt.endswith("/text") and achados["t"] is None:
                achados["t"] = ch.get("text") or ""
            elif rt.endswith("/imagetext") and achados["f"] is None:
                for _, sub in list_child_nodes(ch):
                    if sub.get("sling:resourceType", "").endswith("/text"):
                        corpo = sub.get("text") or ""
                        if len(plano(corpo)) > 25:
                            achados["f"] = corpo
                            break
            walk(ch)

    walk(jcr)
    return achados["h"], achados["t"], achados["f"]


def achar_destino(jcr):
    """Caminhos relativos do textwithimage e do text de Features."""
    cont = ((jcr.get("root") or {}).get("container") or {})
    twi = feat = None
    for nome, wrap in list_child_nodes(cont):
        for n2, comp in list_child_nodes(wrap):
            rt = comp.get("sling:resourceType", "")
            base = f"jcr:content/root/container/{nome}/{n2}"
            if rt.endswith("/textwithimage") and twi is None:
                twi = (base, comp.get("text") or "")
            elif rt.endswith("/text") and feat is None and \
                    plano(comp.get("text") or "").lower().startswith("features"):
                feat = (base, comp.get("text") or "")
    return twi, feat


def achar_origem(session, base_url, dst, dst_root, org_root, auth, cache):
    rel = dst[len(dst_root):].strip("/")
    atual = org_root
    for parte in rel.split("/") if rel else []:
        filhos = cache.get(atual)
        if filhos is None:
            d, _ = get_json(session, urljoin(base_url, f"{atual}.1.json"), auth)
            filhos = [n for n, _ in list_child_nodes(d or {})]
            cache[atual] = filhos
        exato = parte if parte in filhos else next(
            (n for n in filhos if normalize_name(n) == normalize_name(parte)), None)
        if exato is None:
            return None
        atual = f"{atual}/{exato}"
    return atual


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--destino", required=True)
    ap.add_argument("--origem", required=True)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    ap.add_argument("--limiar", type=float, default=0.85)
    ap.add_argument("--pular", action="append", default=[], metavar="TRECHO",
                    help="Ignora páginas cujo caminho contenha este trecho "
                         "(repetível). Use para deixar de fora casos que ainda "
                         "precisam de decisão humana.")
    ap.add_argument("--link-de", default=CONFIG["gwi_prefix"])
    ap.add_argument("--link-para", default=CONFIG["global2_prefix"])
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    dst_root, org_root = args.destino.rstrip("/"), args.origem.rstrip("/")
    allow = ()
    if args.permitir_escrita_global2:
        lib = args.permitir_escrita_global2.rstrip("/")
        if lib != dst_root:
            print("[erro] --permitir-escrita-global2 precisa ser igual a --destino.",
                  file=sys.stderr)
            sys.exit(1)
        allow = (lib,)

    saida = args.output or f"divergencia_{dst_root.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("CORRIGIR DIVERGÊNCIA DE CONTEÚDO (GWI é a fonte da verdade)")
    print(f"  origem : {org_root}\n  destino: {dst_root}")
    print(f"  modo   : {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv = crawl_tree(s, base, dst_root, at, quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")

    cache, linhas, tarefas = {}, [], []
    puladas = []
    for p in paginas:
        if any(x in p for x in args.pular):
            puladas.append(p)
            continue
        dd, _ = fetch_with_depth_fallback(s, base, p, 10, at)
        if dd is None:
            continue
        jcr_d = (dd or {}).get("jcr:content", {}) or {}
        if jcr_d.get("deleted"):
            continue
        gp = achar_origem(s, base, p, dst_root, org_root, at, cache)
        if gp is None:
            continue
        dg, _ = fetch_with_depth_fallback(s, base, gp, 16, at)
        if dg is None:
            continue
        gh, gt, gf = ler_gwi((dg or {}).get("jcr:content", {}) or {})
        twi, feat = achar_destino(jcr_d)

        campos = []
        if twi and (gh or gt):
            esperado = plano(gh) + " " + plano(gt)
            if cobertura(esperado, twi[1]) < args.limiar:
                novo = (f"<h1>{gh}</h1>\n" if gh else "") + (gt or "")
                campos.append(("textwithimage", twi[0], novo,
                               cobertura(esperado, twi[1])))
        if feat and gf:
            if cobertura(gf, feat[1]) < args.limiar:
                novo = "<h3>Features</h3>\n" + gf
                campos.append(("features", feat[0], novo, cobertura(gf, feat[1])))

        if campos:
            tarefas.append((p, campos))
            linhas.append({
                "pagina": p, "origem_gwi": gp,
                "campos": ", ".join(c[0] for c in campos),
                "cobertura": ", ".join(f"{c[3]:.0%}" for c in campos),
                "acao": "pendente"})

    if puladas:
        print(f"  páginas ignoradas por --pular: {len(puladas)}")
        for x in puladas:
            print(f"     - {x.rsplit('/', 1)[-1]}")
        print()
    print(f"  páginas divergentes: {len(tarefas)}\n")
    for p, campos in tarefas:
        print(f"   {p.rsplit('/', 1)[-1][:52]:<54} "
              f"{', '.join(f'{c[0]} {c[3]:.0%}' for c in campos)}")

    if not args.executar:
        write_csv(saida, ["pagina", "origem_gwi", "campos", "cobertura", "acao"], linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    ok = falhas = 0
    for i, (p, campos) in enumerate(tarefas, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(tarefas)}", file=sys.stderr)
            break
        erro = None
        for _, rel, novo, _ in campos:
            texto = rewrite_links_in_html(novo, args.link_de, args.link_para)
            st, corpo = post_node(s, base, f"{p}/{rel}",
                                  {"text": texto, "textIsRich": "true"},
                                  at, allow_extra=allow)
            if st not in (200, 201):
                erro = f"FALHA {st}: {corpo[:70]}"
                break
        if erro:
            falhas += 1
            linhas[i - 1]["acao"] = erro
            print(f"  [{erro}] {p}")
        else:
            ok += 1
            linhas[i - 1]["acao"] = "corrigido"
        if i % 10 == 0:
            print(f"  [{i}/{len(tarefas)}] ok={ok} falhas={falhas}", flush=True)

    write_csv(saida, ["pagina", "origem_gwi", "campos", "cobertura", "acao"], linhas)
    print(f"\n  corrigidas: {ok}   falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
