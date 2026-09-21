#!/usr/bin/env python3
"""staging.py — cópia da árvore revisada para `copia-teste/.../semiconductors-golive`. Dry-run por padrão.

O staging existe para o global2 só receber página PRONTA: a reescrita de referências e a conferência
acontecem aqui, dentro da copia-teste; a árvore revisada (T) não é tocada e continua sendo a referência.
Entram as famílias de _comum.familias() (sem canon e design-gateway, que são da Anion no destino), sem a
landing e sem as 4 páginas de teste. Cópia servidor-a-servidor: o que foi revisado, byte a byte.
"""
import sys
from _comum import BASE, STG, T, TESTE, apagar_no_staging, copiar, criar, familias, ler, sessao


def paginas(raiz):
    r = sessao.get(BASE + "/bin/querybuilder.json", timeout=180, params={
        "path": raiz, "type": "cq:Page", "p.limit": "-1", "p.hits": "selective", "p.properties": "jcr:path"})
    return sorted(h["jcr:path"][len(raiz):] for h in r.json()["hits"] if h["jcr:path"] != raiz)


def main():
    executar = "--executar" in sys.argv
    fams = familias()
    print(f"{'EXECUTANDO' if executar else 'dry-run'} — {len(fams)} famílias: {fams}")
    _, t = ler(T, "/jcr:content.json")
    print("  raiz:", criar(STG, {"jcr:primaryType": "cq:Page", "jcr:content/jcr:primaryType": "cq:PageContent",
                                 "jcr:content/jcr:title": "STAGING do go-live — NÃO REVISAR, NÃO EDITAR",
                                 "jcr:content/cq:template": t["cq:template"], "jcr:content/sling:resourceType": t["sling:resourceType"],
                                 "jcr:content/hideInNav": "true"}, executar))
    for f in fams:
        print(f"  {f}:", copiar(f"{T}/{f}", f"{STG}/{f}", executar))
    for p in sorted(TESTE):
        st, _ = ler(STG + p)
        if st == 200:
            print(f"  tira página de teste {p}:", apagar_no_staging(STG + p, executar))
    esperado = [p for p in paginas(T) if p.strip("/").split("/")[0] in fams and p not in TESTE]
    if executar:
        tem = paginas(STG)
        print(f"páginas: esperado {len(esperado)}, staging {len(tem)}; faltando {sorted(set(esperado) - set(tem))[:5]}; sobrando {sorted(set(tem) - set(esperado))[:5]}")
        sys.exit(0 if tem == esperado else 1)
    print(f"páginas que entram: {len(esperado)}")


if __name__ == "__main__":
    main()
