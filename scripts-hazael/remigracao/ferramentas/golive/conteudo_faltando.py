#!/usr/bin/env python3
"""
conteudo_faltando.py [--executar] [--so REL...] — conteúdo que o GWI mostra e a página do global2 não tem (a seção
"Content missing from the page" do global2_links_pending_<data>.html). Dry-run por padrão.

Pedido do Hazael (24/09/2026): "Work on the 'Content missing from the page' section of the pending pages. For pages that
need a grid, you can use …/solutions/imaging-and-vision.html as a reference" — a aba Suppliers/Partners: container >
flexcontainer "1 Column" (empilha só no celular) > 4 flexcontaineritem por linha > image com link (R59/R62).

Mudança ESTRUTURAL (nós entram e saem), então PILOTO em 1 página e mostrar ao Hazael antes das outras. Cada página é
uma lista fechada de operações (PAGINAS abaixo), com precondição conferida no dry-run E relida antes de gravar:
  asset   cópia do DAM do GWI para o do global2 (`<nome>@CopyFrom` com POST só na pasta do global2; sha1 e GET conferidos)
  props   grava propriedades num nó que existe (4º elemento opcional: valores que o nó TEM de ter agora)
  criar   cria um nó que não existe (na ordem dada; `:order` quando precisa de posição)
  apagar  apaga um nó que existe e está VAZIO (sem fileReference/linkURL/text/jcr:title) — placeholder
  remover apaga um nó COM conteúdo, conferindo antes o que ele tem (lista de (subnó, prop, valor))
  mover   move um nó (Sling :operation=move) — depois, a subárvore no destino tem de ser igual à de antes
Conferência depois, a página inteira contra o backup:
  JCR     só mudam os nós declarados (e o carimbo da página);
  render  HTML normalizado idêntico ANTES da 1ª e DEPOIS da última diferença; o miolo é listado (texto que saiu/entrou);
  print   1400px, animação desligada, fixed/sticky escondidos: igual acima da mudança e igual no fim alinhado pelo rodapé.
Entrada com "feito" já foi gravada (fica como registro); "pagina" quando a chave não é o caminho (2ª passada).
Backup (jcr:content inteiro + render + print) ANTES de gravar, em dados/golive/backup_conteudo_<data>/. Trava da Session vale.

    python3 conteudo_faltando.py                          # dry-run: operações e precondições de cada página
    python3 conteudo_faltando.py --executar --so products
"""
import argparse
import datetime
import difflib
import html
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corrigir_links as C  # noqa: E402  (sessao com trava, ler, url, retrato, achatar, CARIMBO_PAGINA)
from aem_lib import parse_cookie_string  # noqa: E402

M = C.M
DADOS = C.DADOS
G2_DAM = "/content/dam/macnicaglobal2/americas/mai/en"
GWI_DAM = "/content/dam/macnicagwi/americas/mai/public/en"
RT = "macnicaglobal2/components/content/"
GWI = "/content/macnicagwi/americas/mai/en"
S_FLEX_1COL = "1719484596357"                                    # flexcontainer: 1 Column (sp-flex-direction-column)
S_FLEX_GAP0, S_FLEX_GAP_LARGE = "1718800458698", "1718800456497"  # flexcontainer: No Spacing / Large (entre itens)
S_CONT_PAD_SMALL, S_CONT_PAD_W0 = "1717498052331", "1717498055877"   # container: padding Small (altura) / No Padding (largura)
S_CONT_PAD_H0 = "1717498056876"                                  # container: No Padding (altura)
S_BTN_MINW, S_BTN_CENTER = "1722936853890", "1717669229626"      # button: Fixed Minimum Width / Center
sessao = C.sessao
_gwi = {}


def de_gwi(no, prop="text"):
    """Propriedade de um nó do GWI — só GET (a fonte do conteúdo que entra)."""
    if no not in _gwi:
        st, j = C.ler(no, ".json")
        assert st == 200 and "macnicagwi" in no, (no, st)
        _gwi[no] = j
    return _gwi[no][prop]


def de_g2(no, prop):
    st, j = C.ler(no, ".json")
    assert st == 200, (no, st)
    return j.get(prop)


def troca(h, de, para):
    """URLs do GWI -> global2 no HTML copiado; sobrar `macnicagwi` é erro."""
    h = h.replace(de, para)
    assert "macnicagwi" not in h, h[:200]
    return h


def img(ref, alt, link=None, legenda=None):
    """image do global2 com o alt autoral valendo na tela (R49: altValueFromDAM ausente vale true)."""
    d = {"sling:resourceType": RT + "image", "fileReference": ref, "alt": alt, "altValueFromDAM": "false",
         "isDecorative": "false", "titleValueFromDAM": "false", "displayPopupTitle": "false"}
    if link:
        d.update(linkURL=link, linkTarget="_self")
    if legenda:
        d["jcr:title"] = legenda
    return d


def texto(h):
    return {"sling:resourceType": RT + "text", "text": h, "textIsRich": "true"}


def titulo(t, tipo="h1"):
    return {"sling:resourceType": RT + "title", "jcr:title": t, "type": tipo}


def tabela(h):
    return {"sling:resourceType": RT + "table", "text": h, "textIsRich": "true"}


def botao(t, link, estilos=(S_BTN_MINW, S_BTN_CENTER)):
    """button do global2: o próprio componente põe o .html em link interno."""
    return {"sling:resourceType": RT + "button", "jcr:title": t, "linkURL": link, "linkTarget": "_self",
            "cq:styleIds": list(estilos)}


def container(estilos):
    return {"sling:resourceType": RT + "container", "cq:styleIds": list(estilos)}


def flex(estilos=(S_FLEX_1COL,)):
    return {"sling:resourceType": RT + "flexcontainer", "cq:styleIds": list(estilos)}


ITEM = {"sling:resourceType": RT + "flexcontaineritem"}


def xf(nome):
    return {"sling:resourceType": RT + "experiencefragment",
            "fragmentVariationPath": f"/content/experience-fragments/macnicaglobal2/americas/mai/en/site/{nome}/master"}


def centra_celulas(h):
    """Conversão das tabelas da connect-tech no global2 (medida nas 5 vizinhas: G2 == GWI com isto, e nada mais)."""
    return re.sub(r"<(th|td)>", r'<\1 style="text-align: center;">', h)


