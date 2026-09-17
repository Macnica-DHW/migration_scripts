#!/usr/bin/env python3
"""
Acha texto que o destino MOSTRA e o GWI não tem. SOMENTE LEITURA.

POR QUE ISTO EXISTE
O `aem_diff_conteudo.py` responde "chegou tudo?" — ele varre os blocos da
ORIGEM e pergunta se cada um está no destino. A própria docstring dele avisa:
"acha o que FALTA, não o que está SOBRANDO". Este faz a pergunta contrária,
varrendo os blocos do DESTINO e perguntando se existem no GWI.

O caso que motivou: em `4-helio-view-hardware` a página migrada abre com
"Transform your approach to FPGA with our Helio View hardware vWorkshop..."
— texto que NÃO aparece em lugar nenhum da página do GWI. Ele é o
`jcr:description` do GWI, a META DESCRIPTION, que o migrador transformou em
bloco de texto visível.

O mesmo bug tem um segundo sintoma, e é por isso que vale reportar os dois
juntos: a meta description foi para o corpo e NÃO foi para o lugar dela.
Em 17/09/2026, em `semiconductors`: 353 das 355 páginas do GWI tinham
`jcr:description`, e 0 das 355 do destino tinham.

Pela regra do time (o GWI é a fonte da verdade, divergência no destino é bug
nosso), texto visível que a origem não mostra é divergência tanto quanto
texto que sumiu.

O QUE A COLUNA hideInNav FAZ AQUI
Parece assunto de outro script, e não é: `hideInNav=true` tira a página da
navegação E da própria trilha de breadcrumb. No GWI a trilha é
`Macnica Americas / Products / Semiconductors / 4. Helio View Hardware`; no
destino, com a flag, ela para antes da página atual. As páginas Sony, que
não receberam a flag, mostram a trilha inteira. Como o `aem_migrate.py` liga
`hideInNav` por padrão ("diretriz do cliente"), a conta é fácil de fazer
errado — daí a coluna.

COMO DECIDE QUE UM BLOCO SOBRA
Mesmo critério de contenção do aem_diff_conteudo.py, invertido: concatena o
texto visível do GWI e pergunta se o bloco do destino está lá dentro. Isso
absorve fusão e quebra de blocos. Bloco curto (< 25 caracteres) é ignorado:
título de seção e rótulo de botão coincidem por acaso demais para valer
alarme.

COMO RODAR
  python3 aem_conteudo_sobrando.py \
      --destino /content/copia-teste/.../semiconductors \
      --origem  /content/macnicagwi/.../semiconductors

  # só as páginas com problema
  python3 aem_conteudo_sobrando.py --destino ... --origem ... --so-problemas
"""

import argparse
import csv
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import (CONFIG, build_session, crawl_tree, fetch_with_depth_fallback,
                     print_header, write_csv)

PROPS_TEXTO = ("text", "jcr:title", "title", "linkText", "buttonText", "tableData")

# Abaixo disto o bloco coincide por acaso demais ("Overview", "Features",
# "Request a Quote") para acusar divergência.
MIN_BLOCO = 25


def limpar(bruto):
    if not isinstance(bruto, str):
        return ""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", bruto))).strip()


def normalizar(texto):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", texto.lower())).strip()


