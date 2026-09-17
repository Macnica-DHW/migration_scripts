#!/usr/bin/env python3
"""
Conferência final de SEO (Page Properties), confirmada com o Bruno em
16/09/2026. "SEO" aqui é tudo dentro de Page Properties:

  BASIC:    Title, Page Title, Navigation Title, Description
  ADVANCED: Canonical URL
  PRODUCT HIERARCHY DETAILS: Business Categories, Manufacturer (mínimo
            — GWI é a referência: se GWI tiver mais campos preenchidos
            desse grupo, copia também, mas nunca inventa o que não
            existe na origem)

CORRIGE (só o que falta, nunca sobrescreve o que já está preenchido):
  - jcr:description: copiado do GWI (achar_origem_gwi, tolera
    maiúsculas diferentes no nome do nó — achado real: GWI tem
    'TQMT1022-...', destino tem 'tqmt1022-...'). QUANDO O GWI TAMBÉM
    NÃO TEM (achado real em 17/09/2026: 45/50 páginas de
    tq-embedded-x86-modules sem jcr:description em nenhum dos dois
    lados): extrai do primeiro <p> com texto de verdade, do primeiro
    bloco de conteúdo da PRÓPRIA página já migrada (confirmado com o
    Bruno — usar a origem do GWI quando existe, cair para o texto da
    página quando não existe). Ver extrair_meta_description em
    aem_lib.py. Reportado no CSV como 'extraído do 1º parágrafo' para
    revisão — é derivado, não um campo pronto, então vale conferir.
    'TQMT1022-...', destino tem 'tqmt1022-...').
  - cq:canonicalUrl: DERIVADO do próprio caminho da página (não vem do
    GWI) — é sempre o mesmo caminho, começando em
    /content/<site>/... até a própria página. Confirmado com o Bruno.
  - businessCategories/manufacturer: copiados do GWI só se estiverem
    vazios no destino.

CONFERE E REPORTA (não inventa, só avisa se faltar):
  - jcr:title, pageTitle, navTitle: reportados como pendência se
    vazios — não têm de onde vir automaticamente com segurança aqui
    (já deveriam ter sido migrados antes; se faltam, é caso a caso).

NÃO mexe em: pageType e outros campos que a aba Product Hierarchy
Details do GLOBAL2 não expõe (dialog macnicaglobal2/maeproductpage não
tem esses campos — confirmado com o Bruno, decisão de não copiar).

SEGURANÇA: escreve em copia-teste normalmente. Para macnicaglobal2,
precisa de --permitir-escrita-global2 com o --target exato.

COMO RODAR:
  # 1. Sempre simular primeiro:
  python3 aem_fix_seo_final.py --target /content/copia-teste/.../tq-embedded-power-modules --dry-run

  # 2. Conferir o CSV, então rodar de verdade:
  python3 aem_fix_seo_final.py --target /content/copia-teste/.../tq-embedded-power-modules

  # Em macnicaglobal2:
  python3 aem_fix_seo_final.py \\
      --target /content/macnicaglobal2/.../tq-systems-embedded/tq-embedded-power-modules \\
      --gwi-root /content/macnicagwi/.../tq-systems/tq-embedded-power-modules \\
      --permitir-escrita-global2 /content/macnicaglobal2/.../tq-systems-embedded/tq-embedded-power-modules
"""

import argparse
import sys

from aem_lib import (
    CONFIG, assert_target_is_safe, add_common_args, build_session, crawl_tree,
    extrair_meta_description, fetch_with_depth_fallback, list_child_nodes,
    normalize_name, post_node, print_header, session_expired, write_csv,
)

GWI_PREFIX_PADRAO = CONFIG["gwi_prefix"]


def achar_description_no_conteudo(jcr_content, profundidade_max=4):
    """Percorre os blocos de topo da página (em ordem) procurando o
    primeiro componente 'text' com um <p> de verdade — fallback para
    quando nem destino nem GWI têm jcr:description. Devolve o HTML
    bruto do texto (não o extraído), para extrair_meta_description
    processar depois.
    """
    container = (jcr_content.get("root", {}) or {}).get("container", {}) or {}

    def busca(node, profundidade):
        if profundidade > profundidade_max:
            return None
        for _, filho in list_child_nodes(node):
            texto = filho.get("text")
            if isinstance(texto, str) and "<p" in texto.lower():
                candidato = extrair_meta_description(texto)
                if candidato:
                    return candidato
            achado = busca(filho, profundidade + 1)
            if achado:
                return achado
        return None

    return busca(container, 0)


