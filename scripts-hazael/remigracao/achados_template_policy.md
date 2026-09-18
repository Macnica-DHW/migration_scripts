# Achados da policy do template (levantados fora do workflow)

## Slot editável
`root/container` é o ÚNICO nó editável do `mai-mae-product-page`
(`editable=true` na structure). `root/container_1885913789` (breadcrumb) não é.
Confirma o aviso do docstring do BlockBuilder: o nome `container` é obrigatório.

## Componentes permitidos dentro de root/container — 26
policy `macnicaglobal2/components/content/container/policy_1667171337167200`

    accordion      anchorlink     button        cardlist      carousel
    container      contentlist    downloadlist  embed         experiencefragment
    featurednews   filterabletable flexcontainer image        list
    navigation     newslist       searchresults stickytabs    table
    tabs           teaser         text          textwithimage title
    form/container

**Relevante para as pendências de tradução:**
- `experiencefragment` EXISTE no destino (124 ocorrências não traduzidas hoje).
- `accordion`, `stickytabs`, `filterabletable`, `contentlist`, `featurednews`,
  `cardlist` existem e nenhuma das duas páginas de referência usa todos —
  são candidatos para `relatedsuggestions` (251) e `pagesectionlisting` (14).
- `form/container` existe — as 36 ocorrências de `form/*` talvez não estejam
  fora de escopo por falta de componente.

## Policy do container aninhado (policy_1586276378410700)

    layout = responsiveGrid
    columns = 12
    layoutDisabled = true          <<<
    backgroundColorEnabled = true
    backgroundImageEnabled = true
    allowedColorSwatches = ['#fbf5f9', '#7f1080', '#b20080', '#3b1e83',
                            '#007ab6', '#00851c', '#ec6e00', '#000000']

**`layoutDisabled = true`** — o redimensionamento de coluna do grid está
DESLIGADO por policy nos containers aninhados. É provavelmente por isso que as
páginas autorais fazem coluna com `flexcontainer` e não com `cq:responsive`:
no editor não dá para arrastar a largura. O `cq:responsive` gravado por script
até renderiza, mas é uma construção que o autor não consegue reproduzir nem
ajustar pela UI. **Forte argumento para o motor novo usar flexcontainer.**

**`allowedColorSwatches` não contém `#fff` nem `#f7f7f7`** — exatamente os dois
valores que o `ALTERNATING_BACKGROUND_COLORS` do migrador grava. E a `sony` usa
`rgb(235,235,235)` / `rgb(247,247,247)`, que também não estão na lista. Ou seja:
a alternância de fundo do migrador grava cor fora da paleta autorizada pela
policy. Vale conferir com o time se a diretriz de "Alternative background Color
Grading" se refere a estes swatches (`#fbf5f9` é o rosa claro da marca).
