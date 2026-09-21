#!/usr/bin/env python3
"""reescrever_refs.py — aplica a tabela de _reescrita.py em TODA página do staging. Dry-run por padrão.

Grava só propriedade que muda, nó a nó, e só dentro do staging (a árvore revisada e o global2 não
entram: ver _comum.alterar). Log completo `página · nó · prop · antes · depois` em
dados/golive/reescrita_<modo>.csv. Idempotente: a 2ª execução tem de dar 0 mudanças.
Sai com 1 se sobrar qualquer referência a copia-teste / macnicagwi (asset fora do mapa, por exemplo).
"""
import collections, csv, sys
from _comum import DADOS, STG, aborta, alterar, ler
from _reescrita import mapa_assets, mudancas, payload
from staging import paginas


def main():
    executar = "--executar" in sys.argv
    assets = mapa_assets()
    pags = paginas(STG)
    print(f"{'EXECUTANDO' if executar else 'dry-run'} — {len(pags)} páginas no staging")
    log, sobras = [], []
    for rel in pags:
        st, j = ler(f"{STG}{rel}/jcr:content", ".infinity.json")
        if st != 200:
            aborta(f"HTTP {st} lendo {rel} — não reescrevo página que não li inteira")
        muda, erros = [], []
        mudancas(j, f"{STG}{rel}/jcr:content", assets, muda, erros)
        sobras += [(rel,) + e for e in erros]
        for caminho, prop, antes, depois in muda:
            log.append([rel, caminho.split("/jcr:content", 1)[1], prop, antes, depois])
            if executar:
                alterar(caminho, payload(prop, depois), True)
    with open(DADOS / f"reescrita_{'exec' if executar else 'dry'}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["pagina", "no", "prop", "antes", "depois"]); w.writerows(log)
    print(f"{len(log)} propriedades mudam em {len({l[0] for l in log})} páginas:", dict(collections.Counter(l[2] for l in log)))
    for s in sobras[:20]:
        print("  [SOBROU]", s)
    print(f"sobras: {len(sobras)}")
    sys.exit(1 if sobras else 0)


if __name__ == "__main__":
    main()
