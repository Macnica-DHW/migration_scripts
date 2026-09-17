#!/usr/bin/env python3
"""
Compara o CONTEÚDO de páginas migradas com o da origem no GWI.
SOMENTE LEITURA.

Responde a pergunta que o aem_verify.py não responde: a página existe e
tem conteúdo, mas é o MESMO conteúdo da origem? Achou-se, em tq-systems,
página com dois blocos "Features" no GWI e só um no destino — o verify
dava a página como migrada, porque conteúdo havia.

POR QUE COMPARAR TEXTO, E NÃO COMPONENTES
O destino usa outro vocabulário de componentes (title, textwithimage,
flexcontainer...) e os scripts de layout de TQ ainda reorganizam blocos
de propósito — fundem containers, movem o H1 para dentro do
textwithimage. Contar componentes acusaria diferença em página correta.
Então este script ignora estrutura e compara o TEXTO VISÍVEL, extraído
por PROPRIEDADE (text, jcr:title, cq:panelTitle...), não por
sling:resourceType. Funciona igual nos dois lados.

COMO DECIDE SE UM BLOCO CHEGOU
Concatena todo o texto do destino numa string só e pergunta se o bloco
da origem está contido nela. Isso absorve fusão e quebra de blocos (o
caso comum depois dos fixes de layout). Se não estiver contido, calcula
que fração das palavras do bloco aparece no destino: acima do limiar
(--limiar, padrão 0.85) trata como reescrito, não perdido; abaixo,
reporta como AUSENTE.

O nome do nó no GWI costuma ter maiúsculas ('TQMa8MPxL-...') e o do
destino não. O casamento usa normalize_name() nos irmãos do GWI.

COMO RODAR
  python3 aem_diff_conteudo.py \
    --destino /content/macnicaglobal2/americas/mai/en/products/boards-modules/tq-systems \
    --origem  /content/macnicagwi/americas/mai/en/products/boards-modules/tq-systems

  # só as páginas com buraco, sem listar as OK
  python3 aem_diff_conteudo.py --destino ... --origem ... --so-problemas
"""

import argparse
import csv
import html as _html
import re
import sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from urllib.parse import urljoin
from aem_lib import (CONFIG, build_session, crawl_tree, fetch_with_depth_fallback,
                     get_json, list_child_nodes, normalize_name, print_header,
                     session_expired, write_csv)

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
PROPS_TEXTO = ("text", "jcr:title", "jcr:description", "cq:panelTitle", "title")
# Ruído que o template do destino injeta e que não existe na origem.
IGNORAR = {"sign up", "contact us", "read more", "learn more"}

# Blocos que os scripts de layout REMOVEM DE PROPÓSITO da página migrada.
# Sem esta lista o relatório vira ruído: o texto de apoio do bloco de
# botões (que o aem_tq_remove_button_text.py tira por decisão do cliente)
# aparecia como "faltando" em ~150 das 173 páginas de tq-systems,
# escondendo os poucos buracos de verdade. Comparar com --sem-filtro
# para ver tudo, inclusive o que foi removido intencionalmente.
BOILERPLATE = (
    "stay up to date on the latest news from macnica",
    "have a question for the macnica",
    "contact us for more information",
    "request a quote",
)


def eh_boilerplate(n):
    return any(b in n for b in BOILERPLATE)


def limpar(s):
    if not isinstance(s, str):
        return ""
    s = TAG_RE.sub(" ", s)
    s = _html.unescape(s).replace(" ", " ")
    return WS_RE.sub(" ", s).strip()


def extrair(jcr_content):
    """Texto visível e imagens de um jcr:content, olhando propriedades."""
    textos, imagens = [], set()

    def walk(node):
        for _, ch in list_child_nodes(node):
            for p in PROPS_TEXTO:
                v = ch.get(p)
                if isinstance(v, str):
                    orig = limpar(v)
                    n = orig.lower()
                    if len(n) > 2 and n not in IGNORAR:
                        textos.append((n, orig))
            fr = ch.get("fileReference")
            if isinstance(fr, str) and fr.strip():
                imagens.add(fr.rsplit("/", 1)[-1].lower())
            walk(ch)

    walk(jcr_content)
    return textos, imagens


