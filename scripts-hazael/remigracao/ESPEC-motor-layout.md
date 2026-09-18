# ESPECIFICAÇÃO — Motor de layout da remigração `macnicagwi` → `macnicaglobal2`
**Rascunho 1 · arquiteto · 18/09/2026 · somente-leitura, nenhuma escrita feita**

---

## 0. Decisão de fundo: duas chaves de despacho independentes

O erro estrutural do motor atual não é ter uma regra ruim; é ter **uma** regra. O motor novo despacha por **duas chaves ortogonais**, e confundi-las foi o que produziu os 4.870 `_wrap`:

| chave | pergunta que responde | valores |
|---|---|---|
| **forma do topo da origem** | *onde começa e termina uma seção?* | AGRUPADA (322 pág.) · MISTA (20) · PLANA (13) |
| **arquétipo / `cq:template` de origem** | *que gramática de emissão usar dentro da seção?* | P1..P8 (§3) |

A primeira escolhe o **detector de fronteira**; a segunda escolhe o **emissor**. Uma página `product-detail-page-content` PLANA e uma `mae-product-page` PLANA usam o mesmo detector e emissores diferentes. Nenhuma das duas escolhas pode ser inferida da outra.

### A contradição deepx × sony está resolvida — e resolvê-la é o alicerce do motor

Os levantamentos brigaram durante todo o dossiê sobre qual referência imitar: `deepx` (1 container chapado, gap 0px) ou `sony` (4 seções, faixas coloridas). **As duas seguem a mesma regra.** O teste de falsificação sobre 212 pares origem↔autoral provou: *cada filho de topo do corpo GWI que carrega conteúdo renderizável vira um container de seção no destino, na mesma ordem* — precisão 99,3%, recall 96,3%, 3 falsos positivos em 414 previsões.

A `deepx` tem **um** container porque a `deepx` do GWI tem **um** bloco de topo (os 15 `resizablecontainer` dela estão aninhados dentro desse bloco, e os 23 spacers estão dentro também). A `sony` tem quatro porque a origem tem quatro. Não há duas gramáticas Anion: há uma regra estrutural e duas origens diferentes.

Consequência imediata para a especificação: **fronteira de seção é dado da origem, não julgamento estético.** O motor não decide quantas seções a página tem; ele lê.

Os dois preditores que os levantamentos anteriores propuseram estão **falsificados** e não entram no motor como regra primária:

- spacer `&nbsp;` → precisão 16,2%, recall 2,6% (68 previstas, 11 certas);
- heading de nível mais alto → precisão 16,4%, recall 2,3%; em 191 dos 212 pares a página GWI não tem heading nenhum, logo o preditor nem existe.

O spacer sobrevive como **sinal secundário** em dois lugares só (§1.4).

---

## 1. A representação intermediária

`extract_tree(jcr_content, source_path) -> (Page, pendencias)`. Substitui `extract_content`, que devolve lista plana. Toda a perda estrutural de hoje acontece em `aem_lib.py:935-937` — `walk(child, largura_coluna(child) or col_width)` consome o nó invólucro e propaga um escalar. O nó invólucro é justamente o dado.

### 1.1 Nós e campos

```
Page
  source_path, target_path, archetype, topology  # AGRUPADA|MISTA|PLANA
  page_props: dict        # §2.7 — nunca vira conteúdo
  sections: [Section]
  pendencias: [Pendencia] # {origin_path, resourceType, categoria, motivo, ref}

Section
  origin_path        # o nó de topo do GWI que a gerou — rastreabilidade obrigatória
  origin_index       # posição entre os filhos de topo
  role               # hero | body | tabs | related | resources | cta | anchor_index
  full_bleed: bool   # cor sangra até a borda → exige duas camadas (§2.1)
  background: str|None
  max_width_1000: bool
  pad_tb, pad_lr     # none | small | medium | default | large
  rows: [Row]

Row
  kind               # single | columns
  columns: [Column]
  equal: bool        # todas as larguras de origem iguais?
  widths_source      # [6,6] / [8,4] — preservado só para auditoria
  collapse           # textwithimage | flexcontainer | stack   (decidido em §2.3)

Column
  origin_path, width_12, offset, phone_width_12
  blocks: [Block]

Block
  kind               # title|text|image|textwithimage|carousel|embed|table|button
                     # |download|list|tabs|anchorlink|xf|hr|anchor
  origin_path
  props: dict
  panels: [Panel]    # só quando kind == tabs

Panel
  label              # cq:panelTitle da origem
  origin_path
  rows: [Row]        # recursão completa: coluna dentro de aba é caso real (arquétipo C)
```

Três campos são inegociáveis e hoje não existem: **`origin_path` em todo nó** (sem ele não há auditoria nem re-execução idempotente), **`Row`/`Column` como nós de verdade** (não largura carimbada em folha) e **recursão em `Panel`** (coluna dentro de aba existe e o migrador de hoje a perde em silêncio).

### 1.2 Onde o walk começa — e onde NÃO começa

`walk(jcr_content)` (`aem_lib.py:1205`) é a origem de três defeitos de uma vez. O novo começa em **`jcr:content/root/container`** e desce enquanto houver **filho único que seja invólucro puro** (tipo em `KNOWN_CONTAINER_TYPES`, sem `cq:responsive/default/width`, sem propriedade de conteúdo). Para quando o nó tiver 2+ filhos ou carregar conteúdo. Esse nó é o **corpo**.

Os irmãos de `root` — `manufacturerlogo`, `cq:featuredimage`, `productlinelogo`, `image`, `newsDetails`, `pd_*` — **nunca** entram na travessia. Vão para `page_props`. Medido: 244 páginas do destino têm o `manufacturerlogo` injetado como imagem no fim do corpo, e a `/altera` fecha com 405px de logo. Do outro lado, `jcr:content/image` (com `fileReference` e `sling:resourceType` vazio) hoje cai no ramo de invólucro e **some sem registro** — no motor novo isso é `Pendencia(categoria='no_de_topo_desconhecido')`, nunca descarte silencioso.

### 1.3 Detecção de seção (AGRUPADA — 322 páginas, 91%)

Cada filho direto do corpo, na ordem, com estas exceções verificadas:

1. bloco cujo único conteúdo é `pageproperties` (o `resizablecontainer` com `id="cmp-container--title-pageproperties"`, 266 páginas) → **descartado**, não vira seção. É o cabeçalho do GWI, não corpo. É a origem do "logo gigante no fim da página". A Anion descartou os 192 casos equivalentes;
2. `relatedsuggestions` de topo → vira seção `role='related'` com `title` sintetizado + `list` (§2.5);
3. bloco sem nenhum conteúdo renderizável (só spacers) → descartado;
4. 3,7% das fronteiras (16 de 427, concentradas em 11 páginas quase idênticas do ramo sony) são **cortes dentro** de um bloco de topo. Aí, e só aí, o spacer ou um `heading type=h2` marca o corte. Implementar como regra secundária sob flag, não como caminho principal.

Ordem de grandeza do resultado: **1.044 seções nas 355 páginas** (média 2,9/página) contra os 5.020 `_wrap` de hoje.

