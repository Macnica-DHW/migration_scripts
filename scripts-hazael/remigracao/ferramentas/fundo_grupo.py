#!/usr/bin/env python3
"""
fundo_grupo.py — pinta o fundo por GRUPO SEMÂNTICO, não por seção.

Por que existe: no global2 nenhuma das 270 seções coloridas tem um bloco só
(mínimo 2, média 3,8). A faixa embrulha um grupo funcional inteiro —
{título+intro+imagem}, {a spec}, {o formulário} —, e o motor da remigração
pinta no máximo UMA seção por página (a que é só `tabs`), o que deixa 131 das
135 páginas inteiramente brancas. Alternar por SEÇÃO não resolve: como seção =
um filho de topo do GWI, a `/ambarella` viraria 24 listras dentro de 5 ideias.

Este script agrupa primeiro e pinta depois. Escreve SÓ a propriedade
`backgroundColor` nos containers de seção; não cria, não apaga e não mexe em
estilo, padding nem conteúdo. Idempotente: rodar de novo não muda nada.

    python3 fundo_grupo.py /ambarella /canon              # dry-run (padrão)
    python3 fundo_grupo.py /ambarella --executar
    python3 fundo_grupo.py /ambarella --limpar --executar # tira toda a cor

Fronteira de grupo: título de abertura `type=h2`, ou papel de fecho
(cta/related/índice). Seção que é só `<hr>` gruda no grupo anterior.
Nunca pinta: o primeiro grupo, os grupos de fecho e grupo com <2 blocos —
é o que o global2 faz (última seção branca em 220 de 238).
"""
import argparse
import json
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))

from aem_lib import CONFIG, build_session, get_json, post_node

RAIZ_DESTINO = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"
F7 = "rgb(247,247,247)"   # faixa padrão do corpus autoral
EB = "rgb(235,235,235)"   # 2ª cor, quando dois grupos coloridos se encostam
IGN = {"container", "flexcontainer", "flexcontaineritem", "responsivegrid"}

# Nenhuma das 270 seções coloridas do global2 tem menos que 2 blocos, e a faixa
# mais fina medida a 1400px tem 218px. Abaixo disso não é faixa, é tira.
MIN_BLOCOS = 2
PISO_FAIXA_PX = 200       # usado pelo conferidor (ferramentas/faixas.py)


def blocos(no, saida):
    """Componentes-folha de uma seção, em ordem."""
    for chave, valor in no.items():
        if not isinstance(valor, dict) or chave == "cq:responsive":
            continue
        rt = str(valor.get("sling:resourceType", "")).split("/")[-1]
        if rt and rt not in IGN:
            saida.append((rt, valor))
        blocos(valor, saida)
    return saida


def texto(valor):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(valor or ""))).strip()


def so_divisor(bs):
    """Seção que é só um <hr> — divisor DENTRO do grupo, não fronteira."""
    return (len(bs) == 1 and bs[0][0] == "text"
            and not re.sub(r"<[^>]+>|&nbsp;|\s", "", bs[0][1].get("text", "") or ""))


def papel(bs):
    tipos = {rt for rt, _ in bs}
    if "experiencefragment" in tipos or "form" in tipos:
        return "cta"
    if "anchorlink" in tipos:
        return "indice"
    if "list" in tipos and tipos <= {"list", "title"}:
        return "related"
    if tipos & {"tabs"}:
        return "spec"
    return "corpo"


FECHO = ("cta", "related", "indice")


def agrupar(itens):
    """[(nome, nó)] -> [grupo]. Grupo = corrida de seções da mesma ideia."""
    grupos = []
    for i, (nome, no) in enumerate(itens):
        bs = blocos(no, [])
        primeiro = bs[0] if bs else None
        titulo = (primeiro[1].get("jcr:title")
                  if primeiro and primeiro[0] == "title" else None)
        pap = papel(bs)
        nova = (not grupos
                or (titulo and primeiro[1].get("type") == "h2")
                or pap in FECHO
                or grupos[-1]["papel"] in FECHO)
        if so_divisor(bs) and grupos:
            nova = False
        if nova:
            grupos.append({"papel": pap, "nomes": [nome], "i": [i],
                           "titulo": texto(titulo), "nb": len(bs)})
        else:
            grupos[-1]["nomes"].append(nome)
            grupos[-1]["i"].append(i)
            grupos[-1]["nb"] += len(bs)
            if grupos[-1]["papel"] == "corpo" and pap != "corpo":
                grupos[-1]["papel"] = pap
    return grupos