def achar_origem_gwi_generico(session, base_url, dest_path, target_root, gwi_root,
                              auth_tracker, cache_irmaos):
    """Mesma lógica do aem_fix_pages.achar_origem_gwi, mas independente
    de target_root ser copia-teste — funciona para qualquer prefixo de
    site (macnicaglobal2 incluído), já que o caminho relativo depois
    do prefixo é sempre o mesmo entre GWI e destino.
    """
    rel = dest_path[len(target_root):].lstrip("/")
    candidato = f"{gwi_root}/{rel}" if rel else gwi_root

    data, status = fetch_with_depth_fallback(session, base_url, candidato, 1, auth_tracker)
    if data is not None:
        return candidato, data

    if not rel:
        return None, None
    pai_rel, _, nome_dest = rel.rpartition("/")
    pai_gwi = f"{gwi_root}/{pai_rel}" if pai_rel else gwi_root

    if pai_gwi not in cache_irmaos:
        pai_data, _ = fetch_with_depth_fallback(session, base_url, pai_gwi, 1, auth_tracker)
        cache_irmaos[pai_gwi] = [n for n, _ in list_child_nodes(pai_data)] if pai_data else []

    for irmao in cache_irmaos[pai_gwi]:
        if normalize_name(irmao) == nome_dest:
            achado = f"{pai_gwi}/{irmao}"
            data, _ = fetch_with_depth_fallback(session, base_url, achado, 1, auth_tracker)
            if data is not None:
                return achado, data
    return None, None