### 1.4 Detecção de seção (PLANA — 13 páginas; MISTA — 20)

Quando o corpo não tem nenhum filho-invólucro (`/altera/agilex` tem 23 filhos, todos folha), a regra de topo degenera em uma seção por componente — exatamente a doença que estamos curando. **Nessas e só nessas, o spacer `&nbsp;` é o delimitador**: 17 dos 19 spacers de topo dessas páginas caem imediatamente antes de um `heading`, `productlisting` ou `experiencefragment`. `/altera/agilex` vira 4 seções limpas.

MISTA = corpo com alguns filhos-invólucro e algumas folhas soltas: regra de topo para os invólucros, spacer para as corridas de folhas.

Classificação feita antes de qualquer emissão, gravada em `Page.topology`, impressa no relatório.

### 1.5 Detecção de coluna

Um nó invólucro **sem** `cq:responsive/default/width` cujos filhos incluem 2+ nós **com** width é uma **linha**. Cada filho com width é uma **coluna**, e a coluna guarda **todos** os seus filhos.

Duas regras que corrigem bugs medidos:

- **a largura é relativa ao pai, não 12 avos da página.** Um `width=4` dentro de um `width=6` vale 2/12 da tela;
- **as larguras das folhas dentro da coluna são ruído e devem ser ignoradas.** Na `/altera`, a coluna `width=6` contém `text_copy(w=5)` + `button_copy(w=3)` — soma 13 numa coluna de 6. Foi ler isso que quebrou a linha e empurrou o vídeo para baixo (medido: `embed colx=750 y=712`, uma linha abaixo do texto).

Corridas de folhas consecutivas sem linha viram `Row(kind='single')` com uma coluna de 12.

### 1.6 Fusão de texto — a alavanca de ritmo mais barata do sistema

Por causa de `.cmp-text p:first-child{margin-top:0}`, **N parágrafos num único `text` rendem 30px entre si no desktop; os mesmos N parágrafos em N `text` irmãos rendem 0px.** Regra: dentro de uma mesma coluna, `text` consecutivos sem outro componente no meio são **fundidos num só nó**, concatenando o HTML. É o inverso do que o motor faz hoje e é a causa direta do "texto colado".

### 1.7 Spacer não é conteúdo — com duas exceções que não se pode perder

Dos 674 `text` que ficam vazios após remover tags e `&nbsp;`: 506 são `<p>&nbsp;</p>`, 103 string vazia (609 descartáveis), **59 contêm `<hr>`** (régua visível no GWI, divisor autoral entre blocos `imagetext`, em 20 páginas) e **6 contêm âncora nomeada** (`<a name="contact-form">`, com 4 links apontando para ela só na `/analog-devices/macnica-and-adi`).

Regra: descarta só se, além de tags e `&nbsp;`, não sobrar `<hr>`, `<img>` nem `<a name|id>`. `<hr>` vira `Block(kind='hr')`; âncora vira `Block(kind='anchor')`. `strip_empty_blocks` continua removendo parágrafos vazios **dentro** de blocos com conteúdo (1.377 casos em 160 blocos) — ele já não toca em `<hr>` nem em `<p>` com `<a>`.

---

## 2. Regras de emissão

### 2.0 Mecânica de `cq:styleIds` — o que é verdade e o que não é

- **A posição no array não importa para renderizar.** O AEM resolve cada string não-vazia por valor contra a policy do próprio componente e concatena as classes na ordem dos *grupos*. Prova dupla: dois botões da `deepx` com os mesmos ids em ordem invertida emitem `class="button fixed-min-width center"` idêntico; e `title_wrap` da `/altera` com `['1717498053499','1717498052331']` emite as classes em ordem de grupo, não de array.
- **Mesmo assim, gravar na forma canônica posicional** — um slot por grupo, `''` onde não há escolha. É o que o diálogo do AEM grava e o que ele precisa para reabrir com as opções certas. Slots finais podem ser omitidos.
- **`styleId` é por componente.** Um id de `container` gravado num `title` não produz classe nenhuma. O motor precisa de um mapa `{resourceType → policy → grupos}`, nunca de uma tabela única.
- **`@TypeHint=String[]` é obrigatório** (`aem_lib.py:1819` já trata — manter), senão o Sling grava lista de 1 elemento como String simples.

Tabela de referência (slots na ordem):

| componente | policy | slots |
|---|---|---|
| container | 1586276378410700 | [0] MaxWidth `1717410661180`=1000px/fitcontainer · [1] Pad T/B `…50826`Large `…51666`Medium(sem classe) `…52331`Small `…56876`None · [2] Pad L/R `…53499`Large `…54232`Medium(sem classe) `…54937`Small `…55877`None |
| title | 641475696923109 | [0] Cor `1717668061877`Black `…62802`White · [1] Design `…77776`Ball `…92148`BackLine · [2] Posição `1717668113714`Center `…14416`Right · [3] Tamanho `1718280235037`h1 `1718280235888`**BUG→heading1** `1718280237031`heading3 |
| flexcontainer | 1717406963740 | [0] gap `…456497`50px `…525141`Medium(26, sem classe) `…457369`15px `…458698`0 · [1] SP `1719484596357`1 Column `1719484597737`2 Columns |
| image | 589419553064100 | [0] `1717565101174`large(width:100%) · [1] `…547211`Left `…548797`Center(sem classe) `…549719`Right |
| button | 1717669061681 | [0] `1717669222081`White · [1] `1723033446255`FitToText `1722936853890`FixedMinWidth · [2] `1717669229626`Center `…230937`Right |
| table | 1718948212799 | [0] Black `1722937999485` · [1] NoBg `1722858778108` · [2] NoRounded `1722939215525` · [3] NoFrame `1722858697098` |
| textwithimage | 1718154236394 | [0] `1718154328384`Left · [1] `1718154382437`Wrap · [2] `1783061491236`VCenter `1783061500464`VBottom |
| embed | 1719541566086 | [0] `1719541568246`youtube-width_full |
| list | 1717648312626 | 2 grupos, ambos **vazios** — inertes |

**Cuidado:** existe uma segunda policy de `table` (`1719954754334`) com rótulos idênticos e ids diferentes, de outro template. Usar os ids dela aqui não aplica classe nenhuma.

### 2.1 Seção → container

`root/container` (o do template) **nunca recebe `cq:styleIds`** — 212 de 212 pares. Ele já carrega por policy `cq:styleDefaultClasses='main container-padding-height0 container-padding-width0'`, ou seja, padding zero nos quatro lados. Todo respiro vem dos containers de seção. Escrever style nele é desperdício.

**Valores canônicos de padding** (corrigindo três levantamentos que citaram só um breakpoint ou trocaram desktop por mobile):

```
                       mobile (<1050px)   desktop (>=1050px)
padrão                 30px / 15px        50px / 25px
Pad T/B Small          20px               30px
Pad T/B Large          50px               70px      <- NÃO 50px
Pad T/B No Padding     0                  0
Pad L/R Small          10px               15px
Pad L/R Large          25px               50px
```
Breakpoint único do design system: **1050px**. Não há tablet.

**Seção simples:** `['1717410661180','','']` (1000px) ou `['','','']`, conforme o perfil.

