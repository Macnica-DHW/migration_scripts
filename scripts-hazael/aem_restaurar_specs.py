#!/usr/bin/env python3
"""
Restaura a seção "Specifications" (título + tabela) perdida na migração.

O QUE ACONTECEU
Em 8 páginas de tq-systems o bloco Specifications existe no GWI e não
chegou ao destino. A perda é antiga — aconteceu em copia-teste, antes
dos fixes de layout, e foi propagada fielmente por todos os clones
seguintes. O próprio aem_tq_merge_specs_ordering.py registra no
docstring ter encontrado "16 páginas: só Ordering Information": ele viu
o buraco e trabalhou em volta dele, não o causou.

O extract_content do aem_lib lê o Specifications do GWI corretamente
HOJE — conferido. Ou seja: é recuperável, basta reinserir.

ONDE O BLOCO ENTRA
O layout-alvo (documentado no aem_tq_merge_specs_ordering.py e conferido
em página de referência) é um container único com:

    title(Specifications) -> table -> title(Ordering Information) -> table

Nas páginas quebradas esse container existe, mas só com a metade de
Ordering. Então o conserto é inserir título+tabela NO INÍCIO desse mesmo
container, via ':order' do Sling — sem criar container novo e sem mexer
em mais nada da página.

NÃO RECRIA A PÁGINA. Só acrescenta dois nós. Preserva todo o trabalho de
layout e as edições manuais feitas em copia-teste.

IDEMPOTENTE: página que já tem Specifications no destino é pulada.

COMO RODAR
  python3 aem_restaurar_specs.py --destino /content/copia-teste/.../tq-systems \
                                 --origem  /content/macnicagwi/.../tq-systems
  # depois de conferir o relatório:
  python3 aem_restaurar_specs.py --destino ... --origem ... --executar
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from urllib.parse import urljoin
from aem_lib import (CONFIG, HEADING_TYPES, TABLE_TYPES, TITLE_TYPES, build_session,
                     crawl_tree, fetch_with_depth_fallback, get_json, list_child_nodes,
                     normalize_name, post_node, print_header, rewrite_links_in_html,
                     session_expired, write_csv)

TITLE_RT = "macnicaglobal2/components/content/title"
TABLE_RT = "macnicaglobal2/components/content/table"
TAG_RE = re.compile(r"<[^>]+>")


def so_texto(v):
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", v or "")).strip() if isinstance(v, str) else ""


def achar_specs_no_gwi(jcr):
    """Devolve (titulo, html_da_tabela) do bloco Specifications do GWI.

    A tabela é o PRÓXIMO irmão 'table' depois do heading — é assim que as
    páginas do GWI montam a seção. Se não houver tabela logo depois, não
    devolve nada: melhor não inserir do que inserir a tabela errada.
    """
    achado = [None]

    def walk(node):
        filhos = list(list_child_nodes(node))
        for i, (_, ch) in enumerate(filhos):
            rt = ch.get("sling:resourceType", "")
            texto = so_texto(ch.get("text") or ch.get("jcr:title") or "")
            if (rt in HEADING_TYPES or rt in TITLE_TYPES) and \
               texto.lower().startswith("specification"):
                for _, seg in filhos[i + 1:]:
                    if seg.get("sling:resourceType", "") in TABLE_TYPES:
                        achado[0] = (texto, seg.get("text", ""))
                        return
                    if seg.get("sling:resourceType", "") in HEADING_TYPES:
                        break  # chegou na próxima seção sem achar tabela
            walk(ch)

    walk(jcr)
    return achado[0]


def achar_container_ordering(jcr):
    """Caminho relativo do container que tem o title 'Ordering Information'."""
    root = (jcr.get("root") or {})
    cont = root.get("container") or {}
    for nome, wrap in list_child_nodes(cont):
        for _, comp in list_child_nodes(wrap):
            t = so_texto(comp.get("jcr:title") or "")
            if t.lower().startswith("ordering information"):
                return f"jcr:content/root/container/{nome}"
    return None


def tem_specs(jcr):
    achou = [False]

    def walk(n):
        for _, ch in list_child_nodes(n):
            if so_texto(ch.get("jcr:title") or ch.get("text") or "").lower().startswith("specification"):
                achou[0] = True
            walk(ch)
    walk(jcr)
    return achou[0]


def achar_origem(session, base_url, dst_path, dst_root, org_root, auth, cache):
    rel = dst_path[len(dst_root):].strip("/")
    if not rel:
        return org_root
    atual = org_root
    for parte in rel.split("/"):
        filhos = cache.get(atual)
        if filhos is None:
            d, _ = get_json(session, urljoin(base_url, f"{atual}.1.json"), auth)
            filhos = [n for n, _ in list_child_nodes(d or {})]
            cache[atual] = filhos
        exato = parte if parte in filhos else None
        if exato is None:
            iguais = [n for n in filhos if normalize_name(n) == normalize_name(parte)]
            if not iguais:
                return None
            exato = iguais[0]
        atual = f"{atual}/{exato}"
    return atual


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--destino", required=True)
    ap.add_argument("--origem", required=True)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
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

    saida = args.output or f"specs_{dst_root.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("RESTAURAR SPECIFICATIONS")
    print(f"  origem : {org_root}\n  destino: {dst_root}")
    print(f"  modo   : {'ESCRITA' if args.executar else 'diagnóstico (nada será escrito)'}\n")

    inv = crawl_tree(s, base, dst_root, at, quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas no destino\n")

    cache, linhas, alvos = {}, [], []
    for p in paginas:
        dd, _ = fetch_with_depth_fallback(s, base, p, 10, at)
        if dd is None:
            continue
        jcr_d = (dd or {}).get("jcr:content", {}) or {}
        if (jcr_d or {}).get("deleted"):
            continue                      # órfã soft-deleted, não é conteúdo vivo
        if tem_specs(jcr_d):
            continue                      # já tem, idempotente
        gp = achar_origem(s, base, p, dst_root, org_root, at, cache)
        if gp is None:
            continue
        dg, _ = fetch_with_depth_fallback(s, base, gp, 16, at)
        if dg is None:
            continue
        specs = achar_specs_no_gwi((dg or {}).get("jcr:content", {}) or {})
        if not specs:
            continue                      # o GWI também não tem: nada a restaurar
        titulo, html = specs
        cont_rel = achar_container_ordering(jcr_d)
        linhas.append({"pagina": p, "origem_gwi": gp, "titulo": titulo,
                       "tamanho_tabela": len(html or ""),
                       "container_alvo": cont_rel or "(NÃO ACHOU Ordering)",
                       "acao": "pendente"})
        if cont_rel:
            alvos.append((p, cont_rel, titulo, html))

    print(f"  páginas sem Specifications e com o bloco no GWI: {len(linhas)}")
    print(f"  dessas, com container de Ordering identificado : {len(alvos)}\n")
    for l in linhas:
        print(f"   {l['pagina'].rsplit('/', 1)[-1][:52]:<54} tabela={l['tamanho_tabela']:>6}b  "
              f"{l['container_alvo'].rsplit('/', 1)[-1]}")

    if not args.executar:
        write_csv(saida, ["pagina", "origem_gwi", "titulo", "tamanho_tabela",
                          "container_alvo", "acao"], linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    ok = falhas = 0
    for i, (p, cont_rel, titulo, html) in enumerate(alvos, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(alvos)}", file=sys.stderr)
            break
        texto = rewrite_links_in_html(html, args.link_de, args.link_para)
        st1, c1 = post_node(s, base, f"{p}/{cont_rel}/title_spec", {
            "jcr:primaryType": "nt:unstructured", "sling:resourceType": TITLE_RT,
            "jcr:title": titulo, "type": "h3", ":order": "first"}, at, allow_extra=allow)
        st2, c2 = post_node(s, base, f"{p}/{cont_rel}/table_spec", {
            "jcr:primaryType": "nt:unstructured", "sling:resourceType": TABLE_RT,
            "text": texto, "textIsRich": "true", ":order": "1"}, at, allow_extra=allow)
        if st1 in (200, 201) and st2 in (200, 201):
            ok += 1
            for l in linhas:
                if l["pagina"] == p:
                    l["acao"] = "restaurado"
        else:
            falhas += 1
            print(f"  [FALHA] {p} :: title={st1} table={st2} :: {(c1 or c2)[:80]}")
            for l in linhas:
                if l["pagina"] == p:
                    l["acao"] = f"FALHA title={st1} table={st2}"

    write_csv(saida, ["pagina", "origem_gwi", "titulo", "tamanho_tabela",
                      "container_alvo", "acao"], linhas)
    print(f"\n  restauradas: {ok}   falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
