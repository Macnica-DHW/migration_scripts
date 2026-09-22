#!/usr/bin/env python3
"""
xf_lado_a_lado.py — põe os blocos de um Experience Fragment da copia-teste
LADO A LADO, como no GWI, em vez de empilhados.

Por que existe: o XF `products-contact-block/master` (embutido em 104 das 135
páginas) e o `signup-and-contact-experience-fragment/master` (4) vieram do
migrador antigo como `containerpy > <x>_wrap > componente`, um `_wrap` embaixo
do outro — cada um é um container de largura cheia com 50px de padding, então
os botões "Contact Us for More Information" e "Request a Quote" saem
empilhados com um vão enorme. No GWI eles estão em duas colunas (w=5 | w=5).
Apontado pelo Hazael em 21/09/2026.

O que faz (a mesma gramática de coluna que o motor emite, ESPEC §2.2):

    containerpy
      flexcontainer                       cq:styleIds ['', 1719484596357]  (SP 1 Column)
        flexcontaineritem_1 > <componentes do 1º grupo de _wrap>
        flexcontaineritem_2 > <componentes do 2º grupo de _wrap>
      <x>_wrap                            apagados

Os `_wrap` são distribuídos em ordem de documento em N colunas iguais
(`--colunas`, padrão 2): o contact-block tem 2 wraps -> 1 componente por
coluna; o signup tem 4 (texto, botão, texto, botão) -> 2 por coluna, como
no GWI. Botão em coluna leva ['', Fixed Minimum Width, Center]: o padrão do
link-button é min-width 550px e dois não cabem lado a lado abaixo de ~1200px.
Propriedades dos componentes copiadas 1:1.

`--par-ao-centro` — APOSENTADO em 21/09/2026: o CSS do site não tem variante de celular para
`.right`, então abaixo de 1050px (itens empilhados) o 1º botão encostava à direita e o 2º à
esquerda em qualquer janela entre 376 e 1049px. O Hazael decidiu Center nos dois; no global2 isso
é o `golive/xf_botoes_centro.py`. Fica aqui só como registro do que foi feito na copia-teste.
Descrição original (só para XF de 1 botão por coluna): com Center em cada
coluna os botões ficam no meio de cada METADE da página, 317px um do outro
@1400; no GWI o par fica junto no centro (vão de 81px). A flag põe o 1º
botão Right, o último sem posição (= esquerda) e o gap Large (50px): medido
277–675 | 725–1070, vão centrado em x=700. Funciona também sobre um XF que
já tem o flexcontainer (só regrava os cq:styleIds).

ATENÇÃO: os dois XFs foram criados e editados à mão por bruno.jaques
(10/09 e 15/09/2026). Backup do jcr:content inteiro antes de gravar
(scripts-hazael/xf_<nome>_backup_<data>.json). Escreve só dentro de
`root/containerpy`. Não mexe em linkURL (ainda apontam para o GWI; as
páginas-alvo não existem na copia-teste) nem no resourceType da página
(`page` em vez de `xfpage` — item separado).

    python3 xf_lado_a_lado.py products-contact-block                 # dry-run
    python3 xf_lado_a_lado.py products-contact-block --par-ao-centro --executar
    python3 xf_lado_a_lado.py signup-and-contact-experience-fragment --colunas 2 --executar
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))

from aem_lib import CONFIG, build_session, get_json, post_node

XF_RAIZ = "/content/experience-fragments/copia-teste/americas/mai/en/site"
RT = {
    "flex": "macnicaglobal2/components/content/flexcontainer",
    "item": "macnicaglobal2/components/content/flexcontaineritem",
}
S_FLEX_SP_1COL = "1719484596357"
S_BTN_FIXEDMIN = "1722936853890"
S_BTN_CENTER = "1717669229626"
S_BTN_RIGHT = "1717669230937"
S_FLEX_GAP_LARGE = "1718800456497"       # --gap 50px (padrão 26px)
INVOLUCROS = {"container", "responsivegrid"}


def par_ao_centro(cp):
    """Payload que junta o par de botões no CENTRO DA PÁGINA, como no GWI (lá: 376–701 | 782–1026,
    vão de 81px). Com Center em cada coluna os botões ficam no meio de cada metade, com 317px de
    vão @1400. Aqui: botão da 1ª coluna Right, o da última sem posição (= esquerda), gap Large."""
    flex = cp.get("flexcontainer", {})
    itens = [k for k, v in flex.items() if isinstance(v, dict) and rt(v) == "flexcontaineritem"]
    payload = {"flexcontainer/cq:styleIds": [S_FLEX_GAP_LARGE, S_FLEX_SP_1COL],
               "flexcontainer/cq:styleIds@TypeHint": "String[]"}
    for item, estilos in ((itens[0], ["", S_BTN_FIXEDMIN, S_BTN_RIGHT]), (itens[-1], ["", S_BTN_FIXEDMIN])):
        for ck, cv in flex[item].items():
            if isinstance(cv, dict) and rt(cv) == "button":
                payload[f"flexcontainer/{item}/{ck}/cq:styleIds"] = estilos
                payload[f"flexcontainer/{item}/{ck}/cq:styleIds@TypeHint"] = "String[]"
                print(f"    {item}/{ck}: cq:styleIds {cv.get('cq:styleIds')} -> {estilos}")
    return payload


def rt(no):
    return str(no.get("sling:resourceType", "")).split("/")[-1]


def componentes(no):
    """Componentes (não-invólucro) diretamente dentro de um `_wrap`."""
    return [(k, v) for k, v in no.items()
            if isinstance(v, dict) and k != "cq:responsive" and rt(v) not in INVOLUCROS]


def copiar(payload, base, no, estilos_botao):
    payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
    for k, v in no.items():
        if isinstance(v, dict) or k in ("jcr:primaryType",):
            continue
        if k == "cq:styleIds" and rt(no) == "button" and estilos_botao:
            continue
        if isinstance(v, list):
            payload[f"{base}/{k}"] = v
            payload[f"{base}/{k}@TypeHint"] = "String[]"
        else:
            payload[f"{base}/{k}"] = v
    if rt(no) == "button" and estilos_botao:
        payload[f"{base}/cq:styleIds"] = ["", S_BTN_FIXEDMIN, S_BTN_CENTER]
        payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xf", help="nome do XF sob .../site, ex: products-contact-block")
    ap.add_argument("--colunas", type=int, default=2)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--par-ao-centro", action="store_true",
                    help="junta o par de botões no centro da página (Right | esquerda, gap Large); "
                         "vale também para um XF que já tem o flexcontainer")
    args = ap.parse_args()

    sessao, auth = build_session()
    base_url = CONFIG["base_url"]
    xf = f"{XF_RAIZ}/{args.xf}/master"
    jcr, st = get_json(sessao, f"{base_url}{xf}/jcr:content.infinity.json", auth)
    if st != 200 or not jcr:
        print(f"[erro] {xf}: HTTP {st}")
        sys.exit(1)
    print(f"XF: {xf}\n  criado por {jcr.get('jcr:createdBy')} em {jcr.get('jcr:created')}\n"
          f"  último editor: {jcr.get('cq:lastModifiedBy')} em {jcr.get('cq:lastModified')}")
    cp = jcr.get("root", {}).get("containerpy")
    if not isinstance(cp, dict):
        print("[erro] sem root/containerpy — estrutura diferente da esperada; nada feito")
        sys.exit(1)

    def gravar(payload):
        bk = _RAIZ / "scripts-hazael" / f"xf_{args.xf}_backup_{datetime.datetime.now():%Y-%m-%d_%H%M%S}.json"
        json.dump({"quando": datetime.datetime.now().isoformat(), "xf": xf, "jcr_content": jcr},
                  open(bk, "w"), indent=1)
        print(f"  backup -> {bk}")
        st, txt = post_node(sessao, base_url, f"{xf}/jcr:content/root/containerpy", payload, auth)
        print(f"  [gravado] HTTP {st}" if st in (200, 201) else f"  [FALHA] HTTP {st} {txt[:150]}")
        return st in (200, 201)

    wraps = [(k, v) for k, v in cp.items()
             if isinstance(v, dict) and k != "cq:responsive" and rt(v) in INVOLUCROS]
    if "flexcontainer" in cp:
        if not args.par_ao_centro:
            print("  já existe um flexcontainer em containerpy — nada a fazer (idempotente)")
            return
        print("\n  flexcontainer já existe; só os estilos do par:")
        payload = par_ao_centro(cp)
        if not args.executar:
            print("  [dry-run] nada gravado. Use --executar.")
            return
        gravar(payload)
        return
    if not wraps:
        print("  já não há _wrap em containerpy — nada a fazer")
        return
    n = args.colunas
    if len(wraps) % n:
        print(f"[erro] {len(wraps)} wraps não se dividem em {n} colunas; nada feito")
        sys.exit(1)
    por_coluna = len(wraps) // n

    payload = {"flexcontainer/jcr:primaryType": "nt:unstructured",
               "flexcontainer/sling:resourceType": RT["flex"],
               "flexcontainer/cq:styleIds": ["", S_FLEX_SP_1COL],
               "flexcontainer/cq:styleIds@TypeHint": "String[]"}
    print(f"\n  {len(wraps)} wraps -> {n} colunas de {por_coluna}:")
    for i in range(n):
        item = f"flexcontainer/flexcontaineritem_{i + 1}"
        payload[f"{item}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{item}/sling:resourceType"] = RT["item"]
        for wk, wv in wraps[i * por_coluna:(i + 1) * por_coluna]:
            for ck, cv in componentes(wv):
                copiar(payload, f"{item}/{ck}", cv, estilos_botao=True)
                rotulo = cv.get("jcr:title") or (str(cv.get("text", ""))[:40] if cv.get("text") else "")
                print(f"    coluna {i + 1}: {ck} [{rt(cv)}] {rotulo!r}   (de {wk})")
    for wk, _ in wraps:
        payload[f"{wk}@Delete"] = "true"
    print(f"\n  {len(payload)} chaves no payload; apaga: {[w for w, _ in wraps]}")
    if not args.executar:
        print("  [dry-run] nada gravado. Use --executar.")
        return

    if gravar(payload) and args.par_ao_centro:
        jcr, st = get_json(sessao, f"{base_url}{xf}/jcr:content.infinity.json", auth)
        print("\n  estilos do par:")
        gravar(par_ao_centro(jcr["root"]["containerpy"]))


if __name__ == "__main__":
    main()