**Seção com fundo colorido — duas camadas, no eixo da LARGURA:**
```
container externo   backgroundColor=<cor>, cq:styleIds=['','1717498056876','']   # None T/B, sangra
  container interno cq:styleIds=['1717410661180','1717498052331','1717498053499'] # 1000px + Small + Large
```
Correção ao levantamento `ref-deepx`: o nó que carrega a cor **pode** carregar o próprio padding (104 casos com Small, 68 com padrão). O que ele nunca tem é `fitcontainer` — 198 de 258. O motivo é largura, não padding: a cor precisa sangrar enquanto o conteúdo fica em 1000px. Se a seção colorida não precisa sangrar, uma camada só basta (56 casos).

**Espaçamento entre seções:** o gap de margem é zero; o respiro é `padding-bottom(A) + padding-top(B)`. Alternar Small(30) e Default(50) dá 80px no desktop e 50px no mobile em toda fronteira — é a métrica-alvo da `sony`. **Dentro** da seção, irmãos ficam colados (gap medido 0px em 100% dos casos, nas duas referências, em todos os níveis). Não inventar margem entre irmãos: o design system não tem nenhuma.

Exceções ao "nenhum componente tem margem própria", que o motor de espaçamento precisa descontar: `.cmp-table{margin:20px 0}`, `.cmp-textwithimage{margin:30px 0}`, `.link-button{margin-top:20px/40px}`, `.cmp-list__list{margin:55px 0}`. `title`, `text`, `image`, `tabs` e `embed` de fato têm margem 0.

### 2.2 Linha e coluna

| origem | destino |
|---|---|
| linha de 1 coluna | blocos como irmãos diretos da seção. **Sem wrapper.** |
| linha 6/6, 4/4/4, 3/3/3/3 (larguras iguais), conteúdo genérico | `flexcontainer` + N `flexcontaineritem`, `cq:styleIds=['','1719484596357']` |
| linha 6/6 em que uma coluna é **uma** imagem (ou um carousel de 1 slide) e a outra é texto | **`textwithimage`**, nó único (§2.3) |
| linha de larguras **desiguais** (8/4, 5/7, 9/3) | `flexcontainer` de colunas **iguais** — ver decisão abaixo |

**Decisão sobre coluna desigual.** Três levantamentos deixaram a pergunta em aberto; escolho **normalizar para iguais via `flexcontainer`** e **proibir `cq:responsive` no motor novo**. Razões: (a) `layoutDisabled='true'` nas policies de container, flexcontainer e flexcontaineritem — o autor não consegue redimensionar pela UI, então a página nasce não-editável; (b) o grid do AEM quebra em 768/1200px e o design system em 1050px, logo entre 1050 e 1200px a coluna fica em largura de tablet com tipografia de desktop; (c) zero precedente autoral em 196 páginas (`cq:responsive` aparece 2 vezes em 290 `flexcontaineritem`, e a própria Anion não usa em lugar nenhum). A regra do time autoriza: **layout pode divergir do GWI; conteúdo, não.** Nenhum conteúdo se perde ao igualar larguras.

`flexcontaineritem` não recebe style nenhum e não tem propriedade de largura — `.flex_container>.cmp-container>div{flex:1}`. Gap padrão 26px.

**`1719484596357` é obrigatório em todo `flexcontainer` com 2+ itens.** Sem ele as colunas não empilham abaixo de 1050px: medido a 390px, a `deepx` fica com colunas de 152px e 122px, e dois botões `fixed-min-width` estouram a tela (item em `x=431 w=345` numa viewport de 390). 32 dos 85 flexcontainers de 2 itens do corpus autoral estão quebrados assim. **Divergir da referência neste ponto é decisão fechada.** O `phone/width=12` das colunas do GWI corresponde exatamente a esse style.

`flexcontainer` de **um** item é a moda no corpus (107 de 196), usado como invólucro de herói. O motor **não** deve reproduzir: um item só não é coluna, e o invólucro não muda um pixel. Emitir o conteúdo direto na seção.

### 2.3 `textwithimage` — a técnica específica da folha de produto

Não é escolha por bloco, é escolha **por tipo de página**: 28 páginas autorais usam só `image`, **165 usam só `textwithimage`**, 10 usam os dois. `deepx` e `sony` (landings) têm zero `textwithimage`.

Regra: numa linha 6/6 `{imagem} + {texto}`, emitir **um** nó `textwithimage` com `fileReference`, `alt`, `text`, `textIsRich='true'`. O padrão do componente é imagem à **direita** (`flex-direction:row-reverse`); quando a coluna da imagem vem **primeiro** no GWI, carimbar `cq:styleIds=['1718154328384']` (classe `left`) — 174 de 179 casos autorais. Não existe propriedade de proporção: `--textwithimage-image-ratio` nunca é definida em lugar nenhum, é sempre 50/50 com gap 40px — que é exatamente a linha 6/6 do GWI.

**Limite duro:** `textwithimage` guarda **uma** imagem. Se a coluna de mídia é um carousel com 2+ itens, colapsar perde conteúdo e é proibido. Na amostra de 200 carousels: 89 com 1 item (colapsáveis), 64 com 2, 33 com 3, 11 vazios. Ou seja ~45% cabe na regra.

Abaixo de 1050px o `textwithimage` vira `display:block` com a imagem **sempre acima** do texto, independente de left/right, e a imagem nunca é ampliada (`width:auto; max-width:100%`).

### 2.4 Carousel — **divergência deliberada da Anion**

A Anion funde a coluna-carousel com a coluna-texto num `textwithimage` e **descarta os slides 2..N**: 110 dos 111 pares com vídeo no carousel não têm nenhum `embed` no destino. São 182 slides de vídeo perdidos.

**Não copiar.** A regra do time é explícita: conteúdo segue o GWI. Regras:

1. carousel com **1 slide de imagem** + coluna-texto irmã → `textwithimage` (§2.3);
2. carousel com 1 slide de imagem, sem coluna irmã → componente `image`;
3. carousel com **2+ slides** → manter `carousel` do global2, dentro de `flexcontaineritem` pareado com a coluna de texto. O componente existe, tem policy (`1773311509435`), aceita `embed`/`image`/`textwithimage` como slide, está na lista de permitidos do slot e do `flexcontaineritem`, e tem precedente renderizado no herói (`boards-modules/connect-tech/nvidia-jetson-tx2…`). Preservar `cq:panelTitle` por slide (195 rótulos perdidos hoje em 114 páginas);
4. slide de imagem **sem `fileReference`** (62 casos, todos com `cq:featuredimage` também vazio — no GWI renderizam div vazia) → descartar e registrar `Pendencia(categoria='slide_vazio_na_origem')`, não `tipo_nao_reconhecido`;
5. slide 1 vazio + vídeo no slide 2 → a mídia do herói é o `embed` (caso `sony-imx779-aqr`, único precedente autoral);
6. **nunca empilhar** slides como blocos irmãos: 3 vídeos institucionais cobrem 145 das 182 ocorrências, e empilhar poria o mesmo vídeo como bloco de corpo em até 145 páginas.

