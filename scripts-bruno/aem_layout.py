#!/usr/bin/env python3
"""
Motor de layout da remigração: GWI -> global2, no dialeto das páginas autorais.

SUBSTITUI `extract_content` + `BlockBuilder`, que fazem conversão 1-para-1 e
achatam a estrutura. Aqui a travessia devolve uma ÁRVORE
(Page -> Section -> Row -> Column -> Block) e o emissor escreve no dialeto
que a agência Anion usa nas páginas já autoradas do global2.

--------------------------------------------------------------------------
A REGRA DE FRONTEIRA (o alicerce — e o único achado testado por falsificação)
--------------------------------------------------------------------------
    Cada filho de topo do corpo do GWI que carrega conteúdo renderizável
    vira UM container de seção no destino, na mesma ordem.

Medido sobre 212 pares origem<->autoral: precisão 99,3%, recall 96,3%,
3 falsos positivos em 414 previsões.

Isso resolve a contradição que dominou o diagnóstico. A `deepx` tem UM
container e gap 0px; a `sony` tem QUATRO seções com faixa colorida. Parecia
haver duas gramáticas Anion. Não há: a `deepx` do GWI tem um bloco de topo e a
`sony` tem quatro. **Fronteira de seção é dado da origem, não julgamento
estético.** O motor lê, não decide.

Os dois preditores que pareciam óbvios foram FALSIFICADOS e não são caminho
principal: spacer `&nbsp;` (precisão 16,2%) e heading de nível mais alto
(16,4% — e em 191 dos 212 pares a página nem tem heading).

--------------------------------------------------------------------------
POR QUE O ESPAÇAMENTO VEM DAQUI, E NÃO DE MARGEM
--------------------------------------------------------------------------
Neste design system NÃO existe margem entre componentes irmãos: o gap medido é
0px em 100% dos casos, nas duas referências, em todos os níveis. Todo respiro
vertical vem do `container`:

    .container > .cmp-container { padding: 30px 15px }   /* < 1050px  */
    .container > .cmp-container { padding: 50px 25px }   /* >= 1050px */

Breakpoint único do site: 1050px. Não há tablet.

O `root/container` do template é INERTE — a policy já carimba
`cq:styleDefaultClasses='main container-padding-height0 container-padding-width0'`.
Escrever style nele é desperdício (212 de 212 pares autorais não escrevem).

--------------------------------------------------------------------------
DECISÕES DO TIME (18/09/2026) JÁ CODIFICADAS AQUI
--------------------------------------------------------------------------
- **Fundo é propriedade de SEÇÃO, nunca de bloco.** A zebra por bloco do
  migrador antigo (`#fff`/`#f7f7f7` alternando) está morta: nenhuma página
  autoral faz isso e a paleta sancionada não tem essas duas cores. Seção de
  apoio usa `rgb(247,247,247)`, como a `sony`.
- **`download` vira TABELA** (colunas Title/Download), como a Anion fez. O
  componente `download` existe em /apps mas não está na allow-list do slot.
- **Nada é sobrescrito.** O destino é uma árvore nova
  (`semiconductors-remigration`); `/semiconductors` não é tocada.
- **`cq:responsive` é PROIBIDO no motor.** Coluna é `flexcontainer`. As
  policies têm `layoutDisabled='true'`, então largura de grid escrita por
  script produz página que o autor não consegue editar pela UI; e o grid do
  AEM quebra em 768/1200px enquanto o design system quebra em 1050px.

--------------------------------------------------------------------------
DOIS BUGS DO MOTOR ANTIGO QUE NÃO PODEM SER HERDADOS
--------------------------------------------------------------------------
1. `aem_lib.py:2067` — dentro de aba, `add_simple_block()` devolve `False`
   para embed/carousel/list/downloadlist/flexcontainer/tabs aninhado, e o
   chamador conta como migrado sem olhar o retorno. Conteúdo sumia e a
   auditoria dizia 100%. **Aqui o emissor é TOTAL**: todo nó da IR tem
   emissor ou vira pendência explícita. Nunca descarte silencioso.
2. `aem_lib.py:2099` — nomes de nó vindos de contagem de chaves do payload
   (`text_5, text_16, text_27`). Aqui os nomes são determinísticos por pai,
   o que torna o diff legível e a reexecução idempotente.

Ver `scripts-hazael/remigracao/ESPEC-motor-layout.md` para a especificação
completa e a proveniência de cada regra.
"""

import copy
import re
from html import escape
from urllib.parse import quote

from aem_lib import (BUTTON_TYPES, CAROUSEL_TYPES, CONTAINER_RT, DOWNLOAD_TYPES,
                     DOWNLOADLIST_TYPES, HEADING_TYPES, IMAGE_TYPES,
                     IMAGEPACK_TYPES, KNOWN_CONTAINER_TYPES, PRODUCTLISTING_TYPES,
                     RESPONSIVE_GRID_RT, TABLE_TYPES, TEXT_TYPES,
                     is_meaningful_text, list_child_nodes, rewrite_links_in_html,
                     strip_empty_blocks)

# ---------------------------------------------------------------------------
# Vocabulário do destino
# ---------------------------------------------------------------------------

RT = {
    "container": "macnicaglobal2/components/content/container",
    "title": "macnicaglobal2/components/content/title",
    "text": "macnicaglobal2/components/content/text",
    "image": "macnicaglobal2/components/content/image",
    "textwithimage": "macnicaglobal2/components/content/textwithimage",
    "button": "macnicaglobal2/components/content/button",
    "table": "macnicaglobal2/components/content/table",
    "embed": "macnicaglobal2/components/content/embed",
    "tabs": "macnicaglobal2/components/content/tabs",
    "carousel": "macnicaglobal2/components/content/carousel",
    "list": "macnicaglobal2/components/content/list",
    "flexcontainer": "macnicaglobal2/components/content/flexcontainer",
    "flexcontaineritem": "macnicaglobal2/components/content/flexcontaineritem",
    "experiencefragment": "macnicaglobal2/components/content/experiencefragment",
    "form_container": "macnicaglobal2/components/form/container",
    "form_text": "macnicaglobal2/components/form/text",
    "form_button": "macnicaglobal2/components/form/button",
    "downloadlist": "macnicaglobal2/components/content/downloadlist",
    "anchorlink": "macnicaglobal2/components/content/anchorlink",
}

# styleIds — posicionais por GRUPO da policy do PRÓPRIO componente.
# A posição não importa para renderizar (o AEM resolve por valor), mas a forma
# canônica é um slot por grupo: é o que o diálogo grava e precisa para reabrir.
S_CONT_1000 = "1717410661180"   # [0] MaxWidth 1000px (fitcontainer)
S_CONT_TB_LARGE = "1717498050826"
S_CONT_TB_SMALL = "1717498052331"
S_CONT_TB_NONE = "1717498056876"
S_CONT_LR_LARGE = "1717498053499"
S_CONT_LR_NONE = "1717498055877"

S_TITLE_CENTER = "1717668113714"   # [2] Posição
S_TITLE_H3SIZE = "1718280237031"   # [3] Tamanho -> classe heading3

S_FLEX_SP_1COL = "1719484596357"   # [1] Design SP: empilha abaixo de 1050px
S_IMG_LEFT = "1726800547211"       # image [1] Display Position: Left (o padrão é Center)
S_TWI_LEFT = "1718154328384"       # [0] imagem à esquerda
S_TWI_VCENTER = "1783061491236"    # [Vertical Alignment] Center (`vert-center`)
S_TABLE_NOROUND = "1722939215525"  # [2] No Rounded Corner
S_TABLE_BLACK = "1722937999485"    # [0] Color Scheme: Black (texto #4d4d4d)
S_TABLE_NOBG = "1722858778108"     # [1] Header: No Background
S_TABLE_NOFRAME = "1722858697098"  # [3] Frame: No Frame (border:none)
S_BTN_FIXEDMIN = "1722936853890"   # [1] Fixed Minimum Width
S_BTN_CENTER = "1717669229626"     # [2] Center

# Cor de seção de apoio. A `sony` usa rgb(247,247,247); a paleta sancionada da
# policy não inclui nem essa nem #f7f7f7 — decisão do time em 18/09/2026 foi
# seguir o corpus autoral.
COR_APOIO = "rgb(247,247,247)"

XF_MAP = {
    "/content/experience-fragments/macnicagwi/americas/mai/en/site/"
    "products-contact-block/master":
        "/content/experience-fragments/copia-teste/americas/mai/en/site/"
        "products-contact-block/master",
    "/content/experience-fragments/macnicagwi/americas/mai/en/site/"
    "signup-and-contact-experience-fragment/master":
        "/content/experience-fragments/copia-teste/americas/mai/en/site/"
        "signup-and-contact-experience-fragment/master",
}

RELATED_TYPES = {"macnicagwi/components/content/relatedsuggestions"}
XF_TYPES = {"macnicagwi/components/content/experiencefragment"}
VIDEO_TYPES = {"macnicagwi/components/content/video"}
TABS_TYPES = {"macnicagwi/components/content/tabs"}
PAGEPROPS_TYPES = {"macnicagwi/components/content/pageproperties"}
SECTIONLIST_TYPES = {"macnicagwi/components/content/pagesectionlisting"}
# O GWI tem DOIS componentes de título: `heading` (o comum) e `title`. Só o
# primeiro estava mapeado, e o segundo caía em "tipo não reconhecido".
TITLE_TYPES = {"macnicagwi/components/content/title"}
FORM_CONTAINER_RT = "macnicagwi/components/content/form/container"
FORM_TEXT_RT = "macnicagwi/components/content/form/text"
FORM_BUTTON_RT = "macnicagwi/components/content/form/button"
_FORM_CAMPO_PROPS = ("jcr:title", "name", "type", "required", "usePlaceholder",
                     "helpMessage", "constraintMessage", "requiredMessage",
                     "rows", "value", "readOnly")
# Os dois popups que o form container do global2 EXIGE (successFragmentPath /
# errorFragmentPath). Convenção do global2 (APAC): <região>/site/popups/
# form-success|form-error/master. O driver pode trocar a raiz.
XF_FORM_POPUPS = "/content/experience-fragments/macnicaglobal2/americas/mai/en/site/popups"
IMAGETEXT_RT = "macnicagwi/components/content/imagetext"
# O breadcrumb do destino vem do próprio template (`root/container_1885913789`),
# então o da origem é descartável — mas em silêncio, e não como pendência.
DESCARTAVEIS = {"macnicagwi/components/content/breadcrumb"}

# Tipos que são invólucro puro e não geram bloco por si.
WRAPPER_TYPES = set(KNOWN_CONTAINER_TYPES)

YOUTUBE_RT = "core/wcm/components/embed/v1/embed/embeddable/youtube"


# ---------------------------------------------------------------------------
# IR
# ---------------------------------------------------------------------------

class Pendencia:
    def __init__(self, origin_path, resource_type, categoria, motivo, ref=""):
        self.origin_path = origin_path
        self.resourceType = resource_type
        self.categoria = categoria
        self.motivo = motivo
        self.ref = ref

    def as_row(self):
        return {"origem": self.origin_path, "resourceType": self.resourceType,
                "categoria": self.categoria, "motivo": self.motivo, "ref": self.ref}


class Block:
    def __init__(self, kind, origin_path, **props):
        self.kind = kind
        self.origin_path = origin_path
        self.props = props
        self.panels = []


class Column:
    def __init__(self, origin_path, width=None, phone_width=None):
        self.origin_path = origin_path
        self.width = width
        self.phone_width = phone_width
        self.blocks = []
        self.offset = 0            # doze avos vazios à esquerda (grade do GWI)


class Row:
    def __init__(self, kind="single"):
        self.kind = kind
        self.columns = []
        self.vazias = 0            # itens vazios no fim, para fechar a grade (R18)
        self.largura_orfa = None   # coluna única rebaixada: a largura que tinha
        self.cabecalho = []        # títulos que introduzem a linha de colunas (R23)

    @property
    def blocks(self):
        return self.cabecalho + [b for c in self.columns for b in c.blocks]


class Panel:
    def __init__(self, label, origin_path):
        self.label = label
        self.origin_path = origin_path
        self.rows = []


# Diretriz de 18/09/2026: as páginas NÃO têm margem. Sai o `fitcontainer`
# (max-width 1000px, centralizado) e o padding lateral "large" (50px); fica o
# padding padrão do container do design system (25px no desktop, 15px abaixo
# de 1050px). A largura útil passa a ser a da janela. As páginas da Anion
# (sony, deepx) vão mudar igual depois — não são nossas, não são tocadas.
# `True` volta ao dialeto antigo (coluna de 900px) sem mexer em mais nada.
COM_MARGEM = False


class Section:
    def __init__(self, origin_path, origin_index, role="body"):
        self.origin_path = origin_path
        self.origin_index = origin_index
        self.role = role
        self.background = None
        self.full_bleed = False
        self.max_width_1000 = COM_MARGEM
        self.pad_tb = "small"      # none|small|default|large
        self.pad_lr = "large" if COM_MARGEM else "default"
        self.rows = []

    @property
    def blocks(self):
        return [b for r in self.rows for b in r.blocks]


class Page:
    def __init__(self, source_path, archetype=None):
        self.source_path = source_path
        self.archetype = archetype
        self.template = None          # cq:template da origem (decide o h1)
        self.topology = "AGRUPADA"
        self.page_props = {}
        self.sections = []
        self.pendencias = []

    @property
    def blocks(self):
        return [b for s in self.sections for b in s.blocks]


# ---------------------------------------------------------------------------
# Utilidades de leitura da origem
# ---------------------------------------------------------------------------

def _px(v):
    """'345', '345px', 345 -> 345; o resto -> None."""
    m = re.match(r"\s*(\d{2,4})", str(v or ""))
    return int(m.group(1)) if m else None


def rt_of(node):
    return node.get("sling:resourceType", "") or ""


def width_of(node, bp="default"):
    """Largura em doze avos do PAI, quando existe. None = sem largura."""
    resp = node.get("cq:responsive")
    if isinstance(resp, dict):
        cfg = resp.get(bp)
        if isinstance(cfg, dict):
            w = cfg.get("width")
            if w is not None and str(w).isdigit():
                n = int(str(w))
                if 0 < n <= 12:
                    return n
    return None


def offset_of(node, bp="default"):
    """Deslocamento da coluna em doze avos (0 quando não há)."""
    resp = node.get("cq:responsive")
    cfg = resp.get(bp) if isinstance(resp, dict) else None
    o = cfg.get("offset") if isinstance(cfg, dict) else None
    return int(str(o)) if o is not None and str(o).isdigit() else 0


def col_width_of(node):
    """Largura SÓ quando o nó é de fato uma coluna.

    `width=12` é largura cheia, não coluna — e confundir os dois faz um item
    de aba com vários textos de 12 virar uma linha de 6 colunas. É a mesma
    semântica do `largura_coluna` original (`0 < w < 12`).
    """
    w = width_of(node)
    return w if (w is not None and 0 < w < 12) else None


def _texto_visivel(html):
    s = re.sub(r"<[^>]+>", " ", html or "")
    s = s.replace("&nbsp;", " ").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip()


_P_VAZIO = r"<p\b[^>]*>(?:\s|&nbsp;|\u00a0|<br\s*/?>)*</p\s*>"
_ESPACADOR_INICIO = re.compile(r"^\s*(?:" + _P_VAZIO + r"\s*)+", re.I)
_ESPACADOR_FIM = re.compile(r"(?:" + _P_VAZIO + r"\s*)+$", re.I)
_BLOCO_RICO = re.compile(r"<(p|h[1-6])\b([^>]*)>(.*?)</\1\s*>", re.I | re.S)


_ESPACADOR_COM_INLINE = re.compile(
    r"<(p|h[1-6])\b[^>]*>(?:\s|&nbsp;|\u00a0|<br\s*/?>"
    r"|</?(?:b|strong|i|em|u|span|font)\b[^>]*>)*</\1\s*>", re.I)


_CELULA = re.compile(r"<(t[dh])\b([^>]*)>((?:(?!</?t[dh]\b).)*?)</\1\s*>", re.I | re.S)


