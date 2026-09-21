#!/usr/bin/env python3
"""copiar_xfs.py — cria no global2 os XFs que as páginas do escopo embutem. Dry-run por padrão.

O global2 não tem XF de site (só header e footer). Cria
`experience-fragments/macnicaglobal2/americas/mai/en/site/` com o MESMO caminho relativo da copia-teste,
para o `fragmentVariationPath` mudar só de prefixo:

  site/popups/{form-success,form-error}   já são XF de verdade -> cópia da pasta inteira
  site/products-contact-block             na copia-teste a "raiz" é um sling:Folder com uma página
  site/signup-and-contact-...             dentro; aqui a raiz nasce como XF de verdade (cq:Page +
                                          template de experiencefragment, como o `footer`) e o `master`
                                          é copiado para dentro. `master/jcr:content` passa de
                                          `components/page` para `components/xfpage` + cq:xfMasterVariation.

Depois reescreve as referências DENTRO dos XFs novos (os botões apontavam para /content/macnicagwi).
Só cria; se `site` já existir e não for nosso, aborta (ver _comum.py).
"""
import sys
from _comum import XF_G2, XF_T, alterar, copiar, criar, filhos, ler
from _reescrita import mapa_assets, mudancas, payload

RAIZ_XF = {"jcr:primaryType": "cq:Page", "jcr:content/jcr:primaryType": "cq:PageContent",
           "jcr:content/cq:template": "/libs/cq/experience-fragments/components/experiencefragment/template",
           "jcr:content/sling:resourceType": "cq/experience-fragments/components/experiencefragment"}


def main():
    executar = "--executar" in sys.argv
    print("EXECUTANDO" if executar else "dry-run")
    print("  site:", criar(XF_G2, {"jcr:primaryType": "sling:OrderedFolder", "jcr:title": "Site"}, executar))
    for nome in filhos(XF_T):
        st, j = ler(f"{XF_T}/{nome}", ".2.json")
        tipo = j.get("jcr:primaryType")
        if tipo == "cq:Page" or "master" not in j:              # XF de verdade, ou pasta de XFs: copia inteiro
            print(f"  {nome} [{tipo}] cópia inteira:", copiar(f"{XF_T}/{nome}", f"{XF_G2}/{nome}", executar))
            continue
        titulo = (j["master"].get("jcr:content") or {}).get("jcr:title", nome)
        print(f"  {nome} [{tipo} -> XF de verdade] raiz:", criar(f"{XF_G2}/{nome}", {**RAIZ_XF, "jcr:content/jcr:title": titulo}, executar), end="")
        print("  master:", copiar(f"{XF_T}/{nome}/master", f"{XF_G2}/{nome}/master", executar), end="")
        print("  xfpage:", alterar(f"{XF_G2}/{nome}/master/jcr:content",
                                   {"sling:resourceType": "macnicaglobal2/components/xfpage", "cq:xfMasterVariation": "true",
                                    "cq:xfMasterVariation@TypeHint": "Boolean"}, executar) if executar else "dry")

    # referências dentro dos XFs: na origem (dry-run) ou já no destino (executar)
    base, assets = (XF_G2 if executar else XF_T), mapa_assets()
    st, arv = ler(base, ".infinity.json")
    muda, erros = [], []
    mudancas(arv, base, assets, muda, erros)
    for caminho, prop, antes, depois in muda:
        print(f"  ref {caminho[len(base):]} · {prop}\n      - {antes}\n      + {depois}")
        if executar:
            alterar(caminho, payload(prop, depois), True)
    for e in erros:
        print("  [SOBROU]", e)
    print(f"{len(muda)} referências reescritas; {len(erros)} sobras")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
