#!/usr/bin/env python3
"""
Cria os dois XFs de popup que o form container do global2 EXIGE
(successFragmentPath / errorFragmentPath), no espelho de XFs da copia-teste.

  <AEM_EF_ROOT>/popups/form-success/master     "Success"
  <AEM_EF_ROOT>/popups/form-error/master       "Error"

Estrutura copiada de /content/experience-fragments/macnicaglobal2/apac/gfei/en/
site/popups/form-success (cq:Page + xfpage + container > container > popup >
container > title + text); textos dos popups do GWI (…/macnicagwi/americas/
mai/en/site/landingpage_popups/form-success/master1 e form-error/master).

NÃO sobrescreve: se o XF já existe, não faz nada. Escreve só sob
/content/experience-fragments/copia-teste (a trava do aem_lib garante).
Autorizado pelo Hazael em 18/09/2026 (ver PESQUISA-formulario.md).

COMO RODAR (de scripts-hazael/)
  python3 remigracao/ferramentas/criar_xf_popups.py             # só mostra
  python3 remigracao/ferramentas/criar_xf_popups.py --executar
"""
import argparse
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, build_session, get_json, post_node  # noqa: E402

XF_TEMPLATE = "/conf/macnicaglobal2/settings/wcm/templates/xf-web-variation"
POPUPS = [
    ("form-success", "Form Success", "Success",
     "<p>Your request was sent. A member of our team will be in touch with you soon!</p>"),
    ("form-error", "Form Error", "Error",
     "<p>There was an error submitting your message, please try again later.</p>"),
]


def payload_xf(titulo_xf, titulo, texto):
    c = "master/jcr:content/root/container/popup/container"
    return {
        "jcr:primaryType": "cq:Page",
        "jcr:content/jcr:primaryType": "cq:PageContent",
        "jcr:content/jcr:title": titulo_xf,
        "jcr:content/cq:template": "/libs/cq/experience-fragments/components/experiencefragment/template",
        "jcr:content/sling:resourceType": "cq/experience-fragments/components/experiencefragment",
        "master/jcr:primaryType": "cq:Page",
        "master/jcr:content/jcr:primaryType": "cq:PageContent",
        "master/jcr:content/jcr:title": titulo_xf,
        "master/jcr:content/cq:template": XF_TEMPLATE,
        "master/jcr:content/cq:xfMasterVariation": "true",
        "master/jcr:content/cq:xfMasterVariation@TypeHint": "Boolean",
        "master/jcr:content/cq:xfVariantType": "web",
        # xfpage, NÃO page: com `page` o seletor `content` devolve um documento
        # HTML inteiro aninhado (o defeito dos dois XFs feitos à mão em 10/09)
        "master/jcr:content/sling:resourceType": "macnicaglobal2/components/xfpage",
        "master/jcr:content/root/jcr:primaryType": "nt:unstructured",
        "master/jcr:content/root/layout": "responsiveGrid",
        "master/jcr:content/root/sling:resourceType": "macnicaglobal2/components/content/container",
        "master/jcr:content/root/container/jcr:primaryType": "nt:unstructured",
        "master/jcr:content/root/container/sling:resourceType": "macnicaglobal2/components/content/container",
        "master/jcr:content/root/container/popup/jcr:primaryType": "nt:unstructured",
        "master/jcr:content/root/container/popup/sling:resourceType": "macnicaglobal2/components/content/popup",
        f"{c}/jcr:primaryType": "nt:unstructured",
        f"{c}/sling:resourceType": "macnicaglobal2/components/content/container",
        f"{c}/title/jcr:primaryType": "nt:unstructured",
        f"{c}/title/sling:resourceType": "macnicaglobal2/components/content/title",
        f"{c}/title/jcr:title": titulo,
        f"{c}/title/type": "h2",
        f"{c}/text/jcr:primaryType": "nt:unstructured",
        f"{c}/text/sling:resourceType": "macnicaglobal2/components/content/text",
        f"{c}/text/text": texto,
        f"{c}/text/textIsRich": "true",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", default=CONFIG["ef_root"].rstrip("/") + "/popups")
    ap.add_argument("--executar", action="store_true")
    args = ap.parse_args()
    base = CONFIG["base_url"]
    session, auth = build_session(verbose=False)

    pasta, st = get_json(session, f"{base}{args.raiz}.json", auth)
    print(f"pasta {args.raiz}: {'existe' if pasta is not None else 'NÃO existe -> cria sling:OrderedFolder'}")
    if pasta is None and args.executar:
        st, txt = post_node(session, base, args.raiz,
                            {"jcr:primaryType": "sling:OrderedFolder", "jcr:title": "popups"}, auth)
        print("   ->", st)
        if st not in (200, 201):
            sys.exit(f"[erro] não criou a pasta: {txt}")

    for nome, titulo_xf, titulo, texto in POPUPS:
        caminho = f"{args.raiz}/{nome}"
        ja, _ = get_json(session, f"{base}{caminho}.json", auth)
        if ja is not None:
            print(f"{caminho}: JÁ EXISTE — não toco")
            continue
        p = payload_xf(titulo_xf, titulo, texto)
        print(f"{caminho}: criaria {len(p)} propriedades ({titulo!r})")
        if args.executar:
            st, txt = post_node(session, base, caminho, p, auth)
            print("   ->", st, "" if st in (200, 201) else txt)
    if not args.executar:
        print("\n(diagnóstico — nada foi escrito; use --executar)")


if __name__ == "__main__":
    main()
