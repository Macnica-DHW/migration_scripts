#!/usr/bin/env python3
"""
Aplica 5 regras de layout nas páginas-NETA (produtos individuais) de
tq-systems, já migradas em copia-teste. Não mexe nas páginas de
categoria (tq-embedded-arm-modules etc) nem na raiz tq-systems —
essas têm estrutura de listagem, diferente das de produto.

Confirmado com o Bruno em 16/09/2026, a partir da página de referência
.../tq-embedded-arm-modules/tqma64xxl-embedded-cortex-a53-module (ele
mesmo editou em 16/09, 10:36-10:38 UTC — é o padrão-alvo):

  1. TÍTULO    — o primeiro container da página é sempre o do título.
                 Se a página já tem um container só com o componente
                 'title' no início, ajusta o padding dele. Se NÃO tem
                 (74/139 casos: título vem embutido como <h1> dentro
                 do texto corrido, mesmo container do textwithimage),
                 CRIA um novo container no início com um componente
                 'title' vazio — vazio de propósito, sem jcr:title
                 nem type: o componente exibe automaticamente a
                 propriedade Title da página (confirmado comparando
                 com o title da página de referência, que também não
                 tem jcr:title próprio). O texto/h1 embutido no bloco
                 original NÃO é alterado.
                 Padding do container-título: T/B 'No Padding'
                 (1717498056876) + L/R 'Large' (1717498053499).

  2. BACKGROUND — todo container cujo título de seção (jcr:title de um
                 componente title dentro dele) for 'Ordering
                 Information' ou 'Specifications' recebe
                 backgroundColor = '#f7f7f7' (propriedade direta do
                 container, não é cq:styleIds — confirmado no exemplo
                 real). Comparação de título é case-insensitive.

  3. BOTÕES    — o último container da página deve ter um flexcontainer
                 com 2 flexcontaineritem, cada um com um componente
                 button: 'Sign up' (link constant contact) e
                 'Contact us' (link .../contact/form/), mesmos
                 cq:styleIds da referência. 138/139 páginas JÁ têm isso
                 — este script só CRIA do zero na(s) que não têm,
                 clonando a estrutura da página de referência. Não
                 sobrescreve um bloco de botões já existente mesmo que
                 os links sejam diferentes (não é conteúdo nosso pra
                 decidir).

  4. PENÚLTIMO — o container imediatamente ANTES do bloco de botões
                 recebe padding T/B 'No Padding' (1717498056876)
                 explícito, mantendo o L/R que já tinha.

  5. LAYOUT    — largura máxima: mesma correção do aem_fix_pages.py,
                 reaproveitada daqui (apaga cq:responsive estreito,
                 relendo cada bloco isolado com .infinity.json pra não
                 cair no bug de profundidade truncada).

NÃO MEXE em: conteúdo dos blocos (texto, imagens, tabelas), SEO, tags,
estrutura de 3→2 níveis (já corrigida antes) — só os 5 itens acima.

SEGURANÇA: só escreve dentro de copia-teste (assert_target_is_safe em
post_node). macnicagwi e macnicaglobal2 são SOMENTE LEITURA.

COMO RODAR:
  # 1. Sempre simular primeiro:
  python3 aem_fix_tq_layout.py --target /content/copia-teste/.../tq-systems --dry-run

  # 2. Conferir o CSV, então rodar de verdade:
  python3 aem_fix_tq_layout.py --target /content/copia-teste/.../tq-systems
"""

import argparse
import sys

from aem_lib import (
    CONFIG, add_common_args, build_session, crawl_tree,
    fetch_with_depth_fallback, list_child_nodes, post_node,
    print_header, session_expired, write_csv,
)
from aem_fix_pages import detectar_layout_estreito, ler_bloco_isolado

TQ_SYSTEMS_ROOT = "/content/copia-teste/americas/mai/en/products/boards-modules/tq-systems"