def card_produto(nome, alvo, foto, alt):
    """Card da landing /products como no GWI (imagetext com isHeading=false): nome em negrito, centrado, como link, EM
    CIMA da foto, e a foto também linkada. Link de texto com .html (sem ele: 302 -> 403); o image põe o .html sozinho."""
    return [("text_1", texto(f'<p style="text-align: center;"><b><a href="{M}/{alvo}.html">{nome}</a></b></p>')),
            ("image_1", img(f"{G2_DAM}/images/products/{foto}", alt, f"{M}/{alvo}"))]


def grade(base, cards, por_linha=4):
    """flexcontainer 1 Column com `por_linha` flexcontaineritem — o desenho da aba Suppliers/Partners da imaging-and-vision."""
    ops = [("criar", f"{base}/flexcontainer_1", flex())]
    for i, filhos in enumerate(cards, 1):
        item = f"{base}/flexcontainer_1/flexcontaineritem_{i}"
        ops.append(("criar", item, ITEM))
        ops += [("criar", f"{item}/{nome}", props) for nome, props in filhos]
    return ops


def grade_logos(base, cards, antes):
    """Uma linha = container (padding Small, sem padding lateral) > flexcontainer 1 Column > 4 flexcontaineritem com image
    (logo em tela única 458x240 da R62, legenda = nome, link) — exatamente a aba Suppliers/Partners da imaging-and-vision,
    inclusive o item vazio que completa a última linha (R61)."""
    ops = []
    for n, i in enumerate(range(0, len(cards), 4), 1):
        linha = f"{base}/container_{n}"
        ops += [("criar", linha, container((S_CONT_PAD_SMALL, S_CONT_PAD_W0)), f"before {antes}"),
                ("criar", f"{linha}/flexcontainer_1", flex())]
        for k in range(4):
            item = f"{linha}/flexcontainer_1/flexcontaineritem_{k + 1}"
            ops.append(("criar", item, ITEM))
            if i + k < len(cards):
                nome, alvo, arq = cards[i + k]
                ops.append(("criar", f"{item}/image_1", img(f"{CARDS}/{arq}", nome, f"{M}/{alvo}", legenda=nome)))
    return ops


CARDS = f"{G2_DAM}/about-us/partner-with-macnica/cards"           # logos 458x240 da R62, já no DAM (processados)
FORNECEDORES_BM = [   # ordem, nome e link do supplierlist do GWI (orderBy productManufacturerRanking), 24/09
    ("Connect Tech", "products/boards-modules/connect-tech", "card-connect-tech-logo.png"),
    ("Hitek Systems", "products/boards-modules/hitek-systems", "card-hiteklogo-0.png"),
    ("IBASE", "products/boards-modules/ibase", "card-ibas-logo.png"),
    ("IEI", "products/boards-modules/iei", "card-iei.png"),
    ("iENSO", "products/boards-modules/ienso", "card-ienso-logo.png"),
    ("Mpression", "products/boards-modules/mpression", "card-mpression.png"),
    ("Reflex CES", "products/boards-modules/reflex-ces", "card-reflexces-logo-horizontal-nobaseline.png"),
    ("Silex Technology", "products/boards-modules/silex", "card-silex-logo.png"),
    ("Terasic", "products/boards-modules/terasic", "card-terasic-technologies.png"),
    ("TQ Systems", "products/boards-modules/tq-systems", "card-logo-tq-systems-svg.png"),
    ("Transcend", "products/boards-modules/transcend", "card-transcend-logo-trimmed.png"),
]
TQ = "products/boards-modules/tq-systems"
DHW_LAYERSCAPE = "/content/macnicaglobal2/americas/dhw/tq-systems/tq-embedded-qoriqr-layerscape"
LAYERSCAPE_TIT = "TQ Embedded QorIQ® Layerscape"
IEI = "products/boards-modules/iei/iei-smart-healthcare-panel-pcs-terminals-and-computing"
W_IEI = f"{GWI}/{IEI}/jcr:content/root/container/container/container"
W_CT = f"{GWI}/products/boards-modules/connect-tech/jcr:content/root/container/container/container/tabs/item_1756394056435"
MB991 = "products/boards-modules/ibase/embedded-computing/mb991"
W_MB = f"{GWI}/{MB991}/jcr:content/root/container/container"
MBA8 = f"{TQ}/tq-embedded-arm-modules/mba8mp-ras314-single-board-computer"
IMG_IEI = (f"{GWI_DAM}/images/products/", f"{G2_DAM}/products/boards-modules/iei/")
IMG_MB = f"{G2_DAM}/products/boards-modules/ibase/images"
PDF_ROB = f"{G2_DAM}/downloads/robotics-solution-brief.pdf"
PDF_MBA = f"{G2_DAM}/images/pdfs/EMB_Whitepaper_MBa8MP-RAS314_EN_Rev0101.pdf"


