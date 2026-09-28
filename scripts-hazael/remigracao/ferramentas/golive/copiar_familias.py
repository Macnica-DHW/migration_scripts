#!/usr/bin/env python3
"""copiar_familias.py — a cópia final: staging/<família> -> global2/.../semiconductors/<família>. Dry-run por padrão.

NÃO SOBRESCREVE NADA. Para cada família, imediatamente antes de copiar, `_comum.copiar` relê o destino
ao vivo: se `G/<família>` existir (ou existir com outra grafia), ABORTA — é trabalho da Anion ou de
outra pessoa. Sem `:replace`: o Sling também recusa. Não reordena as irmãs (isso gravaria no nó da
landing, que é da Anion): as famílias novas entram no fim.

Tira um retrato de TODAS as páginas de G antes e depois e compara: o que já existia não pode ter sumido
nem ter sido modificado por nós. Retratos e diferença em dados/golive/.
"""
import json, sys
from _comum import DADOS, G, NOSSAS, STG, copiar, eh_nossa, familias, ler, retrato_global2
from staging import paginas


def main():
    executar = "--executar" in sys.argv
    fams = [f for f in familias() if ler(f"{STG}/{f}")[0] == 200]
    print(f"{'EXECUTANDO' if executar else 'dry-run'} — {len(fams)} famílias, {len(paginas(STG))} páginas no staging")
    antes = retrato_global2()
    json.dump(antes, open(DADOS / "retrato_g2_antes.json", "w"), indent=1)
    print(f"  global2 antes: {len(antes)} páginas; famílias lá: {sorted({p[len(G):].strip('/').split('/')[0] for p in antes if p != G})}")
    for f in fams:
        print(f"  {f}:", copiar(f"{STG}/{f}", f"{G}/{f}", executar))
    if not executar:
        return
    depois = retrato_global2()
    json.dump(depois, open(DADOS / "retrato_g2_depois.json", "w"), indent=1)
    novas = sorted(set(depois) - set(antes))
    sumiram = sorted(set(antes) - set(depois))
    mudaram = [(p, antes[p], depois[p]) for p in antes if p in depois and antes[p] != depois[p]]
    fora = [p for p in novas if p[len(G):].strip("/").split("/")[0] not in fams]
    print(f"\n  global2 depois: {len(depois)} páginas; novas {len(novas)} (esperado {len(paginas(STG))}); novas FORA das nossas famílias: {fora}")
    print(f"  páginas que já existiam e SUMIRAM: {sumiram}")
    for p, a, d in mudaram:
        print(f"  mudou durante a janela: {p[len(G):]}  por {d[2]}" + ("   <-- FOMOS NÓS?!" if eh_nossa(d[2], NOSSAS) else "  (edição de outra pessoa, em paralelo)"))
    ruim = bool(sumiram or fora or [m for m in mudaram if eh_nossa(m[2][2], NOSSAS)] or len(novas) != len(paginas(STG)))
    print("  RESULTADO:", "CONFERIR" if ruim else "só acréscimos, dentro das nossas famílias")
    sys.exit(1 if ruim else 0)


if __name__ == "__main__":
    main()