Cuidado medido: `@media(min-width:1050px){.cmp-carousel__content{max-height:36vw!important;overflow:hidden}}` — a 1400px isso corta o slide em 504px. Foto de produto vertical será cortada. Registrar aviso quando `naturalHeight/naturalWidth > 1`.

### 2.5 `relatedsuggestions` → seção `title` + `list`

O alvo é **`list`**, não `cardlist` e muito menos botões: 201 `list` contra 1 `cardlist` no corpus autoral (e esse `cardlist` é um card de blog, não "Similar Products").

Forma fixa, 201 de 201: container de seção com **exatamente dois filhos, `title` depois `list`**, e essa seção é sempre a **última** de `root/container` (194 de 194).

- container: `['1717410661180','1717498056876','']` (1000px + None T/B — o `<ul>` já traz `margin:55px 0`);
- `title`: `jcr:title='Similar Products'`, `type='h2'`, `cq:styleIds=['','','','1718280237031']` (classe `heading3`, 22px — reproduz o tamanho de 51 casos autorais sem abrir mão da semântica). A Anion usa `h1` em 197 casos; ver §6-Q4;
- `list`: `listFrom='static'`, `pages` (String[]), `linkItems='true'`. **Não** gravar `maxItems` (no GWI corta em 1 caso de 193; no corpus autoral está ausente em 197 de 202), **não** gravar `orderBy`, **não** gravar `cq:styleIds` (os dois grupos da policy têm `cq:styles` vazio — inertes).

**A string "Similar Products" não existe em nenhum `jcr:content` do GWI** — está travada em `/conf/macnicagwi/.../macnica-gwi---mae-product-page/structure/.../heading` (`type=h2`). O motor **sintetiza**; não há o que copiar. O template de destino não tem equivalente.

Os três modos da origem, todos materializados em `static`:

| modo GWI | n | técnica |
|---|---|---|
| `static` (193) | cópia 1-para-1 do array `pages`, só reescrevendo caminhos. Offline. |
| `children` (44) | resolver `parentPage`+`childDepth`+`orderBy`+`sortOrder` **contra o GWI** e gravar os caminhos. Nunca manter `listFrom='children'`: o parentPage reescrito passa a avaliar a árvore de destino, que tem outro conjunto de filhos — deriva silenciosa (é o que acontece hoje em 44 páginas). |
| `search` (12) | a policy do `list` tem `disableSearch='true'` — não há escolha. Resolver renderizando a página do GWI com `?wcmmode=disabled` e lendo os `href` de `.cmp-teaser__link`; as tags `macnica-atd-europe:` não aparecem em `cq:tags` de nenhuma página, logo a resolução vive fora do JCR cacheável. Hoje essas 12 páginas perdem a seção inteira. |

**Perda conhecida e inevitável:** `list.html` emite só `${item.title}`; o GWI mostra cards com título **e** descrição (`showDescription='true'` em 158 dos 193). Não há ramo de descrição no HTL. Registrar como perda aceita, não como bug. E o rótulo vem do `navTitle` da página-alvo (core List v2), não de nada gravado no `list` — os rótulos sairão mais curtos que no GWI.

**Não copiar os erros do corpus:** 203 de 1.299 itens autorais apontam para páginas inexistentes (perderam o segmento `/sony-image-sensors/`) e 3 `list` linkam a própria página. O motor segue o GWI.

O que existe hoje é o pior caso possível: `static` vira **um botão por página** com rótulo inventado do slug (`'Sony Imx334Lqr C'`) e `linkURL` **não reescrito**, ainda apontando para `/content/macnicagwi` — 1.272 dos 1.358 botões do `copia-teste`.

### 2.6 Demais tipos — tabela de emissão

| origem (`macnicagwi/components/content/…`) | destino | propriedades / styleIds |
|---|---|---|
| `text` | `…/text` | `text`, `textIsRich='true'`; fundir consecutivos (§1.6); `strip_empty_blocks` + `rewrite_links_in_html` |
| `heading`, `title` | `…/title` | `jcr:title` + **`type` sempre explícito** (§2.8). Título que abre seção: `['','','1717668113714','']` (Center). Título dentro de coluna/aba: `['','','','']` |
| `resizableimage` | `…/image` | `fileReference`, `alt`, `altValueFromDAM='false'`, `isDecorative='false'`, `displayPopupTitle='true'`, `titleValueFromDAM='true'`, `linkTarget='_self'`, `cq:styleIds=['','']`. **Sem `spImage`** (§2.9). Sem `fileReference` → pendência `imagem_quebrada`, exceto se `imageFromPageImage='true'` (20 casos — vem da propriedade da página, não é bug) |
| `imagetext` (123) | `…/textwithimage` | hoje está em `KNOWN_CONTAINER_TYPES` e é **dissolvido**, perdendo o pareamento. `assetPositionLargeScreen='left'` → `['1718154328384','','']`. 54 dos 123 também têm `cq:responsive` — são coluna **e** componente ao mesmo tempo |
| `table` | `…/table` | `text` (HTML cru do GWI, preservado), `textIsRich='true'`. Nunca jogar tabela num `text`: não existe **uma** regra CSS para `table` dentro de `.cmp-text` (0 ocorrências em site.css). Tabela de especificação (aba 1): `['','','1722939215525','']` (No Rounded Corner — determinista: 180/182 na aba 1, 0/181 na aba 2). Largura por coluna: usar as classes utilitárias no HTML do RTE (`fixed`, `columns4`, `wh245`, `center`…), que não estão em policy nenhuma |
| `button` | `…/button` | `jcr:title`, `linkURL` (reescrito), `linkTarget='_self'`. Em coluna/aba: `['','1722936853890','1717669229626']`. Em seção de largura cheia: `['','1723033446255','1717669229626']`. **Armadilha:** "Fit to Text" **não** encolhe — só declara `width:fit-content` e o `min-width:550px` do desktop continua valendo; quem encolhe é "Fixed Minimum Width" (345px). Link para `/content/dam/` troca a variante sozinho para `link-button--download` (margem 30px, 1.3rem) — não se controla por style |
| `video`, `embed` | `…/embed` | `type='embeddable'`, `embeddableResourceType='core/wcm/components/embed/v1/embed/embeddable/youtube'`, `youtubeVideoId`, **`layout='responsive'`**. Divergência deliberada: a Anion usa `fixed` nos 8 embeds e o iframe fica com `height=390` travado, medido 462×396 numa coluna e 340×396 no celular. Copiar a referência aqui seria regressão |
| `download` | `…/downloadlist` ou `…/button` | **decisão pendente (§6-Q7)**: `…/content/download` existe em `/apps` mas **não** está na lista de permitidos do slot nem do `flexcontaineritem`, e tem zero instância autoral. `jcr:title` vem de `dc:title` do asset no DAM — **nunca** inventar do nome do arquivo (506 downloads do GWI têm só `fileReference`; hoje saem 506 rótulos inventados, tipo `'multi power sequencer 2.1.2'` onde o `dc:title` é `'Multi-Rail Power Sequencer and Monitor - Complete Archive'`) |
| `tabs` | `…/tabs` | nó sem propriedade nenhuma (183 de 183). Cada aba é um **container** com `cq:panelTitle`. Componentes como filhos diretos, **sem embrulho** (§2.7) |
| `pagesectionlisting` (14) | `…/anchorlink` | **bloqueado**: o nome do nó-filho que recebe `fixedListItems/item0..N` não está confirmado — as 5 instâncias autorais do global2 não têm filhos. Abrir `/apps/macnicaglobal2/components/content/anchorlink/cq:dialog` antes |
| `experiencefragment` (125) | `…/experiencefragment` | 121 apontam para o **mesmo** fragmento (`products-contact-block/master`) e 4 para `signup-and-contact`. Dois mapeamentos resolvem 125 pendências. Hoje está em `MANUAL_REVIEW_TYPES` e ~108 páginas ficaram sem CTA. O próprio nó do GWI guarda o texto renderizado na propriedade `text` — serve de oráculo de auditoria |
| `productlisting` (11), `supplierlist`, `cardlist`, `embaddedhtml`, `form/*`, `breadcrumb` | — | §5 |
| `filterabletable` (1) | `…/filterabletable` | mapeamento quase direto; muda **um** nome: GWI `parentPath` → global2 `parentPage`. Faltam os rótulos de UI (§6-Q9) |