# ---------------------------------------------------------------- páginas (lista fechada)
# achado/mudanca: em inglês, vão para o relatório (dados/mapas/global2_content_fixes_<data>.html)
PAGINAS = {
    "products": {
        "feito": "piloto 24/09 23:45, backup_conteudo_2026-09-24_234543",
        "gwi": "/content/macnicagwi/americas/mai/en/products",
        "o_que": "4 cards de categoria (em branco: 4 image sem imagem, larguras 2/2+1/3+4/2) -> grade de 4 (texto-link + foto "
                 "linkada), coluna 8+2 como o resto da página; banner (image vazio) -> products-banner.jpg do GWI",
        "achado": "The four category cards (Semiconductors, Boards & Modules, Displays, IP & Software) were blank: four image "
                  "components with no image, caption or link, at uneven widths. The banner under the title was an empty image too.",
        "mudanca": "Built the four cards as a 4-column grid (the Suppliers/Partners grid of Imaging & Vision): each card is the "
                   "category name in bold as a link, above the category photo, also linked — as on the GWI. The photos were "
                   "already in the global2 DAM and have the same proportions, so the cards come out the same size. The grid "
                   "uses the same column width as the text above. Copied the banner (products-banner.jpg) from the GWI into "
                   "the global2 DAM and put it in the empty banner image. Kept the GWI's alt text “mo” on the Boards & "
                   "Modules photo (a GWI typo, migrated as is).",
        "assets": [(f"{GWI_DAM}/banners/products-banner.jpg", f"{G2_DAM}/images/products/products-banner.jpg")],
        "ops": [
            ("props", "root/container/image", img(f"{G2_DAM}/images/products/products-banner.jpg", "Products")),
            ("apagar", "root/container/container/image"),
            ("apagar", "root/container/container/image_1021195315"),
            ("apagar", "root/container/container/image_1899426112"),
            ("apagar", "root/container/container/image_66652080"),
            ("props", "root/container/container", {"cq:styleIds": [S_CONT_PAD_SMALL, S_CONT_PAD_W0]}),
            ("props", "root/container/container/cq:responsive/default", {"width": "8", "offset": "2"}),
        ] + grade("root/container/container", [
            card_produto("Semiconductors", "products/semiconductors", "iStock-1773543830.jpg", "Semiconductors"),
            card_produto("Boards &amp; Modules", "products/boards-modules", "Boards-generic.jpg", "mo"),  # alt do GWI (erro dele)
            card_produto("Displays", "products/displays", "TouchDisplay-generic.jpg", "Displays"),
            card_produto("IP and Software", "products/ip-software", "IP-Software.jpg", "IP & Software"),
        ]),
    },
    "products#padding": {
        "pagina": "products",
        "feito": "24/09 23:48, backup_conteudo_2026-09-24_234845",
        "o_que": "piloto: o container da grade volta ao padding vertical PADRÃO (50px, o que tinha antes); fica só o 'sem "
                 "padding lateral', que alinha a grade com o texto. O 'Small' (30px) encolheu o vão até o rodapé (28px; GWI ~80)",
        "mudanca": "Second pass: restored the grid container's original vertical spacing (the first pass had reduced the gap "
                   "above the footer to 28px); the gaps are now 57px above the cards and 50px below (GWI: 50 and 48).",
        "ops": [("props", "root/container/container", {"cq:styleIds": [S_CONT_PAD_W0]},
                 {"cq:styleIds": [S_CONT_PAD_SMALL, S_CONT_PAD_W0]})],
    },
    f"{TQ}/tq-embedded-x86-modules": {
        "feito": "25/09 00:23, backup_conteudo_2026-09-25_002342",
        "gwi": f"{GWI}/{TQ}/tq-embedded-x86-modules",
        "o_que": "título 'TQ Embedded QorIQ® Layerscape' -> pageTitle; list da DHW Layerscape -> filhos da própria página; "
                 "os 2 botões de contato nos 2 flexcontaineritem VAZIOS depois da lista (como na irmã Layerscape)",
        "achado": "The page is a copy of the Layerscape page that was never finished: the heading said “TQ Embedded QorIQ® "
                  "Layerscape”, the product list showed the 14 Layerscape products of the DHW site instead of this page's "
                  "own x86 products, and the contact block was missing (its two slots were empty).",
        "mudanca": "Heading set to the page title “TQ Embedded x86 Modules” (as on the GWI). Product list now lists this "
                   "page's own products. Added the two contact buttons (Contact Us for More Information, Request a Quote) in "
                   "the two empty slots after the list, like the sister Layerscape page. Note: the list also shows the 4 "
                   "soft-deleted duplicate pages under this page on the author (see “Found, not changed”).",
        "ops": [
            ("props", "root/container/container/title", {"jcr:title": "TQ Embedded x86 Modules"}, {"jcr:title": LAYERSCAPE_TIT}),
            ("props", "root/container/container_1214227721/list", {"parentPage": f"{M}/{TQ}/tq-embedded-x86-modules"},
             {"parentPage": DHW_LAYERSCAPE}),
            ("criar", "root/container/container_1214227721/flexcontainer_copy/flexcontaineritem/button",
             botao("Contact Us for More Information", f"{M}/contact/form")),
            ("criar", "root/container/container_1214227721/flexcontainer_copy/flexcontaineritem_1364030293/button",
             botao("Request a Quote", f"{M}/request-a-quote")),
        ],
    },
    f"{TQ}/tq-embedded-arm-modules": {
        "feito": "25/09 00:23, backup_conteudo_2026-09-25_002342",
        "gwi": f"{GWI}/{TQ}/tq-embedded-arm-modules",
        "o_que": "título 'TQ Embedded QorIQ® Layerscape' -> pageTitle 'TQ Embedded ARM Modules' (fora da lista de pendências)",
        "achado": "Not on the pending list, found while checking the x86 page: the heading also said “TQ Embedded QorIQ® "
                  "Layerscape”.",
        "mudanca": "Heading set to the page title “TQ Embedded ARM Modules” (as on the GWI).",
        "ops": [("props", "root/container/container/title", {"jcr:title": "TQ Embedded ARM Modules"}, {"jcr:title": LAYERSCAPE_TIT})],
    },
    "products/boards-modules/transcend": {
        "feito": "25/09 00:23, backup_conteudo_2026-09-25_002342",
        "gwi": f"{GWI}/products/boards-modules/transcend",
        "o_que": "botão 'View Transcend's Memory Product Portfolio' -> #productportfolio embaixo do texto da intro; id "
                 "'productportfolio' no título 'Product Portfolio' (o título do tema já compensa o header fixo: cai em y=85)",
        "achado": "The “View Transcend's Memory Product Portfolio” button under the introduction was missing.",
        "mudanca": "Added the button under the introduction text; it jumps to the “Product Portfolio” heading (anchor "
                   "“productportfolio”, the GWI's name, set on that heading — nothing visible changes there). Tested: the "
                   "heading lands right under the fixed menu with the tabs visible.",
        "ops": [
            ("props", "root/container/container_1759409534/container_797504348/container/title_copy_copy",
             {"id": "productportfolio"}, {"id": None, "jcr:title": "Product Portfolio"}),
            ("criar", "root/container/container_273709292/flexcontainer/flexcontaineritem_45562908/button",
             botao("View Transcend's Memory Product Portfolio", "#productportfolio", (S_BTN_MINW,))),
        ],
    },
    "products/boards-modules/connect-tech": {
        "feito": "25/09 00:23, backup_conteudo_2026-09-25_002342",
        "gwi": f"{GWI}/products/boards-modules/connect-tech",
        "o_que": "seção NVIDIA Jetson AGX Xavier (h3 com link + Carrier Boards + tabela) entre Orin NX e Xavier NX, na aba 1, "
                 "no mesmo desenho das vizinhas (container sem padding > title h1 + table com células centradas)",
        "achado": "In the NVIDIA Jetson tab, the whole “NVIDIA Jetson AGX Xavier” section was missing (between Orin NX/Orin "
                  "Nano and Xavier NX): the heading with its link, the “Carrier Boards” heading and the table (Rogue, Rogue-X).",
        "mudanca": "Added the section in its place, built like the sections around it (same heading and table styles).",
        "ops": [
            ("criar", "root/container/container_654932871/tabs/item_1/text_agx_xavier",
             texto(troca(de_gwi(f"{W_CT}/text_copy_copy_copy__1793979345"), f"{GWI}/", f"{M}/")), "before text_1098323651"),
            ("criar", "root/container/container_654932871/tabs/item_1/container_agx_xavier",
             container((S_CONT_PAD_W0, S_CONT_PAD_H0)), "before text_1098323651"),
            ("criar", "root/container/container_654932871/tabs/item_1/container_agx_xavier/title_text", titulo("Carrier Boards")),
            ("criar", "root/container/container_654932871/tabs/item_1/container_agx_xavier/table",
             tabela(centra_celulas(de_gwi(f"{W_CT}/table_1576245494_cop_1758683425")))),
        ],
    },
    IEI: {
        "feito": "25/09 00:28, backup_conteudo_2026-09-25_002837",
        "gwi": f"{GWI}/{IEI}",
        "o_que": "Fitness Panel PC (título + tabela FIT1) no fim do bloco Point-of-care/Bedside; Surgical Monitors (título + "
                 "tabela) antes do 2º Ordering Information; a 2ª tabela de Ordering (cópia da 1ª, MMS-21CA) -> a do GWI "
                 "(MMS-27CH); 6 imagens das tabelas copiadas para products/boards-modules/iei/",
        "achado": "Two sections were missing: “Fitness Panel PC” (FIT1 table) and “Surgical Monitors” (27\" surgical "
                  "monitors table). The second “Ordering Information” table was a copy of the first one (endoscopy "
                  "monitors, MMS-21CA) instead of the surgical monitors' (MMS-27CH).",
        "mudanca": "Added both sections in their GWI places, with the same heading and table styles as the tables around them; "
                   "copied their 6 product images from the GWI into the global2 DAM (next to the other IEI images). Replaced "
                   "the duplicated table with the surgical monitors' ordering table from the GWI.",
        "assets": [(f"{IMG_IEI[0]}{n}", f"{IMG_IEI[1]}{n}") for n in (
            "FIT1-W15A-IMX6.png", "FIT1-W15A-IMX6_0.png", "FIT1-W15A-IMX6_1.png", "37.png", "32.png", "31.png")],
        "ops": [
            ("criar", "root/container/container_596104355/container_388357440/title_table_fitness", titulo("Fitness Panel PC")),
            ("criar", "root/container/container_596104355/container_388357440/table_fitness",
             tabela(troca(de_gwi(f"{W_IEI}/table_1535815130"), *IMG_IEI))),
            ("criar", "root/container/container_596104355/container_1484924223/title_table_surgical", titulo("Surgical Monitors"),
             "before title_table_535668141"),
            ("criar", "root/container/container_596104355/container_1484924223/table_surgical",
             tabela(troca(de_gwi(f"{W_IEI}/table_128058284"), *IMG_IEI)), "before title_table_535668141"),
            ("props", "root/container/container_596104355/container_1484924223/table_190094126",
             {"text": de_gwi(f"{W_IEI}/table_544712201")},
             {"text": ("sem_espaço", de_g2(f"{M}/{IEI}/jcr:content/root/container/container_596104355/container_1484924223/"
                                           "table_523589597", "text"))}),   # a 2ª é cópia da 1ª (só quebras de linha diferem)
        ],
    },
    MB991: {
        "feito": "25/09 00:36, backup_conteudo_2026-09-25_003612",
        "gwi": f"{GWI}/{MB991}",
        "o_que": "intro (textwithimage) e Features eram da MI997 -> texto, imagem (MB991.jpeg, já no DAM) e lista da MB991 do "
                 "GWI; os 2 botões Contact/RaQ (o GWI não tem) -> XF signup-and-contact (o bloco de newsletter do GWI)",
        "achado": "The introduction, its image and the Features list described a different board (the MI997 Mini-ITX, 12th "
                  "Gen Intel) — only Specifications and Ordering Information were MB991's. The newsletter block (“Stay up to "
                  "date on the latest news from Macnica Partners.” / Sign up) was missing; in its place were Contact Us / "
                  "Request a Quote buttons that the GWI page does not have.",
        "mudanca": "Replaced the introduction text, the image (the MB991 photo already in the global2 DAM) and the Features "
                   "list with MB991's from the GWI, keeping the existing layout. Replaced the two buttons with the site's "
                   "newsletter block (the global2 “SignUp and Contact” fragment, as on the GWI).",
        "ops": [
            ("props", "root/container/container/container_525028952/textwithimage",
             {"text": f"<h3>{de_gwi(f'{W_MB}/heading')}</h3>\r\n" + re.sub(r"<p>(?:&nbsp;|\xa0)</p>\s*", "", de_gwi(f"{W_MB}/text")),   # sem os parágrafos vazios (padrão da mb990)
              "fileReference": f"{IMG_MB}/MB991.jpeg", "alt": "MB991 board"},
             {"fileReference": f"{IMG_MB}/MI997.png", "alt": "MI997 board", "text": ("contém", "The MI997 Mini-ITX motherboard")}),
            ("props", "root/container/container/container_525028952/textwithimage/spImage",
             {"fileReference": f"{IMG_MB}/MB991.jpeg"}, {"fileReference": f"{IMG_MB}/MI997.png"}),
            ("props", "root/container/container/container_1107099960/text",
             {"text": de_gwi(f"{W_MB}/container/imagetext/text")}, {"text": ("contém", "12th Gen Intel® Processor Support")}),
            ("remover", "root/container/text_3_wrap/flexcontainer_copy",
             [("flexcontaineritem/button", "jcr:title", "Contact Us for More Information"),
              ("flexcontaineritem_861351158/button", "jcr:title", "Request a Quote")]),
            ("criar", "root/container/text_3_wrap/experiencefragment", xf("signup-and-contact-experience-fragment")),
        ],
    },
    MBA8: {
        "feito": "25/09 00:23, backup_conteudo_2026-09-25_002342",
        "gwi": f"{GWI}/{MBA8}",
        "o_que": "parágrafo do whitepaper (link para o PDF) no fim do bloco Features; PDF copiado do GWI para images/pdfs/",
        "achado": "The paragraph linking to the whitepaper (“Read the whitepaper for prototype transition, support resources, "
                  "and more information.”) was missing, and the PDF was not in the global2 DAM.",
        "mudanca": "Copied the PDF from the GWI into the global2 DAM and added the paragraph with its link under the Features "
                   "list, where the GWI has it.",
        "assets": [(f"{GWI_DAM}/images/pdfs/EMB_Whitepaper_MBa8MP-RAS314_EN_Rev0101.pdf", PDF_MBA)],
        "ops": [("criar", "root/container/container_features/text_whitepaper",
                 texto(troca(de_gwi(f"{W_MB.replace(MB991, MBA8)}/container/text_164081127"),
                             f"{GWI_DAM}/images/pdfs/", f"{G2_DAM}/images/pdfs/")))],
    },
    "solutions/robotics-amrs": {
        "feito": "25/09 00:28, backup_conteudo_2026-09-25_002837",
        "gwi": f"{GWI}/technology/robotics-amrs",
        "o_que": "botão 'Download Macnica’s Robotics Solutions Brief' (PDF copiado para downloads/) ao lado do Contact Us, "
                 "como no GWI: flexcontainer (No Spacing + 1 Column, o par de botões da casa) com o botão novo e o button_1 "
                 "MOVIDO (mesmo nó, mesmas propriedades)",
        "achado": "The “Download Macnica’s Robotics Solutions Brief” button next to “Contact Us” was missing, and the PDF was "
                  "not in the global2 DAM.",
        "mudanca": "Copied the PDF from the GWI into the global2 DAM and added the download button; the two buttons now sit "
                   "side by side as on the GWI (the existing Contact Us button was moved into the pair, unchanged).",
        "assets": [(f"{GWI_DAM}/downloads/robotics-solution-brief.pdf", PDF_ROB)],
        "ops": [
            ("criar", "root/container/container_1/container_2/flexcontainer_1", flex((S_FLEX_GAP0, S_FLEX_1COL)), "before button_1"),
            ("criar", "root/container/container_1/container_2/flexcontainer_1/flexcontaineritem_1", ITEM),
            ("criar", "root/container/container_1/container_2/flexcontainer_1/flexcontaineritem_1/button",
             botao(de_gwi(f"{GWI}/technology/robotics-amrs/jcr:content/root/container/container/resizablecontainer/button",
                          "jcr:title"), PDF_ROB)),
            ("criar", "root/container/container_1/container_2/flexcontainer_1/flexcontaineritem_2", ITEM),
            ("mover", "root/container/container_1/container_2/button_1",
             "root/container/container_1/container_2/flexcontainer_1/flexcontaineritem_2/button_1"),
        ],
    },
    "solutions/robotics-amrs#empilhar": {
        "feito": "25/09 00:34, backup_conteudo_2026-09-25_003417",
        "pagina": "solutions/robotics-amrs",
        "o_que": "2ª passada: o botão de download do global2 é a variante link-button--download (14px, 51px de altura, ícone) e "
                 "o normal tem 57px -> lado a lado ficaram 13px desalinhados, e o Contact Us tinha saído do lugar. Contact Us "
                 "VOLTA para o lugar original (mesmo nó, movido de volta), o par sai, e o Download entra logo ACIMA dele, "
                 "empilhado e centrado (como os botões de download da company-profile)",
        "mudanca": "Second pass: the site gives buttons that point to a file a different, shorter design, so side by side the "
                   "two buttons were 13px out of line. The Contact Us button went back exactly where it was, and the download "
                   "button now sits just above it, centred — like the other download buttons on the site (e.g. Company Profile).",
        "ops": [
            ("mover", "root/container/container_1/container_2/flexcontainer_1/flexcontaineritem_2/button_1",
             "root/container/container_1/container_2/button_1"),
            ("remover", "root/container/container_1/container_2/flexcontainer_1",
             [("flexcontaineritem_1/button", "jcr:title", "Download Macnica’s Robotics Solutions Brief"),
              ("flexcontaineritem_1/button", "linkURL", PDF_ROB)]),
            ("criar", "root/container/container_1/container_2/button_download",
             botao("Download Macnica’s Robotics Solutions Brief", PDF_ROB), "before button_1"),
        ],
    },
    "solutions/broadcast-proav-solutions/st-2110-at-scale-resources": {
        "feito": "25/09 00:28, backup_conteudo_2026-09-25_002837",
        "gwi": f"{GWI}/technology/Broadcast-ProAV-Solutions/ST-2110-at-Scale-Resources",
        "o_que": "2º bloco de contato do GWI (XF products-contact-block/master1, só esta página usa) -> 3 botões NA PÁGINA, "
                 "depois do bloco atual: Contact Us / Request a Quote / Request Evaluation Kit (flexcontainer Large + 1 Column, "
                 "como o XF de cima)",
        "achado": "The GWI shows a second contact block under the first one (Contact Us / Request a Quote / Request "
                  "Evaluation Kit); global2 had only the first.",
        "mudanca": "Added the three buttons under the existing contact block, on this page only (the GWI block is used by "
                   "no other page), with the same button style as the block above.",
        "ops": [
            ("criar", "root/container/container_2/container_2/flexcontainer_1", flex((S_FLEX_GAP_LARGE, S_FLEX_1COL))),
        ] + [op for i, (t, alvo) in enumerate([("Contact Us", "contact/form"), ("Request a Quote", "request-a-quote"),
                                                ("Request Evaluation Kit", "contact/request-evaluation-kit")], 1)
             for op in (("criar", f"root/container/container_2/container_2/flexcontainer_1/flexcontaineritem_{i}", ITEM),
                        ("criar", f"root/container/container_2/container_2/flexcontainer_1/flexcontaineritem_{i}/button",
                         botao(t, f"{M}/{alvo}")))],
    },
    "about-us/privacy-policy/privacy-policy-for-california-residents": {
        "feito": "25/09 01:35, backup_conteudo_2026-09-25_013518",
        "gwi": f"{GWI}/about-us/privacy-policy/privacy-policy-for-california-residents",
        "o_que": "Zipteam: linkURL https://www.zipteam.com/ no título 'Zipteam service ( www.zipteam.com )' (decisão do Hazael, "
                 "25/09: 'Link the heading'); o title v2 não tem 'abrir em nova aba' (como os títulos linkados em 24/09)",
        "achado": "The GWI links the domain www.zipteam.com to https://www.zipteam.com/; in global2 the domain is inside the "
                  "heading “Zipteam service ( www.zipteam.com )”, not linked.",
        "mudanca": "Linked the heading to https://www.zipteam.com/ (the whole heading is the link; a linked heading looks the "
                   "same as an unlinked one). The global2 heading component has no “open in a new tab” option, so it opens in "
                   "the same tab, like the headings linked on 24/09.",
        "ops": [("props", "root/container/text_4_wrap/title_text_4", {"linkURL": "https://www.zipteam.com/"},
                 {"linkURL": None, "jcr:title": "Zipteam service ( www.zipteam.com )"})],
    },
    "products/boards-modules": {
        "feito": "25/09 00:36, backup_conteudo_2026-09-25_003612",
        "gwi": f"{GWI}/products/boards-modules",
        "o_que": "grade dos 11 fornecedores do supplierlist do GWI (logos 458x240 já no DAM em partner-with-macnica/cards, "
                 "legenda = nome, link para a página do fornecedor), 3 linhas de 4 como a imaging-and-vision; o botão único "
                 "(https://www.macnica.com/…/contact/form/, aba nova) -> XF products-contact-block (Contact + RaQ)",
        "achado": "The whole supplier grid (11 logo cards: Connect Tech, Hitek Systems, IBASE, IEI, iENSO, Mpression, Reflex "
                  "CES, Silex Technology, Terasic, TQ Systems, Transcend) was missing — the link comparison could not see it "
                  "because the GWI builds it from the child pages. The only button, “Contact Us for More Information”, went "
                  "to https://www.macnica.com/americas/mai/en/contact/form/ (hard-coded domain, new tab); “Request a Quote” "
                  "was missing.",
        "mudanca": "Built the supplier grid like the Suppliers/Partners grid of Imaging & Vision: 3 rows of 4 cards, each the "
                   "supplier's logo (the same-size logo files already in the global2 DAM) with its name as caption, linking "
                   "to the supplier's page, in the GWI's order. Replaced the single button with the site's standard contact "
                   "block (Contact Us for More Information + Request a Quote, internal links), as on the GWI.",
        "ops": grade_logos("root/container/container_498772245", FORNECEDORES_BM, "button") + [
            ("remover", "root/container/container_498772245/button",
             [("", "jcr:title", "Contact Us for More Information"),
              ("", "linkURL", "https://www.macnica.com/americas/mai/en/contact/form/")]),
            ("criar", "root/container/container_498772245/experiencefragment", xf("products-contact-block")),
        ],
    },
}