def nao_quebrar_tokens(html):
    """Célula de tabela com UM token curto não quebra no meio (R41).

    O CSS do global2 põe `word-break:break-word` em `td`/`th`: a célula pode
    encolher até 1 caractere, e o navegador reparte a largura pelas colunas
    de frase longa. Na `altera-arria-10` (13 colunas) 31 de 209 células
    quebravam número no desktop ("101,62/0") e 189 no celular, um caractere
    por linha — tabela de 8.319px de altura contra 2.258 no GWI; na `/i-chips`
    a 1ª coluna saía "IP00C33/5". No GWI a tabela cresce e ROLA dentro do
    `.cmp-table{overflow-x:auto}`; com `white-space:nowrap` nas células de
    token único o destino faz o mesmo (o wrapper `scroll-hint` já rola).
    """
    def troca(m):
        tag, attrs, miolo = m.group(1), m.group(2), m.group(3)
        txt = re.sub(r"<[^>]+>", "", miolo).replace("&nbsp;", " ").replace("\u00a0", " ").strip()
        if not (2 <= len(txt) <= 16) or re.search(r"\s", txt) or "white-space" in attrs.lower():
            return m.group(0)
        ms = re.search(r"""\bstyle\s*=\s*(["'])""", attrs, re.I)
        if ms:
            attrs = attrs[:ms.end()] + "white-space:nowrap;" + attrs[ms.end():]
        else:
            attrs += ' style="white-space:nowrap"'
        return f"<{tag}{attrs}>{miolo}</{tag}>"
    return _CELULA.sub(troca, html or "")


def normalizar_espacadores(html):
    """`<p><b>&nbsp;</b></p>` é linha em branco — vira `<p>&nbsp;</p>` (R37).

    O autor deixou o negrito ligado na linha vazia. `strip_empty_blocks` e
    `_P_VAZIO` só aceitam espaço/&nbsp;/<br> dentro do bloco, então este
    sobrevivia como parágrafo de verdade: 30 de margem + 30 de altura + 30 da
    margem do seguinte = 90px entre "Common deployments include:" e o 1º item
    na `altera-holoscan` (GWI 28). Normalizado, segue o caminho de todo
    espaçador: evidência para a R15/R24 e depois apagado.
    """
    if not html or "&nbsp;" not in html and "\u00a0" not in html:
        return html
    return _ESPACADOR_COM_INLINE.sub(
        lambda m: "<p>&nbsp;</p>" if "<" in m.group(0)[1:-1].replace("<br", "")
        .replace("</" + m.group(1), "") else m.group(0), html)


_BR_FIM_DE_CELULA = re.compile(
    r"(?:\s*<br\s*/?>)+\s*"
    r"(?=(?:</(?:b|strong|i|em|span|a|u|font)\s*>\s*)*(?:</p>\s*)?</t[dh]\s*>)", re.I)

_TAG_HTML = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(/?)>")
_TAGS_DE_BLOCO = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "dl",
                  "table", "div", "blockquote", "hr", "pre", "figure", "section"}
_TAGS_VAZIAS = {"br", "hr", "img", "input", "wbr", "col", "source"}
_TAGS_INLINE = {"a", "b", "strong", "i", "em", "u", "span", "sup", "sub", "br",
                "img", "font", "small"}


def embrulhar_inline_da_raiz(html):
    """Texto/inline SOLTO na raiz do rich text vai para dentro de um `<p>` (R33).

    O RTE do GWI às vezes deixa o parágrafo como `<span>` (ou texto puro)
    filho direto do componente. No GWI não faz diferença; no global2 o estilo
    de parágrafo é `.cmp-text p`, e o que está fora de `<p>` herda a
    tipografia base (14px, letter-spacing 1.4px) e não tem margem: na
    `canon-li8030sa` "Macnica pairs Canon's sensor roadmap…" saía menor, com
    as letras espaçadas e colado no h4 (1px contra 27). HTML que não fecha
    direito volta como veio.
    """
    if not html or not _texto_visivel(html):
        return html
    out, pos, prof, mudou = [], 0, 0, False

    def solta(trecho):
        nonlocal mudou
        if _texto_visivel(trecho):
            mudou = True
            return "<p>" + trecho.strip() + "</p>"
        return trecho

    # Só embrulha o que é comprovadamente inline: `<li>`, `<center>`,
    # `<form>`, comentário… soltos na raiz dariam `<p>` com bloco dentro (o
    # navegador fecha o `<p>` sozinho e sobra um parágrafo vazio de 30px).
    # Qualquer tag fora das duas listas: o HTML volta como veio.
    if "<!--" in html or any(
            m.group(2).lower() not in _TAGS_DE_BLOCO | _TAGS_INLINE | {"li", "tr", "td", "th", "tbody", "thead", "dt", "dd", "caption", "colgroup", "col"}
            for m in _TAG_HTML.finditer(html)):
        return html

    for m in _TAG_HTML.finditer(html):
        tag = m.group(2).lower()
        fecha, auto = bool(m.group(1)), bool(m.group(3)) or tag in _TAGS_VAZIAS
        if prof == 0:
            if fecha and tag in _TAGS_DE_BLOCO:
                return html                      # fecha sem abrir: não mexe
            if not fecha and tag in _TAGS_DE_BLOCO:
                out.append(solta(html[pos:m.start()]))
                pos = m.start()
                if auto:
                    out.append(html[pos:m.end()])
                    pos = m.end()
                else:
                    prof, raiz = 1, tag
            continue                             # inline na raiz: segue acumulando
        if auto:
            continue
        if tag == raiz:
            prof += -1 if fecha else 1
            if prof == 0:
                out.append(html[pos:m.end()])
                pos = m.end()
    if prof != 0:
        return html
    out.append(solta(html[pos:]))
    return "".join(out) if mudou else html


def colar_paragrafos(html):
    """`<p>` que o GWI desenha COLADO no bloco de cima ganha `margin-top:0` (R15).

    No GWI `p{margin:unset}`: entre dois blocos de um rich text o vão é 0, e a
    linha em branco é um `<p>&nbsp;</p>` que o autor digita. No destino todo
    `<p>` que não é o primeiro filho tem `margin-top:30px` (`.cmp-text`,
    `.cmp-table` e `.cmp-textwithimage .paragraph`, a mesma regra), e o
    `<p>&nbsp;</p>` é apagado por `strip_empty_blocks`. Resultado: o título do
    card "CV72S" ficava a 50px do texto (20 do `h3` + 30 do `<p>`) contra 0 no
    GWI, e pergunta/resposta do FAQ da `/ambarella` perdiam o agrupamento.

    Regra: `<p>` com texto cujo vizinho IMEDIATO de cima (só espaço em branco
    entre os dois) é um `<p>`/`<h1-6>` com conteúdo recebe `margin-top:0`.
    Depois de um espaçador fica como está: os 30px do destino fazem o papel da
    linha em branco (28px) do GWI. Estilo inline sobrevive ao filtro do AEM.

    Roda sobre o HTML CRU de cada `text`/`table` da origem — antes de
    `strip_empty_blocks`, que apagaria a evidência, e antes de
    `_fundir_textos`: a emenda entre dois `text` nunca é colada, porque o
    espaçador que havia entre eles pode ter sido um nó à parte, já descartado.
    """
    if not html or "<p" not in html.lower():
        return html
    out, pos, ant = [], 0, None
    for m in _BLOCO_RICO.finditer(html):
        tag, attrs, miolo = m.group(1).lower(), m.group(2), m.group(3)
        cheio = bool(_texto_visivel(miolo)) or "<img" in miolo.lower()
        colado = (ant is not None and ant[1]
                  and not html[ant[0]:m.start()].strip())
        if (tag == "p" and colado and _texto_visivel(miolo)
                and "margin-top" not in attrs.lower()
                and not re.search(r"\bmargin\s*:", attrs, re.I)):
            ms = re.search(r"""\bstyle\s*=\s*(["'])""", attrs, re.I)
            if ms:
                attrs = attrs[:ms.end()] + "margin-top:0;" + attrs[ms.end():]
            else:
                attrs += ' style="margin-top:0"'
            out.append(html[pos:m.start()])
            out.append(f"<{m.group(1)}{attrs}>{miolo}</{m.group(1)}>")
            pos = m.end()
        ant = (m.end(), cheio)
    out.append(html[pos:])
    return "".join(out)


def spacer_kind(node):
    """Classifica um `text` que parece vazio.

    Dos 674 `text` que ficam vazios depois de tirar tags e `&nbsp;`: 609 são
    descartáveis, mas 59 contêm `<hr>` (régua visível, divisor autoral entre
    blocos `imagetext`) e 6 contêm âncora nomeada com links apontando para ela.
    Descartar tudo por "está vazio" apagaria conteúdo de verdade.

    Devolve: 'conteudo' | 'hr' | 'anchor' | 'spacer'
    """
    html = node.get("text", "") or ""
    if _texto_visivel(html):
        return "conteudo"
    if re.search(r"<hr\b", html, re.I):
        return "hr"
    if re.search(r"<a\s[^>]*\b(name|id)\s*=", html, re.I):
        return "anchor"
    if re.search(r"<img\b", html, re.I):
        return "conteudo"
    return "spacer"


def tem_conteudo_renderizavel(node):
    """A subárvore carrega algo que o visitante veria?"""
    rt = rt_of(node)
    if rt in TEXT_TYPES:
        return spacer_kind(node) != "spacer"
    if rt in PAGEPROPS_TYPES:
        return False
    if rt and rt not in WRAPPER_TYPES:
        return True
    for _n, ch in list_child_nodes(node):
        if tem_conteudo_renderizavel(ch):
            return True
    return False


def so_pageproperties(node):
    """O bloco de topo do GWI que só embrulha o cabeçalho da página.

    266 páginas têm um `resizablecontainer` cujo único conteúdo é
    `pageproperties` (no GWI é o `id="cmp-container--title-pageproperties"`).
    É cabeçalho, não corpo — e é a origem do "logo gigante no fim da página",
    porque o migrador antigo entrava nele e tratava o logo como imagem.
    A Anion descartou os 192 casos equivalentes.
    """
    achou = False
    for _n, ch in list_child_nodes(node):
        rt = rt_of(ch)
        if rt in PAGEPROPS_TYPES:
            achou = True
        elif tem_conteudo_renderizavel(ch):
            return False
    return achou or not tem_conteudo_renderizavel(node)


# Regiões EDITÁVEIS da structure de cada template do GWI (censo de
# 18/09/2026 sobre /conf/macnicagwi/settings/wcm/templates/<tpl>/structure).
#
# Em template editável do AEM, um container travado renderiza os filhos da
# STRUCTURE; da página só entra o que estiver sob um nó `editable=true`. Nó
# da página fora dessas regiões existe no JCR e NUNCA chega à tela. Caso
# real: `analog-devices-lidar-development-kit` tem `title`, `imagetext` (a
# descrição inteira do produto) e `experiencefragment` como irmãos diretos
# de `root/container/container` — o GWI só desenha `heading` e `text`, que
# são os editáveis daquele nível. O motor migrava os três fantasmas (R9).
REGIOES_EDITAVEIS = {
    "base-page-content": {
        "root/container/container", "root/container/heading"},
    "manufacturer-detail-page-content": {
        "root/container/container/container",
        "root/container/container/resizablecontainer/pageproperties"},
    "product-detail-page-content": {
        "root/container/container/container",
        "root/container/container/heading",
        "root/container/container/text",
        "root/container/container/resizablecontainer/pageproperties"},
    "macnica-gwi-product-line-detail-page-template": {
        "root/container/container/container"},
    "macnica-gwi---mae-product-page": {
        "root/container/container/relatedsuggestions",
        "root/container/container/resizablecontainer",
        "root/container/container/resizablecontainer_801077606",
        "root/container/container/resizablecontainer_939437349",
        "root/container/container/resizablecontainer_870495439/pageproperties"},
}


def podar_nos_mortos(jcr_content, page):
    """Remove de uma CÓPIA do jcr:content os nós que o GWI não renderiza.

    Mantém: nó editável (e tudo abaixo), e ancestral de nó editável (container
    travado por onde é preciso descer). Descarta o resto — com pendência
    quando o nó descartado tinha conteúdo, porque nada sai em silêncio.
    Template fora da tabela: não poda (comportamento antigo).
    """
    tpl = (page.template or "").rstrip("/").rsplit("/", 1)[-1]
    editaveis = REGIOES_EDITAVEIS.get(tpl)
    if not editaveis or not isinstance(jcr_content.get("root"), dict):
        return jcr_content
    ancestrais = set()
    for e in editaveis:
        partes = e.split("/")
        for i in range(1, len(partes)):
            ancestrais.add("/".join(partes[:i]))

    def copiar(node, caminho):
        novo = {}
        for k, v in node.items():
            if not isinstance(v, dict) or k == "cq:responsive":
                novo[k] = v
                continue
            cp = f"{caminho}/{k}"
            if cp in editaveis:
                novo[k] = v
            elif cp in ancestrais:
                novo[k] = copiar(v, cp)
            else:
                rt = rt_of(v)
                if rt in DESCARTAVEIS or so_pageproperties(v):
                    continue
                if tem_conteudo_renderizavel(v):
                    page.pendencias.append(Pendencia(
                        f"{page.source_path}/jcr:content/{cp}", rt or "",
                        "fora_da_structure",
                        "nó fora das regiões editable do template "
                        f"{tpl}: o GWI não renderiza; descartado"))
        return novo

    copia = dict(jcr_content)
    copia["root"] = copiar(jcr_content["root"], "root")
    return copia


def achar_corpo(jcr_content):
    """`jcr:content/root/container` e desce enquanto for invólucro de 1 filho.

    Nunca começa em `jcr:content`: os irmãos de `root` (`manufacturerlogo`,
    `cq:featuredimage`, `productlinelogo`, `image`, `pd_*`) são propriedade de
    página e não podem virar conteúdo. Era `walk(jcr_content)` no motor antigo
    — a origem de três defeitos de uma vez.
    """
    root = jcr_content.get("root")
    if not isinstance(root, dict):
        return None, "jcr:content/root"
    corpo = root.get("container")
    caminho = "jcr:content/root/container"
    if not isinstance(corpo, dict):
        return None, caminho
    while True:
        # Só conta filho que CARREGA conteúdo. O bloco de `pageproperties`
        # (o cabeçalho do GWI) é irmão do corpo real em 266 páginas: contá-lo
        # fazia a descida parar cedo demais e a página inteira virava UMA
        # seção — a doença que este motor existe para curar.
        uteis = [(n, c) for n, c in list_child_nodes(corpo)
                 if tem_conteudo_renderizavel(c) and not so_pageproperties(c)]
        if len(uteis) != 1:
            return corpo, caminho
        nome, unico = uteis[0]
        if rt_of(unico) not in WRAPPER_TYPES:
            return corpo, caminho
        if col_width_of(unico) is not None:
            return corpo, caminho
        corpo, caminho = unico, f"{caminho}/{nome}"


# ---------------------------------------------------------------------------
# Extração: blocos folha
# ---------------------------------------------------------------------------

def _carousel_slides(node):
    slides = []
    for nome, ch in list_child_nodes(node):
        rt = rt_of(ch)
        item = {"origin": nome, "panelTitle": ch.get("cq:panelTitle")}
        if rt in IMAGE_TYPES or ch.get("fileReference"):
            item["kind"] = "image"
            item["fileReference"] = ch.get("fileReference")
            item["alt"] = ch.get("alt", "")
        elif rt in VIDEO_TYPES or ch.get("youtubeVideoId"):
            item["kind"] = "embed"
            item["youtubeVideoId"] = ch.get("youtubeVideoId")
        else:
            for _n2, neto in list_child_nodes(ch):
                if neto.get("fileReference"):
                    item["kind"] = "image"
                    item["fileReference"] = neto.get("fileReference")
                    item["alt"] = neto.get("alt", "")
                    break
                if neto.get("youtubeVideoId"):
                    item["kind"] = "embed"
                    item["youtubeVideoId"] = neto.get("youtubeVideoId")
                    break
        if item.get("kind"):
            slides.append(item)
    return slides