def achar_origem(session, base_url, dst_path, dst_root, org_root, auth, cache):
    """Caminho equivalente no GWI, tolerando diferença de maiúsculas."""
    rel = dst_path[len(dst_root):].strip("/")
    if not rel:
        return org_root
    partes, atual = rel.split("/"), org_root
    for parte in partes:
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
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--profundidade", type=int, default=14)
    ap.add_argument("--limiar", type=float, default=0.85,
                    help="Cobertura de palavras acima da qual o bloco é dado "
                         "como reescrito, não perdido (padrão 0.85).")
    ap.add_argument("--so-problemas", action="store_true")
    ap.add_argument("--sem-filtro", action="store_true",
                    help="Não filtra o boilerplate removido de propósito "
                         "pelos scripts de layout (relatório cru).")
    ap.add_argument("--incluir-apagadas", action="store_true",
                    help="Audita também páginas com marcador soft-delete "
                         "(por padrão são puladas: são lixo de colisão).")
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    dst_root, org_root = args.destino.rstrip("/"), args.origem.rstrip("/")
    saida = args.output or f"diff_conteudo_{dst_root.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("DIFF DE CONTEÚDO (origem GWI x destino migrado)")
    print(f"  origem : {org_root}\n  destino: {dst_root}\n  limiar : {args.limiar}\n")

    inv = crawl_tree(s, base, dst_root, at, quiet=True)
    paginas = sorted((p for p, m in inv.items() if m["is_page"]),
                     key=lambda x: (x.count("/"), x))
    print(f"  {len(paginas)} páginas no destino\n")

    linhas, cache = [], {}
    sem_origem, com_falta, apagadas = [], [], []
    for i, dp in enumerate(paginas, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(paginas)}", file=sys.stderr)
            break
        if not args.incluir_apagadas:
            jc_d, _ = get_json(s, urljoin(base, f"{dp}/_jcr_content.json"), at)
            if (jc_d or {}).get("deleted"):
                apagadas.append(dp)
                continue

        gp = achar_origem(s, base, dp, dst_root, org_root, at, cache)
        if gp is None:
            sem_origem.append(dp)
            linhas.append({"pagina_destino": dp, "pagina_origem": "",
                           "status": "SEM ORIGEM NO GWI", "blocos_origem": "",
                           "blocos_ausentes": "", "imagens_ausentes": "",
                           "imagens_renomeadas": "", "trechos_ausentes": ""})
            continue

        dg, _ = fetch_with_depth_fallback(s, base, gp, args.profundidade, at)
        dd, _ = fetch_with_depth_fallback(s, base, dp, args.profundidade, at)
        if dg is None or dd is None:
            continue
        t_org, img_org = extrair((dg or {}).get("jcr:content", {}) or {})
        t_dst, img_dst = extrair((dd or {}).get("jcr:content", {}) or {})

        tudo = " ".join(n for n, _ in t_dst)
        palavras = set(tudo.split())
        ausentes = []
        for n, orig in t_org:
            if n in tudo:
                continue
            pal = n.split()
            cob = sum(1 for w in pal if w in palavras) / max(1, len(pal))
            if cob >= args.limiar:
                continue
            if not args.sem_filtro and eh_boilerplate(n):
                continue  # removido de propósito pelos fixes de layout
            ausentes.append((orig, cob))

        # Imagem NÃO se compara por nome de arquivo: o DAM do destino foi
        # repovoado com assets renomeados (GWI 'emb-mba28.jpg' -> destino
        # 'stka28.jpeg', que casa com o slug da página e é mais correto que
        # o original). Comparar nome dava 120 falsos positivos em 144
        # páginas. O que importa é não ter sumido imagem: compara QUANTIDADE.
        img_falta = []
        if len(img_dst) < len(img_org):
            img_falta = [f"origem {len(img_org)} x destino {len(img_dst)}"]
        renomeadas = len(img_org - img_dst) if len(img_dst) >= len(img_org) else 0
        status = "OK" if not ausentes and not img_falta else "FALTA CONTEÚDO"
        if ausentes:
            com_falta.append((dp, ausentes))
        linhas.append({
            "pagina_destino": dp, "pagina_origem": gp, "status": status,
            "blocos_origem": len(t_org), "blocos_ausentes": len(ausentes),
            "imagens_ausentes": "; ".join(img_falta),
            "imagens_renomeadas": renomeadas,
            "trechos_ausentes": " || ".join(t[:160] for t, _ in ausentes[:5]),
        })
        if i % 20 == 0:
            print(f"  [{i}/{len(paginas)}] {len(com_falta)} com falta", flush=True)

    write_csv(saida, ["pagina_destino", "pagina_origem", "status", "blocos_origem",
                      "blocos_ausentes", "imagens_ausentes", "imagens_renomeadas",
                      "trechos_ausentes"], linhas)

    print_header("RESULTADO")
    ok = sum(1 for l in linhas if l["status"] == "OK")
    print(f"  páginas conferidas ....... {len(linhas)}")
    print(f"  íntegras ................. {ok}")
    print(f"  com conteúdo faltando .... {len(com_falta)}")
    print(f"  sem origem no GWI ........ {len(sem_origem)}")
    print(f"  puladas (soft-delete) .... {len(apagadas)}")
    if not args.sem_filtro:
        print(f"  (boilerplate removido de propósito foi filtrado; "
              f"use --sem-filtro para vê-lo)")
    if com_falta:
        print(f"\n  --- páginas com buraco (até 15) ---")
        for dp, aus in com_falta[:15]:
            print(f"\n  {dp.rsplit('/', 1)[-1]}  ({len(aus)} bloco(s))")
            for t, cob in aus[:3]:
                print(f"     [{cob:.0%}] {t[:100]}")
    print(f"\n  CSV: {saida}")


if __name__ == "__main__":
    main()