# ---------------------------------------------------------------- precondições
CONTEUDO = ("fileReference", "linkURL", "text", "jcr:title", "fragmentVariationPath", "tableData")


def no_de(j, rel):
    for p in rel.split("/"):
        if not isinstance(j, dict) or p not in j:
            return None
        j = j[p]
    return j


def confere(atual, esperado):
    """esperado: valor exato, ("contém", trecho) ou ("sem_espaço", valor) — igual tirando espaço/quebra de linha e entidades (&quot; x &#34;)."""
    if isinstance(esperado, tuple) and esperado[0] == "contém":
        return esperado[1] in (atual or "")
    if isinstance(esperado, tuple) and esperado[0] == "sem_espaço":
        return re.sub(r"\s+", "", html.unescape(atual or "")) == re.sub(r"\s+", "", html.unescape(esperado[1]))
    return atual == esperado


def conferir(pag, cfg, jc):
    """Lista de problemas (vazia = pode gravar) contra o jcr:content lido agora."""
    prob = []
    criados = set()
    for op in cfg["ops"]:
        tipo, rel = op[0], op[1]
        no, pai = no_de(jc, rel), no_de(jc, rel.rsplit("/", 1)[0]) if "/" in rel else jc
        if tipo == "props" and no is None and rel.rsplit("/", 1)[0] not in criados:
            prob.append(f"props: {rel} não existe")
        elif tipo == "props" and len(op) > 3:
            prob += [f"props: {rel}.{k} = {str(no.get(k))[:80]!r}, esperado {str(v)[:80]!r}" for k, v in op[3].items()
                     if not confere(no.get(k), v)]
        elif tipo == "remover":
            if no is None:
                prob.append(f"remover: {rel} não existe")
            else:
                prob += [f"remover: {rel}/{sub}.{k} = {(no_de(no, sub) if sub else no or {}).get(k)!r}, esperado {v!r}"
                         for sub, k, v in op[2] if ((no_de(no, sub) if sub else no) or {}).get(k) != v]
        elif tipo == "mover":
            if no is None:
                prob.append(f"mover: {rel} não existe")
            if no_de(jc, op[2]) is not None:
                prob.append(f"mover: destino {op[2]} já existe")
            if no_de(jc, op[2].rsplit("/", 1)[0]) is None and op[2].rsplit("/", 1)[0] not in criados:
                prob.append(f"mover: pai do destino {op[2]} não existe")
        elif tipo == "criar":
            if no is not None:
                prob.append(f"criar: {rel} já existe")
            if pai is None and rel.rsplit("/", 1)[0] not in criados:
                prob.append(f"criar: pai de {rel} não existe")
            criados.add(rel)
        elif tipo == "apagar":
            if no is None:
                prob.append(f"apagar: {rel} não existe")
            elif any(k in no for k in CONTEUDO) or any(isinstance(v, dict) and k != "cq:responsive" for k, v in no.items()):
                prob.append(f"apagar: {rel} NÃO está vazio")
        if C.motivo_bloqueio("POST", C.url(f"{M}/{pag}/jcr:content/{rel}"), {"a": "b"}):
            prob.append(f"página protegida ({rel})")
    for origem, destino in cfg.get("assets", []):
        st_d, _ = C.ler(destino, ".0.json")
        st_p, _ = C.ler(destino.rsplit("/", 1)[0], ".0.json")
        st_o, _ = C.ler(origem + "/jcr:content/metadata", ".json")
        if st_d != 404 or st_p != 200 or st_o != 200:
            prob.append(f"asset {destino[len(G2_DAM):]}: destino HTTP {st_d} (quero 404), pasta {st_p}, origem {st_o}")
    return prob