def bloco_de(node, caminho, page):
    """Converte um nó folha da origem em Block. None = não gera bloco."""
    rt = rt_of(node)

    if rt in TEXT_TYPES:
        tipo = spacer_kind(node)
        if tipo == "spacer":
            return None
        if tipo == "hr":
            return Block("hr", caminho)
        if tipo == "anchor":
            m = re.search(r"<a\s[^>]*\b(?:name|id)\s*=\s*[\"']([^\"']+)",
                          node.get("text", ""), re.I)
            return Block("anchor", caminho, nome=m.group(1) if m else "")
        bruto = embrulhar_inline_da_raiz(
            normalizar_espacadores(node.get("text", "") or ""))
        # `id` de âncora num `text` COM conteúdo (a R22 só cobre o espaçador):
        # na `/design-gateway` o link "See the full … product lineup here"
        # (`#productlineup`) aponta para um parágrafo, e o clique não fazia
        # nada; nas duas `test-277-*` os 3 alvos do índice são `text` (R39).
        return Block("text", caminho, html=colar_paragrafos(bruto),
                     id=(node.get("id") or "").strip() or None,
                     respiro_antes=bool(_ESPACADOR_INICIO.match(bruto)),
                     respiro_depois=bool(_ESPACADOR_FIM.search(bruto)))

    if rt in DESCARTAVEIS:
        return None

    if rt in TITLE_TYPES:
        txt = node.get("jcr:title") or node.get("text") or ""
        if not _texto_visivel(txt):
            return None
        # Sem `type`, o `title` do GWI é h1: o HTL do componente é
        # `<h1 data-sly-element="${title.type}">` e a policy que os templates
        # do escopo aplicam ("Macnica Title"/"Page Title") é type=h1. A landing
        # `/semiconductors` mostra "Semiconductors" como h1 — o padrão "h2"
        # antigo rebaixava o título. O `heading` continua h2 sem `type`: o
        # HTL dele é `<h2 data-sly-element="${heading.type}">`.
        return Block("title", caminho, titulo=_texto_visivel(txt),
                     tipo=node.get("type") or "h1")

    if rt in HEADING_TYPES:
        txt = node.get("text", "")
        if not _texto_visivel(txt):
            return None
        # `jcr:title` e `type` andam SEMPRE juntos no corpus autoral
        # (413 com os dois, 67 com nenhum, nunca um sem o outro).
        #
        # `alignment=center` no GWI rende `cmp-heading--center`: 14 headings
        # em 10 páginas (família canon, sulfur-som). O style Center existe na
        # policy do title e estava definido aqui sem uso — o título da tabela
        # "Canon CMOS Sensors" saía à esquerda (R13). `left` é o padrão dos
        # dois lados; `right` não ocorre no escopo.
        estilos = (["", "", S_TITLE_CENTER]
                   if str(node.get("alignment") or "").lower() == "center" else [])
        return Block("title", caminho, titulo=_texto_visivel(txt),
                     tipo=node.get("type") or "h2", id=node.get("id"),
                     styles=estilos)

    if rt in IMAGE_TYPES:
        ref = node.get("fileReference")
        if not ref:
            if str(node.get("imageFromPageImage", "")).lower() == "true":
                return None      # vem da propriedade da página, não é bug
            page.pendencias.append(Pendencia(
                caminho, rt, "imagem_quebrada", "sem fileReference"))
            return None
        return Block("image", caminho, fileReference=ref, alt=node.get("alt", ""),
                     linkURL=node.get("linkURL") or "",
                     alinhamento=str(node.get("alignment") or "").lower(),
                     largura_px=_px(node.get("width")))

    if rt in BUTTON_TYPES:
        # `linkTarget` vem da origem: gravado fixo como `_self`, o datasheet
        # externo que o GWI abre em aba nova tirava o visitante do site (R31).
        return Block("button", caminho, titulo=node.get("jcr:title", ""),
                     linkURL=node.get("linkURL", ""),
                     linkTarget=node.get("linkTarget") or "_self")

    if rt in TABLE_TYPES:
        bruto = node.get("text", "") or ""
        # Tabela de LAYOUT: `border="0"`, com `<img>` e sem `<th>` — o GWI a usa
        # só para centrar um ícone sobre a legenda e não desenha borda nenhuma
        # (`/analog-devices`, R16). Continua `table` (é a célula que segura o
        # ícone de 1042px em ~100px), mas sem moldura.
        abre = re.search(r"<table\b[^>]*>", bruto, re.I)
        sem_borda = bool(abre and re.search(r"""\bborder\s*=\s*["']?0\b""",
                                            abre.group(0), re.I))
        # `<br>` pendurado no fim da célula é espaçador do autor, da família
        # do `<p>&nbsp;</p>` que `strip_empty_blocks` apaga — só que dentro do
        # bloco, então passava: a linha ficava 15px mais alta que as vizinhas
        # (`altera-stratix-10-dx`; 24 células em 12 páginas). `<br>` ENTRE
        # textos fica (R32).
        bruto = nao_quebrar_tokens(
            _BR_FIM_DE_CELULA.sub("", normalizar_espacadores(bruto)))
        return Block("table", caminho, html=colar_paragrafos(bruto),
                     de_layout=(sem_borda and "<img" in bruto.lower()
                                and "<th" not in bruto.lower()))

    if rt in VIDEO_TYPES:
        vid = node.get("youtubeVideoId")
        if not vid:
            page.pendencias.append(Pendencia(
                caminho, rt, "video_sem_id", "video sem youtubeVideoId"))
            return None
        return Block("embed", caminho, youtubeVideoId=vid, largura=width_of(node))

    if rt in CAROUSEL_TYPES:
        slides = _carousel_slides(node)
        if not slides:
            page.pendencias.append(Pendencia(
                caminho, rt, "slide_vazio_na_origem",
                "carousel sem slide com mídia — no GWI renderiza div vazia"))
            return None
        return Block("carousel", caminho, slides=slides)

    if rt in DOWNLOAD_TYPES:
        ref = node.get("fileReference")
        if not ref:
            page.pendencias.append(Pendencia(
                caminho, rt, "download_sem_arquivo", "sem fileReference"))
            return None
        # NUNCA inventar rótulo do nome do arquivo: é o que produz os 506
        # rótulos falsos de hoje. O título real é o `dc:title` do asset, que
        # o driver resolve no DAM; aqui fica o que a origem tiver.
        return Block("download", caminho, fileReference=ref,
                     titulo=node.get("jcr:title") or "")

    if rt in DOWNLOADLIST_TYPES:
        itens = []
        for nome, ch in list_child_nodes(node):
            if ch.get("fileReference"):
                itens.append({"fileReference": ch["fileReference"],
                              "titulo": ch.get("jcr:title") or ""})
        if not itens:
            return None
        return Block("downloadlist", caminho, itens=itens)

    if rt in XF_TYPES:
        origem = node.get("fragmentVariationPath", "")
        alvo = XF_MAP.get(origem)
        if not alvo:
            page.pendencias.append(Pendencia(
                caminho, rt, "xf_sem_mapeamento",
                f"fragmentVariationPath não mapeado: {origem}", origem))
            return None
        return Block("xf", caminho, fragmentVariationPath=alvo)

    if rt in RELATED_TYPES:
        # `maxItems` TEM de vir junto: as 26 páginas de design-gateway têm
        # `listFrom=children` + `maxItems=3`, e o GWI mostra só 3 cards. Sem
        # repassar o limite, o driver materializava os 26 filhos do
        # parentPage — 22 itens a mais por página, a maior fatia da "sobra"
        # da primeira varredura (R8 em REGRAS-disposicao.md).
        return Block("related", caminho,
                     listFrom=node.get("listFrom", "static"),
                     pages=node.get("pages"),
                     parentPage=node.get("parentPage"),
                     childDepth=node.get("childDepth"),
                     orderBy=node.get("orderBy"),
                     sortOrder=node.get("sortOrder"),
                     maxItems=node.get("maxItems"),
                     query=node.get("query"),
                     searchIn=node.get("searchIn"),
                     tags=node.get("tags"))

    if rt in TABS_TYPES:
        b = Block("tabs", caminho)
        for nome, item in list_child_nodes(node):
            p = Panel(item.get("cq:panelTitle") or "", f"{caminho}/{nome}")
            p.rows = extrair_linhas(item, p.origin_path, page)
            b.panels.append(p)
        if not b.panels:
            return None
        return b

    if rt in PAGEPROPS_TYPES:
        return None

    if rt in SECTIONLIST_TYPES:
        # Índice de âncoras. O `anchorlink` do destino guarda os itens num
        # multifield COMPOSTO chamado `anchor` (confirmado no cq:dialog:
        # name='./anchor', composite=true, com `./text` e `./linkId` por item).
        #
        # Na origem, `listingMode=automatic` + `useHeadings=true` monta a lista
        # a partir dos HEADINGS da própria página que têm `id` — é o `id` que
        # vira o alvo da âncora. Modo manual traz os itens em `fixedListItems`.
        itens = []
        fixos = node.get("fixedListItems")
        # `fixedListItems` só vale em `listingMode=static` — é o mesmo padrão
        # do `pages` na R11. A página de teste TEST-AUTOGENERATE está em
        # `automatic` e guarda 6 itens fixos RESIDUAIS (cópia da n1-soc): o
        # GWI os ignora e lista os headings da própria página. Ler os fixos
        # em qualquer modo punha "Features"/"N1-655 GenAI" num índice que a
        # origem não mostra.
        estatico = str(node.get("listingMode") or "automatic").lower() == "static"
        if estatico and isinstance(fixos, dict):
            for _n, it in list_child_nodes(fixos):
                # O diálogo do GWI grava `./label` e `./id` (60 de 60 itens
                # do corpus); `text`/`linkId` são os nomes do DESTINO. Ler os
                # nomes errados deixava a lista vazia em todo modo `static`
                # e o fallback por headings inventava um item (R10).
                rotulo = it.get("label") or it.get("text")
                if rotulo:
                    itens.append({"text": rotulo,
                                  "linkId": it.get("id") or it.get("linkId") or ""})
        return Block("anchorlink", caminho,
                     itens=itens,
                     listingMode=node.get("listingMode", "automatic"),
                     useHeadings=str(node.get("useHeadings", "true")).lower() != "false")

    if rt in PRODUCTLISTING_TYPES:
        # O `productlisting` do GWI lista páginas-filhas como cards com link.
        # O destino tem `list`, que é exatamente isso — e é o que a Anion usa
        # (201 `list` contra 1 `cardlist` no corpus). Sem este mapeamento a
        # `/ambarella` perdia os dois links "Ambarella CV72S SoC" e
        # "Ambarella N1 SoC" que o GWI mostra no rodapé da página.
        return Block("productlist", caminho,
                     listFrom=node.get("listFrom", "children"),
                     pages=node.get("pages"),
                     parentPage=node.get("parentPage"),
                     childDepth=node.get("childDepth"),
                     orderBy=node.get("orderBy"),
                     sortOrder=node.get("sortOrder"),
                     maxItems=node.get("maxItems"))

    if rt in IMAGEPACK_TYPES:
        page.pendencias.append(Pendencia(
            caminho, rt, "sem_destino_mapeado", f"{rt} sem componente alvo"))
        return None

    if rt == FORM_CONTAINER_RT:
        return _bloco_form(node, caminho, page)

    if rt:
        page.pendencias.append(Pendencia(
            caminho, rt, "tipo_nao_reconhecido", "nenhum emissor conhece este tipo"))
    return None


def _bloco_form(node, caminho, page):
    """Core Form Container do GWI -> Block('form') (R27).

    O form do GWI é proxy do Core (`form/container/v2`) com a action
    customizada `macnicadefault` (valida o reCAPTCHA e manda os valores por
    e-mail). O global2 tem os MESMOS proxies e a MESMA action, e a policy do
    template permite `form/container` no corpo (não dentro de
    `flexcontaineritem`). Só essa action é migrada: `mail`/`rpc` não existem
    no destino e viram pendência. Levantamento em `PESQUISA-formulario.md`.
    """
    acao = str(node.get("actionType", ""))
    if not acao.endswith("/actions/macnicadefault"):
        page.pendencias.append(Pendencia(
            caminho, rt_of(node), "form_action_sem_alvo",
            f"actionType '{acao}' não existe no global2"))
        return None
    campos, botoes = [], []
    for _n, ch in list_child_nodes(node):
        crt = rt_of(ch)
        if crt == FORM_TEXT_RT:
            campos.append({k: ch[k] for k in _FORM_CAMPO_PROPS if k in ch})
        elif crt == FORM_BUTTON_RT:
            botoes.append({"jcr:title": ch.get("jcr:title", ""),
                           "type": ch.get("type") or "submit"})
        else:
            page.pendencias.append(Pendencia(
                caminho, crt, "campo_de_form_sem_alvo",
                "filho do form sem componente alvo mapeado"))
    mailto = node.get("mailto") or []
    if isinstance(mailto, str):
        mailto = [mailto]
    return Block("form", caminho, subject=node.get("subject", ""),
                 mailto=list(mailto), campos=campos, botoes=botoes)


# ---------------------------------------------------------------------------
# Extração: linhas e colunas
# ---------------------------------------------------------------------------

def _colunas_de(node):
    """Filhos que são coluna de verdade (largura própria, 0<w<12)."""
    return [(n, c) for n, c in list_child_nodes(node)
            if col_width_of(c) is not None and tem_conteudo_renderizavel(c)]


def _is_linha(node):
    """O nó é UMA linha de colunas — e nada além disso.

    Exige que TODO filho renderizável seja coluna. A versão anterior aceitava
    "2+ filhos com largura" e isso descartava em silêncio tudo o que não fosse
    coluna: o item de aba da `/altera` tem 4 títulos e 3 textos de largura
    cheia ao lado de 3 colunas de 4/12, e o resultado foi a aba renderizar só
    as três colunas — "Overview", "Portfolio At-a-Glance", "Where these
    devices fit" e "Why Macnica?" sumiram da tela.
    """
    if col_width_of(node) is not None:
        return False
    renderizaveis = [(n, c) for n, c in list_child_nodes(node)
                     if tem_conteudo_renderizavel(c)]
    colunas = _colunas_de(node)
    return len(colunas) >= 2 and len(colunas) == len(renderizaveis)


