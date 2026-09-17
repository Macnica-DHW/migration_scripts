#!/usr/bin/env python3
"""
Remove cópias repetidas do conteúdo dentro de uma mesma página.

POR QUE ISTO EXISTE
Em 17/09/2026, 355 páginas de `semiconductors` em copia-teste tinham o
conteúdo gravado mais de uma vez na MESMA página. A causa é a armadilha nº 1
do README: **Sling POST faz merge, não substituição**. Cada passada do
migrador gravou seus nós ao lado dos da passada anterior, com outro esquema
de nome, e nada foi sobrescrito.

Sobraram três lugares onde o conteúdo pode estar:

    root/containerpy            esquema `*_wrap`  — INVISÍVEL (ver abaixo)
    root/container/<filhos>     cópia A           — renderiza
    root/container/content_area cópia B           — renderiza

**Só `root/container` renderiza.** Confirmado em 17/09/2026 lendo o HTML
servido: os `src` das imagens citam `/root/container/...` e
`/root/container/content_area/...`, e nunca `/root/containerpy/...`. Então
`containerpy` é lixo no JCR — ocupa espaço e aparece em busca, mas o
visitante nunca viu. Já A e B convivendo dentro de `container` é a
duplicação de verdade: a página inteira aparece duas vezes na tela (em
`/renesas` a segunda cópia começa no pixel 15.171 de 31.467).

A forma saudável, que 216 das 355 páginas já têm, é uma só:

    root/container/content_area/<conteúdo>

NUNCA APAGA CONTEÚDO QUE SÓ EXISTE NA CÓPIA DESCARTADA
Antes de apagar qualquer coisa, confere bloco a bloco (texto visível e nome
do asset, normalizados) se a cópia que FICA contém tudo o que a cópia que SAI
tem. Se não contiver, a página é marcada `REVISAR` e não se toca nela — e
isso vale também quando `--manter` forçou a escolha: dizer "fica o
content_area" não é licença para apagar bloco que só existe do outro lado.
Foi assim que apareceram as páginas em que as duas cópias divergem de verdade
— a maioria do canon, onde a cópia direta tem o layout trabalhado
(flexcontainer/carousel/botões) e o content_area é a migração plana.

Comparar por asset usa só o nome do arquivo: a mesma imagem aparece com três
prefixos de DAM diferentes (`/content/dam/copia-teste/americas/...`,
`/content/dam/copia-teste/products/...`, `/content/dam/macnicagwi/...`)
conforme a passada que a gravou. Comparar o caminho inteiro acusaria
divergência onde é o mesmo arquivo.

IDEMPOTENTE: página que já tem uma cópia só é reportada como "já correta" e
não é reescrita.

COMO RODAR
  # diagnóstico (padrão — não escreve nada)
  python3 aem_deduplicar_containers.py --raiz /content/copia-teste/.../semiconductors

  # só o lixo invisível, que não muda nada na tela
  python3 aem_deduplicar_containers.py --raiz ... --alvo containerpy --executar

  # a duplicação visível, apenas onde as duas cópias são equivalentes,
  # e sem tocar em página que não existe no GWI
  python3 aem_deduplicar_containers.py --raiz ... --alvo duplicata \
      --origem-gwi /content/macnicagwi/.../semiconductors --executar

  # blindar uma subárvore que não deve ser tocada
  python3 aem_deduplicar_containers.py --raiz ... --pular-contendo sony-image-sensors
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import (CONFIG, build_session, crawl_tree, delete_node,
                     fetch_with_depth_fallback, print_header, session_expired,
                     write_csv)

# Propriedades que carregam conteúdo visível. Mesma lista do
# aem_diff_conteudo.py, mais o asset e o vídeo — aqui a pergunta não é "o
# texto chegou?" e sim "esta cópia tem algo que a outra não tem?", e uma
# imagem a menos é perda igual.
PROPS_CONTEUDO = ("text", "jcr:title", "title", "linkText", "buttonText",
                  "tableData", "fileReference", "youtubeVideoId")

# Boilerplate que os componentes de destino injetam sozinhos; conta como
# ruído na comparação, não como conteúdo.
BOILERPLATE = re.compile(r"^(opens in a new tab|read more|learn more|home)$", re.I)


def texto_limpo(bruto):
    """HTML -> texto comparável."""
    if not isinstance(bruto, str):
        return ""
    sem_tag = re.sub(r"<[^>]+>", " ", bruto)
    return re.sub(r"\s+", " ", html.unescape(sem_tag)).strip()


def filhos(node):
    return [(k, v) for k, v in node.items()
            if isinstance(v, dict) and not k.startswith("jcr:") and k != "cq:responsive"]


def normalizar(valor):
    """Bloco comparável entre cópias gravadas por passadas diferentes.

    Asset vira só o nome do arquivo sem extensão: a mesma imagem existe sob
    três prefixos de DAM conforme quem a gravou. Texto perde pontuação e
    caixa, que os migradores tratam de formas diferentes.
    """
    if valor.startswith("/content/dam/"):
        # Nome do arquivo sem extensão e sem separador: a MESMA imagem
        # aparece como `dg-ab17-m2fmc-320` e `dg-ab17-m2fmc_320`, e como
        # `dg-tls1-3-block` e `dg-tls1.3-block`, conforme a passada.
        nome = valor.rsplit("/", 1)[-1].lower().rsplit(".", 1)[0]
        return "asset:" + re.sub(r"[^a-z0-9]+", "", nome)
    # Colapsar espaço DEPOIS de trocar pontuação por espaço. Sem isto
    # `Its’ compact` vira "its  compact" e `Its compact` vira "its compact":
    # o mesmo texto de dois migradores diferentes contava como divergência,
    # e a página ia para REVISAR à toa.
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", valor.lower())).strip()


def blocos(node, acc=None):
    """Conteúdo de uma subárvore, normalizado, sem boilerplate."""
    acc = [] if acc is None else acc
    for prop in PROPS_CONTEUDO:
        valor = node.get(prop)
        if isinstance(valor, str) and valor.strip():
            limpo = texto_limpo(valor)
            if limpo and not BOILERPLATE.match(limpo):
                acc.append(normalizar(limpo))
    for _, filho in filhos(node):
        blocos(filho, acc)
    return acc


def componentes(node, acc=None):
    """Quantos componentes de verdade (não o container em si) a cópia tem."""
    acc = 0 if acc is None else acc
    for _, filho in filhos(node):
        tipo = (filho.get("sling:resourceType") or "").rsplit("/", 1)[-1]
        if tipo and tipo != "container":
            acc += 1
        acc = componentes(filho, acc)
    return acc


def analisar(jcr_content):
    """Descreve o estado de uma página. Só leitura, sem efeito colateral."""
    root = jcr_content.get("root") or {}
    container = root.get("container")
    irmaos = [k for k, _ in filhos(root) if k != "container"]

    if container is None:
        return {"estado": "SEM root/container", "irmaos": irmaos}

    content_area = container.get("content_area")
    diretos = [(k, v) for k, v in filhos(container) if k != "content_area"]

    b_direto = set(b for _, nodo in diretos for b in blocos(nodo))
    b_area = set(blocos(content_area)) if content_area is not None else set()

    info = {
        "irmaos": irmaos,
        "tem_content_area": content_area is not None,
        "blocos_direto": b_direto,
        "blocos_area": b_area,
        "comp_direto": sum(componentes(nodo) for _, nodo in diretos),
        "comp_area": componentes(content_area) if content_area is not None else 0,
        "nomes_diretos": [k for k, _ in diretos],
    }

    # Texto corrido de cada cópia, para a comparação por contenção. Um
    # migrador guardou a introdução em `text_intro` sozinho e o outro a
    # concatenou dentro de `text_1`: por conjunto isso conta como bloco
    # exclusivo, por contenção não. Mesmo princípio do aem_diff_conteudo.py.
    info["texto_direto"] = " || ".join(b for _, nodo in diretos for b in blocos(nodo))
    info["texto_area"] = " || ".join(blocos(content_area)) if content_area is not None else ""

    # O que o visitante vê hoje: tudo que está sob root/container.
    info["blocos_visiveis"] = b_direto | b_area

    if b_direto and b_area:
        info["estado"] = "DUPLICADO"
    elif b_area:
        info["estado"] = "OK (content_area)"
    elif b_direto:
        info["estado"] = "OK (direto)"
    else:
        info["estado"] = "VAZIO"
    return info


# Abaixo disto um bloco é curto demais para "está contido" significar algo:
# "sony" aparece dentro de qualquer frase sobre a Sony.
MIN_CONTENCAO = 14


def ausentes(blocos_copia, texto_outra):
    """Blocos que a outra cópia não tem nem como pedaço de um bloco maior."""
    faltando = []
    for bloco in sorted(blocos_copia):
        if len(bloco) >= MIN_CONTENCAO:
            if bloco not in texto_outra:
                faltando.append(bloco)
        elif bloco not in texto_outra.split(" || "):
            faltando.append(bloco)
    return faltando


def decidir_copia(info, preferencia):
    """Qual cópia fica. Devolve ('area'|'direto', motivo)."""
    b_direto, b_area = info["blocos_direto"], info["blocos_area"]
    if preferencia == "content_area":
        return "area", "forçado por --manter"
    if preferencia == "direto":
        return "direto", "forçado por --manter"

    so_direto = ausentes(b_direto, info["texto_area"])
    so_area = ausentes(b_area, info["texto_direto"])
    if so_direto and not so_area:
        return "direto", "só a cópia direta tem blocos exclusivos"
    if so_area and not so_direto:
        return "area", "só o content_area tem blocos exclusivos"
    if not so_direto and not so_area:
        # Mesmo conteúdo: fica o content_area, a forma das 216 páginas já
        # corretas.
        #
        # NÃO desempatar por número de componentes. Parece sensato e está
        # errado: em `/altera` a cópia direta tem 99 componentes contra 57
        # do content_area, e é a PIOR — ela é o resultado de um migrador que
        # achatou as 4 abas do GWI em texto corrido, e cada aba virou vários
        # `heading_*_wrap`/`text_*_wrap` soltos. O content_area guarda o
        # `tabs` com os 4 itens nomeados como no GWI. Mais nós = mais
        # estrutura perdida, não mais conteúdo.
        return "area", "conteúdo igual, content_area é a forma padrão"
    return None, "as duas cópias têm blocos exclusivos"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", required=True)
    ap.add_argument("--alvo", choices=("containerpy", "duplicata", "ambos"),
                    default="ambos",
                    help="containerpy: só o lixo invisível. duplicata: só a "
                         "duplicação que aparece na tela. Padrão: os dois.")
    ap.add_argument("--manter", choices=("auto", "content_area", "direto"),
                    default="auto",
                    help="qual cópia fica quando há duplicação (padrão: auto)")
    ap.add_argument("--origem-gwi", default=None, metavar="CAMINHO",
                    help="raiz equivalente no GWI. Com isto, página que não "
                         "existe lá é PULADA — não se mexe no que não dá para "
                         "conferir contra a fonte da verdade.")
    ap.add_argument("--pular-contendo", action="append", default=[], metavar="TEXTO",
                    help="não toca em página cujo caminho contenha TEXTO. "
                         "Repetível. Use para blindar subárvore que está "
                         "correta e não deve ser mexida.")
    ap.add_argument("--incluir-divergentes", action="store_true",
                    help="NÃO recomendado: age também onde as duas cópias têm "
                         "blocos exclusivos. Sem isto, essas páginas só são "
                         "listadas como REVISAR.")
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--backup", default=None, metavar="ARQUIVO",
                    help="onde gravar o conteúdo dos nós antes de apagar "
                         "(padrão: <output sem .csv>_backup.json). Apagar "
                         "subárvore é irreversível e o CSV só guarda o "
                         "caminho; o backup guarda o JSON inteiro.")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    raiz = args.raiz.rstrip("/")
    allow = ()
    if args.permitir_escrita_global2:
        liberado = args.permitir_escrita_global2.rstrip("/")
        if liberado != raiz:
            print("[erro] --permitir-escrita-global2 não bate com --raiz.",
                  file=sys.stderr)
            sys.exit(1)
        allow = (liberado,)

    saida = args.output or f"dedup_{raiz.rsplit('/', 1)[-1]}.csv"
    sess, auth = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("DEDUPLICAR CONTAINERS")
    print(f"  raiz  : {raiz}")
    print(f"  alvo  : {args.alvo}")
    print(f"  manter: {args.manter}")
    print(f"  modo  : {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv = crawl_tree(sess, base, raiz, auth,
                     skip_contains=CONFIG.get("skip_path_contains", ()), quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")

    linhas, planejadas = [], []
    resumo = {"ja_correta": 0, "duplicada": 0, "revisar": 0, "lixo": 0,
              "soft_deleted": 0, "ilegivel": 0, "sem_origem": 0, "blindada": 0}

    for i, pagina in enumerate(paginas, 1):
        dados, status = fetch_with_depth_fallback(
            sess, base, f"{pagina}/jcr:content", CONFIG["source_depth"], auth)
        if not dados:
            resumo["ilegivel"] += 1
            linhas.append({"pagina": pagina, "estado": f"ILEGÍVEL {status}"})
            continue
        if any(t in pagina for t in args.pular_contendo):
            resumo["blindada"] += 1
            linhas.append({"pagina": pagina, "estado": "BLINDADA (--pular-contendo)"})
            continue
        if args.origem_gwi:
            gwi = args.origem_gwi.rstrip("/") + pagina[len(raiz):]
            origem, _ = fetch_with_depth_fallback(sess, base, f"{gwi}/jcr:content",
                                                  1, auth)
            if origem is None:
                resumo["sem_origem"] += 1
                linhas.append({"pagina": pagina, "estado": "SEM ORIGEM NO GWI (pulada)"})
                continue
        if dados.get("deleted"):
            # Soft-delete: a página sumiu do console mas continua no JCR.
            # Mexer nela é trabalho jogado fora — ver aem_soft_delete.py.
            resumo["soft_deleted"] += 1
            linhas.append({"pagina": pagina, "estado": "SOFT-DELETED (pulada)"})
            continue

        info = analisar(dados)
        linha = {
            "pagina": pagina,
            "estado": info["estado"],
            "irmaos_invisiveis": ";".join(info.get("irmaos", [])),
            "blocos_direto": len(info.get("blocos_direto", ())),
            "blocos_content_area": len(info.get("blocos_area", ())),
            "comp_direto": info.get("comp_direto", ""),
            "comp_content_area": info.get("comp_area", ""),
        }

        acoes = []

        # 1. Irmãos de root/container: invisíveis. Só saem se o que eles
        #    guardam já estiver no que renderiza — senão seriam a única
        #    cópia de algum bloco.
        if args.alvo in ("containerpy", "ambos"):
            for irmao in info.get("irmaos", []):
                nodo = (dados.get("root") or {}).get(irmao) or {}
                exclusivos = set(blocos(nodo)) - info.get("blocos_visiveis", set())
                if exclusivos:
                    linha["aviso_irmao"] = (f"{irmao} tem {len(exclusivos)} bloco(s) "
                                            f"que NÃO estão no que renderiza")
                    resumo["revisar"] += 1
                else:
                    acoes.append((f"{pagina}/jcr:content/root/{irmao}",
                                  f"invisível, conteúdo já presente em root/container"))
                    resumo["lixo"] += 1

        # 2. Duplicação visível dentro de root/container.
        if info["estado"] == "DUPLICADO" and args.alvo in ("duplicata", "ambos"):
            resumo["duplicada"] += 1
            fica, motivo = decidir_copia(info, args.manter)
            linha["decisao"] = motivo
            so_d = ausentes(info["blocos_direto"], info["texto_area"])
            so_a = ausentes(info["blocos_area"], info["texto_direto"])

            # A trava vale TAMBÉM quando --manter forçou a escolha: dizer
            # "fica o content_area" não pode virar licença para apagar um
            # bloco que só existe na cópia direta. `fica is None` já cai
            # aqui, porque nesse caso as duas têm exclusivo.
            perdidos = (so_d if fica == "area"
                        else so_a if fica == "direto"
                        else so_d + so_a)
            if perdidos and not args.incluir_divergentes:
                linha["estado"] = "REVISAR (a cópia descartada tem bloco exclusivo)"
                linha["exclusivo_direto"] = " ~ ".join(so_d[:3])
                linha["exclusivo_content_area"] = " ~ ".join(so_a[:3])
                linha["blocos_perdidos"] = len(perdidos)
                resumo["revisar"] += 1
            else:
                fica = fica or "area"
                if fica == "area":
                    for nome in info["nomes_diretos"]:
                        acoes.append((f"{pagina}/jcr:content/root/container/{nome}",
                                      "cópia repetida; fica o content_area"))
                    linha["copia_removida"] = "direta"
                else:
                    acoes.append((f"{pagina}/jcr:content/root/container/content_area",
                                  "cópia repetida; fica a cópia direta"))
                    linha["copia_removida"] = "content_area"
                linha["blocos_perdidos"] = len(perdidos)
        elif info["estado"].startswith("OK"):
            resumo["ja_correta"] += 1

        linha["nos_a_apagar"] = ";".join(c for c, _ in acoes)
        linhas.append(linha)
        planejadas.extend(acoes)

        if i % 50 == 0:
            print(f"  ... {i}/{len(paginas)}", flush=True)

    print(f"\n  já corretas (uma cópia só) ....... {resumo['ja_correta']}")
    print(f"  duplicadas ....................... {resumo['duplicada']}")
    print(f"  a revisar à mão .................. {resumo['revisar']}")
    print(f"  nós invisíveis a remover ......... {resumo['lixo']}")
    print(f"  soft-deleted (puladas) ........... {resumo['soft_deleted']}")
    print(f"  sem origem no GWI (puladas) ...... {resumo['sem_origem']}")
    print(f"  blindadas (--pular-contendo) ..... {resumo['blindada']}")
    print(f"  ilegíveis ........................ {resumo['ilegivel']}")
    print(f"\n  nós que seriam apagados: {len(planejadas)}")
    for caminho, motivo in planejadas[:8]:
        print(f"    - {caminho}\n        {motivo}")
    if len(planejadas) > 8:
        print(f"    ... e mais {len(planejadas) - 8}")

    campos = ["pagina", "estado", "irmaos_invisiveis", "blocos_direto",
              "blocos_content_area", "comp_direto", "comp_content_area",
              "decisao", "copia_removida", "blocos_perdidos", "nos_a_apagar",
              "exclusivo_direto", "exclusivo_content_area", "aviso_irmao", "acao"]

    if not args.executar:
        write_csv(saida, campos, linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    # Backup antes de qualquer delete. Sem isto o CSV diria O QUE foi
    # apagado sem dar como refazer.
    backup = args.backup or (saida[:-4] if saida.endswith(".csv") else saida) + "_backup.json"
    guardados, sem_backup = {}, []
    for caminho, _ in planejadas:
        nodo, st = fetch_with_depth_fallback(sess, base, caminho,
                                             CONFIG["source_depth"], auth)
        if nodo is None:
            sem_backup.append((caminho, st))
        else:
            guardados[caminho] = nodo
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(guardados, f, ensure_ascii=False, indent=1)
    print(f"  backup de {len(guardados)} nó(s): {backup}")
    if sem_backup:
        print(f"  [erro] {len(sem_backup)} nó(s) não puderam ser lidos para backup; "
              f"nada foi apagado.", file=sys.stderr)
        for caminho, st in sem_backup[:5]:
            print(f"     {caminho} (HTTP {st})", file=sys.stderr)
        sys.exit(1)

    ok = falhas = 0
    for i, (caminho, _) in enumerate(planejadas, 1):
        if session_expired(auth):
            print(f"\n[erro] sessão expirou em {i-1}/{len(planejadas)}", file=sys.stderr)
            break
        status, corpo = delete_node(sess, base, caminho, auth, allow_extra=allow)
        if status in (200, 204):
            ok += 1
        else:
            falhas += 1
            print(f"  [FALHA {status}] {caminho} :: {corpo[:90]}")
        if i % 25 == 0:
            print(f"  [{i}/{len(planejadas)}] ok={ok} falhas={falhas}", flush=True)

    for linha in linhas:
        if linha.get("nos_a_apagar"):
            linha["acao"] = "apagado" if not falhas else "ver log"
    write_csv(saida, campos, linhas)
    print(f"\n  apagados: {ok}   falhas: {falhas}\n  CSV: {saida}")
    print("\n  Depois disto: aem_diff_conteudo.py para confirmar que nada sumiu,")
    print("  e aem_screenshot.py numa amostra para ver o resultado na tela.")


if __name__ == "__main__":
    main()