def main():
    parser = argparse.ArgumentParser(
        description="Confere e corrige SEO final (Basic/Advanced/Product Hierarchy) "
                    "comparando com o GWI, onde GWI é a referência")
    parser.add_argument("--target", required=True)
    parser.add_argument("--gwi-root", default=None,
                        help="Raiz correspondente no GWI. Padrão: deriva do --target "
                             "trocando o prefixo do site.")
    add_common_args(parser)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    parser.add_argument("--output", default="fix_seo_final.csv")
    args = parser.parse_args()

    target_root = args.target.rstrip("/")

    # Deriva o site-prefix do próprio target_root (primeiros 2
    # segmentos: /content/<site>), para achar o gwi_root por troca de
    # prefixo, igual à regra confirmada de reescrita de links.
    partes = target_root.strip("/").split("/")
    if len(partes) < 2 or partes[0] != "content":
        print(f"[erro] --target precisa começar com /content/<site>/...: {target_root}",
              file=sys.stderr)
        sys.exit(1)
    site_prefix = f"/content/{partes[1]}"

    if args.gwi_root:
        gwi_root = args.gwi_root.rstrip("/")
    else:
        gwi_root = GWI_PREFIX_PADRAO + target_root[len(site_prefix):]

    allow_extra = ()
    if args.permitir_escrita_global2:
        liberado = args.permitir_escrita_global2.rstrip("/")
        if liberado != target_root:
            print(f"[erro] --permitir-escrita-global2 não bate com --target:\n"
                  f"  liberado: {liberado}\n  target:   {target_root}", file=sys.stderr)
            sys.exit(1)
        allow_extra = (liberado,)
    else:
        assert_target_is_safe(target_root)

    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    print_header("CONFERÊNCIA FINAL DE SEO (Page Properties)")
    print(f"  Destino: {target_root}")
    print(f"  Origem:  {gwi_root}   (somente leitura, referência)")
    print(f"  Corrige: jcr:description (do GWI), cq:canonicalUrl (derivado do "
          f"caminho), businessCategories/manufacturer (do GWI, só se vazios)")
    print(f"  Reporta (não corrige): jcr:title/pageTitle/navTitle vazios")
    if allow_extra:
        print(f"  *** ESCRITA EM MACNICAGLOBAL2 LIBERADA (exceção pontual): "
              f"{allow_extra[0]} ***")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada será escrito ***")
    print()

    print(f"== Percorrendo {target_root} ==")
    inventory = crawl_tree(session, base_url, target_root, auth_tracker,
                           max_pages=args.max_pages, delay=args.delay, only_pages=True)
    paginas = sorted(p for p, m in inventory.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")
    if not paginas:
        print(f"[erro] nenhuma página em {target_root}.", file=sys.stderr)
        sys.exit(1)

    resultados = []
    cache_irmaos = {}
    print(f"== Processando {len(paginas)} páginas ==")

    for i, path in enumerate(paginas, 1):
        if session_expired(auth_tracker):
            print(f"\n  [erro] sessão expirou — {i-1}/{len(paginas)} processadas.",
                  file=sys.stderr)
            for resto in paginas[i-1:]:
                resultados.append({"pagina": resto, "status": "NÃO TENTADO (sessão expirou)"})
            break

        linha = {"pagina": path, "origem_gwi": "", "description": "", "canonical": "",
                 "business_categories": "", "manufacturer": "", "pendencias_basic": "",
                 "status": ""}

        data, status = fetch_with_depth_fallback(session, base_url, path,
                                                 args.source_depth, auth_tracker)
        if data is None:
            linha["status"] = f"ERRO ao ler ({status})"
            resultados.append(linha)
            continue

        jcr = data.get("jcr:content", {}) or {}
        payload = {}

        # --- Basic: só reporta o que falta, não corrige aqui ---
        faltando_basic = [c for c in ("jcr:title", "pageTitle", "navTitle")
                          if not (jcr.get(c) or "").strip()]
        if faltando_basic:
            linha["pendencias_basic"] = ", ".join(faltando_basic)

        # --- Canonical URL: sempre derivável, não depende do GWI ---
        canonical_esperado = path
        if jcr.get("cq:canonicalUrl") != canonical_esperado:
            payload["jcr:content/cq:canonicalUrl"] = canonical_esperado
            linha["canonical"] = "corrigido"

        # --- Origem no GWI, para description/business/manufacturer ---
        gwi_path, gwi_data = achar_origem_gwi_generico(
            session, base_url, path, target_root, gwi_root, auth_tracker, cache_irmaos)
        if gwi_data is not None:
            linha["origem_gwi"] = gwi_path
            gwi_full, _ = fetch_with_depth_fallback(session, base_url, gwi_path,
                                                    args.source_depth, auth_tracker)
            gwi_jcr = (gwi_full or {}).get("jcr:content", {}) or {}

            if not (jcr.get("jcr:description") or "").strip():
                descricao_gwi = gwi_jcr.get("jcr:description", "")
                if descricao_gwi:
                    payload["jcr:content/jcr:description"] = descricao_gwi
                    linha["description"] = "copiado do GWI"
                else:
                    # GWI também não tem — fallback: extrai do 1º
                    # parágrafo da própria página já migrada.
                    extraida = achar_description_no_conteudo(jcr)
                    if extraida:
                        payload["jcr:content/jcr:description"] = extraida
                        linha["description"] = "extraído do 1º parágrafo"

            if not jcr.get("businessCategories"):
                bc_gwi = gwi_jcr.get("businessCategories")
                if bc_gwi:
                    payload["jcr:content/businessCategories"] = bc_gwi
                    payload["jcr:content/businessCategories@TypeHint"] = "String[]"
                    linha["business_categories"] = "copiado do GWI"

            if not (jcr.get("manufacturer") or "").strip():
                man_gwi = gwi_jcr.get("manufacturer")
                if man_gwi:
                    payload["jcr:content/manufacturer"] = man_gwi
                    linha["manufacturer"] = "copiado do GWI"
        else:
            linha["origem_gwi"] = "(não encontrada no GWI)"
            # Sem GWI nenhum pra comparar, mas ainda dá pra tentar o
            # fallback do próprio conteúdo pra description.
            if not (jcr.get("jcr:description") or "").strip():
                extraida = achar_description_no_conteudo(jcr)
                if extraida:
                    payload["jcr:content/jcr:description"] = extraida
                    linha["description"] = "extraído do 1º parágrafo"

        if not payload:
            linha["status"] = "OK (já correto)"
            resultados.append(linha)
            if i % 20 == 0 or i <= 5:
                print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")
            continue

        if args.dry_run:
            linha["status"] = "DRY-RUN"
        else:
            st, resposta = post_node(session, base_url, path, payload, auth_tracker,
                                     allow_extra=allow_extra)
            if st not in (200, 201):
                linha["status"] = f"ERRO ao escrever ({st}): {resposta[:120]}"
                resultados.append(linha)
                continue
            linha["status"] = "OK"

        resultados.append(linha)
        if i % 20 == 0 or i <= 5 or "ERRO" in linha["status"]:
            print(f"  [{i}/{len(paginas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")

    write_csv(args.output,
              ["pagina", "origem_gwi", "description", "canonical", "business_categories",
               "manufacturer", "pendencias_basic", "status"],
              resultados)

    ok = sum(1 for r in resultados if r["status"] in ("OK", "DRY-RUN", "OK (já correto)"))
    erros = [r for r in resultados if "ERRO" in r["status"]]
    com_pendencia_basic = [r for r in resultados if r["pendencias_basic"]]
    sem_origem = [r for r in resultados if r["origem_gwi"] == "(não encontrada no GWI)"]

    print()
    print_header("RESUMO")
    print(f"  Páginas processadas: {len(resultados)}")
    print(f"    ok:                {ok}")
    print(f"    description corrigida:  {sum(1 for r in resultados if r['description'])}")
    print(f"    canonical corrigido:    {sum(1 for r in resultados if r['canonical'])}")
    print(f"    business_categories:    {sum(1 for r in resultados if r['business_categories'])}")
    print(f"    manufacturer:           {sum(1 for r in resultados if r['manufacturer'])}")
    print(f"    pendências Basic (não corrigidas): {len(com_pendencia_basic)}")
    print(f"    sem origem no GWI:      {len(sem_origem)}")
    print(f"    erros:                  {len(erros)}")

    if com_pendencia_basic:
        print(f"\n  --- {len(com_pendencia_basic)} página(s) com Basic incompleto ---")
        for r in com_pendencia_basic[:10]:
            print(f"        {r['pagina'].rsplit('/', 1)[-1]}: {r['pendencias_basic']}")

    print(f"\n  Relatório: {args.output}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada foi escrito. Confira o CSV e rode sem --dry-run. ***")


if __name__ == "__main__":
    main()