### 2.7 Abas

Cada aba = nó com `sling:resourceType='macnicaglobal2/components/content/container'` e `cq:panelTitle`. `jcr:title` e `layout='responsiveGrid'` são resíduo de UI antiga — dispensáveis.

**Conteúdo como filho direto da aba, sem container interno.** Isto **reverte** o conserto de "espaço-abas" do `ACHADOS` (container com Padding T/B Small dentro da aba, 60px): as duas referências e o corpus de 196 deixam gap 0 lá dentro e confiam no padding do `title` (h3 = `padding-bottom:20px`) e no `margin` dos `<p>`. O próprio nó da aba **é** um container e já traz 50/25 no desktop, 30/15 no mobile.

`cq:styleIds` da aba: se a seção que contém o `tabs` é **full-bleed colorida**, a aba carrega `['1717410661180','1717498056876']` (1000px + None T/B) — é assim que o conteúdo volta para 1000px dentro da faixa que sangra; 361 de 372 itens de aba do corpus carregam `fitcontainer`. Se a seção já é `fitcontainer`, a aba fica **sem style**. Aplicar ou não aplicar em **todas** as abas da mesma página — no desktop não muda nada (950 < 1000), no mobile muda 15px.

**Nunca** `backgroundColor` em item de aba: 45 dos 181 pares do corpus têm cor no `item_1` e nada no `item_2` (aba 1 cinza, aba 2 branca) — descuido de autoria visível na tela.

Rótulos: `cq:panelTitle` da origem está íntegro (449 de 449). Os `jcr:title` `'Tab 1'/'Tab 2'` do JCR **nunca chegam à tela** no GWI — o componente renderiza `'Specifications'` e `'Related Documents'` fixos. Gravar esses dois. 102 itens sem `jcr:title` e 1 página com 3 abas → §6-Q8.

Com 6+ abas o JS adiciona `tab-list--over6` (mas só a `.tab-list`, não a `.cmp-tabs` — não há compactação automática no componente de aba do global2; elas quebram em várias linhas de pílulas de 233px).

### 2.8 Tipografia — decisão fechada

Neste design system **h2 é maior e mais pesado que h1**: desktop h1 25px/500, h2 29px/600, h3 22px/600 (`padding-bottom` 20px, sem padding em cima), h4 18px/500. `1rem = 10px` (`html{font-size:62.5%}`). Isso responde sozinho a queixa "títulos sem negrito": peso 600 existe dentro do sistema, basta usar `h2`.

**Decisão: preservar o `type` da origem.** O GWI tem 51 h1, 522 h2, 264 h3, 113 h4 — o nível vem da origem e é conteúdo, não layout. Preservar dá títulos de seção em h2 (29px/600), que é simultaneamente o certo por SEO, o certo visualmente e o que a `sony` faz. Os 7 h1 da `deepx` e os 351 h1 do corpus são **frequência de descuido**, não intenção de design — e o próprio corpus prova: as páginas feitas com cuidado (`sony-imx785-series`: 1 h1 + 12 h2) usam a hierarquia.

**Nunca usar o grupo 【Font Size】 para controlar tamanho**: o style rotulado "Heading 2" (`1718280235888`) emite a classe `heading1`. Bug de policy. Tamanho se controla por `type`. A única exceção sancionada é `1718280237031` (heading3) para **diminuir** um título sem mexer na semântica.

**O h1 da página — regra que resolve três achados de uma vez.** O h1 servido pelo GWI é o **`pageTitle`**, não o `jcr:title` (112 de 354 páginas divergem; o migrador usa o errado, e em 45 páginas a string do `jcr:title` não existe em lugar nenhum da origem = invenção pura).

```
se o corpo do GWI já tem um heading type='h1':
    emitir esse heading; NÃO injetar bloco de título
senão:
    emitir um nó title VAZIO (sem jcr:title, sem type)
    -> o AEM renderiza o pageTitle da página como h1
```
O `title` vazio é idioma autoral confirmado (65 de 196 páginas) e reproduz exatamente o cabeçalho do GWI sem inventar conteúdo. Regra rígida do corpus: **`jcr:title` e `type` andam sempre juntos** — 413 títulos têm os dois, 67 não têm nenhum, nunca um sem o outro. Nunca gravar `jcr:title` sem `type`.

### 2.9 Imagem: **não emitir `spImage`** — a ação em lote está cancelada

Contradição entre `ref-deepx` ("sem spImage a imagem SOME no celular") e `ref-sony` ("não some"). **`ref-sony` está certa** e a investigação dedicada fechou com experimento:

- o CSS base `.cmp-image .cmp-image__inner{display:block}` nunca é desligado; os modificadores `--pc/--sp` só entram no markup quando existe `spImage` **com `fileReference`**;
- A/B na mesma imagem, mesma página, convertendo uma forma na outra no DOM: **0px de diferença em 32 de 32 medições**, a 390px e a 1400px. A única diferença real é 6px a mais de altura de bloco no `textwithimage` desktop, **contra** o `spImage`;
- `/americas/dhw` tem 411 componentes com **zero** `spImage`, no ar, funcionando;
- não é art direction: 209 de 220 apontam o mesmo asset; e os **11 que diferem são erro de cópia** servindo a imagem errada no celular nas próprias páginas da Anion (`sony`: pai `sonyrs-sensorlineup.png`, spImage `sony-global-shutter-lineup.png`);
- custa banda: a policy tem `disableLazyLoading='true'`, então no celular o visitante baixa o mesmo arquivo duas vezes.

**Consequências:** (a) o motor não emite `spImage` preenchido (emitir o nó vazio é aceitável, renderiza igual, mas não acrescenta nada); (b) **a ação em lote proposta para as 355 páginas não existe** — não há bug a corrigir; (c) "tem nó `spImage`?" nunca serve como critério de diagnóstico, porque o diálogo cria o nó vazio sempre.

Sem style, `.cmp-image{max-width:100%;text-align:center}` dá imagem em tamanho natural, centrada, limitada à coluna. A Anion não usa `large` (`width:100%`) em lugar nenhum.

