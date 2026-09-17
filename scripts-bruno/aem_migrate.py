#!/usr/bin/env python3
"""
Motor de migração: cria páginas e migra conteúdo de qualquer árvore.

Absorve o que antes eram 4 scripts separados (criar páginas, migrar
conteúdo, clonar corrigindo template, clonar em lote), porque são a
mesma operação com origens diferentes.

TRÊS MODOS:

  1. completo (padrão) — lê do GWI, traduz o vocabulário de componentes
     para o do GLOBAL2, cria a página e já popula o conteúdo.

  2. --so-estrutura — cria só o esqueleto (título + nome + template),
     sem conteúdo. Útil para validar a árvore antes de migrar.

  3. --modo-clone — a origem já usa componentes do GLOBAL2, então copia
     fielmente (sem tradução) e troca só o cq:template. Para páginas com
     conteúdo certo mas template errado.

ESTRUTURA DE CONTAINERS (confirmado com o Bruno): cada bloco de conteúdo
ganha o SEU próprio container, dentro de um container pai único. Nunca
tudo solto lado a lado.

REESCRITA DE LINKS (confirmado com o Bruno): links internos têm só o
prefixo do site trocado, o resto do caminho continua igual:
    /content/macnicagwi/americas/mai/en/x
 -> /content/macnicaglobal2/americas/mai/en/x
Aponta para o destino FINAL (macnicaglobal2), não para copia-teste, para
as páginas já nascerem com os links definitivos. Desligue com
--sem-reescrever-links ou mude o alvo com --link-para.

SEGURANÇA: só escreve dentro de copia-teste. Toda escrita passa pela
trava assert_target_is_safe(). macnicagwi e macnicaglobal2 são SOMENTE
LEITURA.

COMO RODAR:
  # 1. SEMPRE simular primeiro:
  python3 aem_migrate.py --source /content/macnicagwi/americas/mai/en/products/semiconductors --dry-run

  # 2. Conferir o CSV e o relatório de pendências, e então rodar de verdade:
  python3 aem_migrate.py --source /content/macnicagwi/americas/mai/en/products/semiconductors

  # Só a estrutura, sem conteúdo:
  python3 aem_migrate.py --source /content/macnicagwi/.../tq-systems --so-estrutura

  # Clonar do GLOBAL2 corrigindo o template:
  python3 aem_migrate.py --source /content/macnicaglobal2/.../tq-systems --modo-clone
"""

import argparse
import sys
import time
from collections import Counter

from aem_lib import (
    CONFIG, add_common_args, auditar_migracao, build_clone_payload,
    build_content_payload, build_page_payload, build_pd_props, build_seo_props,
    build_session, build_tag_props, crawl_tree, detect_tag_region, extract_content,
    fetch_with_depth_fallback, load_tag_taxonomy, normalize_path, post_node,
    print_header, resolve_template, rewrite_links_in_html, session_expired,
    write_csv,
)


def montar_mapeamento(inventory, source_root, target_root, skip_contains=()):
    """Origem -> destino, com cada segmento do caminho normalizado.

    Ordenado por profundidade: pais antes de filhos, senão o AEM recusa
    criar uma página cujo pai ainda não existe.
    """
    mapping = []
    for source_path in sorted(inventory.keys()):
        if any(p in source_path for p in skip_contains):
            continue
        mapping.append({
            "source_path": source_path,
            "dest_path": normalize_path(source_path, source_root, target_root),
            "title": inventory[source_path]["title"],
            "depth": inventory[source_path]["depth"],
        })
    # Ordem determinística: profundidade primeiro (pais antes de filhos,
    # senão o AEM recusa criar página órfã), caminho como desempate. Sem
    # o desempate, a fatia N poderia conter páginas diferentes entre
    # execuções e --inicio/--limite ficariam sem sentido.
    mapping.sort(key=lambda m: (m["depth"], m["source_path"]))
    return mapping