def blocos(node, acc=None):
    acc = [] if acc is None else acc
    for prop in PROPS_TEXTO:
        valor = node.get(prop)
        if isinstance(valor, str) and valor.strip():
            limpo = limpar(valor)
            if limpo:
                acc.append(limpo)
    for chave, filho in node.items():
        if isinstance(filho, dict) and not chave.startswith("jcr:") and chave != "cq:responsive":
            blocos(filho, acc)
    return acc


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--destino", required=True)
    ap.add_argument("--origem", required=True)
    ap.add_argument("--so-problemas", action="store_true")
    ap.add_argument("--min-bloco", type=int, default=MIN_BLOCO)
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    destino = args.destino.rstrip("/")
    origem = args.origem.rstrip("/")
    saida = args.output or f"sobrando_{destino.rsplit('/', 1)[-1]}.csv"
    sess, auth = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("CONTEÚDO SOBRANDO NO DESTINO")
    print(f"  destino: {destino}")
    print(f"  origem : {origem}\n")

    inv = crawl_tree(sess, base, destino, auth,
                     skip_contains=CONFIG.get("skip_path_contains", ()), quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")

    linhas = []
    resumo = {"ok": 0, "sobrando": 0, "meta_no_corpo": 0, "sem_origem": 0,
              "sem_description": 0, "hide_in_nav": 0}

    for i, pagina in enumerate(paginas, 1):
        gwi = origem + pagina[len(destino):]
        dados, _ = fetch_with_depth_fallback(sess, base, f"{pagina}/jcr:content",
                                             CONFIG["source_depth"], auth)
        if not dados:
            linhas.append({"pagina": pagina, "situacao": "DESTINO ILEGÍVEL"})
            continue
        fonte, _ = fetch_with_depth_fallback(sess, base, f"{gwi}/jcr:content",
                                             CONFIG["source_depth"], auth)
        if not fonte:
            resumo["sem_origem"] += 1
            linhas.append({"pagina": pagina, "situacao": "SEM ORIGEM NO GWI"})
            continue

        raiz = (dados.get("root") or {}).get("container") or {}
        do_destino = [b for b in blocos(raiz) if len(b) >= args.min_bloco]
        texto_gwi = normalizar(" || ".join(blocos(fonte)))

        sobrando = [b for b in do_destino if normalizar(b) not in texto_gwi]

        # A meta description do GWI virou bloco visível?
        desc_gwi = limpar(fonte.get("jcr:description") or "")
        meta_no_corpo = [b for b in sobrando
                         if desc_gwi and normalizar(b) == normalizar(desc_gwi)]

        hide = str(dados.get("hideInNav", "")).lower() == "true"
        sem_desc = not (dados.get("jcr:description") or "").strip()
        if hide:
            resumo["hide_in_nav"] += 1
        if sem_desc:
            resumo["sem_description"] += 1
        if meta_no_corpo:
            resumo["meta_no_corpo"] += 1
        if sobrando:
            resumo["sobrando"] += 1
        else:
            resumo["ok"] += 1

        if sobrando or not args.so_problemas:
            linhas.append({
                "pagina": pagina,
                "situacao": "SOBRANDO" if sobrando else "OK",
                "blocos_sobrando": len(sobrando),
                "meta_description_no_corpo": "sim" if meta_no_corpo else "",
                "destino_sem_description": "sim" if sem_desc else "",
                "hide_in_nav": "sim" if hide else "",
                "breadcrumb_sem_a_propria_pagina": "sim" if hide else "",
                "trechos_sobrando": " || ".join(b[:110] for b in sobrando[:4]),
            })
        if i % 50 == 0:
            print(f"  ... {i}/{len(paginas)}", flush=True)

    print(f"\n  sem texto sobrando ............... {resumo['ok']}")
    print(f"  com texto sobrando ............... {resumo['sobrando']}")
    print(f"    destes, meta description no corpo {resumo['meta_no_corpo']}")
    print(f"  destino sem jcr:description ...... {resumo['sem_description']}")
    print(f"  hideInNav=true (breadcrumb curto)  {resumo['hide_in_nav']}")
    print(f"  sem origem no GWI ................ {resumo['sem_origem']}")

    campos = ["pagina", "situacao", "blocos_sobrando", "meta_description_no_corpo",
              "destino_sem_description", "hide_in_nav",
              "breadcrumb_sem_a_propria_pagina", "trechos_sobrando"]
    write_csv(saida, campos, linhas)
    print(f"\n  CSV: {saida}")


if __name__ == "__main__":
    main()