def _coletar_blocos(node, caminho, page):
    """Achata um nó de coluna em blocos, na ordem do documento.

    As larguras das FOLHAS aqui dentro são ruído e são ignoradas de propósito:
    na `/altera` a coluna `width=6` contém `text(w=5)` + `button(w=3)`, que
    somam 13 numa coluna de 6. Foi ler isso que quebrou a linha e empurrou o
    vídeo para a linha de baixo.
    """
    out = []
    rt = rt_of(node)
    if rt and rt not in WRAPPER_TYPES:
        b = bloco_de(node, caminho, page)
        return _destacar_hr(b) if b else []
    if rt == IMAGETEXT_RT:
        # O `imagetext` do GWI não é só invólucro: ele tem INTERRUPTORES DE
        # VISIBILIDADE. `isText=false` esconde o texto, `isButton=false`
        # esconde o botão, `isHeading=false` esconde o título — e o GWI
        # respeita isso ao renderizar.
        #
        # Ignorá-los ressuscita conteúdo que o visitante nunca viu. Caso real:
        # na `/ambarella`, dois `imagetext` com isText=false/isButton=true
        # guardam textos de MCU Renesas (RL78/F, RH850) que o GWI não mostra —
        # ele desenha só os dois botões. O motor emitia os textos, e a página
        # migrada ganhava conteúdo de outro fabricante.
        mostra_txt = str(node.get("isText", "true")).lower() != "false"
        mostra_btn = str(node.get("isButton", "true")).lower() != "false"
        mostra_head = str(node.get("isHeading", "true")).lower() != "false"

        filhos = []
        for nome, ch in list_child_nodes(node):
            crt = rt_of(ch)
            if crt in TEXT_TYPES and not mostra_txt:
                continue
            if crt in BUTTON_TYPES and not mostra_btn:
                continue
            if (crt in HEADING_TYPES or crt in TITLE_TYPES) and not mostra_head:
                continue
            filhos.extend(_coletar_blocos(ch, f"{caminho}/{nome}", page))

        # `assetPosition` diz COMO imagem e texto se arranjam. Só
        # `left`/`right` é lado a lado; `top`/`bottom` é EMPILHADO, e o
        # `textwithimage` do destino não tem essa opção (a policy só oferece
        # Left/Wrap/VCenter/VBottom). Tratar `top` como side-by-side espremia
        # o texto numa coluna estreita ao lado da imagem — foi o que
        # aconteceu com os cards CV28AQ/CV28M/H22AQ da `/ambarella`.
        # O `imagetext` desenha UM asset. Na `analog-devices-multimodal-sensor-
        # front-ends` o nó guarda dois filhos de imagem — o `resizableimage` e
        # um `image` residual — com o MESMO arquivo: o GWI mostra um, o motor
        # emitia os dois, e com `len(img)==2` ainda desistia do lado a lado
        # (R25). Mesmo `fileReference` dentro do mesmo imagetext = uma imagem.
        vistos, unicos = set(), []
        for b in filhos:
            ref = b.props.get("fileReference") if b.kind == "image" else None
            if ref and ref in vistos:
                continue
            if ref:
                vistos.add(ref)
            unicos.append(b)
        filhos = unicos

        pos = str(node.get("assetPositionLargeScreen", "")).lower()
        img = [b for b in filhos if b.kind == "image"]
        txt = [b for b in filhos if b.kind == "text"]
        tit = [b for b in filhos if b.kind == "title"]
        if (pos in ("left", "right") and len(img) == 1 and len(txt) >= 1
                and len(filhos) == len(img) + len(txt) + len(tit)):
            # O `heading` do imagetext (isHeading=true) entra no rich text do
            # `textwithimage`, em cima do parágrafo — como o GWI o desenha, na
            # coluna do texto. Antes o título quebrava a condição e o bloco
            # caía em `return filhos`: título, FOTO de 1280px e texto
            # empilhados em largura cheia (`canon-li8030sa`, R21).
            cab = "".join(
                "<{0}{1}>{2}</{0}>".format(
                    t.props.get("tipo") or "h2",
                    ' id="%s"' % escape(t.props["id"], quote=True)
                    if t.props.get("id") else "",
                    escape(t.props.get("titulo", ""), quote=False))
                for t in tit)
            corpo = "".join(t.props.get("html", "") for t in txt)
            return [Block("textwithimage", caminho,
                          fileReference=img[0].props.get("fileReference"),
                          alt=img[0].props.get("alt", ""),
                          html=colar_paragrafos(cab + corpo) if cab else corpo,
                          imagem_esquerda=(pos == "left"),
                          origem_midia="imagetext",
                          largura_px=img[0].props.get("largura_px"),
                          dims=img[0].props.get("dims"),
                          centro_vertical=str(node.get(
                              "elementsPositionVerticalAlignCenter", ""
                          )).lower() == "true")]
        if pos == "top" and img:
            # imagem primeiro, depois o resto, na ordem do documento
            return img + [b for b in filhos if b.kind != "image"]
        if pos == "bottom" and img:
            return [b for b in filhos if b.kind != "image"] + img
        return filhos
    espaco = False
    for nome, ch in list_child_nodes(node):
        if rt_of(ch) in TEXT_TYPES and spacer_kind(ch) == "spacer":
            espaco = True
            continue
        bs = _coletar_blocos(ch, f"{caminho}/{nome}", page)
        if bs:
            if espaco:
                bs[0].props["espaco_antes"] = True
            espaco = False
        out.extend(bs)
    return out


_VAZIO = r"(?:\s|&nbsp;|\u00a0|<br\s*/?>|<p>(?:\s|&nbsp;|\u00a0|<br\s*/?>)*</p>)*"
_HR_INICIO = re.compile(r"^" + _VAZIO + r"<hr\s*/?>" + _VAZIO, re.I)
_HR_FIM = re.compile(_VAZIO + r"<hr\s*/?>" + _VAZIO + r"$", re.I)


def _destacar_hr(b):
    """`<hr>` no começo ou no fim de um `text` com conteúdo vira Block('hr').

    O GWI escreve o separador de duas formas: num `text` só dele (que
    `spacer_kind` já reconhece) e EMBUTIDO no fim do parágrafo anterior —
    `...</p><p>&nbsp;</p><hr><p>&nbsp;</p>`. Embutido, o hr ficava dentro do
    `text`, e como `strip_empty_blocks` apaga os `&nbsp;` que davam o respiro,
    a régua nascia colada na última linha, lendo como sublinhado (R13).
    `<hr>` no MEIO do texto fica onde está.
    """
    if b.kind != "text":
        return [b]
    h = b.props.get("html", "") or ""
    antes, depois = [], []
    m = _HR_INICIO.match(h)
    if m:
        antes = [Block("hr", b.origin_path)]
        h = h[m.end():]
    m = _HR_FIM.search(h)
    if m and "<hr" in m.group(0).lower():
        depois = [Block("hr", b.origin_path)]
        h = h[:m.start()]
    if not antes and not depois:
        return [b]
    b.props["html"] = h
    return antes + ([b] if _texto_visivel(h) else []) + depois


_MIDIA = ("image", "embed", "carousel", "anchorlink", "textwithimage")
# margem vertical (em cima, embaixo) que o CSS do global2 dá ao componente:
# .cmp-table 20/20, .cmp-textwithimage 30/30, .link-button 40/0, ul.cmp-list 55/55
_MARGEM_PROPRIA = {"table": (20, 20), "textwithimage": (30, 30),
                   "button": (40, 0), "related": (55, 55), "productlist": (55, 55),
                   "anchorlink": (0, 60)}


def _nivel(b):
    """2 para h2, 3 para h3… (título sem tipo conta como h2)."""
    m = re.search(r"(\d)", str(b.props.get("tipo") or "h2"))
    return int(m.group(1)) if m else 2


def _quebrar_em_subsecoes(blocos, caminho):
    """Uma Row por SUBSEÇÃO — um título abre subseção.

    Neste design system o título tem `padding-bottom:20px` e NENHUM padding em
    cima: encostado no parágrafo anterior, fica colado. No GWI o respiro vinha
    dos blocos espaçadores `&nbsp;`, descartados aqui de propósito (§1.7). Sem
    esta quebra, "Portfolio At-a-Glance", "Where these devices fit" e "Why
    Macnica?" nascem grudadas — a queixa original que abriu este trabalho.
    """
    grupos, atual = [], []
    for b in blocos:
        # O `hr` fica SOZINHO no seu container: como último bloco do grupo
        # anterior ele nascia colado no texto (gap 0 entre irmãos) e lia como
        # sublinhado do último bullet, não como divisor de seção (R13).
        abre = b.kind in ("title", "hr") or (atual and atual[-1].kind == "hr")
        # …menos o `hr` que vem LOGO depois de um título, sem espaçador: é o
        # FIO do título (24px acima, 24 abaixo no GWI), e título + fio + bloco
        # ficam no mesmo container. Em três containers o fio boiava num branco
        # de 175px e o título "120MXS Eval Kits" ficava mais perto da tabela
        # de cima que do texto que introduz (`canon-120mxs`, R40).
        if (b.kind == "hr" and atual and atual[-1].kind == "title"
                and not b.props.get("espaco_antes")):
            b.props["fio_de_titulo"] = True
            abre = False
        elif (atual and atual[-1].kind == "hr"
              and atual[-1].props.get("fio_de_titulo") and b.kind != "title"
              and not b.props.get("espaco_antes")):
            abre = False
        # Título logo depois de título é SUBTÍTULO: fica no mesmo container.
        # Na `ambarella-n1-soc` o par h2 "Leading the Family…" + h3
        # "High-Performance Edge GenAI…" anda colado no GWI (16px) e saía com
        # 60px, o h2 boiando a meio caminho do bloco de cima (R20).
        if b.kind == "title" and atual and all(x.kind == "title" for x in atual):
            abre = False
            # …menos quando o GWI tem um NÓ espaçador entre os dois e o de
            # baixo é de nível MENOR: h2 "SiTime Buffer Product Lineup",
            # espaçador, h3 do 1º produto — 65px no GWI, igual aos outros h3
            # da série; colado, a série saía 22/71/71/71/71 (R38, 6 páginas).
            if b.props.get("espaco_antes") and _nivel(b) > _nivel(atual[-1]):
                abre = True
        # Texto que o autor do GWI fechou com `<p>&nbsp;</p>` antes de uma
        # imagem (ou abriu com ele depois dela): o respiro era essa linha em
        # branco, que `strip_empty_blocks` apaga — e entre irmãos o gap é 0. A
        # imagem do "Why Macnica?" nascia COLADA no último bullet nas 26
        # `design-gateway` (GWI 44px, destino 0). Só com a evidência do
        # espaçador na origem: sem ele o GWI também cola (R24).
        if atual and not abre:
            ant = atual[-1]
            # texto<->tabela com o espaçador na origem (no fim/começo do
            # `text`, ou como nó à parte): UMA linha em branco no `text`
            # (30 + 20 da `.cmp-table` = 50px; GWI 16 + a linha de 28). Sem
            # isto saía 20px ou 80px conforme o autor digitou a linha dentro
            # ou fora do `text` — o mesmo desenho no GWI.
            if ({ant.kind, b.kind} == {"text", "table"}
                    and (b.props.get("espaco_antes")
                         or (ant.kind == "text" and ant.props.get("respiro_depois"))
                         or (b.kind == "text" and b.props.get("respiro_antes")))):
                if ant.kind == "text":
                    ant.props["linha_depois"] = True
                else:
                    b.props["linha_antes"] = True
            elif ((ant.kind == "text" and ant.props.get("respiro_depois")
                 and b.kind in _MIDIA)
                    or (ant.kind in _MIDIA and b.kind == "text"
                        and b.props.get("respiro_antes"))):
                abre = True
            # O espaçador também vem como NÓ à parte (`text` só com &nbsp;)
            # entre dois blocos: tabela, ESPAÇADOR, vídeo na
            # `canon-li3030sa`. É a mesma evidência da R24, e sem ela a R29
            # colava o vídeo na tabela. Menos depois de título (que anda com o
            # bloco que introduz) e entre dois textos (o `<p>` já traz 30px).
            # Nem antes do XF (o bloco de contato já traz 100px+ de padding
            # interno), nem onde as margens próprias dos dois componentes já
            # dão o respiro (tabela→botão 20+40, imagem→botão 40…): somar 60px
            # de subseção a isso recriaria o aberto G.
            elif (b.props.get("espaco_antes") and ant.kind != "title"
                  and b.kind != "xf"
                  and not (ant.kind == "text" and b.kind == "text")
                  and (_MARGEM_PROPRIA.get(ant.kind, (0, 0))[1]
                       + _MARGEM_PROPRIA.get(b.kind, (0, 0))[0]) < 40):
                abre = True
        if abre and atual:
            grupos.append(atual)
            atual = []
        atual.append(b)
    if atual:
        grupos.append(atual)
    linhas = []
    for g in grupos:
        r = Row("single")
        c = Column(caminho, width=12)
        c.blocks = g
        r.columns = [c]
        linhas.append(r)
    return linhas


def _fundir_textos(blocos):
    """`text` consecutivos na mesma coluna viram UM nó.

    Por causa de `.cmp-text p:first-child{margin-top:0}`, N parágrafos dentro
    de um único `text` rendem 30px entre si no desktop; os mesmos N parágrafos
    em N `text` irmãos rendem 0px. É a alavanca de ritmo mais barata do
    sistema, e é o inverso do que o motor antigo fazia — a causa direta do
    "texto colado".
    """
    out = []
    for b in blocos:
        # `text` com `id` é alvo de âncora: não se funde no de cima, senão o
        # clique pararia no começo do bloco errado (R39)
        if (b.kind == "text" and out and out[-1].kind == "text"
                and not b.props.get("id")):
            out[-1].props["html"] = (out[-1].props.get("html", "")
                                     + b.props.get("html", ""))
            out[-1].props["respiro_depois"] = b.props.get("respiro_depois", False)
            continue
        out.append(b)
    return _fundir_downloads(out)


def _item_download(b):
    return {"fileReference": b.props.get("fileReference", ""),
            "titulo": b.props.get("titulo") or ""}


def _fundir_downloads(blocos):
    """`download`/`downloadlist` consecutivos na mesma coluna viram UMA lista.

    O destino desenha download como tabela Title/Download (decisão do time,
    18/09/2026). Emitir uma tabela POR `download` repete o cabeçalho a cada
    arquivo: numa página com 4 downloads são 8 células de cabeçalho em vez
    de 2, e 4 tabelas empilhadas onde a Anion faz uma. Os `download` do GWI
    vêm sempre em sequência (só espaçadores `&nbsp;` entre eles, que já foram
    descartados aqui), então "consecutivo" é a regra certa — um heading ou
    texto real no meio fecha a lista (R7 em REGRAS-disposicao.md).

    Um `download` sozinho continua `download`: emissão idêntica, e a contagem
    no CSV continua honesta.
    """
    out = []
    for b in blocos:
        if b.kind not in ("download", "downloadlist"):
            out.append(b)
            continue
        itens = (list(b.props.get("itens") or []) if b.kind == "downloadlist"
                 else [_item_download(b)])
        if out and out[-1].kind in ("download", "downloadlist"):
            ant = out[-1]
            if ant.kind == "download":
                out[-1] = Block("downloadlist", ant.origin_path,
                                itens=[_item_download(ant)])
            elif ant.kind == "downloadlist" and not ant.props.get("_fundida"):
                # nunca mutar a lista do bloco de origem
                out[-1] = Block("downloadlist", ant.origin_path,
                                itens=list(ant.props.get("itens") or []))
            out[-1].props["_fundida"] = True
            out[-1].props["itens"].extend(itens)
            continue
        out.append(b)
    return out


def _linha_de(node, caminho, page):
    """Constrói uma Row a partir de um nó que JÁ é uma linha de colunas."""
    r = Row("columns")
    for cn, col in list_child_nodes(node):
        w = col_width_of(col)
        if w is None or not tem_conteudo_renderizavel(col):
            continue
        c = Column(f"{caminho}/{cn}", width=w, phone_width=width_of(col, "phone"))
        c.offset = offset_of(col)
        c.blocks = _fundir_textos(_coletar_blocos(col, c.origin_path, page))
        if c.blocks:
            r.columns.append(c)
    if len(r.columns) < 2:
        r.kind = "single"
        for c in r.columns:
            r.largura_orfa = c.width
            c.width = 12
    return r


def _quebrar_por_largura(r):
    """Uma Row de colunas -> tantas Rows quantas a grade de 12 do GWI desenha (R19).

    A grade responsiva do AEM QUEBRA a linha quando a soma (offset + width)
    passa de 12. Na `/i-chips/i-chips-scaler-lsi` o `resizablecontainer` tem
    seis cards `width=4`: o GWI mostra 3 + 3, e o motor emitia um
    `flexcontainer` de seis itens `flex:1` — seis cards espremidos numa linha,
    40% menores numa página mais larga.
    """
    if r.kind != "columns" or len(r.columns) < 2:
        return [r]
    grupos, atual, soma = [], [], 0
    for c in r.columns:
        ocupa = (c.width or 12) + (c.offset or 0)
        if atual and soma + ocupa > 12:
            grupos.append(atual)
            atual, soma = [], 0
        atual.append(c)
        soma += ocupa
    grupos.append(atual)
    if len(grupos) == 1:
        return [r]
    out = []
    for g in grupos:
        nova = Row("columns" if len(g) > 1 else "single")
        nova.columns = g
        if len(g) == 1:
            nova.largura_orfa = g[0].width
            g[0].width = 12
        out.append(nova)
    return out


def _titulo_com_colunas(linhas):
    """Título que introduz uma linha de COLUNAS vai para o container dela (R23).

    A 13d já faz o título acompanhar tabela, carousel e invólucro. Para linha
    de colunas não fazia: o título ficava sozinho num sub-container e o
    `flexcontainer` no seguinte, 60px abaixo (30+30) — contra 25–32px no GWI
    (`/altera` "Leading Altera FPGAs…", `macnica-and-adi` "Why Engage…", os
    h3 de "Focus Markets" da `agilex-5`, equidistantes do bloco de cima e das
    colunas que introduzem).
    """
    out = []
    for r in linhas:
        ant = out[-1] if out else None
        if (ant is not None and r.kind == "columns" and ant.kind == "single"
                and not ant.cabecalho and ant.blocks
                and all(b.kind == "title" for b in ant.blocks)):
            r.cabecalho = ant.blocks
            out[-1] = r
        else:
            out.append(r)
    return out


def _e_card_orfao(node):
    """Invólucro cujo único filho renderizável é UMA coluna (`0 < width < 12`)."""
    if rt_of(node) not in WRAPPER_TYPES or rt_of(node) == IMAGETEXT_RT:
        return False
    vivos = [c for _n, c in list_child_nodes(node) if tem_conteudo_renderizavel(c)]
    return len(vivos) == 1 and col_width_of(vivos[0]) is not None