def pintar(grupos):
    """Decide a cor de cada grupo. Devolve os grupos com a chave `cor`."""
    anterior = None
    for j, g in enumerate(grupos):
        if j == 0 or g["papel"] in FECHO or g["nb"] < MIN_BLOCOS:
            g["cor"] = None
            anterior = None
            continue
        g["cor"] = F7 if anterior is None else None
        anterior = g["cor"]
    # dois coloridos encostados: o segundo troca de cor (lei medida, 211/211)
    for j in range(1, len(grupos)):
        if grupos[j]["cor"] and grupos[j]["cor"] == grupos[j - 1]["cor"]:
            grupos[j]["cor"] = EB
    return absorver_ilhas(grupos)


def absorver_ilhas(grupos):
    """Grupo pequeno demais para ser faixa também é pequeno demais para ser VÃO.

    Medido a 1400px: a faixa mais fina de todo o global2 tem 218px, e nenhuma
    fica abaixo de 200px. O índice de âncoras da `/ambarella` (1 bloco) ficava
    branco entre duas faixas `#f7f7f7` e rendia uma tira de 126px — mais fina
    que qualquer coisa da referência. Faixa fina é sintoma de cor errada
    (diretriz do Hazael, 21/09/2026).

    Mesma régua dos dois lados: `MIN_BLOCOS` já impede pintar grupo com menos
    de 2 blocos (no global2 são 0 de 270); aqui ele também impede que um grupo
    desses ABRA um vão. Se os dois vizinhos têm a mesma cor, a ilha some dentro
    deles. Grupo grande entre duas faixas continua sendo vão legítimo — é o
    `branco` de 685px da `sony-imx939`, que a referência tem e é para manter.
    """
    for j in range(1, len(grupos) - 1):
        g, ant, prox = grupos[j], grupos[j - 1], grupos[j + 1]
        if g["nb"] >= MIN_BLOCOS:
            continue
        if ant["cor"] is not None and ant["cor"] == prox["cor"] != g["cor"]:
            g["cor"] = ant["cor"]
            g["absorvido"] = True
    return grupos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paginas", nargs="+", help="caminhos relativos, ex: /ambarella")
    ap.add_argument("--executar", action="store_true", help="grava (padrão é dry-run)")
    ap.add_argument("--limpar", action="store_true", help="remove toda cor em vez de pintar")
    args = ap.parse_args()

    sessao, auth = build_session()
    base = CONFIG["base_url"]

    for rel in args.paginas:
        destino = RAIZ_DESTINO + "/" + rel.strip("/")
        dados, st = get_json(sessao, f"{base}{destino}/jcr:content.20.json", auth)
        if st != 200 or not dados:
            print(f"[erro] {rel}: HTTP {st}")
            continue
        cont = dados.get("root", {}).get("container")
        if not isinstance(cont, dict):
            print(f"[erro] {rel}: sem root/container")
            continue
        itens = [(k, v) for k, v in cont.items()
                 if isinstance(v, dict) and k != "cq:responsive"]
        grupos = pintar(agrupar(itens))

        # cor desejada por nome de seção
        desejado = {}
        for g in grupos:
            for nome in g["nomes"]:
                desejado[nome] = None if args.limpar else g["cor"]

        payload = {}
        for nome, no in itens:
            atual = no.get("backgroundColor")
            alvo = desejado.get(nome)
            if atual == alvo:
                continue
            if alvo is None:
                payload[f"{nome}/backgroundColor@Delete"] = "true"
            else:
                payload[f"{nome}/backgroundColor"] = alvo

        print(f"\n=== {rel}  —  {len(itens)} seções -> {len(grupos)} grupos ===")
        for j, g in enumerate(grupos):
            cor = "BRANCO" if not g["cor"] else g["cor"]
            print(f"  grupo {j} [{g['papel']:7}] seções {g['i'][0]:>2}–{g['i'][-1]:<2} "
                  f"{g['nb']:>3} blocos  {cor:16} \"{g['titulo'][:42]}\"")
        if not payload:
            print("  nada a mudar (já está assim)")
            continue
        print(f"  {len(payload)} propriedade(s) a gravar:")
        for k, v in sorted(payload.items()):
            print(f"     {k} = {v}")
        if not args.executar:
            print("  [dry-run] nada foi gravado. Use --executar.")
            continue
        st, txt = post_node(sessao, base, f"{destino}/jcr:content/root/container",
                            payload, auth)
        print(f"  [gravado] HTTP {st}" if st in (200, 201)
              else f"  [FALHA] HTTP {st} {txt[:120]}")


if __name__ == "__main__":
    main()