# ---------------------------------------------------------------- gravação
def payload(props):
    d = {"_charset_": "utf-8"}
    for k, v in props.items():
        if isinstance(v, list):
            d[k], d[f"{k}@TypeHint"] = v, "String[]"
        else:
            d[k] = v
    return d


def copiar_asset(origem, destino):
    pasta, nome = destino.rsplit("/", 1)
    assert destino.startswith(G2_DAM + "/") and "macnicagwi" not in pasta, destino           # só LÊ o GWI
    _, md_o = C.ler(origem + "/jcr:content/metadata", ".json")
    r = sessao.post(C.url(pasta), data={f"{nome}@CopyFrom": origem, "_charset_": "utf-8"}, timeout=300)
    st, j = C.ler(destino, ".2.json")
    _, md_d = C.ler(destino + "/jcr:content/metadata", ".json")
    rend = [k for k, v in ((j or {}).get("jcr:content", {}).get("renditions") or {}).items() if isinstance(v, dict)]
    g = sessao.get(C.url(destino), timeout=300, allow_redirects=False)
    ok = (r.status_code in (200, 201) and (j or {}).get("jcr:primaryType") == "dam:Asset"
          and (md_d or {}).get("dam:sha1") == (md_o or {}).get("dam:sha1") and g.status_code == 200
          and len(g.content) == int((md_o or {}).get("dam:size") or -1))
    print(f"   asset {destino[len(G2_DAM):]}: POST {r.status_code}; sha1 {'igual' if ok else (md_d or {}).get('dam:sha1')}; "
          f"GET {g.status_code} {len(g.content)} bytes; {len(rend)} renditions -> {'COPIADO' if ok else 'FALHOU'}")
    return ok