def main():
    parser = argparse.ArgumentParser(
        description="Cria páginas e migra conteúdo de uma árvore do AEM")

    parser.add_argument("--source", required=True,
                        help="Caminho raiz de origem. Ex: /content/macnicagwi/.../semiconductors")
    parser.add_argument("--target", default=None,
                        help="Caminho raiz de destino. Padrão: espelha a origem dentro "
                             "de copia-teste, preservando a estrutura depois do prefixo.")
    add_common_args(parser)

    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--so-estrutura", action="store_true",
                      help="Cria só página + título + nome + template, sem conteúdo.")
    modo.add_argument("--modo-clone", action="store_true",
                      help="Origem já usa componentes do GLOBAL2: copia fielmente e "
                           "troca só o template, sem traduzir vocabulário.")

    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sem escrever nada. RODE SEMPRE ANTES.")
    parser.add_argument("--template-title", default=CONFIG["template_title"],
                        help="Título do template a usar (buscado em /conf).")
    parser.add_argument("--template-path", default=None,
                        help="Caminho técnico do template, se já souber (pula a busca).")
    parser.add_argument("--templates-root", default=CONFIG["templates_root"])
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--skip-path-contains", action="append", default=None,
                        help="Ignora caminhos contendo este texto (pode repetir).")
    parser.add_argument("--inicio", type=int, default=0,
                        help="Processa a partir desta posição da lista de páginas "
                             "(0 = do começo). Para árvores grandes, permite rodar "
                             "em fatias sem perder o já feito.")
    parser.add_argument("--limite", type=int, default=None,
                        help="Processa no máximo esta quantidade de páginas a partir "
                             "de --inicio. Use com --inicio para fatiar.")

    parser.add_argument("--sem-reescrever-links", action="store_true",
                        help="Mantém os links apontando para o caminho original.")
    parser.add_argument("--link-de", default=CONFIG["gwi_prefix"],
                        help="Prefixo a substituir nos links internos.")
    parser.add_argument("--link-para", default=CONFIG["global2_prefix"],
                        help="Prefixo novo dos links internos. Padrão: o destino final "
                             "(macnicaglobal2), não copia-teste.")
    # Diretriz do cliente: "Enable/select hide in Navigation for ALL pages"
    # — é regra, não opção, então vem ligado. --sem-hide-in-nav desliga.
    parser.add_argument("--hide-in-nav", action="store_true", default=True,
                        help=argparse.SUPPRESS)
    parser.add_argument("--sem-hide-in-nav", dest="hide_in_nav", action="store_false",
                        help="NÃO marca 'Hide in Navigation'. Por padrão é marcado em "
                             "todas as páginas, por diretriz do cliente.")
    parser.add_argument("--sem-bloco-titulo", action="store_true",
                        help="Não cria o componente de título no topo do conteúdo.")
    parser.add_argument("--sem-tags", action="store_true",
                        help="Não copia/corrige as tags de taxonomia (manufacturer, "
                             "businessCategories etc.) — só o conteúdo.")
    parser.add_argument("--sem-seo", action="store_true",
                        help="Não copia o SEO curado da origem (pageTitle, navTitle, "
                             "keywords); usa o título da página neles.")

    parser.add_argument("--output", default=None,
                        help="CSV de saída. Padrão: migracao_<ultimo-segmento>.csv")
    parser.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO",
                        help="Exceção pontual à trava de macnicaglobal2 (SOMENTE "
                             "LEITURA por padrão). Passe o --target EXATO que você "
                             "quer liberar — se não bater com --target, a exceção não "
                             "vale e a escrita é abortada. Só use com aprovação "
                             "explícita para o caminho específico.")
    args = parser.parse_args()

    source_root = args.source.rstrip("/")
    if not source_root.startswith("/"):
        print(f"[erro] --source precisa ser um caminho absoluto: {source_root}",
              file=sys.stderr)
        sys.exit(1)

    # Destino: espelha a origem dentro de copia-teste.
    if args.target:
        target_root = args.target.rstrip("/")
    else:
        for prefixo in (CONFIG["gwi_prefix"], CONFIG["global2_prefix"]):
            if source_root.startswith(prefixo):
                target_root = CONFIG["target_prefix"] + source_root[len(prefixo):]
                break
        else:
            print(f"[erro] não sei derivar o destino de {source_root}.\n"
                  f"  A origem não começa com {CONFIG['gwi_prefix']} nem "
                  f"{CONFIG['global2_prefix']}.\n"
                  f"  Passe --target explicitamente.", file=sys.stderr)
            sys.exit(1)

    # Exceção pontual à trava de macnicaglobal2: só vale se o caminho
    # liberado bater EXATO com o --target desta execução — não dá pra
    # passar um caminho e escrever em outro.
    allow_extra = ()
    if args.permitir_escrita_global2:
        liberado = args.permitir_escrita_global2.rstrip("/")
        if liberado != target_root:
            print(f"[erro] --permitir-escrita-global2 não bate com --target:\n"
                  f"  liberado: {liberado}\n"
                  f"  target:   {target_root}", file=sys.stderr)
            sys.exit(1)
        allow_extra = (liberado,)

    skip = args.skip_path_contains if args.skip_path_contains is not None \
        else CONFIG["skip_path_contains"]
    output = args.output or f"migracao_{source_root.rsplit('/', 1)[-1]}.csv"
    reescrever = not args.sem_reescrever_links

    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    modo_label = ("estrutura (sem conteúdo)" if args.so_estrutura
                  else "clone fiel (troca só o template)" if args.modo_clone
                  else "completo (cria + migra conteúdo)")

    print_header("MIGRAÇÃO")
    print(f"  Modo:     {modo_label}")
    print(f"  Origem:   {source_root}   (somente leitura)")
    print(f"  Destino:  {target_root}")
    if not args.so_estrutura:
        print(f"  Links:    " + (f"{args.link_de} -> {args.link_para}" if reescrever
                                 else "mantidos como estão"))
    print(f"  Hide in Nav: {'sim' if args.hide_in_nav else 'NÃO (--sem-hide-in-nav)'}")
    if allow_extra:
        print(f"  *** ESCRITA EM MACNICAGLOBAL2 LIBERADA (exceção pontual): "
              f"{allow_extra[0]} ***")
    if not args.so_estrutura and not args.modo_clone:
        print(f"  SEO:      " + ("pageTitle/navTitle/keywords copiados da origem"
                                 if not args.sem_seo else "NÃO copiado (--sem-seo)"))
    if skip:
        print(f"  Ignorando: {', '.join(skip)}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada será escrito ***")
    print()

    # --- 1. Template ---
    template_path = resolve_template(session, base_url, args, auth_tracker)

    # --- 1b. Taxonomia de tags (mai:/macnica-atd-europe:) ---
    # Só faz sentido no modo completo (extract_content lê o jcr:content de
    # origem); estrutura e clone não passam por aqui.
    aplicar_tags = not args.so_estrutura and not args.modo_clone and not args.sem_tags
    tag_taxonomy = load_tag_taxonomy(session, base_url, auth_tracker) if aplicar_tags else None
    tag_region = detect_tag_region(source_root) if aplicar_tags else None
    if aplicar_tags:
        print(f"  Tags:     região '{tag_region}' "
              f"({'mai:' if tag_region == 'americas' else 'macnica-atd-europe:'})")

    # --- 2. Árvore de origem ---
    print(f"== Percorrendo {source_root} ==")
    inventory = crawl_tree(session, base_url, source_root, auth_tracker,
                           max_pages=args.max_pages, delay=args.delay,
                           skip_contains=skip)
    if not inventory:
        print(f"\n[erro] nenhuma página encontrada em {source_root}.", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(inventory)} nós encontrados\n")

    mapping = montar_mapeamento(inventory, source_root, target_root, skip)
    total_arvore = len(mapping)

    # Fatiamento: permite rodar árvores grandes em pedaços, sem perder o
    # progresso se a sessão expirar ou o processo for interrompido.
    # O mapping é sempre ordenado igual (por profundidade, depois caminho),
    # então a fatia N é estável entre execuções.
    if args.inicio or args.limite:
        fim = args.inicio + args.limite if args.limite else len(mapping)
        mapping = mapping[args.inicio:fim]
        print(f"== Fatia: páginas {args.inicio} a {args.inicio + len(mapping) - 1} "
              f"de {total_arvore} ==")

    print(f"== Processando {len(mapping)} páginas ==")

    # --- 3. Processar ---
    resultados = []
    totais = Counter()
    pendencias = Counter()
    ef_unicos = {}
    tipos_desconhecidos = {}
    imagens_quebradas = []
    tags_invalidas = []
    # Conferência de cobertura: quanto do conteúdo da origem chegou ao
    # destino. 'incompletas' lista as páginas que não bateram 100%.
    total_auditoria = {"origem": 0, "migrado": 0, "nao_migravel": 0}
    incompletas = []

    for i, m in enumerate(mapping, 1):
        if session_expired(auth_tracker):
            print(f"\n  [erro] sessão expirou — {i - 1}/{len(mapping)} processadas.",
                  file=sys.stderr)
            for resto in mapping[i - 1:]:
                resultados.append({**resto, "blocos": "", "pendencias": "",
                                   "status": "NÃO TENTADO (sessão expirou)"})
            break

        # --- Estrutura: não precisa ler o conteúdo da origem ---
        if args.so_estrutura:
            payload = build_page_payload(m["title"], template_path,
                                         hide_in_nav=args.hide_in_nav)
            contagens, skipped = {}, []
        else:
            source_data, status = fetch_with_depth_fallback(
                session, base_url, m["source_path"], args.source_depth, auth_tracker)
            if source_data is None:
                resultados.append({**m, "blocos": "", "pendencias": "",
                                   "status": f"ERRO ao ler origem ({status})"})
                continue

            if args.modo_clone:
                payload = build_clone_payload(source_data, template_path)
                contagens, skipped = {}, []
            else:
                jcr_content = source_data.get("jcr:content", {}) or {}
                titulo = jcr_content.get("jcr:title") or m["title"]
                descricao = jcr_content.get("jcr:description", "")
                componentes, skipped = extract_content(jcr_content)

                tag_props = {}
                if aplicar_tags:
                    tag_props, tag_skipped = build_tag_props(
                        jcr_content.get("sling:resourceType", ""), jcr_content,
                        tag_region, tag_taxonomy)
                    skipped = skipped + tag_skipped

                # SEO curado da origem (pageTitle/navTitle/keywords) —
                # diretriz do cliente item 2. Sem isso, o título da página
                # sobrescreveria valores curados em 100% dos casos.
                seo = {} if args.sem_seo else build_seo_props(jcr_content)

                payload, contagens = build_content_payload(
                    titulo, componentes, template_path, description=descricao,
                    hide_in_nav=args.hide_in_nav, rewrite_links=reescrever,
                    from_prefix=args.link_de, to_prefix=args.link_para,
                    title_block=not args.sem_bloco_titulo, seo_props=seo,
                )
                if seo:
                    contagens["seo"] = len(seo)
                for prop, valor in tag_props.items():
                    payload[f"jcr:content/{prop}"] = valor
                if tag_props:
                    contagens["tags"] = len(tag_props)

                # Campos "Product Details" (pd_*) — derivados do que já
                # foi migrado, sem propriedade nova do GWI. Só nas mesmas
                # páginas que recebem tags dedicadas (aplicar_tags), já
                # que pd_* é parte do mesmo bloco de Product Hierarchy
                # Details confirmado com o Bruno.
                if aplicar_tags and tag_props:
                    nome_pagina = m["dest_path"].rsplit("/", 1)[-1]
                    # slug do fabricante a partir da tag já migrada
                    # (mai:manufacturers/sony -> 'sony'), pra saber que
                    # prefixo tirar do nome do nó em pd_modelName.
                    fabricante = tag_props.get("manufacturer", "")
                    fabricante_slug = fabricante.rsplit("/", 1)[-1] if fabricante else None
                    pd_props = build_pd_props(jcr_content, nome_pagina, fabricante_slug)
                    if descricao:
                        # pd_description passa pela MESMA reescrita de
                        # links que a description normal, pra não deixar
                        # um dos dois apontando pro GWI.
                        pd_props["pd_description"] = rewrite_links_in_html(
                            descricao, args.link_de, args.link_para) \
                            if reescrever else descricao
                    for prop, valor in pd_props.items():
                        payload[f"jcr:content/{prop}"] = valor
                    if pd_props:
                        contagens["pd"] = len(pd_props)

                # Conferência: quanto do conteúdo da ORIGEM foi migrado.
                auditoria = auditar_migracao(
                    jcr_content, contagens,
                    title_block=not args.sem_bloco_titulo,
                    tem_descricao=bool(descricao))
                m["pct_conteudo"] = auditoria["pct"]
                m["conteudo_origem"] = auditoria["total_origem"]
                m["conteudo_migrado"] = auditoria["total_migrado"]
                total_auditoria["origem"] += auditoria["total_origem"]
                total_auditoria["migrado"] += auditoria["total_migrado"]
                total_auditoria["nao_migravel"] += auditoria["nao_migravel"]
                if not auditoria["completo"]:
                    incompletas.append({
                        "pagina": m["source_path"],
                        "pct": auditoria["pct"],
                        "origem": auditoria["total_origem"],
                        "migrado": auditoria["total_migrado"],
                        "faltando": "; ".join(
                            f"{t}: {v['origem']}->{v['migrado']}"
                            for t, v in auditoria["detalhe"].items()
                            if v["migrado"] < v["origem"]),
                    })

        totais.update(contagens)

        # Agrupa pendências para os relatórios separados
        for s in skipped:
            pendencias[s["categoria"]] += 1
            if s["categoria"] in ("experience_fragment", "related_suggestions"):
                chave = s.get("ref") or s["resourceType"]
                entrada = ef_unicos.setdefault(
                    chave, {"paginas": set(), "categoria": s["categoria"],
                            "motivo": s["motivo"]})
                entrada["paginas"].add(m["source_path"])
            elif s["categoria"] == "tipo_nao_reconhecido":
                entrada = tipos_desconhecidos.setdefault(
                    s["resourceType"], {"count": 0, "exemplo": m["source_path"]})
                entrada["count"] += 1
            elif s["categoria"] == "imagem_quebrada":
                imagens_quebradas.append({"pagina": m["source_path"],
                                          "componente": s["path"]})
            elif s["categoria"] == "tag_invalida":
                tags_invalidas.append({"pagina": m["source_path"],
                                       "propriedade": s["path"], "motivo": s["motivo"]})

        # --- Escrita ---
        if args.dry_run:
            status_label = "DRY-RUN"
        else:
            status, resposta = post_node(session, base_url, m["dest_path"],
                                         payload, auth_tracker,
                                         allow_extra=allow_extra)
            status_label = "OK" if status in (200, 201) else f"ERRO {status}"
            if status not in (200, 201):
                print(f"      resposta: {resposta}")
            time.sleep(CONFIG["write_delay"])

        total_blocos = sum(contagens.values())
        resultados.append({**m, "blocos": total_blocos,
                           "pendencias": len(skipped), "status": status_label})

        if i % 25 == 0 or i <= 5 or "ERRO" in status_label:
            detalhe = (f"{total_blocos} blocos, {len(skipped)} pendências"
                       if not args.so_estrutura else "estrutura")
            print(f"  [{i}/{len(mapping)}] {m['dest_path']} -> {detalhe} -> {status_label}")

    # --- 4. Relatórios ---
    write_csv(output,
              ["source_path", "dest_path", "title", "depth", "blocos",
               "pendencias", "conteudo_origem", "conteudo_migrado",
               "pct_conteudo", "status"],
              resultados)

    base_nome = output.replace(".csv", "")
    if ef_unicos:
        write_csv(f"{base_nome}_pendencias_referencias.csv",
                  ["referencia", "categoria", "qtd_paginas", "motivo", "paginas"],
                  [{"referencia": ref, "categoria": v["categoria"],
                    "qtd_paginas": len(v["paginas"]), "motivo": v["motivo"],
                    "paginas": "; ".join(sorted(v["paginas"]))}
                   for ref, v in sorted(ef_unicos.items(),
                                        key=lambda x: -len(x[1]["paginas"]))])
    if tipos_desconhecidos:
        write_csv(f"{base_nome}_tipos_desconhecidos.csv",
                  ["resourceType", "qtd_ocorrencias", "exemplo_pagina"],
                  [{"resourceType": rt, "qtd_ocorrencias": v["count"],
                    "exemplo_pagina": v["exemplo"]}
                   for rt, v in sorted(tipos_desconhecidos.items(),
                                       key=lambda x: -x[1]["count"])])
    if imagens_quebradas:
        write_csv(f"{base_nome}_imagens_quebradas.csv",
                  ["pagina", "componente"], imagens_quebradas)
    if tags_invalidas:
        write_csv(f"{base_nome}_tags_invalidas.csv",
                  ["pagina", "propriedade", "motivo"], tags_invalidas)

    # --- 5. Resumo ---
    ok = sum(1 for r in resultados if r["status"] in ("OK", "DRY-RUN"))
    migrados = sum(totais.values())
    total_pendencias = sum(pendencias.values())
    universo = migrados + total_pendencias
    pct = round(100 * migrados / universo) if universo else 0

    print()
    print_header("RESUMO")
    print(f"  Páginas processadas: {len(resultados)}  ({ok} com sucesso)")

    if totais:
        print(f"\n  Blocos migrados ({migrados}):")
        for kind, n in totais.most_common():
            print(f"    {n:5d}  {kind}")

    if pendencias:
        print(f"\n  Pendências ({total_pendencias}):")
        for cat, n in pendencias.most_common():
            print(f"    {n:5d}  {cat}")

    if universo:
        print(f"\n  >>> Taxa de automação: ~{pct}% <<<")
        print(f"      ({migrados} blocos migrados de {universo} encontrados)")

    # --- Conferência de cobertura do conteúdo ---
    if total_auditoria["origem"]:
        cobertura = round(100 * total_auditoria["migrado"]
                          / total_auditoria["origem"], 1)
        print()
        print(f"  >>> COBERTURA DO CONTEÚDO: {cobertura}% <<<")
        print(f"      {total_auditoria['migrado']} de {total_auditoria['origem']} "
              f"blocos de conteúdo da origem chegaram ao destino")
        if total_auditoria["nao_migravel"]:
            print(f"      (+ {total_auditoria['nao_migravel']} bloco(s) sem "
                  f"equivalente conhecido, fora da conta)")
        if incompletas:
            write_csv(f"{base_nome}_cobertura_incompleta.csv",
                      ["pagina", "pct", "origem", "migrado", "faltando"],
                      incompletas)
            print(f"\n      {len(incompletas)} página(s) abaixo de 100%:")
            print(f"      {base_nome}_cobertura_incompleta.csv")
            for item in sorted(incompletas, key=lambda x: x["pct"])[:8]:
                print(f"        {item['pct']:5.1f}%  {item['pagina'].rsplit('/', 1)[-1]}"
                      f"  ({item['faltando']})")
        else:
            print(f"      ✓ TODAS as páginas com 100% do conteúdo migrado")

    print(f"\n  Relatório principal: {output}")

    if ef_unicos:
        print(f"\n  --- {len(ef_unicos)} referência(s) única(s) pendente(s) ---")
        print(f"      {base_nome}_pendencias_referencias.csv")
        for ref, v in sorted(ef_unicos.items(), key=lambda x: -len(x[1]["paginas"]))[:8]:
            print(f"      [{len(v['paginas'])}x] {ref or '(sem ref)'}")

    if tipos_desconhecidos:
        print(f"\n  --- {len(tipos_desconhecidos)} tipo(s) de componente não tratado(s) ---")
        print(f"      {base_nome}_tipos_desconhecidos.csv")
        print(f"      Diga quais desses você quer que eu passe a tratar.")
        for rt, v in sorted(tipos_desconhecidos.items(), key=lambda x: -x[1]["count"])[:8]:
            print(f"      [{v['count']}x] {rt}")

    if imagens_quebradas:
        print(f"\n  --- {len(imagens_quebradas)} imagem(ns)/download(s) quebrado(s) na ORIGEM ---")
        print(f"      {base_nome}_imagens_quebradas.csv")
        print(f"      Já estavam quebrados no GWI — não é problema do script.")

    if tags_invalidas:
        print(f"\n  --- {len(tags_invalidas)} tag(s) inválida(s), omitida(s) na ORIGEM ---")
        print(f"      {base_nome}_tags_invalidas.csv")
        print(f"      Não bateram com a taxonomia real depois da correção mecânica —")
        print(f"      omitidas em vez de inventadas. Decisão humana (criar tag ou não).")

    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada foi escrito. Confira o CSV e rode sem --dry-run. ***")
    elif ok and not args.so_estrutura:
        print(f"\n  Confira visualmente algumas páginas no editor antes de confiar no lote.")
        print(f"  Em especial: 'navTitle' e o componente 'download' seguem por convenção,")
        print(f"  sem exemplo autoral real confirmando as propriedades.")


if __name__ == "__main__":
    main()