### 2.10 Propriedades de página

Nunca vão para o corpo; vão para `jcr:content`:

- `sling:resourceType='macnicaglobal2/components/maeproductpage'` — **não** `…/components/page`. Não é cosmético: o diálogo com os fieldsets `Model Information`, `Product Hierarchy Details` etc. só existe no `maeproductpage` (24.874 bytes contra 3.162). Com `components/page` o autor não consegue nem ver nem editar as propriedades `pd_*`. 16 de 16 páginas migradas estão erradas;
- `manufacturerlogo` (`core/wcm/components/image/v3/image` + `fileReference` + `alt`) e `cq:featuredimage` (vazio, só `altValueFromDAM='false'`). Aviso de reunião: o template **não renderiza** `manufacturerlogo` (zero ocorrência no HTML da `deepx`, que tem a propriedade preenchida). Depois da correção o logo **some da tela** — igual às referências;
- nós vazios `pd_downloadAsset`, `pd_productFamilyImage`, `pd_technologyImage`;
- **taxonomia copiada nome a nome**: o diálogo do `maeproductpage` usa exatamente os nomes do GWI (`businessCategories`, `manufacturer`, `productcategory`, `sensorcategory`, `shuttertype`, `sensortype`, `pixelsize`, `resolution`, `opticalformat`, `interface`, `arcoating`, `productLines`, `productFamily`, `productManufacturerRanking`). Não há renomeação. **Preservar o tipo:** `businessCategories` é `String[]` dos dois lados e o migrador gravou String simples. Usar os valores do namespace `mai:`, **não** as variantes `interface1`, `pixelsize1`, `shuttertype1/2` (namespace `macnica-atd-europe`, que a tabela americana não lê);
- `pd_*` (override curado, opcional): `pd_modelName` do **`navTitle` do GWI** (acerta 189/209 contra 181/209 da regra atual de slug-em-maiúsculas, que produz lixo tipo `'6-ALTERA-SOC-EMBEDDED-DESIGN-SUITE'`); `pd_resolution`/`pd_pixelSize`/`pd_interface`/`pd_productFamilyText` = `valor[0]` quando a origem é multivalorada (125/128 e 125/129 de acerto); `pd_downloadAsset/fileReference` = o PDF que no GWI é um `download` dentro da aba 2 (202 de 209 folhas autorais têm). **`pd_modelName` e `pd_isModelNameLinkToPage` não são invenção do migrador** — são padrão autoral, 209/209; o dossiê errou nesse ponto;
- o `filterabletable` cai para a propriedade **sem prefixo** quando `pd_X` falta (provado: 74/74 em resolution, 75/75 em pixelsize, 73/73 em interface, 47/47 em productFamily). Logo o alvo obrigatório é a taxonomia crua; `pd_*` é bônus;
- `build_seo_props` (pageTitle/navTitle/keywords) e `jcr:description` continuam como estão. **`navTitle` é o mínimo indispensável** — sem ele a primeira coluna da listagem sai em branco (cadeia: `pd_modelName` → `navTitle` → vazio; `jcr:title` não é usado);
- **não inventar** `hideInNav`, `pd_description` nem `pd_isModelNameLinkToPage` quando a origem não tem.

---

## 3. Estratégias por arquétipo

Pedido explícito do usuário, e o levantamento confirma que é necessário: os 6 `cq:template` de origem viram hoje um template só e as técnicas diferem de verdade.

**Escopo real primeiro.** 213 das 354 páginas do GWI **já estão autoradas** no global2 (204 completas, 9 divergentes por conteúdo). O motor novo tem **141 páginas** de escopo, 137 sem as de teste. Em particular, 186 das 188 fichas do arquétipo A já estão prontas: **a "maior alavanca de automação" do dossiê vale 2 páginas, não 188.** O valor do motor está em E (68), B (45), C (15), D (7).