def _grade_uniforme(r):
    """(n, largura) se a Row é uma linha de 2+ colunas de MESMA largura."""
    if r.kind != "columns" or len(r.columns) < 2:
        return None
    ws = {c.width for c in r.columns}
    return (len(r.columns), ws.pop()) if len(ws) == 1 else None


def _completar_grades(linhas):
    """Última linha de uma grade, com menos cards, é completada com vazios (R18).

    No GWI a grade é de largura fixa: três cards `width=3` numa linha e, na
    linha seguinte, dois cards `width=3` — que ficam sob as duas primeiras
    colunas. No destino o `flexcontaineritem` é `flex:1`: os dois cards
    esticavam para 50% cada (`/ambarella`, H32AQ/A12AQ) e o card sozinho
    virava faixa de largura cheia (`/canon`, o "Aberto C"). Completar a linha
    com itens VAZIOS devolve a largura da coluna.

    Só vale para linha IMEDIATAMENTE abaixo de uma linha de colunas uniformes
    da mesma largura: é a evidência de que as duas são a mesma grade.
    """
    ref = None
    for r in linhas:
        g = _grade_uniforme(r)
        if g:
            if ref and g[1] == ref[1] and g[0] < ref[0]:
                r.vazias = ref[0] - g[0]
            else:
                ref = g
        elif (ref and r.kind == "single" and r.largura_orfa == ref[1]
              and len(r.columns) == 1):
            r.kind = "columns"
            r.vazias = ref[0] - 1
        else:
            ref = None
    return linhas


def extrair_linhas(node, caminho, page):
    """Filhos de um nó viram linhas: `single` ou `columns`.

    O próprio `node` pode SER a linha — é o caso da seção de intro da
    `/altera`, cujo nó de topo é o `resizablecontainer` que segura as duas
    colunas. Sem este teste as colunas eram achatadas numa corrida só e o
    resultado era [text+button+embed] empilhado: exatamente o defeito
    original (botão no lugar errado, vídeo fora da linha).
    """
    # `imagetext` filho DIRETO do corpo chega aqui como invólucro. Iterar os
    # filhos pulava o único ramo que lê `assetPositionLargeScreen` e os
    # interruptores isText/isButton/isHeading (`_coletar_blocos`): o bloco
    # "Features" da `agilex-7-i-series` (lista | foto, lado a lado) saía
    # empilhado com a foto em cima, e a R1 ficava sem efeito para todo
    # imagetext de topo — 19 nós em 8 páginas (R13).
    if rt_of(node) == IMAGETEXT_RT:
        blocos = _fundir_textos(_coletar_blocos(node, caminho, page))
        return _quebrar_em_subsecoes(blocos, caminho)

    if _is_linha(node):
        r = _linha_de(node, caminho, page)
        return _completar_grades(_quebrar_por_largura(r)) if r.columns else []

    linhas = []
    corrida = []          # folhas consecutivas de largura cheia
    colunas = []          # colunas consecutivas -> uma linha
    antes = []            # a corrida que a 1ª coluna interrompeu (R29)
    vivos = [c for _n, c in list_child_nodes(node) if tem_conteudo_renderizavel(c)]

    def fechar_corrida():
        """Fecha a corrida, quebrando numa Row por SUBSEÇÃO.

        Um título abre subseção. Isso existe porque neste design system o
        título tem `padding-bottom:20px` e NENHUM padding em cima: encostado
        no parágrafo anterior, ele fica colado. No GWI o respiro vinha dos
        blocos espaçadores `&nbsp;`, que aqui são descartados de propósito
        (§1.7) — sem quebrar em subseção, "Portfolio At-a-Glance", "Where
        these devices fit" e "Why Macnica?" voltam a nascer grudadas, que foi
        a queixa original.
        """
        if not corrida:
            return
        blocos = _fundir_textos(corrida[:])
        corrida.clear()
        linhas.extend(_quebrar_em_subsecoes(blocos, caminho))

    def fechar_colunas():
        if not colunas:
            return
        # A corrida que a 1ª coluna interrompeu só é fechada AQUI, quando já se
        # sabe se era coluna de verdade. Fechá-la na chegada da coluna deixava
        # o título "Resources" das 7 `design-gateway/*nvme*` numa Row e o botão
        # que ele introduz (`width=4`, coluna SOLITÁRIA, logo largura cheia) na
        # seguinte: 89px do título, 90px do título de baixo — boiando (R29).
        corrida[:0] = antes
        antes.clear()
        if len(colunas) == 1:
            g = _grade_uniforme(linhas[-1]) if (linhas and not corrida) else None
            so_ele = (not linhas and not corrida and len(vivos) == 1
                      and not any(b.kind == "title" for b in colunas[0].blocks))
            if so_ele or (g and g[1] == colunas[0].width):
                # card órfão de uma grade: continua coluna (R18). `so_ele`: o
                # invólucro inteiro é UMA coluna — se a seção de cima for a
                # grade, `_completar_grades` de `extract_tree` o completa; se
                # não for, sai como antes (largura cheia).
                r = Row("single")
                r.largura_orfa = colunas[0].width
                r.columns = colunas[:]
                linhas.append(r)
            else:
                # coluna sozinha não é coluna: vira conteúdo de largura cheia,
                # na MESMA corrida que ela interrompeu
                corrida.extend(colunas[0].blocks)
        else:
            fechar_corrida()
            r = Row("columns")
            r.columns = colunas[:]
            linhas.extend(_quebrar_por_largura(r))
        colunas.clear()

    espaco = False        # passou um `text` espaçador desde o último bloco (R24)

    def marcar(blocos):
        nonlocal espaco
        if blocos:
            if espaco:
                blocos[0].props["espaco_antes"] = True
            espaco = False
        return blocos

    for nome, ch in list_child_nodes(node):
        p = f"{caminho}/{nome}"
        if not tem_conteudo_renderizavel(ch):
            if rt_of(ch) in TEXT_TYPES:
                espaco = True
            continue

        w = col_width_of(ch)
        if w is not None:
            # É uma coluna. Colunas irmãs CONSECUTIVAS formam uma linha; o que
            # vier no meio (título de largura cheia, por exemplo) fecha a linha
            # e começa outra — é assim que o item de aba da `/altera` produz
            # título + 3 colunas + título, em vez de perder os títulos.
            c = Column(p, width=w, phone_width=width_of(ch, "phone"))
            c.offset = offset_of(ch)
            c.blocks = _fundir_textos(marcar(_coletar_blocos(ch, p, page)))
            if c.blocks:
                if not colunas:
                    antes[:] = corrida
                    corrida.clear()
                colunas.append(c)
            continue

        fechar_colunas()
        if _e_card_orfao(ch) and linhas and not corrida:
            g = _grade_uniforme(linhas[-1])
            r = _linha_de(ch, p, page)
            if g and r.columns and r.largura_orfa == g[1]:
                # invólucro com UMA coluna logo abaixo de uma grade da mesma
                # largura: é o card que sobrou da grade (`/canon`, R18)
                linhas.append(r)
                continue
        if _is_linha(ch) and rt_of(ch) != IMAGETEXT_RT:
            fechar_corrida()
            r = _linha_de(ch, p, page)
            if r.columns:
                linhas.extend(_quebrar_por_largura(r))
            continue
        corrida.extend(marcar(_coletar_blocos(ch, p, page)))

    fechar_colunas()
    fechar_corrida()
    return _titulo_com_colunas(_completar_grades(linhas))


# ---------------------------------------------------------------------------
# Extração: seções
# ---------------------------------------------------------------------------

def _classificar_topologia(corpo):
    """AGRUPADA (91%) | PLANA | MISTA.

    PLANA é a exceção que a regra de topo não cobre: quando o corpo não tem
    nenhum filho-invólucro (a `/altera/agilex` tem 23 filhos, todos folha), a
    regra degenera em uma seção por componente — exatamente a doença que
    estamos curando. Nessas, e SÓ nessas, o spacer `&nbsp;` é o delimitador:
    17 dos 19 spacers de topo dessas páginas caem imediatamente antes de um
    heading, productlisting ou experiencefragment.
    """
    filhos = [ch for _n, ch in list_child_nodes(corpo)]
    if not filhos:
        return "AGRUPADA"
    inv = sum(1 for ch in filhos if rt_of(ch) in WRAPPER_TYPES or not rt_of(ch))
    folhas = len(filhos) - inv
    if inv == 0:
        return "PLANA"
    if folhas > inv:
        return "MISTA"
    return "AGRUPADA"


# Blocos que sempre abrem seção própria: são peças grandes, com identidade
# visual própria, e é imediatamente antes deles que caem 17 dos 19 spacers de
# topo das páginas PLANAS.
#
# `table` e `productlist` SAÍRAM daqui (R28): onde o GWI tem o espaçador antes
# deles, o espaçador já corta a corrida; onde não tem, o GWI os desenha
# colados no texto que os apresenta (texto→tabela 16px, tabela→botão 13px na
# `/altera/agilex`) e a seção própria punha 130 e 170px — o botão "Product
# Overview" agrupava com a série SEGUINTE.
MAJOR = {"tabs", "xf", "related", "carousel", "anchorlink"}


def _secoes(corpo, caminho, page):
    """Fronteira de seção — cobre as três topologias com uma regra só.

    AGRUPADA (91% das páginas): todo filho de topo é invólucro, então cada um
    vira uma seção — que é exatamente a regra validada por falsificação sobre
    212 pares (precisão 99,3%, recall 96,3%).

    PLANA/MISTA: onde o corpo tem folhas soltas, a regra de topo degenera em
    uma seção por parágrafo. Aí as folhas consecutivas são agrupadas numa
    seção só, e o corte vem do spacer `&nbsp;` ou da chegada de um bloco
    grande (tabs, CTA, tabela...). Sem isso a `/altera/agilex` viraria 19
    seções e a `/altera` viraria 12.
    """
    secoes = []
    corrida = []          # folhas consecutivas aguardando fechamento

    def fechar():
        if not corrida:
            return
        s = Section(corrida[0][1], len(secoes))
        blocos = []
        for ch, p in corrida:
            blocos.extend(_coletar_blocos(ch, p, page))
        blocos = _fundir_textos(blocos)
        corrida.clear()
        if not blocos:
            return
        s.rows = _quebrar_em_subsecoes(blocos, s.origin_path)
        s._de_corrida = True
        secoes.append(s)

    def titulo_que_introduz():
        """Os títulos imediatamente anteriores acompanham o bloco grande que abrem.

        Em página MISTA/PLANA o heading é folha solta e o bloco que ele
        introduz (table, carousel, imagetext, invólucro) abre seção própria.
        O título ficava para trás, como último item da seção anterior: na
        `agilex-7-i-series`, "Features" e "Specifications" nasciam MAIS PERTO
        do bloco de cima (90px) que do conteúdo que anunciam (170px), porque
        entre os dois se somavam três paddings de container (R13). Vale
        também com espaçador no meio, que já tinha fechado a corrida.

        TODOS os títulos consecutivos do fim, não só o último: na `/canon` o
        h2 "Canon Image Sensors" e o h3 "Ultra-High Resolution Industrial
        Sensors" andam colados no GWI (16px) e introduzem a mesma grade; só o
        h3 vinha, e o h2 ficava sozinho numa seção, a 80px dele — boiando
        entre o bloco de cima e o subtítulo (R30, a R20 na fronteira de seção).
        Devolve a lista (vazia se não há título).
        """
        ts = []
        if corrida:
            while corrida and (rt_of(corrida[-1][0]) in HEADING_TYPES
                               or rt_of(corrida[-1][0]) in TITLE_TYPES):
                ch_t, p_t = corrida.pop()
                b_t = bloco_de(ch_t, p_t, page)
                if b_t:
                    ts.insert(0, b_t)
            return ts
        if secoes and getattr(secoes[-1], "_de_corrida", False):
            ult = secoes[-1]
            if ult.rows and all(b.kind == "title" for b in ult.rows[-1].blocks):
                ts = ult.rows.pop().blocks
                if not ult.rows:
                    secoes.pop()
        return ts

    corte = False         # passou espaçador de topo desde o último bloco

    def cortar(b=None):
        """Aplica o corte pendente do espaçador — com as exceções da R24 estendida.

        Não corta DEPOIS de título (o título anda com o bloco que introduz:
        na `namuga-vicon-lite`, heading, ESPAÇADOR, imagem deixava "Ready to
        Evaluate Vicon Lite?" sozinho numa seção, a 60px da imagem) nem ANTES
        de botão (a margem própria dele já separa: na `/toppan` tabela,
        ESPAÇADOR, botão ficava a 140px, o botão do datasheet mais perto da
        série seguinte). `b` é o bloco-folha que chega; invólucro passa None.
        """
        nonlocal corte
        if not corte:
            return
        corte = False
        if corrida and (rt_of(corrida[-1][0]) in HEADING_TYPES
                        or rt_of(corrida[-1][0]) in TITLE_TYPES):
            return
        if b is not None and b.kind == "button":
            return
        fechar()

    for i, (nome, ch) in enumerate(list_child_nodes(corpo)):
        p = f"{caminho}/{nome}"

        if not tem_conteudo_renderizavel(ch):
            # spacer de topo: não é conteúdo, mas CORTA a corrida de folhas.
            # Tem de vir ANTES de `so_pageproperties`, que devolve True para
            # todo nó sem conteúdo: com a ordem trocada este ramo era código
            # morto e o espaçador nunca cortava nada (R28). O corte fica
            # PENDENTE até se conhecer o próximo bloco — ver `cortar()`.
            if rt_of(ch) in TEXT_TYPES:
                corte = True
            continue
        if so_pageproperties(ch):
            continue

        rt = rt_of(ch)
        folha = bool(rt) and rt not in WRAPPER_TYPES

        if folha:
            b = bloco_de(ch, p, page)
            if not b:
                continue
            cortar(b)
            if b.kind in MAJOR:
                # related/xf ficam de fora: a seção deles tem papel próprio
                # em `_marcar_papeis` (sem padding; CTA) que depende de o
                # bloco estar SOZINHO na seção. `tabs` ficava também (era o
                # aberto H): o título numa seção e a faixa das abas na
                # seguinte — 152px contra 80 na `/namuga`, 150 na
                # `/design-gateway`. Agora entra na faixa, em cima da barra de
                # abas; `_marcar_papeis` aceita {title, tabs}.
                ts = (titulo_que_introduz()
                      if b.kind not in ("related", "xf") else [])
                fechar()
                s = Section(p, len(secoes),
                            role="related" if b.kind == "related" else "body")
                r = Row("single")
                c = Column(p, width=12)
                c.blocks = ts + [b]
                r.columns = [c]
                s.rows = [r]
                secoes.append(s)
            else:
                corrida.append((ch, p))
            continue

        # invólucro: seção própria, com suas linhas e colunas
        cortar()
        ts = titulo_que_introduz()
        fechar()
        s = Section(p, len(secoes))
        s.rows = extrair_linhas(ch, p, page)
        if ts:
            if s.rows and s.rows[0].kind == "single" and s.rows[0].columns:
                s.rows[0].columns[0].blocks[:0] = ts
            else:
                r0 = Row("single")
                c0 = Column(p, width=12)
                c0.blocks = ts
                r0.columns = [c0]
                s.rows.insert(0, r0)
        if s.rows:
            secoes.append(s)

    fechar()
    for i, s in enumerate(secoes):
        s.origin_index = i
    return secoes


