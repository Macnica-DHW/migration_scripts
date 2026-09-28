#!/usr/bin/env python3
"""
pixels.py <print.png>... [--json] — leitura VISUAL de um print full-page do GLOBAL2: faixas cinza, respiro dentro
delas, vãos entre blocos e o fundo dos botões finais. SOMENTE LEITURA (só lê o PNG; nenhuma requisição).
Também é módulo: `from pixels import analisa, resumo`.

Pressupostos do print (o que render.py e `aem_screenshot.py --full --publicado` produzem):
  - página inteira, janela de 1400px, FORA do editor (?wcmmode=disabled: no modo de edição cada container ganha um
    placeholder de 29px e os vãos incham); rolada antes (imagem lazy); o PNG sai com 1412px de largura (os 12px a
    mais são do cabeçalho/rodapé, em toda página);
  - tema do global2: fundo branco rgb(255,255,255), faixa cinza rgb(247,247,247) (tolerância de 2 por canal), barra
    roxa do breadcrumb debaixo do cabeçalho e rodapé roxo (R>90, G<60, B>90; o roxo é rgb(127,16,128)).
    O conteúdo = do fim da barra roxa do breadcrumb até o começo do rodapé (roxo por 200 linhas seguidas).
    Print do GWI NÃO serve: outro tema (cabeçalho/rodapé azul-marinho rgb(12,35,85), fundo cinza 239, sem roxo) —
    dá ValueError;
  - fundo da linha = a cor do pixel em x=8 (borda esquerda: fora de qualquer conteúdo, a página não tem margem);
  - "tinta" = pixel entre x=40 e x=1300 que difere do fundo da linha em mais de 24 num canal. Essa faixa de x deixa
    de fora o widget fixo "Page Top" (x 1328–1411), que aparece no print em toda altura de tela e fingiria respiro
    0px dentro da faixa.

Saída de analisa(): H, ini/fim (conteúdo), faixas [{topo, base, alt, resp_topo, resp_base}] (resp = respiro
interno: linhas sem tinta entre a borda da faixa e o 1º/último bloco; nas páginas aprovadas, 37–50px),
vaos [{y, vao, troca_fundo}] (linhas sem tinta entre blocos; troca_fundo = o vão cruza a borda de uma faixa),
fundo_botoes (fundo do último bloco antes do rodapé: TEM de ser "branco") e ult (y do último bloco).
Diretriz de vão: fechar os de mais de ~125px (os aprovados ficam em ~121px ou menos), sem encostar blocos.

    cd scripts-hazael
    python3 remigracao/ferramentas/pagina/pixels.py remigracao/dados/paginas/<nome>/<nome>__g2__antes.png
    python3 remigracao/ferramentas/pagina/pixels.py antes.png depois.png --json
"""
import argparse
import json
import sys

import numpy as np
from PIL import Image

CINZA = np.array([247, 247, 247]); BRANCO = np.array([255, 255, 255])
X_BORDA, X0, X1 = 8, 40, 1300          # x0..x1 exclui o "Page Top" fixo (x 1328–1411)
LIMIAR_TINTA = 24
VAO_MOSTRA, VAO_GRANDE = 100, 125


def analisa(arq, x0=X0, x1=X1):
    im = np.asarray(Image.open(arq).convert("RGB")).astype(int); H = im.shape[0]
    borda = im[:, X_BORDA, :]                                        # cor de fundo da linha (borda esquerda)

    def eh(c, alvo):
        return np.abs(c - alvo).max(axis=-1) <= 2
    fundo_cinza, fundo_branco = eh(borda, CINZA), eh(borda, BRANCO)
    miolo = im[:, x0:x1, :]
    tinta = (np.abs(miolo - borda[:, None, :]).max(axis=-1) > LIMIAR_TINTA).any(axis=1)
    # cabeçalho: fim da barra roxa do breadcrumb; rodapé: 1ª linha roxa por 200 linhas seguidas
    roxo = (borda[:, 0] > 90) & (borda[:, 1] < 60) & (borda[:, 2] > 90)
    ini = next((i for i in range(H) if roxo[i]), None)
    if ini is None:
        raise ValueError(f"{arq}: sem o roxo do cabeçalho do global2 — print do GWI, do editor ou de outra largura?")
    ini = next((i for i in range(ini, H) if not roxo[i]), H)
    fim = next((i for i in range(ini, H - 200) if roxo[i:i + 200].all()), None)
    if fim is None:
        raise ValueError(f"{arq}: sem o rodapé roxo do global2 — print cortado (não é --full)?")
    # faixas cinza (corridas de fundo cinza entre ini e fim)
    faixas, y = [], ini
    while y < fim:
        if fundo_cinza[y]:
            a = y
            while y < fim and fundo_cinza[y]:
                y += 1
            if y - a >= 20:
                t = np.where(tinta[a:y])[0]
                faixas.append(dict(topo=a, base=y, alt=y - a, resp_topo=int(t[0]) if len(t) else None,
                                   resp_base=int(y - a - 1 - t[-1]) if len(t) else None))
        y += 1
    # blocos de tinta e vãos (linhas sem tinta), marcando se o vão cruza troca de fundo
    blocos, y = [], ini
    while y < fim:
        if tinta[y]:
            a = y
            while y < fim and tinta[y]:
                y += 1
            blocos.append((a, y))
        y += 1
    vaos = []
    for (a0, b0), (a1, b1) in zip(blocos, blocos[1:]):
        troca = len({("c" if fundo_cinza[k] else "b" if fundo_branco[k] else "o") for k in range(b0, a1)}) > 1
        vaos.append(dict(y=b0, vao=a1 - b0, troca_fundo=troca))
    # botões finais: último bloco de tinta antes do rodapé — fundo da linha
    ult = blocos[-1] if blocos else None
    fundo_botoes = None
    if ult:
        m = (ult[0] + ult[1]) // 2
        fundo_botoes = "cinza" if fundo_cinza[m] else "branco" if fundo_branco[m] else str(tuple(int(c) for c in borda[m]))
    return dict(H=H, largura=int(im.shape[1]), ini=ini, fim=fim, faixas=faixas, vaos=vaos, fundo_botoes=fundo_botoes,
                ult=list(ult) if ult else None)


def resumo(d):
    """Uma linha: fundo dos botões, faixas (altura, respiro topo/base), vãos >= 100 (* = cruza borda de faixa,
    ! = 125 ou mais)."""
    fx = " ".join(f"[{x['alt']} {x['resp_topo']}/{x['resp_base']}]" for x in d["faixas"]) or "-"
    vs = " ".join(f"{v['vao']}{'*' if v['troca_fundo'] else ''}{'!' if v['vao'] >= VAO_GRANDE else ''}"
                  for v in d["vaos"] if v["vao"] >= VAO_MOSTRA) or "-"
    aviso = "" if d["fundo_botoes"] == "branco" else "  <- botões finais têm de estar no BRANCO"
    return f"botões={d['fundo_botoes']}{aviso}  faixas[alt resp_topo/resp_base]={fx}  vãos>={VAO_MOSTRA}: {vs}  altura={d['H']}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prints", nargs="+")
    ap.add_argument("--json", action="store_true", help="o dicionário inteiro, em vez do resumo")
    a = ap.parse_args()
    erro = False
    for f in a.prints:
        try:
            d = analisa(f)
        except (ValueError, OSError) as e:
            print(e, file=sys.stderr); erro = True; continue
        print(json.dumps({"print": f, **d}, indent=1) if a.json else f"{f}\n   {resumo(d)}")
    sys.exit(1 if erro else 0)


if __name__ == "__main__":
    main()