def aplicar(pag, op):
    tipo, rel = op[0], op[1]
    alvo = C.url(f"{M}/{pag}/jcr:content/{rel}")
    if tipo in ("apagar", "remover"):
        r = sessao.post(alvo, data={":operation": "delete"}, timeout=120)
    elif tipo == "mover":
        r = sessao.post(alvo, data={":operation": "move", ":dest": f"{M}/{pag}/jcr:content/{op[2]}"}, timeout=120)
    else:
        d = payload(op[2])
        if tipo == "criar":
            d.setdefault("jcr:primaryType", "nt:unstructured")
            if len(op) > 3:
                d[":order"] = op[3]
        r = sessao.post(alvo, data=d, timeout=120)
    return r.status_code


# ---------------------------------------------------------------- conferência
def prints(pags, pasta):
    """{pag: png} — página inteira a 1400px fora do editor."""
    from playwright.sync_api import sync_playwright
    host = C.BASE.split("//", 1)[1]
    ck = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
    pasta.mkdir(parents=True, exist_ok=True)
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        c = b.new_context(viewport={"width": 1400, "height": 1000})
        c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in ck.items()])
        pg = c.new_page()
        pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(C.BASE) else r.abort())
        for pag in pags:
            pg.goto(f"{C.BASE}{M}/{pag}.html?wcmmode=disabled", timeout=180000, wait_until="networkidle")
            pg.add_style_tag(content="*,*::before,*::after{animation:none!important;transition:none!important}")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(3000)
            pg.evaluate("""() => document.querySelectorAll('body *').forEach(e => {
                const p = getComputedStyle(e).position; if (p === 'fixed' || p === 'sticky') e.style.visibility = 'hidden'; })""")
            png = pasta / f"{pag.replace('/', '__') or 'raiz'}.png"
            pg.screenshot(path=str(png), full_page=True)
            out[pag] = png
        b.close()
    return out