def _ids_de_espacador_para_titulo(jcr_content):
    """`id` de âncora gravado num `text` ESPAÇADOR passa para o título seguinte (R22).

    Nas `/sitime/*` o alvo do índice de âncoras não é o heading: é o `text`
    vazio logo antes dele — `{id: "xos", text: "<p>&nbsp;</p>"}` ou
    `{id: "tcxos", text: "<p>&nbsp;</p><hr><p>&nbsp;</p>"}`. O motor descarta
    o espaçador e emite o `hr` sem `id`: os 14 links do índice de 3 páginas
    não rolavam para lugar nenhum, e nenhum print mostra isso. O `title` do
    destino aceita `id` (é o que as outras âncoras já usam).
    Trabalha numa cópia: o JCR de entrada pode estar em cache.
    """
    jcr_content = copy.deepcopy(jcr_content)

    def visita(node):
        filhos = list_child_nodes(node)
        for i, (_n, ch) in enumerate(filhos):
            if (rt_of(ch) in TEXT_TYPES and ch.get("id")
                    and not _texto_visivel(ch.get("text", "") or "")):
                for _m, prox in filhos[i + 1:]:
                    if not tem_conteudo_renderizavel(prox):
                        continue
                    # o título pode estar um nível abaixo: o primeiro
                    # renderizável de um invólucro (`sitime-clock-buffers`)
                    while rt_of(prox) in WRAPPER_TYPES:
                        vivos = [c for _k, c in list_child_nodes(prox)
                                 if tem_conteudo_renderizavel(c)]
                        if not vivos:
                            break
                        prox = vivos[0]
                    if ((rt_of(prox) in HEADING_TYPES or rt_of(prox) in TITLE_TYPES)
                            and not prox.get("id")):
                        prox["id"] = ch.pop("id")
                    break
            visita(ch)

    visita(jcr_content)
    return jcr_content


def extract_tree(jcr_content, source_path, archetype=None):
    """Ponto de entrada. Devolve Page (com .pendencias e .page_props)."""
    page = Page(source_path, archetype)
    page.template = jcr_content.get("cq:template") or None
    page.page_props = _page_props(jcr_content)
    jcr_content = podar_nos_mortos(jcr_content, page)
    jcr_content = _ids_de_espacador_para_titulo(jcr_content)
    corpo, caminho = achar_corpo(jcr_content)
    if corpo is None:
        page.pendencias.append(Pendencia(
            source_path, "", "sem_corpo", "jcr:content/root/container não existe"))
        return page

    page.topology = _classificar_topologia(corpo)
    page.sections = _secoes(corpo, caminho, page)
    # a grade pode continuar na SEÇÃO seguinte: na `/ambarella` cada linha de
    # cards é um `resizablecontainer` de topo, logo uma seção (R18)
    _completar_grades([r for sec in page.sections for r in sec.rows])
    # depois da grade (que olha a Row anterior): o título que a 13d trouxe
    # para a seção junta-se à linha de colunas que ele introduz (R23)
    for sec in page.sections:
        sec.rows = _titulo_com_colunas(sec.rows)

    _resolver_anchorlinks(page)
    _marcar_papeis(page)
    return page


def _resolver_anchorlinks(page):
    """Modo `automatic`: os itens vêm dos headings COM `id` da própria página.

    Tem de rodar depois da árvore montada, porque precisa ver todos os títulos
    na ordem do documento.
    """
    titulos = [b for b in page.blocks if b.kind == "title" and b.props.get("id")]
    for b in page.blocks:
        if b.kind != "anchorlink" or b.props.get("itens"):
            continue
        # `static` sem itens fixos é lista vazia no GWI também — completar
        # com headings aqui inventava um índice que a origem não tem (a
        # `ambarella-n1-soc` ganhava "The N1 Family At-a-Glance" no lugar dos
        # 6 rótulos autorais). Vira pendência `anchorlink_sem_itens` no emissor.
        if str(b.props.get("listingMode") or "automatic").lower() == "static":
            continue
        if not b.props.get("useHeadings"):
            continue
        b.props["itens"] = [{"text": t.props.get("titulo", ""),
                             "linkId": t.props["id"]} for t in titulos]


def _marcar_papeis(page):
    """Papel e aparência de cada seção.

    Fundo é propriedade de SEÇÃO (decisão do time, 18/09/2026). Só seção de
    apoio recebe cor — a zebra por bloco do motor antigo morreu aqui.
    """
    for s in page.sections:
        kinds = {b.kind for b in s.blocks}
        if s.role == "related" or kinds == {"productlist"}:
            s.pad_tb = "none"          # o <ul> já traz margin 55px
            s.background = None
        elif "tabs" in kinds and kinds <= {"tabs", "title"}:
            # só a seção que é O bloco de abas ganha faixa — pintar uma seção
            # que apenas CONTÉM abas pintaria a página inteira
            s.role = "tabs"
            s.background = COR_APOIO
            s.full_bleed = True
        elif "xf" in kinds and len(s.blocks) == 1:
            s.role = "cta"
            s.background = None
    # alterna o respiro para dar 80px no desktop entre seções (Small+Default)
    for i, s in enumerate(page.sections):
        if s.role in ("related",) or {b.kind for b in s.blocks} == {"productlist"}:
            continue
        s.pad_tb = "small" if i % 2 == 0 else "default"
        # Seção que é SÓ um `textwithimage`: o componente já traz 30px de
        # margem em cima e embaixo. Somada ao padding das duas seções dava
        # 110–140px em volta de cada bloco (hero das 36 páginas
        # design-gateway/sitime/canon; a série "Why Choose" da `/ambarella`;
        # a série da `/renesas` partida no meio) (R28).
        if (len(s.rows) == 1 and not s.rows[0].cabecalho and s.blocks
                and (all(b.kind == "textwithimage" for b in s.blocks)
                     or _tentar_textwithimage(s.rows[0]) is not None)):
            s.pad_tb = "none"
        # {título(s) + textwithimage}: o título precisa do respiro de cima,
        # então `small` — o 1º item da série "Why Choose" da `/ambarella`
        # ficava a 110 do divisor e os outros 12 a 60.
        elif (len(s.rows) == 1 and len(s.blocks) > 1
              and s.blocks[-1].kind == "textwithimage"
              and all(b.kind == "title" for b in s.blocks[:-1])):
            s.pad_tb = "small"
    # `related` sem padding (o `<ul>` traz 55px) supõe que a seção de CIMA
    # pague o respiro. Seção com subseções deixou de pagar (R28b): o título
    # "Similar Products" ficava a 30px do texto de cima e a 55 da própria lista
    # (4 `/sitime`, `canon-li8030sa`). Só fica `none` depois do XF, que traz
    # 100px+ de padding interno.
    for ant, s in zip(page.sections, page.sections[1:]):
        if s.role == "related" and not (ant.blocks and ant.blocks[-1].kind == "xf"):
            s.pad_tb = "small"
    # Seção que é SÓ o XF de contato: o fragmento já traz 100px+ de padding
    # próprio (dois containers de 50). Os 30|50 do nosso container em cima e
    # embaixo só aumentavam o buraco antes dos botões (lista→botão 245px
    # contra 104 na `altera-max-10`; pedido por 2 revisores independentes).
    for s in page.sections:
        if s.role == "cta":
            s.pad_tb = "none"


def _page_props(jcr_content):
    """Propriedades de página. NUNCA viram conteúdo."""
    props = {}
    logo = jcr_content.get("manufacturerlogo")
    if isinstance(logo, dict) and logo.get("fileReference"):
        props["manufacturerlogo"] = {
            "fileReference": logo["fileReference"],
            "alt": logo.get("alt") or "",
        }
    return props


# ---------------------------------------------------------------------------
# Emissão
# ---------------------------------------------------------------------------

PAD_TB = {"none": S_CONT_TB_NONE, "small": S_CONT_TB_SMALL,
          "default": "", "large": S_CONT_TB_LARGE}
PAD_LR = {"none": S_CONT_LR_NONE, "large": S_CONT_LR_LARGE, "default": ""}


class _Nomes:
    """Nomes de nó determinísticos POR PAI.

    O motor antigo derivava o nome de uma contagem de chaves do payload, o que
    produzia `text_5, text_16, text_27` em vez de `text_1..3`. Não colidia, mas
    impedia diff legível e reexecução idempotente (`aem_lib.py:2099`).
    """

    def __init__(self):
        self.c = {}

    def __call__(self, pai, kind):
        chave = (pai, kind)
        self.c[chave] = self.c.get(chave, 0) + 1
        return f"{kind}_{self.c[chave]}"


def _styles(payload, base, ids):
    """Grava cq:styleIds na forma canônica posicional.

    Sem `@TypeHint=String[]` o Sling grava lista de 1 elemento como String
    simples, e o diálogo do AEM reabre sem as opções marcadas.
    """
    while ids and ids[-1] == "":
        ids = ids[:-1]
    if not ids:
        return
    payload[f"{base}/cq:styleIds"] = ids
    payload[f"{base}/cq:styleIds@TypeHint"] = "String[]"


def _container(payload, base, *, max_width=False, pad_tb="default",
               pad_lr="default", background=None):
    payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{base}/sling:resourceType"] = RT["container"]
    if background:
        payload[f"{base}/backgroundColor"] = background
    _styles(payload, base, [
        S_CONT_1000 if max_width else "",
        PAD_TB.get(pad_tb, ""),
        PAD_LR.get(pad_lr, ""),
    ])