TITLE_RT = "macnicaglobal2/components/content/title"
CONTAINER_RT = "macnicaglobal2/components/content/container"
TEXT_RT = "macnicaglobal2/components/content/text"
BUTTON_RT = "macnicaglobal2/components/content/button"
FLEXCONTAINER_RT = "macnicaglobal2/components/content/flexcontainer"
FLEXCONTAINERITEM_RT = "macnicaglobal2/components/content/flexcontaineritem"

STYLE_PADDING_TOP_BOTTOM_NO_PADDING = "1717498056876"
STYLE_PADDING_LEFT_RIGHT_LARGE = "1717498053499"
STYLE_FLEX_GAP_NO_SPACING = "1718800458698"
STYLE_BUTTON_FIXED_MIN_WIDTH = "1722936853890"
STYLE_BUTTON_DISPLAY_CENTER = "1717669229626"

BACKGROUND_COLOR_SECTIONS = "#f7f7f7"
SECTION_TITLES_COM_BACKGROUND = {"ordering information", "specifications"}

# Bloco de botões clonado bit a bit da referência confirmada com o
# Bruno: .../tq-embedded-arm-modules/tqma64xxl-embedded-cortex-a53-module
# (container_746606129_), incluindo os textos de apoio de cada botão.
BOTOES_SIGN_UP_LINK = (
    "https://visitor.r20.constantcontact.com/manage/optin?v=001dwtC1_5l2X9"
    "5pEGF-tfajTnjuco352BxLxaAjPBvxZ5ajvboL3j82hAC5eShsFYX4Y8c7eb7Psk1Wt0l"
    "NdmFTyykwvu3nROM6dYUzZFUXPCW1dI_Zl0xB0K2b9h3AzAVkJ9SdocYJEjotB7mFAE2S"
    "bv_nGmDoHTm2i-E6X2JCP8ki47J_MKW8AXLzNumSzfSYiLtqpHza8sJthaI2rGXod-2Xd"
    "CthogWDb8BRgH4ZI1or8ZkCRV81nlRPueUwIlPyqAHAf_SvzE%3D"
)
BOTOES_CONTACT_US_LINK = "https://www.macnica.com/americas/mai/en/contact/form/"


def eh_container(node):
    return node.get("sling:resourceType") == CONTAINER_RT


def primeiro_filho_eh_title_puro(container_topo):
    """True se o container tiver como único filho de conteúdo um title."""
    filhos = [n for n, v in list_child_nodes(container_topo)
              if v.get("sling:resourceType") == TITLE_RT]
    outros = [n for n, v in list_child_nodes(container_topo)
              if v.get("sling:resourceType") not in (TITLE_RT,)]
    return len(filhos) >= 1 and not outros


def _titulo_bate_secao(titulo):
    """Compara por 'contém', não igualdade exata — achado real: 2/139
    páginas têm '- Ordering Information' (traço na frente) em vez do
    texto limpo. Comparar por igualdade exata deixava essas de fora.
    """
    t = titulo.strip().lower()
    return any(alvo in t for alvo in SECTION_TITLES_COM_BACKGROUND)


def achar_secoes_para_background(container_pai):
    """Acha, entre os blocos de topo, quais têm título de seção
    'Ordering Information'/'Specifications' em QUALQUER profundidade
    dentro do bloco — devolve lista de nomes de blocos de topo.
    Alguns blocos têm containers aninhados (achado real: bloco com
    texto + container + Specifications + Ordering Information juntos,
    não um bloco por seção), então a busca desce a árvore inteira.
    """
    achados = []
    for nome, node in list_child_nodes(container_pai):
        def tem_secao(n):
            for _, filho in list_child_nodes(n):
                if _titulo_bate_secao(filho.get("jcr:title") or ""):
                    return True
                if tem_secao(filho):
                    return True
            return False
        if tem_secao(node):
            achados.append(nome)
    return achados