def compara_prints(pa, pd):
    """Linhas iguais no topo e no fim (alinhado pelo rodapé); o miolo é a região que mudou."""
    import numpy as np
    from PIL import Image
    a, d = np.array(Image.open(pa).convert("RGB")), np.array(Image.open(pd).convert("RGB"))
    w = min(a.shape[1], d.shape[1])
    a, d = a[:, :w], d[:, :w]
    n = min(len(a), len(d))
    topo = next((y for y in range(n) if not np.array_equal(a[y], d[y])), n)
    fim = next((k for k in range(1, n + 1) if not np.array_equal(a[-k], d[-k])), n + 1) - 1
    return {"altura": (len(a), len(d)), "igual_no_topo_ate": topo, "igual_no_fim_px": fim,
            "miolo_antes": (topo, len(a) - fim), "miolo_depois": (topo, len(d) - fim)}


def tokens(h):
    h = C.DL_RE.sub("", h)
    h = C.MODIFY_RE.sub(r"\1<data>", h)
    h = re.sub(r"\s+", " ", h)
    return [t for t in re.split(r"(<[^>]+>)", h) if t.strip()]


def compara_render(ha, hd):
    ta, td = tokens(ha), tokens(hd)
    sm = difflib.SequenceMatcher(None, ta, td, autojunk=False)
    ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
    txt = lambda ts: C.texto(" ".join(t for t in ts if not t.startswith("<")))
    tags = lambda ts: sorted({re.match(r"<(\w+)", t).group(1) for t in ts if re.match(r"<\w", t)})
    saiu = [t for o in ops for t in ta[o[1]:o[2]]]
    entrou = [t for o in ops for t in td[o[3]:o[4]]]
    return {"blocos": len(ops), "igual_antes_do_1o": ops[0][1] if ops else len(ta), "igual_depois_do_ultimo": len(ta) - ops[-1][2] if ops else 0,
            "texto_saiu": txt(saiu), "texto_entrou": txt(entrou), "tags_saiu": tags(saiu), "tags_entrou": tags(entrou),
            "links_saiu": sorted(set(re.findall(r'href="([^"]*)"', " ".join(saiu)))),
            "links_entrou": sorted(set(re.findall(r'href="([^"]*)"', " ".join(entrou)))),
            "imgs_entrou": sorted(set(re.findall(r'src="([^"]*)"', " ".join(entrou))))}