def _emitir_bloco(payload, pai, nomes, b, page, link_de=None, link_para=None):
    """Um Block -> nós no payload. Emissor TOTAL: o que não souber emitir vira
    pendência explícita, nunca descarte silencioso (o bug de `aem_lib.py:2067`
    descartava embed/carousel/list dentro de aba e contava como migrado)."""

    def html(s):
        s = strip_empty_blocks(s or "")
        if link_de and link_para:
            s = rewrite_links_in_html(s, link_de, link_para)
        return s

    k = b.kind

    if k == "text":
        n = nomes(pai, "text")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["text"]
        # linha em branco que `_respiro_na_coluna` mandou manter (R24b): entra
        # DEPOIS de `strip_empty_blocks`, que a apagaria
        corpo = html(b.props.get("html", ""))
        if b.props.get("linha_antes"):
            # a linha vira o 1º filho; o `<p>` que ERA o 1º passaria a ganhar
            # os 30px de margem — e o respiro seria pago duas vezes
            corpo = _LINHA_EM_BRANCO + re.sub(r"^\s*<p>", '<p style="margin-top:0">',
                                              corpo, count=1)
        if b.props.get("linha_depois"):
            corpo += _LINHA_EM_BRANCO
        payload[f"{base}/text"] = corpo
        if b.props.get("id"):
            payload[f"{base}/id"] = b.props["id"]      # core text v2: vira o id do <div>
        payload[f"{base}/textIsRich"] = "true"
        return True

    if k == "title":
        n = nomes(pai, "title")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["title"]
        # jcr:title e type andam SEMPRE juntos (413 com os dois, 67 com
        # nenhum, nunca um sem o outro no corpus autoral).
        payload[f"{base}/jcr:title"] = b.props.get("titulo", "")
        payload[f"{base}/type"] = b.props.get("tipo") or "h2"
        # o `id` da origem é o alvo das âncoras do anchorlink — sem ele os
        # links do índice apontam para lugar nenhum
        if b.props.get("id"):
            payload[f"{base}/id"] = b.props["id"]
        _styles(payload, base, b.props.get("styles") or [])
        return True

    if k == "title_vazio":
        # Title SEM jcr:title e SEM type: o AEM renderiza o pageTitle da
        # página como h1. Idioma autoral confirmado (65 de 196 páginas) e a
        # forma de reproduzir o cabeçalho do GWI sem inventar conteúdo — o h1
        # servido pelo GWI é o pageTitle, não o jcr:title.
        n = nomes(pai, "title")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["title"]
        return True

    if k == "image":
        n = nomes(pai, "image")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["image"]
        payload[f"{base}/fileReference"] = b.props.get("fileReference", "")
        payload[f"{base}/alt"] = b.props.get("alt", "") or ""
        payload[f"{base}/altValueFromDAM"] = "false"
        payload[f"{base}/isDecorative"] = "false"
        # banner clicável (`macnica-and-adi`: a imagem TEM um botão desenhado
        # e o `resizableimage` aponta para #contact-form)
        url = b.props.get("linkURL") or ""
        if url:
            if link_de and link_para and url.startswith(link_de):
                url = link_para + url[len(link_de):]
            payload[f"{base}/linkURL"] = url
        # foto de card alinhada com a legenda (R35): ver `_emitir_linha`
        if b.props.get("a_esquerda"):
            _styles(payload, base, ["", S_IMG_LEFT])
        # SEM spImage: experimento A/B na mesma imagem deu 0px de diferença em
        # 32 de 32 medições (390px e 1400px). Não é art direction (209 de 220
        # apontam o mesmo asset) e a policy tem disableLazyLoading=true, então
        # preencher faz o celular baixar o arquivo duas vezes.
        return True

    if k == "textwithimage":
        n = nomes(pai, "textwithimage")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["textwithimage"]
        payload[f"{base}/fileReference"] = b.props.get("fileReference", "")
        payload[f"{base}/alt"] = b.props.get("alt", "") or ""
        payload[f"{base}/text"] = html(b.props.get("html", ""))
        payload[f"{base}/textIsRich"] = "true"
        ratio = _image_ratio(b, getattr(page, "_util_px", JANELA_REF_PX - 50))
        if ratio and ratio != 50:
            payload[f"{base}/imageRatio"] = str(ratio)
        # padrão do componente é imagem à DIREITA (row-reverse); só carimba
        # quando a origem põe a imagem primeiro (174 de 179 casos autorais)
        # `elementsPositionVerticalAlignCenter` do imagetext: o GWI centra o
        # texto na altura da foto; sem o style ele sobe para o topo e sobra um
        # buraco embaixo (`canon-li8030sa`: 0 em cima, 231px embaixo) (R34).
        # forma posicional: [Image Position, Text Wrapping, Vertical Alignment]
        _styles(payload, base, [
            S_TWI_LEFT if b.props.get("imagem_esquerda") else "", "",
            S_TWI_VCENTER if b.props.get("centro_vertical") else ""])
        return True

    if k == "button":
        n = nomes(pai, "button")
        base = f"{pai}/{n}"
        url = b.props.get("linkURL", "")
        if link_de and link_para and url.startswith(link_de):
            url = link_para + url[len(link_de):]
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["button"]
        payload[f"{base}/jcr:title"] = b.props.get("titulo", "")
        payload[f"{base}/linkURL"] = url
        payload[f"{base}/linkTarget"] = b.props.get("linkTarget") or "_self"
        # "Fit to Text" NÃO encolhe (só declara width:fit-content e o
        # min-width:550px do desktop continua valendo); quem encolhe é
        # "Fixed Minimum Width" (345px).
        _styles(payload, base, ["", S_BTN_FIXEDMIN, S_BTN_CENTER])
        return True

    if k == "table":
        n = nomes(pai, "table")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["table"]
        # HTML cru do GWI preservado: não existe UMA regra CSS para <table>
        # dentro de .cmp-text (0 ocorrências no site.css), então jogar tabela
        # num `text` perde a formatação inteira.
        payload[f"{base}/text"] = html(b.props.get("html", ""))
        payload[f"{base}/textIsRich"] = "true"
        if b.props.get("de_layout"):
            _styles(payload, base, [S_TABLE_BLACK, S_TABLE_NOBG,
                                    S_TABLE_NOROUND, S_TABLE_NOFRAME])
        else:
            _styles(payload, base, ["", "", S_TABLE_NOROUND])
        return True

    if k == "embed":
        # Vídeo SOZINHO que no GWI ocupa 7 ou 8 doze avos (569-651px): fora de
        # coluna o `layout=responsive` o esticava para a largura da página —
        # 1350x759 numa janela de 1400, três quartos da tela
        # (`i-chips-scaler-lsi`, `/altera/agilex`). Ganha um `flexcontainer`
        # com um item vazio ao lado: metade da linha, 662x372 (R26).
        larg = b.props.get("largura")
        if larg and larg <= 8 and "flexcontaineritem" not in pai:
            fc = f"{pai}/{nomes(pai, 'flexcontainer')}"
            payload[f"{fc}/jcr:primaryType"] = "nt:unstructured"
            payload[f"{fc}/sling:resourceType"] = RT["flexcontainer"]
            _styles(payload, fc, ["", S_FLEX_SP_1COL])
            for i in (1, 2):
                payload[f"{fc}/flexcontaineritem_{i}/jcr:primaryType"] = "nt:unstructured"
                payload[f"{fc}/flexcontaineritem_{i}/sling:resourceType"] = RT["flexcontaineritem"]
            pai = f"{fc}/flexcontaineritem_1"
        n = nomes(pai, "embed")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["embed"]
        payload[f"{base}/type"] = "embeddable"
        payload[f"{base}/embeddableResourceType"] = YOUTUBE_RT
        payload[f"{base}/youtubeVideoId"] = b.props.get("youtubeVideoId", "")
        # Divergência deliberada da referência: a Anion usa layout='fixed' nos
        # 8 embeds e o iframe fica travado em height=390 (medido 462x396 numa
        # coluna e 340x396 no celular). Copiar seria regressão.
        payload[f"{base}/layout"] = "responsive"
        return True

    if k == "carousel":
        slides = b.props.get("slides") or []
        n = nomes(pai, "carousel")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["carousel"]
        sn = _Nomes()
        for s in slides:
            item = f"{base}/{sn(base, 'item')}"
            payload[f"{item}/jcr:primaryType"] = "nt:unstructured"
            if s.get("panelTitle"):
                payload[f"{item}/cq:panelTitle"] = s["panelTitle"]
            if s.get("kind") == "image":
                payload[f"{item}/sling:resourceType"] = RT["image"]
                payload[f"{item}/fileReference"] = s.get("fileReference", "")
                payload[f"{item}/alt"] = s.get("alt", "") or ""
            else:
                payload[f"{item}/sling:resourceType"] = RT["embed"]
                payload[f"{item}/type"] = "embeddable"
                payload[f"{item}/embeddableResourceType"] = YOUTUBE_RT
                payload[f"{item}/youtubeVideoId"] = s.get("youtubeVideoId", "")
                payload[f"{item}/layout"] = "responsive"
        return True

    if k == "xf":
        n = nomes(pai, "experiencefragment")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["experiencefragment"]
        payload[f"{base}/fragmentVariationPath"] = b.props.get("fragmentVariationPath", "")
        return True

    if k == "download":
        # Decisão do time (18/09/2026): download vira TABELA com colunas
        # Title/Download, como a Anion fez. O componente `download` existe em
        # /apps mas NÃO está na allow-list do slot nem do flexcontaineritem.
        return _emitir_tabela_download(payload, pai, nomes,
                                       [b.props], link_de, link_para)

    if k == "downloadlist":
        return _emitir_tabela_download(payload, pai, nomes,
                                       b.props.get("itens") or [],
                                       link_de, link_para)

    if k == "related":
        return _emitir_related(payload, pai, nomes, b, page, link_de, link_para)

    if k == "productlist":
        pages = b.props.get("pages")
        if isinstance(pages, str):
            pages = [pages]
        pages = [x for x in (pages or []) if x]
        if not pages:
            page.pendencias.append(Pendencia(
                b.origin_path, "productlisting", "productlist_nao_resolvido",
                f"listFrom={b.props.get('listFrom')} sem 'pages' materializado"))
            return False
        if link_de and link_para and getattr(page, "_reescrever_listas", True):
            pages = [link_para + x[len(link_de):] if x.startswith(link_de) else x
                     for x in pages]
        n = nomes(pai, "list")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["list"]
        payload[f"{base}/listFrom"] = "static"
        payload[f"{base}/pages"] = pages
        payload[f"{base}/pages@TypeHint"] = "String[]"
        payload[f"{base}/linkItems"] = "true"
        return True

    if k == "tabs":
        n = nomes(pai, "tabs")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["tabs"]
        # o nó tabs não tem propriedade nenhuma (183 de 183 no corpus) e não
        # tem policy: o que se controla é o container de cada aba
        pn = _Nomes()
        for idx, p in enumerate(b.panels, 1):
            item = f"{base}/{pn(base, 'item')}"
            rotulo = p.label
            # `cq:panelTitle` no GWI às vezes é String[]; sem achatar, o Sling
            # grava array e o rótulo da aba sai duplicado.
            if isinstance(rotulo, (list, tuple)):
                rotulo = rotulo[0] if rotulo else ""
            rotulo = (rotulo or f"Tab {idx}").strip()
            payload[f"{item}/jcr:primaryType"] = "nt:unstructured"
            payload[f"{item}/sling:resourceType"] = RT["container"]
            payload[f"{item}/cq:panelTitle"] = rotulo
            payload[f"{item}/cq:panelTitle@TypeHint"] = "String"
            payload[f"{item}/jcr:title"] = rotulo
            # `layout=responsiveGrid` é o que faz o container da aba
            # renderizar os filhos — sem isso a aba fica vazia na tela ainda
            # que os nós existam no JCR. As abas da `deepx` têm os três:
            # jcr:title, cq:panelTitle e layout.
            payload[f"{item}/layout"] = "responsiveGrid"
            # painel com subseções: mesmo princípio da seção (R28) — barra de
            # abas→painel media 103px contra 25 no GWI
            _styles(payload, item, [S_CONT_1000] if COM_MARGEM
                    else ["", S_CONT_TB_NONE if len(p.rows) > 1 else "",
                          S_CONT_LR_NONE])
            if len(p.rows) > 1:
                for r in p.rows:
                    sub = f"{item}/{nomes(item, 'container')}"
                    _container(payload, sub, pad_tb="small", pad_lr="none")
                    _emitir_linha(payload, sub, nomes, r, page, link_de, link_para)
            else:
                for r in p.rows:
                    _emitir_linha(payload, item, nomes, r, page, link_de, link_para)
        return True

    if k == "anchorlink":
        itens = b.props.get("itens") or []
        if not itens:
            page.pendencias.append(Pendencia(
                b.origin_path, "pagesectionlisting", "anchorlink_sem_itens",
                f"listingMode={b.props.get('listingMode')} sem heading com id "
                "na página — índice de âncoras ficaria vazio"))
            return False
        n = nomes(pai, "anchorlink")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["anchorlink"]
        payload[f"{base}/anchor/jcr:primaryType"] = "nt:unstructured"
        for i, it in enumerate(itens):
            item = f"{base}/anchor/item{i}"
            payload[f"{item}/jcr:primaryType"] = "nt:unstructured"
            payload[f"{item}/text"] = it.get("text", "")
            payload[f"{item}/linkId"] = it.get("linkId", "")
        return True

    if k == "hr":
        # <hr> visível no GWI: vira separador de seção no nível de cima
        # (tratado em _emitir_secao); aqui sobrevive como texto mínimo.
        n = nomes(pai, "text")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["text"]
        payload[f"{base}/text"] = "<hr />"
        payload[f"{base}/textIsRich"] = "true"
        return True

    if k == "form":
        n = nomes(pai, "container_form")
        base = f"{pai}/{n}"
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["form_container"]
        payload[f"{base}/actionType"] = "macnicaglobal2/components/form/actions/macnicadefault"
        payload[f"{base}/macnicadefault_subject"] = b.props.get("subject", "")
        payload[f"{base}/macnicadefault_mailto"] = list(b.props.get("mailto") or [])
        payload[f"{base}/macnicadefault_mailto@TypeHint"] = "String[]"
        payload[f"{base}/macnicadefault_includePageTitle"] = "false"
        payload[f"{base}/successFragmentPath"] = f"{XF_FORM_POPUPS}/form-success/master"
        payload[f"{base}/errorFragmentPath"] = f"{XF_FORM_POPUPS}/form-error/master"
        # campos SEM cq:responsive: uma coluna, como todo form do global2
        for i, campo in enumerate(b.props.get("campos") or [], 1):
            c = f"{base}/text_{i}"
            payload[f"{c}/jcr:primaryType"] = "nt:unstructured"
            payload[f"{c}/sling:resourceType"] = RT["form_text"]
            for kk, vv in campo.items():
                payload[f"{c}/{kk}"] = vv
        for i, bt in enumerate(b.props.get("botoes") or [], 1):
            c = f"{base}/button_{i}"
            payload[f"{c}/jcr:primaryType"] = "nt:unstructured"
            payload[f"{c}/sling:resourceType"] = RT["form_button"]
            payload[f"{c}/jcr:title"] = bt.get("jcr:title", "")
            payload[f"{c}/type"] = bt.get("type", "submit")
        return True

    if k == "anchor":
        n = nomes(pai, "text")
        base = f"{pai}/{n}"
        nome_ancora = b.props.get("nome", "")
        payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{base}/sling:resourceType"] = RT["text"]
        payload[f"{base}/text"] = f'<p><a id="{nome_ancora}" name="{nome_ancora}"></a></p>'
        payload[f"{base}/textIsRich"] = "true"
        return True

    page.pendencias.append(Pendencia(
        b.origin_path, k, "sem_emissor",
        f"IR kind '{k}' chegou ao emissor sem regra"))
    return False


def _emitir_tabela_download(payload, pai, nomes, itens, link_de, link_para):
    """Downloads como tabela Title/Download — a forma que a Anion usou."""
    linhas = []
    for it in itens:
        ref = it.get("fileReference", "")
        titulo = (it.get("titulo") or "").strip()
        if not titulo:
            # sem dc:title resolvido, usa o nome do arquivo SEM inventar
            # rótulo bonito — o driver preenche `titulo` a partir do DAM
            titulo = ref.rsplit("/", 1)[-1]
        # href CODIFICADO: o HTML rico do `table` passa pelo filtro XSS do
        # AEM, que descarta o <a> inteiro quando o href tem espaço cru e
        # deixa só o texto. "WP-14033 - Altera SoC Design Advantages .pdf"
        # virava a palavra "Download" sem link — invisível para qualquer
        # conferência de JCR ou de texto (R13).
        href = quote(ref, safe="/")
        linhas.append(
            f"<tr><td>{titulo}</td>"
            f'<td><a href="{href}" target="_blank">Download</a></td></tr>')
    if not linhas:
        return False
    n = nomes(pai, "table")
    base = f"{pai}/{n}"
    payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{base}/sling:resourceType"] = RT["table"]
    payload[f"{base}/text"] = (
        "<table><thead><tr><th>Title</th><th>Download</th></tr></thead>"
        "<tbody>" + "".join(linhas) + "</tbody></table>")
    payload[f"{base}/textIsRich"] = "true"
    _styles(payload, base, ["", "", S_TABLE_NOROUND])
    return True


def _emitir_related(payload, pai, nomes, b, page, link_de, link_para):
    """relatedsuggestions -> title 'Similar Products' + list estática.

    Alvo é `list`, não `cardlist`: 201 contra 1 no corpus autoral. A string
    "Similar Products" NÃO existe em nenhum jcr:content do GWI — está travada
    na structure do template de origem. O motor SINTETIZA; não há o que copiar.

    `listFrom` é sempre materializado em 'static': manter 'children' faria o
    parentPage reescrito avaliar a árvore de DESTINO, que tem outro conjunto
    de filhos — deriva silenciosa (é o que acontece hoje em 44 páginas).
    """
    pages = b.props.get("pages")
    if isinstance(pages, str):
        pages = [pages]
    pages = [p for p in (pages or []) if p]
    if not pages:
        # Caso real e confuso: o nó diz `listFrom=static` mas NÃO tem `pages`
        # — tem `query`/`searchIn`/`parentPage`. É busca disfarçada de estática,
        # e nas 9 páginas em que aparece aponta para `sony-image-sensors`, que
        # está fora do escopo (a Anion já autorou). Emitir uma lista vazia
        # seria pior que não emitir; fica registrado para decisão humana.
        page.pendencias.append(Pendencia(
            b.origin_path, "relatedsuggestions", "related_nao_resolvido",
            f"listFrom={b.props.get('listFrom')} sem 'pages'; "
            f"query={str(b.props.get('query') or '-')[:40]} "
            f"parentPage={str(b.props.get('parentPage') or '-')[-40:]}"))
        return False

    if link_de and link_para and getattr(page, "_reescrever_listas", True):
        pages = [link_para + p[len(link_de):] if p.startswith(link_de) else p
                 for p in pages]

    nt = nomes(pai, "title")
    bt = f"{pai}/{nt}"
    payload[f"{bt}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{bt}/sling:resourceType"] = RT["title"]
    payload[f"{bt}/jcr:title"] = "Similar Products"
    payload[f"{bt}/type"] = "h2"
    _styles(payload, bt, ["", "", "", S_TITLE_H3SIZE])

    nl = nomes(pai, "list")
    bl = f"{pai}/{nl}"
    payload[f"{bl}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{bl}/sling:resourceType"] = RT["list"]
    payload[f"{bl}/listFrom"] = "static"
    payload[f"{bl}/pages"] = pages
    payload[f"{bl}/pages@TypeHint"] = "String[]"
    payload[f"{bl}/linkItems"] = "true"
    # sem maxItems (ausente em 197 de 202 autorais), sem orderBy, sem styleIds
    # (os dois grupos da policy do list têm cq:styles vazio — inertes)
    return True


# `margin-top:0`: todo `<p>` que não é o primeiro filho tem 30px de margem no
# global2, e a linha vazia já mede 30px de altura — sem isto a "linha em
# branco" rendia 60px (medido em render local), contra 28 no GWI.
_LINHA_EM_BRANCO = '<p style="margin-top:0">&nbsp;</p>'

GWI_COLUNA_PX = 976               # coluna de conteúdo do GWI a 1400px
GWI_IMAGETEXT_MAX_H = 277         # .cmp-image-text img{max-height:277px}
GWI_IMAGETEXT_COL = 480           # coluna do asset no imagetext left/right
GWI_CAROUSEL_PX = 380             # carousel numa coluna de 6: 480 - 2x50 das setas


def _image_ratio(b, util_px):
    """`imageRatio` (Image Width %) do `textwithimage`: a imagem no tamanho que o GWI mostra (R36).

    Sem ele a coluna da imagem vale 50% da linha e a foto sai no tamanho
    natural: 655x436 numa página de 1350px contra 415x277 no GWI. O texto ao
    lado não cresce junto (fica até mais baixo, a linha é mais larga), e o
    que sobra é BURACO embaixo dele: 231–317px na `canon-li8030sa`, 397px
    entre o parágrafo e "Application Uses" nas 7 folhas `i-chips-ip00c*`; no
    hero das 26 `design-gateway` e das 6 `/sitime` a imagem 1,7x empurra o
    índice de âncoras para fora da 1ª dobra. Era o aberto J ("sem campo
    alvo") — o campo existe: `./imageRatio` no diálogo, que o HTL passa ao CSS
    como `--textwithimage-image-ratio`.

    A largura-alvo é a que o GWI DESENHA, em px:
      largura autoral do `resizableimage`                       (345 na ip00c787)
      imagetext left/right: min(480, 277 x L/A)  -- o teto de 277px de altura
      carousel de 1 slide numa coluna de 6: 380
      coluna de imagem: a largura da coluna, ou a natural se for menor
    `dims` (L, A do asset) é preenchido pelo driver a partir do DAM; sem ele
    assume-se foto 3:2. Entre 15 e 50%; 50 é o padrão do componente e não é
    gravado.
    """
    px = b.props.get("largura_px")
    dims = b.props.get("dims")
    origem = b.props.get("origem_midia")
    if not px:
        if origem == "imagetext":
            # `dims[0]`: foto menor que isso sai no tamanho natural (256px
            # na `altera-max-10`) — sem ele a coluna da imagem ficava com 36%
            # e a foto encostada num canto dela
            px = (min(GWI_IMAGETEXT_COL, dims[0],
                      round(GWI_IMAGETEXT_MAX_H * dims[0] / dims[1]))
                  if dims else round(GWI_IMAGETEXT_MAX_H * 1.5))
        elif origem == "carousel":
            px = min(GWI_CAROUSEL_PX, dims[0]) if dims else GWI_CAROUSEL_PX
        elif origem == "coluna":
            col = round(GWI_COLUNA_PX * (b.props.get("coluna_w") or 6) / 12) - 16
            px = min(col, dims[0]) if dims else col
        else:
            return None
    # piso de 15 (era 25): a foto em retrato do Eval Kit da `canon-120mxs`
    # pede 19% (252px) e com 25 saía 1,3x, com 239px de buraco sob o texto. O
    # diálogo aceita 0–100 e o CSS funciona abaixo de 25 (simulado no navegador).
    return max(15, min(50, round(100 * px / max(util_px, 1))))