def flexcontainer_tem_botoes(node):
    """True se node (ou algo dentro) for um flexcontainer com >=1 button."""
    for _, v in list_child_nodes(node):
        if v.get("sling:resourceType") == FLEXCONTAINER_RT:
            for _, item in list_child_nodes(v):
                for _, comp in list_child_nodes(item):
                    if comp.get("sling:resourceType") == BUTTON_RT:
                        return True
        if flexcontainer_tem_botoes(v):
            return True
    return False


def processar_pagina(session, base_url, path, source_depth, auth_tracker, dry_run):
    """Aplica as 5 regras numa página. Devolve dict de resultado p/ CSV."""
    linha = {
        "pagina": path, "titulo_criado": "", "titulo_padding": "",
        "background_secoes": "", "botoes_criados": "", "penultimo_padding": "",
        "layouts_corrigidos": 0, "status": "",
    }

    data, status = fetch_with_depth_fallback(session, base_url, path,
                                             source_depth, auth_tracker)
    if data is None:
        linha["status"] = f"ERRO ao ler ({status})"
        return linha

    jcr = data.get("jcr:content", {}) or {}
    container = (jcr.get("root", {}) or {}).get("container", {}) or {}
    blocos = list_child_nodes(container)
    if not blocos:
        linha["status"] = "SEM CONTEÚDO (fora do escopo deste script)"
        return linha

    payload = {}
    novo_titulo_nome = None  # se preenchido, precisa de POST de reordenação à parte

    # --- Regra 1: container de título no início ---
    primeiro_nome, primeiro_node = blocos[0]
    ja_eh_title = eh_container(primeiro_node) and primeiro_filho_eh_title_puro(primeiro_node)

    if ja_eh_title:
        atuais = primeiro_node.get("cq:styleIds") or []
        if isinstance(atuais, str):
            atuais = [atuais]
        alvo = {STYLE_PADDING_TOP_BOTTOM_NO_PADDING, STYLE_PADDING_LEFT_RIGHT_LARGE}
        if set(atuais) != alvo:
            base = f"jcr:content/root/container/{primeiro_nome}"
            payload[f"{base}/cq:styleIds"] = [STYLE_PADDING_TOP_BOTTOM_NO_PADDING,
                                              STYLE_PADDING_LEFT_RIGHT_LARGE]
            payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"
            linha["titulo_padding"] = "ajustado"
    else:
        # Cria um novo container ANTES do primeiro bloco existente. A
        # reordenação para o início não pode ir no mesmo POST da
        # criação — testado em 16/09/2026: '<nome>@Order' no payload de
        # criação dá 409 (repository state conflicting), e mesmo em
        # POST separado só funcionou com ':order' minúsculo, direto no
        # próprio nó, DEPOIS que ele já existe. '<nome>@Order' (com @)
        # nunca teve efeito, mesmo em requisição própria.
        novo_titulo_nome = "title_wrap_novo"
        base = f"jcr:content/root/container/{novo_titulo_nome}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = CONTAINER_RT
        payload[f"{base}/cq:styleIds"] = [STYLE_PADDING_TOP_BOTTOM_NO_PADDING,
                                          STYLE_PADDING_LEFT_RIGHT_LARGE]
        payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"
        payload[f"{base}/title/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/title/sling:resourceType"] = TITLE_RT
        # título vazio de propósito: exibe a propriedade Title da página
        linha["titulo_criado"] = novo_titulo_nome

    # --- Regra 2: background color em Ordering Information/Specifications ---
    secoes = achar_secoes_para_background(container)
    secoes_a_gravar = []
    for nome in secoes:
        atual = dict(container.get(nome, {})).get("backgroundColor")
        if atual != BACKGROUND_COLOR_SECTIONS:
            base = f"jcr:content/root/container/{nome}"
            payload[f"{base}/backgroundColor"] = BACKGROUND_COLOR_SECTIONS
            secoes_a_gravar.append(nome)
    if secoes_a_gravar:
        linha["background_secoes"] = ", ".join(secoes_a_gravar)

    # --- Regra 3: ÚLTIMO container sempre vira o bloco de botões ---
    # Confirmado com o Bruno em 16/09/2026: a 1ª rodada só criava
    # quando faltava — mas os botões que já existiam tinham
    # cq:styleIds incompletos (faltava '1717669229626', Display
    # Position Center; achado: 62/62 amostrados só tinham o de
    # Fixed Minimum Width). Correção: apaga o ÚLTIMO container da
    # página, sempre, e recria do zero clonado da referência — não
    # tenta reaproveitar/corrigir o que já está lá.
    nome_ultimo_atual, node_ultimo_atual = blocos[-1]
    apagar_ultimo_atual = nome_ultimo_atual  # delete_node feito após o POST

    ultimo_nome = "botoes_wrap_novo"
    base = f"jcr:content/root/container/{ultimo_nome}"
    payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{base}/sling:resourceType"] = CONTAINER_RT
    payload[f"{base}/cq:styleIds"] = [STYLE_PADDING_LEFT_RIGHT_LARGE]
    payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"

    fc = f"{base}/flexcontainer"
    payload[f"{fc}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{fc}/sling:resourceType"] = FLEXCONTAINER_RT
    payload[f"{fc}/cq:styleIds"] = STYLE_FLEX_GAP_NO_SPACING

    item1 = f"{fc}/flexcontaineritem"
    payload[f"{item1}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{item1}/sling:resourceType"] = FLEXCONTAINERITEM_RT
    payload[f"{item1}/text/jcr:primaryType"] = "nt:unstructured"
    payload[f"{item1}/text/sling:resourceType"] = TEXT_RT
    payload[f"{item1}/text/textIsRich"] = "true"
    payload[f"{item1}/text/text"] = ("<p><b>Stay up to date on the latest "
                                     "news from Macnica Partners.</b></p>")
    payload[f"{item1}/button/jcr:primaryType"] = "nt:unstructured"
    payload[f"{item1}/button/sling:resourceType"] = BUTTON_RT
    payload[f"{item1}/button/jcr:title"] = "Sign up"
    payload[f"{item1}/button/linkURL"] = BOTOES_SIGN_UP_LINK
    payload[f"{item1}/button/linkTarget"] = "_self"
    payload[f"{item1}/button/cq:styleIds"] = [STYLE_BUTTON_FIXED_MIN_WIDTH,
                                               STYLE_BUTTON_DISPLAY_CENTER]
    payload[f"{item1}/button/cq:styleIds@TypeHint"] = "String[]"

    item2 = f"{fc}/flexcontaineritem_novo"
    payload[f"{item2}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{item2}/sling:resourceType"] = FLEXCONTAINERITEM_RT
    payload[f"{item2}/text/jcr:primaryType"] = "nt:unstructured"
    payload[f"{item2}/text/sling:resourceType"] = TEXT_RT
    payload[f"{item2}/text/textIsRich"] = "true"
    payload[f"{item2}/text/text"] = "<p><b>For more information:</b></p>"
    payload[f"{item2}/button/jcr:primaryType"] = "nt:unstructured"
    payload[f"{item2}/button/sling:resourceType"] = BUTTON_RT
    payload[f"{item2}/button/jcr:title"] = "Contact us"
    payload[f"{item2}/button/linkURL"] = BOTOES_CONTACT_US_LINK
    payload[f"{item2}/button/linkTarget"] = "_self"
    payload[f"{item2}/button/cq:styleIds"] = [STYLE_BUTTON_FIXED_MIN_WIDTH,
                                               STYLE_BUTTON_DISPLAY_CENTER]
    payload[f"{item2}/button/cq:styleIds@TypeHint"] = "String[]"

    linha["botoes_criados"] = f"{ultimo_nome} (substituiu {nome_ultimo_atual})"

    # --- Regra 4: penúltimo container (o que sobra antes do bloco de
    # botões novo) sem padding T/B. Como o último SEMPRE é substituído
    # agora, o penúltimo é sempre blocos[-2] da leitura atual — a menos
    # que a página só tenha 1 bloco (aí não há penúltimo).
    if len(blocos) >= 2:
        nome_penultimo, node_penultimo = blocos[-2]
        if eh_container(node_penultimo):
            atuais = node_penultimo.get("cq:styleIds") or []
            if isinstance(atuais, str):
                atuais = [atuais]
            novos = list(atuais)
            if STYLE_PADDING_TOP_BOTTOM_NO_PADDING not in novos:
                novos.append(STYLE_PADDING_TOP_BOTTOM_NO_PADDING)
            if STYLE_PADDING_LEFT_RIGHT_LARGE not in novos:
                novos.append(STYLE_PADDING_LEFT_RIGHT_LARGE)
            if novos != list(atuais):
                base = f"jcr:content/root/container/{nome_penultimo}"
                payload[f"{base}/cq:styleIds"] = novos
                payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"
                linha["penultimo_padding"] = nome_penultimo

    # --- Regra 5: layout largura máxima (reaproveita aem_fix_pages) ---
    layouts_estreitos = []
    for nome_wrap, node_wrap in blocos:
        base = f"jcr:content/root/container/{nome_wrap}"
        caminho_real = f"{path}/{base}"
        fresco = ler_bloco_isolado(session, base_url, caminho_real, auth_tracker)
        no_para_checar = fresco if fresco is not None else node_wrap
        for caminho in detectar_layout_estreito(no_para_checar, base):
            layouts_estreitos.append(caminho)
    linha["layouts_corrigidos"] = len(layouts_estreitos)

    if not payload and not layouts_estreitos:
        linha["status"] = "OK (já correto)"
        return linha

    if dry_run:
        linha["status"] = "DRY-RUN"
        return linha

    if payload:
        st, resposta = post_node(session, base_url, path, payload, auth_tracker)
        if st not in (200, 201):
            linha["status"] = f"ERRO ao escrever ({st}): {resposta[:150]}"
            return linha

    if novo_titulo_nome:
        # Reordenação em POST próprio, direto no nó já criado — ver nota
        # acima sobre por que não dá pra fazer isso junto da criação.
        caminho_novo = (f"{path}/jcr:content/root/container/{novo_titulo_nome}")
        st_ordem, resp_ordem = post_node(session, base_url, caminho_novo,
                                         {":order": "first"}, auth_tracker)
        if st_ordem not in (200, 201):
            linha["status"] = (f"OK (título criado), mas ERRO ao reordenar "
                              f"({st_ordem}): {resp_ordem[:100]}")
            return linha

    from aem_lib import delete_node

    # Apaga o container antigo de botões DEPOIS do novo já existir —
    # nunca fica um instante sem nenhum bloco de botões na página. Só
    # apaga se o nome for diferente (não deleta o que acabamos de criar
    # por engano num eventual nome igual).
    if apagar_ultimo_atual != ultimo_nome:
        del_st, del_resp = delete_node(
            session, base_url,
            f"{path}/jcr:content/root/container/{apagar_ultimo_atual}", auth_tracker)
        if del_st not in (200, 204):
            linha["status"] = (f"OK (botões criados), mas ERRO ao apagar "
                              f"container antigo ({del_st}) — remover "
                              f"{apagar_ultimo_atual} manualmente")
            return linha

    erros_layout = []
    for caminho_relativo in layouts_estreitos:
        del_st, _ = delete_node(session, base_url, f"{path}/{caminho_relativo}",
                                auth_tracker)
        if del_st not in (200, 204):
            erros_layout.append(caminho_relativo)

    linha["status"] = "OK"
    if erros_layout:
        linha["status"] += f" | ERRO ao apagar layout: {', '.join(erros_layout)}"

    return linha


