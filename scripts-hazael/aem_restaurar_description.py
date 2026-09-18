#!/usr/bin/env python3
"""
Tira a meta description do corpo da página e devolve ao jcr:description.

O PROBLEMA
O migrador leu o `jcr:description` do GWI — a META DESCRIPTION, que não
aparece no corpo da página — e gravou o texto como bloco VISÍVEL no destino.
E não preencheu o `jcr:description` do destino. Um bug, duas pontas:

    GWI      jcr:description = "Transform your approach to FPGA with..."
    destino  jcr:description = (vazio)
    destino  corpo visível   = "Transform your approach to FPGA with..."

Foi assim que `4-helio-view-hardware` passou a abrir com um parágrafo que não
existe em lugar nenhum da página do GWI. Em `semiconductors` (17/09/2026):
155 páginas com a description no corpo, 348 sem a propriedade — de 353 que o
GWI tem.

Este script conserta as duas pontas na mesma passada: apaga o bloco e grava a
propriedade.

A TRAVA QUE IMPORTA
Só apaga bloco cujo texto **não aparece no corpo do GWI**. Uma description
bem escrita costuma repetir a primeira frase da página; quando isso acontece,
o texto é conteúdo legítimo e some da lista. A comparação com o corpo do GWI
usa contenção (o bloco pode ter sido quebrado ou fundido na migração), e a
igualdade com a description é exata depois de normalizar — nada de parecido
demais, porque apagar parágrafo é irreversível.

Olha só dentro de `jcr:content/root/container`, que é o único lugar que
renderiza. O que estiver em nó irmão (`containerpy`) é invisível e fica como
está — ver o aem_deduplicar_containers.py.

QUAL NÓ SAI
Se o invólucro do bloco (`text_intro_wrap`, por exemplo) só tem esse texto
dentro, sai o invólucro inteiro, senão fica um container vazio ocupando
espaçamento na página. Se tiver mais coisa junto, sai só o nó do texto.

IDEMPOTENTE: página sem o bloco e com a description no lugar é reportada como
"já correta" e não é reescrita.

COMO RODAR
  # diagnóstico (padrão — não escreve nada)
  python3 aem_restaurar_description.py \
      --destino /content/copia-teste/.../semiconductors \
      --origem  /content/macnicagwi/.../semiconductors

  # executando, sem tocar numa subárvore
  python3 aem_restaurar_description.py --destino ... --origem ... \
      --pular-contendo sony-image-sensors --executar
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import (CONFIG, build_session, crawl_tree, delete_node,
                     fetch_with_depth_fallback, post_node, print_header,
                     session_expired, write_csv)

PROPS_TEXTO = ("text", "jcr:title", "title", "linkText", "buttonText", "tableData")


def limpar(bruto):
    if not isinstance(bruto, str):
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", bruto))).strip()


def normalizar(texto):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", texto.lower())).strip()


def filhos(node):
    return [(k, v) for k, v in node.items()
            if isinstance(v, dict) and not k.startswith("jcr:") and k != "cq:responsive"]


def textos(node, acc=None):
    acc = [] if acc is None else acc
    for prop in PROPS_TEXTO:
        valor = node.get(prop)
        if isinstance(valor, str) and valor.strip():
            limpo = limpar(valor)
            if limpo:
                acc.append(limpo)
    for _, filho in filhos(node):
        textos(filho, acc)
    return acc


def achar_blocos(node, alvo_norm, caminho="", pai=None, nome=""):
    """Nós cujo texto é exatamente a description. Devolve (caminho, pai, nome)."""
    achados = []
    for prop in PROPS_TEXTO:
        valor = node.get(prop)
        if isinstance(valor, str) and valor.strip():
            if normalizar(limpar(valor)) == alvo_norm:
                achados.append((caminho, pai, nome))
                break
    for chave, filho in filhos(node):
        achados.extend(achar_blocos(filho, alvo_norm, f"{caminho}/{chave}", node, chave))
    return achados


def tem_outro_conteudo(involucro, nome_do_bloco):
    """O invólucro guarda algo além do bloco que vai sair?"""
    for chave, filho in filhos(involucro):
        if chave != nome_do_bloco and textos(filho):
            return True
    return bool([p for p in PROPS_TEXTO if limpar(involucro.get(p, ""))])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--destino", required=True)
    ap.add_argument("--origem", required=True)
    ap.add_argument("--pular-contendo", action="append", default=[], metavar="TEXTO")
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--backup", default=None, metavar="ARQUIVO")
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    destino = args.destino.rstrip("/")
    origem = args.origem.rstrip("/")
    allow = ()
    if args.permitir_escrita_global2:
        liberado = args.permitir_escrita_global2.rstrip("/")
        if liberado != destino:
            print("[erro] --permitir-escrita-global2 não bate com --destino.",
                  file=sys.stderr)
            sys.exit(1)
        allow = (liberado,)

    saida = args.output or f"description_{destino.rsplit('/', 1)[-1]}.csv"
    sess, auth = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("META DESCRIPTION: DO CORPO PARA A PROPRIEDADE")
    print(f"  destino: {destino}")
    print(f"  origem : {origem}")
    print(f"  modo   : {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv = crawl_tree(sess, base, destino, auth,
                     skip_contains=CONFIG.get("skip_path_contains", ()), quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")

    linhas, planejadas = [], []
    resumo = {"ja_correta": 0, "corrigir": 0, "so_propriedade": 0, "so_bloco": 0,
              "legitimo": 0, "sem_description_na_origem": 0, "sem_origem": 0,
              "blindada": 0}

    for i, pagina in enumerate(paginas, 1):
        if any(t in pagina for t in args.pular_contendo):
            resumo["blindada"] += 1
            linhas.append({"pagina": pagina, "situacao": "BLINDADA"})
            continue
        dados, _ = fetch_with_depth_fallback(sess, base, f"{pagina}/jcr:content",
                                             CONFIG["source_depth"], auth)
        if not dados:
            linhas.append({"pagina": pagina, "situacao": "DESTINO ILEGÍVEL"})
            continue
        gwi = origem + pagina[len(destino):]
        fonte, _ = fetch_with_depth_fallback(sess, base, f"{gwi}/jcr:content",
                                             CONFIG["source_depth"], auth)
        if not fonte:
            resumo["sem_origem"] += 1
            linhas.append({"pagina": pagina, "situacao": "SEM ORIGEM NO GWI"})
            continue

        desc = limpar(fonte.get("jcr:description") or "")
        if not desc:
            resumo["sem_description_na_origem"] += 1
            linhas.append({"pagina": pagina, "situacao": "GWI SEM DESCRIPTION"})
            continue

        alvo = normalizar(desc)
        corpo_gwi = normalizar(" || ".join(textos(fonte)))
        container = (dados.get("root") or {}).get("container") or {}
        achados = achar_blocos(container, alvo)

        # A description repete uma frase que a página do GWI mostra de
        # verdade? Então o bloco é conteúdo legítimo e não se apaga.
        legitimo = bool(achados) and alvo in corpo_gwi
        if legitimo:
            resumo["legitimo"] += 1

        desc_atual = limpar(dados.get("jcr:description") or "")
        precisa_prop = normalizar(desc_atual) != alvo
        precisa_bloco = bool(achados) and not legitimo

        if not precisa_prop and not precisa_bloco:
            resumo["ja_correta"] += 1
            linhas.append({"pagina": pagina, "situacao": "já correta"})
            continue

        alvos_delete = []
        for caminho, pai, nome in achados if precisa_bloco else []:
            # Invólucro só com esse bloco dentro sai inteiro; senão sai só o nó.
            partes = caminho.strip("/").split("/")
            if pai is not None and len(partes) >= 2 and not tem_outro_conteudo(pai, nome):
                pai_caminho = "/".join(partes[:-1])
                alvos_delete.append(f"{pagina}/jcr:content/root/container/{pai_caminho}")
            else:
                alvos_delete.append(f"{pagina}/jcr:content/root/container/{caminho.strip('/')}")

        resumo["corrigir"] += 1
        if precisa_prop and not precisa_bloco:
            resumo["so_propriedade"] += 1
        if precisa_bloco and not precisa_prop:
            resumo["so_bloco"] += 1

        linhas.append({
            "pagina": pagina,
            "situacao": "a corrigir",
            "description_gwi": desc[:200],
            "description_destino_antes": desc_atual[:200],
            "grava_propriedade": "sim" if precisa_prop else "",
            "blocos_a_apagar": ";".join(sorted(set(alvos_delete))),
            "bloco_e_legitimo": "sim" if legitimo else "",
        })
        planejadas.append((pagina, desc if precisa_prop else None,
                           sorted(set(alvos_delete))))

        if i % 50 == 0:
            print(f"  ... {i}/{len(paginas)}", flush=True)

    total_blocos = sum(len(b) for _, _, b in planejadas)
    print(f"\n  já corretas ...................... {resumo['ja_correta']}")
    print(f"  a corrigir ....................... {resumo['corrigir']}")
    print(f"    só a propriedade ............... {resumo['so_propriedade']}")
    print(f"    só o bloco do corpo ............ {resumo['so_bloco']}")
    print(f"  bloco legítimo (o GWI mostra) .... {resumo['legitimo']}")
    print(f"  GWI sem description .............. {resumo['sem_description_na_origem']}")
    print(f"  sem origem no GWI ................ {resumo['sem_origem']}")
    print(f"  blindadas ........................ {resumo['blindada']}")
    print(f"\n  blocos que sairiam do corpo: {total_blocos}")
    for pagina, _, blocos_ in planejadas[:5]:
        for b in blocos_:
            print(f"    - {b}")

    campos = ["pagina", "situacao", "description_gwi", "description_destino_antes",
              "grava_propriedade", "blocos_a_apagar", "bloco_e_legitimo", "acao"]

    if not args.executar:
        write_csv(saida, campos, linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    # Backup do que vai sair do corpo. Gravar propriedade é reversível pelo
    # CSV (tem o valor antigo); apagar nó, não.
    backup = args.backup or (saida[:-4] if saida.endswith(".csv") else saida) + "_backup.json"
    guardados, falhou_backup = {}, []
    for _, _, blocos_ in planejadas:
        for caminho in blocos_:
            nodo, st = fetch_with_depth_fallback(sess, base, caminho,
                                                 CONFIG["source_depth"], auth)
            if nodo is None:
                falhou_backup.append((caminho, st))
            else:
                guardados[caminho] = nodo
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(guardados, f, ensure_ascii=False, indent=1)
    print(f"  backup de {len(guardados)} nó(s): {backup}")
    if falhou_backup:
        print(f"  [erro] {len(falhou_backup)} nó(s) ilegíveis para backup; "
              f"nada foi escrito.", file=sys.stderr)
        sys.exit(1)

    ok_prop = ok_del = falhas = 0
    for i, (pagina, desc, blocos_) in enumerate(planejadas, 1):
        if session_expired(auth):
            print(f"\n[erro] sessão expirou em {i-1}/{len(planejadas)}", file=sys.stderr)
            break
        for caminho in blocos_:
            st, corpo = delete_node(sess, base, caminho, auth, allow_extra=allow)
            if st in (200, 204):
                ok_del += 1
            else:
                falhas += 1
                print(f"  [FALHA {st}] {caminho} :: {corpo[:80]}")
        if desc is not None:
            st, corpo = post_node(sess, base, f"{pagina}/jcr:content",
                                  {"jcr:description": desc}, auth, allow_extra=allow)
            if st in (200, 201):
                ok_prop += 1
            else:
                falhas += 1
                print(f"  [FALHA {st}] description de {pagina} :: {corpo[:80]}")
        if i % 25 == 0:
            print(f"  [{i}/{len(planejadas)}] props={ok_prop} blocos={ok_del} "
                  f"falhas={falhas}", flush=True)

    for linha in linhas:
        if linha.get("situacao") == "a corrigir":
            linha["acao"] = "corrigido" if not falhas else "ver log"
    write_csv(saida, campos, linhas)
    print(f"\n  descriptions gravadas: {ok_prop}   blocos apagados: {ok_del}   "
          f"falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