def _respiro_na_coluna(blocos):
    """Dentro de COLUNA não há subseção: o respiro volta como linha em branco (R24b).

    A R24 abre um sub-container (60px) onde o GWI tinha o espaçador. Dentro de
    `flexcontaineritem` não dá: os blocos da coluna são irmãos diretos, gap 0,
    e `strip_empty_blocks` já apagou o `<p>&nbsp;</p>`. Na `/toppan`, coluna do
    C11U, o h3 "Key Features…" ficava COLADO no parágrafo de cima (0px contra
    28 no GWI) e a 24px da lista que introduz — lia como legenda do parágrafo.
    Com a evidência do espaçador na origem (fim/começo do `text`, ou nó
    espaçador entre os dois), UM `<p>&nbsp;</p>` é mantido no `text` vizinho:
    30px no destino, 28 no GWI. Nunca depois de título, nem onde a margem
    própria dos componentes já separa.
    """
    for ant, b in zip(blocos, blocos[1:]):
        if ant.kind == "title":
            continue
        if not (b.props.get("espaco_antes")
                or (ant.kind == "text" and ant.props.get("respiro_depois"))
                or (b.kind == "text" and b.props.get("respiro_antes"))):
            continue
        if (_MARGEM_PROPRIA.get(ant.kind, (0, 0))[1]
                + _MARGEM_PROPRIA.get(b.kind, (0, 0))[0]) >= 40:
            continue
        if ant.kind == "text":
            ant.props["linha_depois"] = True
        elif b.kind == "text":
            b.props["linha_antes"] = True


def _emitir_linha(payload, pai, nomes, row, page, link_de, link_para):
    """Row -> irmãos diretos (single) ou flexcontainer (columns)."""
    for b in row.cabecalho:
        _emitir_bloco(payload, pai, nomes, b, page, link_de, link_para)
    if not row.vazias and (row.kind == "single" or len(row.columns) < 2):
        for c in row.columns:
            for b in c.blocks:
                _emitir_bloco(payload, pai, nomes, b, page, link_de, link_para)
        return

    # Colunas que são SÓ botão têm de caber: o botão tem min-width 345px
    # ("Fixed Minimum Width" é o menor que a policy oferece) e o gap do flex
    # é 26px. Quantos cabem depende da LARGURA ÚTIL da seção, que
    # `_emitir_secao` deixa em `page._util_px`:
    #   com margem (fitcontainer 1000 - 2x50)  -> 900px  -> cabem 2
    #   sem margem (janela de referência)      -> ~1266px -> cabem 3
    # Na `/renesas` (3 botões) com 900px o terceiro passava 187px da margem.
    # Sem margem os 3 cabem lado a lado, como no GWI, e a regra só age de 4
    # botões para cima. Quebra em linhas EQUILIBRADAS (4 -> 2+2, não 3+1).
    if all(c.blocks and all(b.kind == "button" for b in c.blocks)
           for c in row.columns):
        util = getattr(page, "_util_px", LARGURA_UTIL_COM_MARGEM)
        cabem = max(1, (util + FLEX_GAP_PX) // (BTN_MIN_PX + FLEX_GAP_PX))
        n = len(row.columns)
        if n > cabem:
            linhas_n = -(-n // cabem)
            por_linha = -(-n // linhas_n)
            for i in range(0, n, por_linha):
                sub = Row("columns")
                sub.columns = row.columns[i:i + por_linha]
                _emitir_linha(payload, pai, nomes, sub, page, link_de, link_para)
            return

    # Linha 6/6 {uma imagem} + {texto} vira UM textwithimage — é a técnica da
    # folha de produto: 165 das 196 páginas autorais usam só textwithimage.
    fundido = None if row.vazias else _tentar_textwithimage(row)
    if fundido:
        _emitir_bloco(payload, pai, nomes, fundido, page, link_de, link_para)
        return

    n = nomes(pai, "flexcontainer")
    base = f"{pai}/{n}"
    payload[f"{base}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{base}/sling:resourceType"] = RT["flexcontainer"]
    # 1719484596357 é OBRIGATÓRIO: sem ele as colunas não empilham abaixo de
    # 1050px. Medido a 390px na própria deepx: colunas de 152px e 122px, e
    # botões fixed-min-width (345px) estourando a viewport. 32 dos 85
    # flexcontainers de 2 itens do corpus autoral estão quebrados assim —
    # divergir da referência aqui é decisão fechada.
    _styles(payload, base, ["", S_FLEX_SP_1COL])
    itn = _Nomes()
    for c in row.columns:
        item = f"{base}/{itn(base, 'flexcontaineritem')}"
        payload[f"{item}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{item}/sling:resourceType"] = RT["flexcontaineritem"]
        # flexcontaineritem não recebe style e não tem largura:
        # .flex_container>.cmp-container>div{flex:1} — itens SEMPRE iguais.
        # Coluna desigual do GWI (8/4, 5/7) é normalizada de propósito.
        _respiro_na_coluna(c.blocks)
        # Foto de card com legenda na mesma coluna: o `image` do global2
        # centra por padrão e o `title`/`text` encosta à esquerda — na
        # `/toppan` a foto (512px numa coluna de 662) ficava 75px para dentro
        # da legenda, nos 4 cards. Só quando o GWI NÃO centra (`alignment`
        # diferente de center); os cards da `/ambarella`, `/canon` e
        # `/renesas` são centrados na origem e continuam (R35).
        legenda = [b for b in c.blocks if b.kind in ("title", "text")]
        centrada = any(
            re.search(r"text-align\s*:\s*center", b.props.get("html", ""), re.I)
            or S_TITLE_CENTER in (b.props.get("styles") or []) for b in legenda)
        # …e a imagem SOZINHA na coluna (herói foto | título+texto da
        # `/i-chips`: foto de 546px centrada numa coluna de 662, 58px para
        # dentro da borda do h1; 188px a 1920): sem legenda não há o risco da
        # legenda centrada.
        so_imagem = all(b.kind == "image" for b in c.blocks)
        if (legenda and not centrada) or so_imagem:
            for b in c.blocks:
                if b.kind == "image" and b.props.get("alinhamento") == "left":
                    b.props["a_esquerda"] = True
        for b in c.blocks:
            _emitir_bloco(payload, item, nomes, b, page, link_de, link_para)
    # itens vazios fecham a grade: `flex:1` dá a cada card a largura da coluna
    for _ in range(row.vazias):
        item = f"{base}/{itn(base, 'flexcontaineritem')}"
        payload[f"{item}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{item}/sling:resourceType"] = RT["flexcontaineritem"]


def _tentar_textwithimage(row):
    """Linha de 2 colunas {imagem} + {texto} -> um nó textwithimage.

    Limite duro: textwithimage guarda UMA imagem. Carousel com 2+ slides não
    pode ser colapsado — a Anion colapsou e descartou os slides 2..N, perdendo
    182 slides de vídeo em 110 páginas. Aqui isso é proibido.
    """
    if len(row.columns) != 2:
        return None
    a, b = row.columns
    for midia, texto, esquerda in ((a, b, True), (b, a, False)):
        if len(midia.blocks) != 1 or not texto.blocks:
            continue
        m = midia.blocks[0]
        if m.kind == "image":
            ref, alt = m.props.get("fileReference"), m.props.get("alt", "")
            origem, dims = "coluna", m.props.get("dims")
        elif m.kind == "carousel" and len(m.props.get("slides") or []) == 1:
            s = m.props["slides"][0]
            if s.get("kind") != "image":
                continue
            ref, alt = s.get("fileReference"), s.get("alt", "")
            origem, dims = "carousel", s.get("dims")
        else:
            continue
        if not all(t.kind == "text" for t in texto.blocks):
            continue
        return Block("textwithimage", m.origin_path, fileReference=ref, alt=alt,
                     html="".join(t.props.get("html", "") for t in texto.blocks),
                     imagem_esquerda=esquerda, origem_midia=origem, dims=dims,
                     largura_px=m.props.get("largura_px"),
                     coluna_w=midia.width)
    return None


# Largura útil de uma seção, para decidir o que cabe lado a lado.
BTN_MIN_PX = 345                  # .fixed-min-width .link-button__anchor
FLEX_GAP_PX = 26                  # .flex_container > .cmp-container {--gap}
LARGURA_UTIL_COM_MARGEM = 900     # fitcontainer (1000px) - 2 x 50px (LR large)
JANELA_REF_PX = 1366              # notebook comum; abaixo de 1050 o flex empilha
PAD_LR_PX = {"none": 0, "default": 25, "large": 50}


def _largura_util(s):
    if s.max_width_1000:
        return 1000 - 2 * PAD_LR_PX.get(s.pad_lr, 25)
    return JANELA_REF_PX - 2 * PAD_LR_PX.get(s.pad_lr, 25)


def _emitir_secao(payload, slot, nomes, s, page, link_de, link_para):
    page._util_px = _largura_util(s)
    nome = nomes(slot, "container")
    base = f"{slot}/{nome}"
    if s.background and s.full_bleed:
        # Faixa colorida = DUAS camadas, e o eixo é a LARGURA, não o padding:
        # a cor precisa sangrar até a borda enquanto o conteúdo fica em 1000px.
        _container(payload, base, max_width=False, pad_tb="none",
                   pad_lr="default", background=s.background)
        interno = f"{base}/container"
        _container(payload, interno, max_width=COM_MARGEM, pad_tb=s.pad_tb,
                   pad_lr="large" if COM_MARGEM else "none")
        alvo = interno
    else:
        # Seção com subseções não tem padding T/B próprio: o respiro é o dos
        # sub-containers (30+30). Somados davam 110–140px em toda fronteira de
        # seção, contra 56–84px do espaçador do GWI (R28).
        _container(payload, base, max_width=s.max_width_1000,
                   pad_tb="none" if len(s.rows) > 1 else s.pad_tb,
                   pad_lr=s.pad_lr, background=s.background)
        alvo = base
    # Várias subseções na mesma seção: cada uma ganha o seu container, com
    # padding SÓ no eixo vertical. `Pad L/R = No Padding` é de propósito — o
    # padrão do container é `50px 25px` e esses 25px empurrariam o texto para
    # dentro, desalinhando com o resto da seção.
    if len(s.rows) > 1:
        for r in s.rows:
            sub = f"{alvo}/{nomes(alvo, 'container')}"
            # subseção que é SÓ o índice de âncoras: `.anchor-link__list` já
            # traz 60px de margem embaixo — com o 30+30 do sub-container o
            # índice ficava a 119px do título seguinte (GWI 55) e "boiava para
            # cima" (`sitime-clock-buffers`)
            so_indice = r.blocks and all(b.kind == "anchorlink" for b in r.blocks)
            # …e a que é SÓ um `textwithimage` (30/30 de margem própria): a
            # R28e por LINHA. Na `altera-arria-10` os vãos em volta dos `hr`
            # mediam 97/97 contra 52/52 no GWI.
            so_twi = (not r.cabecalho and r.blocks
                      and (all(b.kind == "textwithimage" for b in r.blocks)
                           or _tentar_textwithimage(r) is not None))
            _container(payload, sub,
                       pad_tb="none" if (so_indice or so_twi) else "small",
                       pad_lr="none")
            _emitir_linha(payload, sub, nomes, r, page, link_de, link_para)
    else:
        for r in s.rows:
            _emitir_linha(payload, alvo, nomes, r, page, link_de, link_para)
    # Seção cujo bloco não emitiu nada (o `related` que não resolve vira
    # pendência e devolve False): o container ficava vazio no JCR — 9 páginas.
    # Invisível na tela (h=0), mas é lixo para quem abrir a página no editor.
    tipos = {v.rsplit("/", 1)[-1] for k, v in payload.items()
             if k.startswith(base + "/") and k.endswith("/sling:resourceType")}
    if not tipos - {"container"}:
        for k in [k for k in payload if k == base or k.startswith(base + "/")]:
            del payload[k]


def build_layout_payload(page, template_path=None, link_de=None, link_para=None,
                         slot="jcr:content/root/container", reescrever_listas=True):
    """Page (IR) -> payload achatado para o Sling POST.

    O `root/container` NUNCA recebe cq:styleIds: a policy do template já
    carimba `main container-padding-height0 container-padding-width0`
    (212 de 212 pares autorais concordam). Todo respiro vem das seções.
    """
    payload = {}
    payload["jcr:content/root/jcr:primaryType"] = "nt:unstructured"
    payload["jcr:content/root/sling:resourceType"] = RESPONSIVE_GRID_RT
    payload[f"{slot}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{slot}/sling:resourceType"] = CONTAINER_RT

    nomes = _Nomes()
    page._reescrever_listas = reescrever_listas
    for s in page.sections:
        _emitir_secao(payload, slot, nomes, s, page, link_de, link_para)

    contagens = {}
    for b in page.blocks:
        contagens[b.kind] = contagens.get(b.kind, 0) + 1
    return payload, contagens


def precisa_title_vazio(page):
    """Sempre. O cabeçalho da página é um `title` VAZIO, em toda página.

    O h1 servido pelo GWI é o `pageTitle`, não o `jcr:title` — 112 de 354
    páginas divergem, e em 45 a string do jcr:title não existe em lugar nenhum
    da origem (invenção pura do migrador antigo). Um `title` sem jcr:title e
    sem type faz o AEM renderizar o pageTitle como h1.

    A versão anterior pulava o title vazio quando o corpo tinha um h1 próprio,
    supondo que ele SUBSTITUÍA o cabeçalho. Não substitui: o template do GWI
    desenha o pageTitle num `title` da própria estrutura
    (`cmp-container--title-pageproperties`, junto com o logo do fabricante),
    ANTES do corpo — e o corpo pode ter quantos h1 quiser em cima disso. Na
    `i-chips-ip00c787` o visitante vê "i-Chips IP00C787" (pageTitle) e, logo
    abaixo, "2K Warping/Edge-blending LSI with Built in Memory" (h1 do corpo).
    Pular o title vazio apagava o primeiro: era a causa comum das 44 páginas
    com `falta=1` da primeira varredura (R6 em REGRAS-disposicao.md).

    A única exceção é dado da origem, não julgamento: a structure do template
    `base-page-content` NÃO tem `title` nem `pageproperties` (conferido nos
    5 templates do escopo em 18/09/2026 — os outros 4 têm os dois). Duas
    páginas o usam: `test-277-gwi-base-page`, que não mostra h1 nenhum de
    cabeçalho, e a landing `/semiconductors`, cujo h1 "Semiconductors" é um
    componente `title` do PRÓPRIO corpo (migra como conteúdo, não como
    cabeçalho). Injetar título nelas inventaria conteúdo.
    """
    tpl = (page.template or "").rstrip("/")
    return tpl.rsplit("/", 1)[-1] not in TEMPLATES_GWI_SEM_TITULO


def inserir_titulo_da_pagina(page, origem):
    """Põe o cabeçalho da página (`title` vazio -> pageTitle, R6) na árvore.

    O título é de LARGURA CHEIA e vem antes de tudo (R3) — mas NÃO é seção
    própria: como seção, entre ele e o 1º bloco somavam-se o padding de baixo
    da seção dele, o de cima da seção seguinte e o do sub-container (60–90px,
    medido em 9 de 10 páginas), contra 16–33px no GWI, onde o título e o corpo
    andam juntos. Ele entra como `cabecalho` da 1ª linha da 1ª seção: o mesmo
    mecanismo da R23, que emite o título em cima do `flexcontainer` (ou do
    bloco), no mesmo container. Continua fora de qualquer coluna (R28).

    Seção própria só quando a 1ª seção tem papel próprio (faixa de abas, CTA,
    related) ou a página não tem seção nenhuma. Devolve True se inseriu.
    """
    if not precisa_title_vazio(page):
        return False
    t = Block("title_vazio", origem)
    prim = page.sections[0] if page.sections else None
    if (prim is not None and prim.role == "body" and not prim.background
            and prim.rows):
        prim.rows[0].cabecalho = [t] + list(prim.rows[0].cabecalho)
        if prim.pad_tb == "none" and len(prim.rows) == 1:
            prim.pad_tb = "small"      # o título precisa do respiro de cima
        return True
    cab = Section(origem, -1, role="header")
    cab.pad_tb = "small"
    linha = Row("single")
    col = Column(origem, width=12)
    col.blocks = [t]
    linha.columns = [col]
    cab.rows = [linha]
    page.sections.insert(0, cab)
    return True


# Templates do GWI cuja structure não desenha o pageTitle. Levantado lendo
# /conf/macnicagwi/settings/wcm/templates/<tpl>/structure — os que TÊM
# `macnicagwi/components/content/title` na structure: product-detail-page-content,
# manufacturer-detail-page-content, macnica-gwi-product-line-detail-page-template,
# macnica-gwi---mae-product-page.
TEMPLATES_GWI_SEM_TITULO = {"base-page-content"}