def main():
    parser = argparse.ArgumentParser(
        description="Aplica 5 regras de layout nas páginas-neta de tq-systems "
                    "(título, background de seções, botões, padding, largura máxima)")
    parser.add_argument("--target", required=True,
                        help="Raiz de tq-systems dentro de copia-teste.")
    add_common_args(parser)
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sem escrever nada. RODE SEMPRE ANTES.")
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--output", default="fix_tq_layout.csv")
    args = parser.parse_args()

    target_root = args.target.rstrip("/")
    if not target_root.startswith(CONFIG["target_prefix"]):
        print(f"[erro] --target precisa estar dentro de {CONFIG['target_prefix']}: "
              f"{target_root}", file=sys.stderr)
        sys.exit(1)

    session, auth_tracker = build_session(prompt_if_missing=not args.no_prompt)
    base_url = args.base_url.rstrip("/")

    print_header("TQ-SYSTEMS: TÍTULO, BACKGROUND, BOTÕES, PADDING, LAYOUT")
    print(f"  Destino: {target_root}")
    print(f"  Escopo: só páginas-NETA (categoria/produto) — sem categorias/raiz")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada será escrito ***")
    print()

    print(f"== Percorrendo {target_root} ==")
    inventory = crawl_tree(session, base_url, target_root, auth_tracker,
                           max_pages=args.max_pages, delay=args.delay, only_pages=True)
    todas = sorted(p for p, m in inventory.items() if m["is_page"])

    # Filtra só netas: dois segmentos depois da raiz de tq-systems
    # (categoria/produto) — ancorado em TQ_SYSTEMS_ROOT, não em
    # target_root, porque --target pode apontar para qualquer nível
    # (a raiz inteira, uma categoria, ou uma página-folha direta).
    netas = []
    for p in todas:
        rel = p[len(TQ_SYSTEMS_ROOT):].lstrip("/")
        partes = rel.split("/") if rel else []
        if len(partes) == 2:
            netas.append(p)
    print(f"  {len(todas)} páginas no total, {len(netas)} são netas (escopo)\n")
    if not netas:
        print(f"[erro] nenhuma página-neta em {target_root}.", file=sys.stderr)
        sys.exit(1)

    resultados = []
    print(f"== Processando {len(netas)} páginas ==")
    for i, path in enumerate(netas, 1):
        if session_expired(auth_tracker):
            print(f"\n  [erro] sessão expirou — {i-1}/{len(netas)} processadas.",
                  file=sys.stderr)
            for resto in netas[i-1:]:
                resultados.append({"pagina": resto, "status": "NÃO TENTADO (sessão expirou)"})
            break

        linha = processar_pagina(session, base_url, path, args.source_depth,
                                 auth_tracker, args.dry_run)
        resultados.append(linha)
        if i % 10 == 0 or i <= 5 or "ERRO" in linha["status"]:
            print(f"  [{i}/{len(netas)}] {path.rsplit('/',1)[-1]} -> {linha['status']}")

    write_csv(args.output,
              ["pagina", "titulo_criado", "titulo_padding", "background_secoes",
               "botoes_criados", "penultimo_padding", "layouts_corrigidos", "status"],
              resultados)

    ok = sum(1 for r in resultados if r["status"] in ("OK", "DRY-RUN", "OK (já correto)"))
    erros = [r for r in resultados if "ERRO" in r["status"]]

    print()
    print_header("RESUMO")
    print(f"  Páginas processadas:     {len(resultados)}")
    print(f"    ok:                    {ok}")
    print(f"    títulos criados:       {sum(1 for r in resultados if r['titulo_criado'])}")
    print(f"    títulos com padding ajustado: {sum(1 for r in resultados if r['titulo_padding'])}")
    print(f"    com background aplicado:     {sum(1 for r in resultados if r['background_secoes'])}")
    print(f"    blocos de botões criados:    {sum(1 for r in resultados if r['botoes_criados'])}")
    print(f"    penúltimo ajustado:          {sum(1 for r in resultados if r['penultimo_padding'])}")
    print(f"    layouts (largura) corrigidos: {sum(r['layouts_corrigidos'] for r in resultados)}")
    print(f"    erros:                 {len(erros)}")

    print(f"\n  Relatório: {args.output}")
    if args.dry_run:
        print(f"\n  *** DRY-RUN: nada foi escrito. Confira o CSV e rode sem --dry-run. ***")


if __name__ == "__main__":
    main()