| perfil | quem | n (escopo) | técnica |
|---|---|---|---|
| **P1 — ficha de sensor sony** (A) | `mae-product-page` + `tabs` cujo item[0] tem um `table` como filho único e item[1] só `download`/`downloadlist` (regra 100% precisa, zero falso-positivo) | 2 | **Não é conversor, é gerador**: template fixo de 3 seções (#0 herói `fitcontainer`+None T/B com `title`+`textwithimage`; #1 faixa `backgroundColor=rgb(247,247,247)` com `tabs`+`button`; #2 `fitcontainer` com `title`+`list`) e dois interruptores (herói embrulhado ou não, botão presente ou não). 3 esqueletos cobrem 140 das 196 páginas do corpus |
| **P2 — datasheet Design Gateway** (B1) | `/design-gateway`, sem tabs, com `experiencefragment` e `heading` | 26 | Lista de seções **constante** nas 26 (`Highlights`, `Why Macnica?`, `Key Specifications`\|`Typical Applications` em 6/6, `Resources`, `Get Started`). Regra de topo + sub-perfil com nomes de seção esperados como asserção de auditoria. 270 spacers nas 62 páginas B — são intra-bloco, não fronteira de topo |
| **P3 — editorial mae-product-page** (B2) | canon, sitime, sony fora do padrão, deepx | 19 | Faixa automatizável: 4 canon + 9 sony `imx92x` (esqueleto repetido). Faixa de revisão: o resto. É aqui que moram as "33 páginas puladas por insegurança" — o casamento origem↔destino por texto é ambíguo quando há muitos blocos curtos parecidos |
| **P4 — landing de fabricante** (C) | `manufacturer-detail-page-content` | 15 | O mais complexo: única família com **coluna dentro de aba** (`Panel.rows` recursivo) e mais níveis de aninhamento. Alta visibilidade (porta de entrada de cada fabricante) e pior destino atual (`/altera` 109 `_wrap`, `/ambarella` 117). **Conversão assistida, uma a uma**, com `deepx` do global2 ao lado como teste de regressão — é o único par origem↔autoral fora do sony |
| **P5 — landing de linha de produto** (D) | `macnica-gwi-product-line-detail-page-template` | 7 | Sem `pageproperties` e sem `cmp-container--title-pageproperties` (0 de 9): **não aplicar a correção de logo aqui**. `productlisting` é a peça central e não tem destino (§5). Volume pequeno, revisão manual |
| **P6 — product-detail curta** (E1) | `product-detail-page-content`, ≤12 folhas | ~38 | **Automação total e barata**: 1 seção `fitcontainer`, `title`+`text`+`table` dentro. Sem coluna (só 4 de 76 páginas E têm coluna multi-membro), sem aba, sem logo no corpo. A largura `'8'` de 15 páginas vira a largura de conteúdo do container, não um `flexcontaineritem` de 8/12 |
| **P7 — product-detail longa com `imagetext`** (E2) | `product-detail-page-content`, >12 folhas | ~30 | `imagetext` → `textwithimage` 1-para-1 (o `aem_padronizar_textwithimage.py` já codifica o design de referência). 167 dos 702 spacers estão aqui. As 4 maiores (`macnica-and-sony`, `sony-pregius-pregius-s`, `macnica-and-adi`, `ambarella-n1-soc`) são editoriais longas: conferência visual individual |
| **P8 — fora de padrão** (F, G) | `news-page-content` (1) + 4 páginas de teste do ambarella | 0 | Excluir do lote. 3 das 4 de G têm corpo byte-a-byte idêntico entre si |

**Sub-rotina transversal — PLANAS (13 páginas).** `/altera/agilex`, `/altera/altera-stratix-10`, `/altera/altera-max-10`, `/altera/opencl-software-technology`, `/altera/altera-arria-10/{gt,sx}-soc-fpga`, `/altera/altera-cyclone-10-fpga/{gx,lp}`, 3 de `/altera/development-kits`, `/i-chips/i-chips-warping-lsi`, `/i-chips/i-chips-scaler-warper-lsi`. Nenhuma tem par autoral. Detector de fronteira = spacer (§1.4). Sem essa sub-rotina, a regra de topo cria 19 seções na `agilex` — a doença de volta.

---

## 4. Reaproveitar de `aem_lib.py` sem tocar

Sessão, travas e transporte:
`build_session` · `assert_target_is_safe` · `session_expired` · `get_json` · `fetch_with_depth_fallback` · `post_node` · `delete_node`

Links: `rewrite_link` · `rewrite_links_in_html` (não têm layout dentro)

Assets: `map_asset_path` · `ensure_dam_folder` · `copy_asset` (idempotente — checa `<destino>.json` antes)

Metadados de página: `detect_tag_region` · `load_tag_taxonomy` · `build_product_tags` · `build_tag_props` · `build_seo_props` · `build_pd_props` (com a correção do §2.10 para `pd_modelName`)

Criação, crawl e saída: `build_page_payload` (não gera nenhum bloco de conteúdo) · `find_template_path` · `resolve_template` · `crawl_tree` · `normalize_path` · `normalize_name` · `list_child_nodes` · `is_page` · `write_csv` · `add_common_args` · `print_header`

Limpeza de HTML: `is_meaningful_text` · `strip_empty_blocks` (com a exceção do §1.7) · `slug_to_label` — **este último só para rótulo de UI, nunca para conteúdo**: é ele que produz os 1.241 rótulos de botão e os 506 de download inventados.

Modo clone: `flatten_node` · `build_clone_payload` — **com correção obrigatória**: `SKIP_PREFIXES` (`aem_lib.py:196-199`) cobre `cq:lastModif*` mas **não** `jcr:lastModified`/`jcr:lastModifiedBy`. Clonar hoje fabrica autoria falsa (10.614 nós em `boards-modules` com editores que nunca tocaram `copia-teste`).

**Não reaproveitar:** `extract_content`, `BlockBuilder`, `build_content_payload`, `add_simple_block`, `ALTERNATING_BACKGROUND_COLORS`, `contar_conteudo_migravel`, `auditar_migracao`.

**Encaixe — exatamente duas chamadas em `aem_migrate.py`:**
```
linha 324   componentes, skipped = extract_content(jcr_content)
            -> arvore, skipped, page_props = extract_tree(jcr_content, source_path)

linha 338   payload, contagens = build_content_payload(titulo, componentes, ...)
            -> payload, contagens = build_layout_payload(titulo, arvore, template_path,
                                                         perfil=<P1..P8>, **mesmos kwargs)
```
Tudo em volta (226-241 template/taxonomia/crawl, 328-335 tags, 336 SEO, 355-374 `pd_*`, 425-430 `post_node`) fica como está. Módulo novo: `scripts-bruno/aem_layout.py`.

**Dois bugs que não podem ser herdados:**
1. `aem_lib.py:2067-2069` — no ramo de `tabs`, `add_simple_block(...)` é chamado e `conta(sub['kind'])` executa **sem olhar o retorno**. `add_simple_block` só conhece text/table/heading/image/button e devolve `False` para o resto: `embed`, `carousel`, `list`, `downloadlist`, `flexcontainer` e `tabs` aninhado dentro de aba são **descartados e contados como migrados**. A auditoria reporta 100%. O ramo de `flexcontainer` (2048-2049) faz certo. **O emissor novo tem de ser total**: todo nó da IR tem emissor ou vira pendência explícita — nunca `False` silencioso;
2. `aem_lib.py:2099` — os nomes de nó vêm de contagem de **chaves do payload**, produzindo `text_5, text_16, text_27` em vez de `text_1..4`. Não colide, mas impede diff e re-execução idempotente. Nomes determinísticos por pai.

**Auditoria nova.** `contar_conteudo_migravel`/`auditar_migracao` comparam contagem por tipo — não detectam troca de posição nem perda de agrupamento, e dão 100% com o bug acima. Substituir por: (a) diff de **sequência** `(kind, texto normalizado)` origem↔destino; (b) cobertura de **vocabulário** por página, não contenção de string (comparar por substring dá falso positivo porque o motor funde blocos); (c) geometria renderizada com `?wcmmode=disabled` (modo de autoria injeta placeholders de 29px). E o `aem_diff_conteudo.py` precisa parar de filtrar `'contact us for more information'` e `'request a quote'` na lista `BOILERPLATE` — é exatamente o conteúdo dos 125 XF, e por isso a perda ficou invisível.

---

## 5. Fora de escopo

1. **As 213 páginas já autoradas pela Anion no global2.** Escrever gerador para elas é retrabalho; as 9 divergentes (§6-Q12) são correção pontual de conteúdo, não layout. **Nunca** copiar `copia-teste` por cima do global2: o único caminho relativo em comum é `deepx` (89 componentes autorais seriam sobrescritos) e os outros 353 entrariam como novos, 209 deles duplicando lado a lado as fichas autorais. Não há versão publicada para restaurar.
2. **Recuperação de conteúdo/SEO**: ~213 páginas sem `jcr:description`, 266 com a meta description como texto visível no corpo. É passada separada; o `aem_restaurar_description.py` já cobre parte.
3. **`containerpy`** (111 páginas, nó irmão que nunca renderiza). O censo fechou: das 1.572 folhas de texto lá dentro, só 2 não têm par no GWI, e as duas são rótulos de download inventados pelo próprio migrador. Não guarda nada insubstituível — mas a faxina é operação própria, com backup, não efeito colateral da remigração. **O motor precisa decidir como escreve** (§6-Q2).
4. **Criação dos Experience Fragments no destino.** O motor aponta; alguém cria os 2 fragmentos.
5. **`productlisting` (11) e `pagesectionlisting` (14)**: sem destino mapeado. `pagesectionlisting` esbarra no nó-filho não confirmado do `anchorlink`. Isolar as páginas antes do lote.
6. **`embaddedhtml` (2, JSON-LD schema.org na `/sony-image-sensors`)**, **`form/options` (2, na `/deepx`)**, **`breadcrumb` (2 — descartável, o template já traz)**.
7. **Correção em lote de `spImage`**: cancelada (§2.9). Não há bug.
8. **Publicação/replicação**: nenhuma das 217 páginas do global2 nem das 355 de `copia-teste` tem `cq:lastReplicationAction`. Nada foi publicado; o motor não publica.
9. **A landing `/sony-image-sensors`** (única com truncamento real, 16.852 → 149 caracteres, resíduo do HTTP 300): hoje `jcr:content.50.json` responde 200 e traz tudo. Re-migração normal resolve, mas a página já está autorada em `global2/semiconductors/sony`.

---

## 6. Riscos e decisões humanas

**Riscos de processo (mitigação obrigatória no motor)**

- **Não existe rede.** Zero versões JCR na árvore de destino (`jcr:baseVersion` 0, `jcr:versionHistory` 0) e `/var/audit` devolve 404. **Backup próprio do `jcr:content` inteiro antes da primeira escrita é requisito, não boa prática.**
- **`copia-teste` tem mais de um editor.** 79 nós foram editados à mão por `bruno.jaques` depois do último lote (16/09), todos em `/canon`: 56 containers de padding, 7 títulos padronizados com `['','','1717668113714','']` (Center) e **1 anotação viva** (`cq:annotations/1_1789691368692`, texto `'Imagem se separou '`) que nenhum inventário por tipo de componente enxerga. Mais 8 blocos de texto **em português** na `/canon`, únicos conteúdos da família que não existem no GWI. Remigrar `/canon` apaga tudo isso. **Checar `jcr:lastModifiedBy` por nó antes de qualquer lote** — e saber que `cq:lastModifiedBy` de página **não serve**: uma rajada de script posterior sobrescreve o carimbo (erro em 5 de 12 páginas do canon, 42%).
- **O global2 não está congelado**: houve escrita de `bruno.jaques` em 17/09. Qualquer diff GWI×global2 precisa ser refeito perto da hora de decidir.
- **Duas gerações de migrador no destino**: `canon` foi migrada com `flexcontainer` (9/21, sem zebra), as outras 15 com `_wrap`+zebra; e a família se divide em 80 páginas com blocos em `root/container/*_wrap` e 274 em `root/container/content_area/*_wrap`. **Detectar a geração antes de agir** — foi o ponto cego de `content_area` que fez a varredura anterior contar 26 logos em vez de 252.

**Decisões que precisam de humano (com minha recomendação)**

| # | questão | recomendo |
|---|---|---|
| Q1 | **Zebra de fundo.** O `guidelines-to-follow.txt` do cliente manda alternar `#fff`/`#f7f7f7` a cada bloco (confirmado com o Bruno em 11/09); nem `deepx` nem `sony` fazem isso. A resposta muda o desenho do motor. | Cor é propriedade de **seção**, nunca de bloco. Default: sem fundo. Colorir só blocos "de apoio" (artigo relacionado, bloco de abas). Levar o conflito guideline×referência à reunião |
| Q2 | **Como escrever por cima do que existe.** Uma remigração que só reescreva `root/container` deixa 111 `containerpy` fantasmas e mistura nós velhos com novos. | `:operation=delete` em `root/container` antes de recriar, com backup do `jcr:content` inteiro. Precisa de piloto |
| Q3 | **`sling:resourceType` `page` → `maeproductpage`** troca o componente de página inteiro. | Trocar (o diálogo `pd_*` depende disso), mas **com piloto visual em 1 página de `copia-teste` antes do lote** |
| Q4 | **`h1` do "Similar Products"**: a Anion usa h1 em 197/201; eu proponho h2+heading3. | Minha regra (um h1 por página). Se o time preferir fidelidade ao corpus, trocar para `type='h1'` — é uma linha |
| Q5 | **Coluna desigual (8/4, 5/7)**: normalizar para iguais? | Sim, `flexcontainer` igual; `cq:responsive` **proibido** no motor. Vale um levantamento de quantas linhas do GWI são desiguais antes de fechar |
| Q6 | **Cor das faixas**: a `sony` usa `rgb(235,235,235)` e `rgb(247,247,247)`, que **não estão** na paleta sancionada (`#fbf5f9`, `#7f1080`, `#b20080`, `#3b1e83`, `#007ab6`, `#00851c`, `#ec6e00`, `#000000`). | Se gerar faixa, usar `rgb(247,247,247)` (é o que o corpus de 196 usa em massa e o que o migrador já acerta por acaso) |
| Q7 | **`download`**: o componente existe em `/apps` mas não está na lista de permitidos do slot e tem zero instância autoral. A Anion converteu os downloads do GWI numa **segunda tabela** com colunas `Title`/`Download`. | `downloadlist` (está na lista de permitidos) ou tabela, à escolha do time. **Não** botão |
| Q8 | **Rótulos de aba**: 102 itens sem `jcr:title` e 1 página com 3 abas. | `'Specifications'`/`'Related Documents'` nas duas primeiras; a terceira precisa de rótulo do time |
| Q9 | **Rótulos de UI do `filterabletable`** (`Filter`, `Apply`, `Clear All`, busca) não existem no GWI. | Adotar os da página `sony` de referência |
| Q10 | **Logo do fabricante**: mandar para `manufacturerlogo` faz ele sumir da tela (o template não renderiza). | Sumir, como as referências. Se o time quer visível, é bloco de conteúdo próprio ou ajuste de template — o motor não pode inventar |
| Q11 | **`anchorlink`**: nome do nó-filho não confirmado. | Abrir `/apps/macnicaglobal2/components/content/anchorlink/cq:dialog` antes de escrever qualquer `pagesectionlisting` |
| Q12 | **9 páginas autorais divergentes** e 5 com erro de dado na tabela de specs (ex.: `'165fps'` virou `'65fps'`, Pixel Size `6.90µm` virou `3.91µm`). Pela regra "GWI é a fonte da verdade", são correções a fazer no global2 — mas o global2 é somente-leitura para nós. | Lista entregue ao time; correção por quem tem permissão |
| Q13 | **Os 8 textos em português da `/canon`**: trabalho manual intencional ou engano? Remigrar apaga. | Confirmar com o Bruno antes de tocar em `/canon` |
| Q14 | **Os 59 `<hr>`**: divisor vira componente, style de container, ou quebra de seção? | Quebra de seção (dois containers) quando o `<hr>` está entre blocos `imagetext`; senão preservar no HTML do `text` |

**Riscos técnicos residuais**

- Os modos `children` (44) e `search` (12) do `relatedsuggestions` exigem **resolver a consulta contra o GWI no momento da migração** — o `search` só é confiável renderizando a página com `?wcmmode=disabled`. Isso torna essas 56 páginas dependentes de rede e de a origem estar no ar. Materializar uma vez e versionar o resultado.
- `tabs` não tem policy nenhuma no global2 — zero styleGroups. O que se controla é o container de cada aba. Não gastar decisão procurando estilo de aba.
- Três estilos são letra morta: `slim` (cardlist), `cmp-stickytabs__8columns`, e o "Heading 2" quebrado. Nenhum tem regra CSS em `clientlib-base`/`site`/`mai` (só a subsidiária `mai` foi verificada).
- 43 dos 53 styleIds não aparecem em nenhuma das duas referências. Isso não significa que estejam errados — significa que a Anion não precisou deles. Os mais prováveis de fazer falta na conversão: `1719541568246` (youtube responsivo), `1717565101174` (imagem largura cheia), os quatro de `table` (a tabela cinza do GWI é muito mais parecida com `black-ptn`+`normal-form` que com a roxa arredondada padrão) e `1718800456497`/`457369`/`458698` (gap do flexcontainer).