def compara_jcr(ja, jd, cfg):
    fa, fd = C.achatar(ja), C.achatar(jd)
    declarados = [op[1] for op in cfg["ops"]]
    props_de = {op[1]: set(op[2]) | {f"{k}@TypeHint" for k in op[2]} for op in cfg["ops"] if op[0] == "props"}
    auto = {"jcr:lastModified", "jcr:lastModifiedBy", "jcr:created", "jcr:createdBy"}

    def previsto(no, k):
        if (no, k) in C.CARIMBO_PAGINA:
            return True
        for op in cfg["ops"]:
            rel = op[1]
            if op[0] in ("criar", "apagar", "remover", "mover") and (no == rel or no.startswith(rel + "/")):
                return True
            if op[0] == "mover" and (no == op[2] or no.startswith(op[2] + "/")):
                return True
            if op[0] == "props" and no == rel and (k in props_de[rel] or k in auto):
                return True
        return False
    fora = sorted(f"{no}.{k}" for no, k in set(fa) | set(fd) if fa.get((no, k)) != fd.get((no, k)) and not previsto(no, k))
    for op in cfg["ops"]:                                  # nó movido: a subárvore chega igual (tirando o carimbo do nó)
        if op[0] == "mover":
            sub = lambda f, r: {(n[len(r):], k): v for (n, k), v in f.items() if (n == r or n.startswith(r + "/")) and k not in auto}
            if sub(fa, op[1]) != sub(fd, op[2]):
                fora.append(f"MOVIDO DIFERENTE: {op[1]} -> {op[2]}")
    return fora, declarados


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--so", nargs="*", default=[])
    ap.add_argument("--testar-comparador", action="store_true", help="só GET: 2 leituras de cada página têm de dar 0 diferença")
    a = ap.parse_args()
    if a.testar_comparador:
        pags = sorted({cfg.get("pagina", ch) for ch, cfg in PAGINAS.items() if not a.so or ch in a.so})
        pasta = Path(os.environ.get("CF_TESTE", "/tmp")) / f"teste_comparador_{datetime.datetime.now():%H%M%S}"
        r1 = {p: C.retrato(f"{M}/{p}") for p in pags}
        p1 = prints(pags, pasta / "1")
        r2 = {p: C.retrato(f"{M}/{p}") for p in pags}
        p2 = prints(pags, pasta / "2")
        for p in pags:
            fora, _ = compara_jcr(r1[p][0], r2[p][0], {"ops": []})
            rr, pr = compara_render(r1[p][1], r2[p][1]), compara_prints(p1[p], p2[p])
            ok = not fora and rr["blocos"] == 0 and pr["igual_no_topo_ate"] == min(pr["altura"])
            print(f"{'OK ' if ok else 'DIFERENÇA'} /{p}: JCR {fora or 'igual'}; render {rr['blocos']} trechos; print {pr}")
        return
    lista = []
    for chave, cfg in PAGINAS.items():
        if a.so and chave not in a.so:
            continue
        pag = cfg.get("pagina", chave)
        if cfg.get("feito"):
            print(f"## {chave}: já gravado ({cfg['feito']})"); continue
        st, jc = C.ler(f"{M}/{pag}/jcr:content", ".infinity.json")
        assert st == 200, (pag, st)
        prob = conferir(pag, cfg, jc)
        print(f"## {chave} -> /{pag}  (última edição {jc.get('cq:lastModified', '')[:24]} por {jc.get('cq:lastModifiedBy', '')})\n   {cfg['o_que']}")
        for origem, destino in cfg.get("assets", []):
            print(f"   asset  {origem[len(GWI_DAM):]} -> {destino[len(G2_DAM):]}")
        for op in cfg["ops"]:
            extra = ""
            if op[0] in ("props", "criar"):
                extra = "; ".join(f"{k}={str(v)[:70]}" for k, v in op[2].items() if k != "sling:resourceType")
                extra = f"<{op[2].get('sling:resourceType', '').rsplit('/', 1)[-1]}> {extra}" if op[0] == "criar" else extra
            print(f"   {op[0]:6} {op[1]}  {extra}")
        print("   PULA: " + "; ".join(prob) if prob else "   precondições OK")
        if not prob:
            lista.append((pag, cfg, jc))
    assert len({x[0] for x in lista}) == len(lista), "a mesma página duas vezes na rodada: rodar as passadas separadas"
    if not a.executar:
        print(f"\n{len(lista)} páginas prontas (DRY-RUN: nada gravado)")
        return

    agora = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    pasta = DADOS / f"backup_conteudo_{agora}"
    pasta.mkdir(parents=True)
    retratos = {pag: C.retrato(f"{M}/{pag}") for pag, _, _ in lista}                                  # backup ANTES
    (pasta / "jcr_content.json").write_text(json.dumps({k: v[0] for k, v in retratos.items()}, ensure_ascii=False), encoding="utf-8")
    (pasta / "render.json").write_text(json.dumps({k: v[1] for k, v in retratos.items()}, ensure_ascii=False), encoding="utf-8")
    p_antes = prints([pag for pag, _, _ in lista], pasta / "prints_antes")
    print(f"backup: {len(lista)} páginas (jcr:content + render + print) -> {pasta}")

    feitos = []
    for pag, cfg, jc_plano in lista:
        st, jc = C.ler(f"{M}/{pag}/jcr:content", ".infinity.json")                                  # relido agora
        if C.achatar(jc) != C.achatar(jc_plano) or conferir(pag, cfg, jc):
            print(f"## /{pag}: MUDOU desde o plano — pulado"); continue
        print(f"## /{pag}")
        ok = all(copiar_asset(o, d) for o, d in cfg.get("assets", []))
        if not ok:
            print("   asset FALHOU — página não mexida"); continue
        codigos = []
        for op in cfg["ops"]:
            codigos.append(aplicar(pag, op))
            if codigos[-1] not in (200, 201):
                print(f"   {op[0]} {op[1]}: HTTP {codigos[-1]} — PAROU"); break
        print(f"   {len(codigos)} operações: HTTP {sorted(set(codigos))}")
        with open(DADOS / "manifesto_links.jsonl", "a") as f:
            f.write(json.dumps({"grupo": "G-conteudo", "pagina": f"{M}/{pag}", "tipo": "conteudo", "txt": cfg["o_que"],
                                "ops": [op[:2] for op in cfg["ops"]], "assets": cfg.get("assets", []), "quando": agora,
                                "status": "gravado" if all(c in (200, 201) for c in codigos) and len(codigos) == len(cfg["ops"]) else "falhou",
                                "http": codigos}, ensure_ascii=False) + "\n")
        feitos.append((pag, cfg))

    p_depois = prints([pag for pag, _ in feitos], pasta / "prints_depois")
    comp = []
    print("\n== antes x depois ==")
    for pag, cfg in feitos:
        jd, hd = C.retrato(f"{M}/{pag}")
        fora, _ = compara_jcr(retratos[pag][0], jd, cfg)
        rr = compara_render(retratos[pag][1], hd)
        pr = compara_prints(p_antes[pag], p_depois[pag])
        print(f"/{pag}: JCR fora do previsto {fora or 'nada'}\n   render: {rr['blocos']} trechos diferentes; saiu “{rr['texto_saiu'][:200]}” "
              f"{rr['tags_saiu']}; entrou “{rr['texto_entrou'][:300]}” {rr['tags_entrou']}\n   links que entraram {rr['links_entrou']}; "
              f"saíram {rr['links_saiu']}\n   imagens que entraram {rr['imgs_entrou']}\n   print: altura {pr['altura']}; igual até y={pr['igual_no_topo_ate']}; "
              f"igual nos últimos {pr['igual_no_fim_px']} px; miolo {pr['miolo_antes']} -> {pr['miolo_depois']}")
        comp.append({"pagina": pag, "jcr_fora": fora, "render": rr, "prints": pr})
    (pasta / "comparacao.json").write_text(json.dumps(comp, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
