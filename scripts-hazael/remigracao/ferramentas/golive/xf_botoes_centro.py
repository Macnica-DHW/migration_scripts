#!/usr/bin/env python3
"""xf_botoes_centro.py [--executar] — os dois botões do XF products-contact-block do global2 com posição CENTER.
Dry-run por padrão. Backup do jcr:content inteiro antes de gravar. Só grava dentro do XF (lista branca de _comum).

Por que existe (21/09/2026): o `--par-ao-centro` do xf_lado_a_lado.py dava ao 1º botão o estilo Right e deixava
o 2º sem posição (= esquerda) para o par ficar junto no centro a 1400px (vão de 50px). O CSS do site não tem
variante de celular para `.right`/`.center` (só `margin-left/right:auto`), então abaixo de 1050px — onde o
`sp-flex-direction-column` empilha os itens — o 1º botão encosta à direita e o 2º à esquerda (escada) em
qualquer janela entre 376 e 1049px: celular largo, iPhone 8 Plus (415), iPad (768 e 1024). Medido com e sem
editor, Chromium e Firefox: é igual; a 375px não aparece porque o vão (345px) é exatamente a largura do botão.

Correção decidida pelo Hazael: Center nos dois (o padrão da casa — o XF signup-and-contact e os pares de botões
do boards-modules já são assim). Desktop: botões no meio de cada metade (164..561 | 865..1210 a 1400px, vão 304,
antes 277..675 | 725..1070). Celular/tablet: os dois no mesmo x, centrados. Gap do flex (Large) mantido.

  python3 xf_botoes_centro.py            # dry-run: mostra o que muda
  python3 xf_botoes_centro.py --executar
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import DADOS, NOSSAS, XF_G2, alterar, eh_nossa, ler, sessao, url

XF = f"{XF_G2}/products-contact-block/master"
S_FIXEDMIN, S_CENTER, S_RIGHT = "1722936853890", "1717669229626", "1717669230937"
ALVO = ["", S_FIXEDMIN, S_CENTER]


def rt(no):
    return str(no.get("sling:resourceType", "")).split("/")[-1]


def main():
    executar = "--executar" in sys.argv
    print("EXECUTANDO" if executar else "dry-run", "-", XF)
    st, jc = ler(f"{XF}/jcr:content", ".infinity.json")
    if st != 200 or not isinstance(jc, dict) or "root" not in jc:
        sys.exit(f"[erro] HTTP {st} lendo {XF}/jcr:content — nada feito")
    print(f"  criado por {jc.get('jcr:createdBy')}; último editor {jc.get('cq:lastModifiedBy')} em {jc.get('cq:lastModified')}")
    if not eh_nossa(jc.get("cq:lastModifiedBy"), NOSSAS):
        print(f"  [ATENÇÃO] o último editor não é uma das nossas contas ({', '.join(sorted(NOSSAS))}) — conferir antes de gravar")
        if executar:
            sys.exit(1)
    flex = jc["root"].get("containerpy", {}).get("flexcontainer")
    if not isinstance(flex, dict):
        sys.exit("[erro] sem root/containerpy/flexcontainer — estrutura diferente da esperada; nada feito")
    botoes = [(f"{XF}/jcr:content/root/containerpy/flexcontainer/{item}/{k}", v)
              for item, iv in flex.items() if isinstance(iv, dict)
              for k, v in iv.items() if isinstance(v, dict) and rt(v) == "button"]
    if len(botoes) != 2:
        sys.exit(f"[erro] esperava 2 botões, achei {len(botoes)}; nada feito")
    muda = []
    for caminho, no in botoes:
        atual = no.get("cq:styleIds") or []
        print(f"  {caminho[len(XF):]}  {no.get('jcr:title')!r}\n      cq:styleIds {atual} -> {ALVO}" + ("   (= já está)" if atual == ALVO else ""))
        if atual != ALVO:
            muda.append(caminho)
    if not muda:
        print("  nada a gravar (idempotente)"); return
    if not executar:
        print("  [dry-run] nada gravado. Use --executar."); return
    pasta = DADOS / "backup_xf"; pasta.mkdir(parents=True, exist_ok=True)
    bk = pasta / f"products-contact-block__master__{datetime.datetime.now():%Y-%m-%d_%H%M%S}.json"
    json.dump({"quando": datetime.datetime.now().isoformat(timespec="seconds"), "xf": XF, "jcr_content": jc}, open(bk, "w"), indent=1, ensure_ascii=False)
    print(f"  backup -> {bk}")
    for caminho in muda:
        r = alterar(caminho, {"cq:styleIds": ALVO, "cq:styleIds@TypeHint": "String[]"}, True)
        print(f"  [{r}] {caminho[len(XF):]}")
    st, depois = ler(f"{XF}/jcr:content", ".infinity.json")
    for caminho, _ in botoes:
        no = depois
        for parte in caminho[len(XF) + len("/jcr:content/"):].split("/"):
            no = no[parte]
        print(f"  conferido: {caminho[len(XF):]} cq:styleIds = {no.get('cq:styleIds')}" + ("  OK" if no.get("cq:styleIds") == ALVO else "  DIVERGE"))


if __name__ == "__main__":
    main()
