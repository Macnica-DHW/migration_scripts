# Regras de disposição — achados página a página

Registro vivo dos defeitos de disposição encontrados conferindo página
migrada × página do GWI, com **a regra que passou a valer** e **como detectar
o mesmo problema em outras páginas**.

Cada entrada existe porque alguém olhou a tela e viu a diferença. O diagnóstico
automático não pega nenhum destes: todos passam pela verificação de conteúdo
(`aem_fidelidade_render.py`) sem acusar nada, porque o texto está lá — só está
no lugar errado.

**Princípio que resolve todos:** o destino segue a **disposição visível do
GWI**, não o que está no JCR do GWI. As duas coisas divergem mais do que
parece.

---

## R1 — `imagetext` tem interruptor de visibilidade

**Onde apareceu:** `/ambarella`, rodapé. A página migrada mostrava dois blocos
"Automotive MCU RL78/F Series" e "Automotive MCU RH850 Series" — produtos
**Renesas**, de outro fabricante — que o GWI não mostra em lugar nenhum.

**Causa:** o `imagetext` do GWI não é só invólucro. Ele tem três
interruptores, e o GWI os respeita ao renderizar:

```
isText    = false   ->  não desenha o filho `text`
isButton  = false   ->  não desenha o filho `button`
isHeading = false   ->  não desenha o título
```

Os dois nós tinham `isText=false` + `isButton=true`: o GWI desenha **só os
dois botões** ("Supplier Website", "Request a Quote"). O motor ignorava as
flags e emitia o texto escondido junto.

**Regra:** filtrar os filhos do `imagetext` por `isText`/`isButton`/
`isHeading` antes de coletar. Ausente = visível; `false` explícito = pular.

**Como detectar em outras páginas:**
```
grep por isText=false / isButton=false / isHeading=false no jcr:content do GWI
```
Toda ocorrência é conteúdo que o GWI esconde e que uma migração ingênua
ressuscita. É o espelho do `containerpy`: lá o JCR tem conteúdo que a tela não
mostra no DESTINO; aqui, na ORIGEM.

---

## R2 — `assetPosition` decide empilhado × lado a lado

**Onde apareceu:** `/ambarella`, cards CV28AQ / CV28M / H22AQ. No GWI: imagem
em cima, título embaixo da imagem, texto embaixo do título, até 3 colunas por
linha. Na migrada: título e imagem **lado a lado**, e o texto espremido numa
coluna estreita, gastando uma altura enorme.

**Causa:** o motor mandava todo `imagetext` para `textwithimage`, que no
destino só sabe fazer lado a lado. Mas o GWI tem
`assetPositionLargeScreen = top`, que é **empilhado**.

**Regra:**

| `assetPositionLargeScreen` | destino |
|---|---|
| `left` / `right` | `textwithimage` (com o style Left quando `left`) |
| `top` | blocos separados: imagem primeiro, depois o resto |
| `bottom` | blocos separados: o resto primeiro, imagem depois |

O `textwithimage` **não tem** opção de imagem em cima — a policy
(`1718154236394`) só oferece Left, Wrap, VCenter e VBottom. Forçar `top` nele é
garantir texto espremido.

**Como detectar:** `assetPositionLargeScreen` diferente de `left`/`right` em
qualquer `imagetext` da origem.

---

## R3 — o título da página é seção própria, nunca filho de coluna

**Onde apareceu:** `/ambarella`, topo. No GWI o título ocupa a largura toda
(com o logo do fabricante à direita, desenhado pelo template), e **abaixo**
dele vêm vídeo e texto lado a lado. Na migrada, título e vídeo apareciam
empilhados na coluna da esquerda e o texto sozinho na direita.

**Causa:** o driver injetava o bloco `title_vazio` em
`sections[0].rows[0].columns[0]` — e quando a primeira linha da página já era
uma linha de COLUNAS, o título caía dentro da primeira coluna.

**Regra:** o `title_vazio` entra como **Section própria**, largura cheia, na
posição 0.

**Lembrete:** o h1 que o GWI serve é o `pageTitle`, **não** o `jcr:title`
(divergem em 112 das 354 páginas, e em 45 o `jcr:title` não existe em lugar
nenhum da origem). Por isso o bloco é um `title` **vazio**: o AEM resolve o
`pageTitle` sozinho, e não se inventa texto.

**Como detectar:** página cuja primeira seção é linha de colunas. (A condição
"que não tem h1 próprio no corpo" caiu com a R6: o título vazio entra sempre,
tenha o corpo h1 ou não.)

---

## R4 — `productlisting` é conteúdo visível, não pendência

**Onde apareceu:** `/ambarella`, rodapé. O GWI mostra dois cards com link,
"Ambarella CV72S SoC" e "Ambarella N1 SoC". A migrada não tinha nada ali.

**Causa:** `productlisting` estava marcado como "sem destino mapeado". Mas ele
é exatamente o que o `list` do destino faz — e a Anion usa `list` em 201 de
202 casos.

**Regra:** `productlisting` → `list`, com `listFrom=static` e as páginas
resolvidas **contra o GWI**, respeitando `orderBy`, `sortOrder` e `maxItems`
da origem (a `/ambarella` tem `maxItems=2`; ignorar traria a lista inteira).
Até 18/09/2026 o `orderBy` era lido e não usado — ver R11.

Nunca manter `listFrom=children`: o `parentPage` reescrito passaria a avaliar
a árvore de DESTINO, que tem outro conjunto de filhos — deriva silenciosa.

**Como detectar:** as 11 ocorrências de `productlisting` no escopo; a perda
aparece como bloco de links faltando no rodapé das landings de fabricante.

---

## R5 — `list` resolve a página no RENDER: alvo inexistente = lista vazia

**Onde apareceu:** `/ambarella`, rodapé. Depois de mapear o `productlisting`
(R4), o nó `list` estava gravado com os dois caminhos certos — e mesmo assim
**nada aparecia na tela**.

**Causa:** o componente `list` do AEM resolve cada página em tempo de
renderização. Os caminhos tinham sido reescritos para
`/content/macnicaglobal2/.../ambarella/ambarella-cv72s-soc`, que **ainda não
existe** — o global2 só tem `sony`, `deepx`, `Titles` e `sony-test` neste
ramo. Página inexistente não vira item, e o componente desenha vazio, sem
erro nenhum.

É diferente de um link dentro de um `text`: aquele é só um href e sobrevive
apontando para o futuro. O `list` não.

**Regra:** `--links-de-lista destino` (padrão) aponta os itens de `list` para
a própria árvore de rascunho, para a página ser revisável agora.
`--links-de-lista global2` grava o alvo final. **Trocar para `global2` é
passada de go-live**, depois que as páginas existirem lá.

**Como detectar:** `list` gravado com `pages` preenchido e nenhum item na
tela. Conferir se o caminho de destino existe:
`GET <caminho>.json` → 404 significa lista vazia garantida.

---

## R6 — o `pageTitle` é h1 em TODA página, mesmo com h1 no corpo

**Onde apareceu:** 44 páginas com `falta=1` na primeira varredura (i-chips,
canon, analog-devices, genesys-logic, microchip, renesas, ambarella-n1-soc…).
A unidade que faltava era sempre o título da página: "i-Chips IP00C787",
"Canon 120MXS CMOS Image Sensors", "Shop Various Types of Analog Devices
Products & Components".

**Causa:** a regra anterior só injetava o `title` vazio quando o corpo não
tinha h1 próprio, supondo que o h1 do corpo SUBSTITUÍA o cabeçalho. Não
substitui. O template do GWI desenha o `pageTitle` num `title` da própria
structure (`/root/container/container/resizablecontainer/title`, ao lado do
`pageproperties` com o logo do fabricante), antes do corpo. Na
`i-chips-ip00c787` o visitante vê dois h1: "i-Chips IP00C787" (pageTitle) e,
logo abaixo, "2K Warping/Edge-blending LSI with Built in Memory" (heading do
corpo). Na `canon-120mxs` são três.

**Regra:** `title_vazio` como seção própria na posição 0 em toda página cujo
template do GWI tem `title` na structure. Dos 5 templates do escopo, 4 têm
(`product-detail-page-content`, `manufacturer-detail-page-content`,
`macnica-gwi-product-line-detail-page-template`,
`macnica-gwi---mae-product-page`); `base-page-content` NÃO tem. Duas páginas
o usam: `test-277-gwi-base-page` (sem h1 nenhum no GWI) e a landing
`/semiconductors`, cujo h1 "Semiconductors" é um componente `title` do
próprio corpo — migra como conteúdo. Nas duas, injetar cabeçalho inventaria
conteúdo. A lista vive em `TEMPLATES_GWI_SEM_TITULO`.

**Como detectar:** `<h1 class="cmp-title__text">` no HTML da origem sem
correspondente no destino. Ou, no JCR: `cq:template` da origem cuja structure
tem `macnicagwi/components/content/title` e destino sem `title` sem
`jcr:title` na primeira seção.

---

## R7 — `download` consecutivos são UMA tabela

**Onde apareceu:** 20 páginas com download (13 com 2 ou mais: design-gateway
e `altera-max-10/multi-rail`). Cada `download` virava uma tabela própria,
cada uma repetindo o cabeçalho `Title`/`Download`: na `low-latency-emac` eram
4 tabelas empilhadas, 8 células de cabeçalho em vez de 2.

**Causa:** o emissor tratava bloco a bloco. No GWI os `download` vêm em
sequência, separados só por espaçadores `&nbsp;`, que o motor descarta — logo
chegam adjacentes na coluna, mas ninguém os juntava.

**Regra:** `download`/`downloadlist` adjacentes na mesma coluna fundem num
único `downloadlist` (`_fundir_downloads`, chamado onde `_fundir_textos` já
era chamado, então cobre coluna, corrida, subseção e aba). Heading ou texto
real no meio fecha a lista. Um `download` sozinho continua `download`.

**Como detectar:** duas `table` irmãs consecutivas cujo `text` começa com
`<table><thead><tr><th>Title</th><th>Download</th>`. Na tela: cabeçalho
Title/Download repetido.

---

## R8 — `relatedsuggestions` em `children` respeita `maxItems`

**Onde apareceu:** as 26 páginas de `design-gateway`, `sobra=19–38`. O GWI
mostra 3 cards em "Similar Products" (UDP25G, UDP10G, UDP100G); a migrada
listava os 26 filhos de `/design-gateway`. Era a maior fatia da sobra da
primeira varredura (~22 unidades por página, ~570 no total) — o HANDOFF
atribuía isso à tabela de download, que responde por 4 a 8 por página.

**Causa:** `bloco_de` passava `maxItems` para o `productlist` mas não para o
`related`; `resolver_related` no driver lê `b.props.get("maxItems")` e, sem
ele, materializava a lista inteira.

**Regra:** `related` carrega `maxItems`, `orderBy` e `sortOrder` da origem, e
o driver aplica os três ao materializar `children` em `static`. Em
design-gateway `orderBy=title` (= jcr:title), por isso a ordem batia; onde o
`orderBy` é `pageTitle` ela não batia — ver R11.

E o GWI **tira a própria página depois de cortar, sem repor**: a `udp25g`
(1ª por título desc, `maxItems=3`) mostra 2 cards, UDP10G e UDP100G — não 3.
Excluir antes de cortar traria o TOE25G a mais; não excluir faria a página
listar a si mesma. É o que `resolver_related` faz para `related` (não para
`productlist`, onde não há evidência de auto-exclusão).

**Como detectar:** `list` do destino com mais `pages` que o `maxItems` do
`relatedsuggestions` de origem. Na tela: "Similar Products" com mais cards
que o GWI.

---

## R9 — o corpo é a união das regiões `editable` da structure do template

**Onde apareceu:** `/analog-devices/analog-devices-lidar-development-kit`,
`sobra=3` na primeira varredura. A migrada mostrava a descrição inteira do
produto ("The AD-FMCLIDAR1-EBZ is a proven modular hardware platform…"), um
título "Analog Devices LIDAR Development Kit" em h2 e o bloco de contato. O
GWI mostra só o h1 do template, o heading "AD-FMCLIDAR1-EBZ Development
Platform" e um parágrafo.

**Causa:** em template editável do AEM, um container **travado** renderiza os
filhos da STRUCTURE; da página só entra o que estiver sob um nó
`editable=true`. Em `product-detail-page-content`, `root/container/container`
é travado e os editáveis são `heading`, `text`, `container` e
`resizablecontainer/pageproperties`. A LIDAR tem `title`, `imagetext` e
`experiencefragment` como irmãos diretos desse container — sobras de um
initial antigo — e o GWI nunca os desenha. O motor lia o JCR e os migrava.

É a mesma família da R1 (o JCR da origem não é a página da origem), com outro
mecanismo: lá, flags do componente; aqui, a structure do template.

**Regra:** `podar_nos_mortos` remove, de uma cópia do jcr:content, todo nó
que não está sob região editável nem é ancestral de uma (container travado
por onde se desce). Nó descartado COM conteúdo vira pendência
`fora_da_structure` — nada sai em silêncio. As regiões por template estão em
`REGIOES_EDITAVEIS` (5 templates do escopo, lidas da structure em
18/09/2026); template desconhecido não é podado.

**Censo:** 1 página em 136 tem nó morto com conteúdo (a LIDAR, 3 nós). Outras
3 têm nós mortos vazios. Está confinado, mas a regra fica no motor porque o
próximo template pode não estar.

**Como detectar:** `ferramentas/censo_nos_mortos.py` lista, por página, os
nós fora das regiões editáveis do seu template. Na tela: texto presente no
destino que não existe no HTML da origem — aparece como `sobra` no
comparador, com texto que só existe nesta página.

**Corolário para o `title` do GWI:** o único `title` de corpo VIVO no escopo
é o "Semiconductors" da landing, e ele renderiza **h1** sem ter `type` (o
HTL do componente é `<h1 data-sly-element="${title.type}">`, e a policy
"Macnica Title" é h1). O motor assumia h2; agora assume h1. O `heading` sem
`type` continua h2 — o HTL dele é `<h2 …>`.

## R10 — índice de âncoras: o GWI grava `label`/`id`, e `static` vazio é vazio

**Onde apareceu:** `/ambarella/ambarella-n1-soc` (e as duas cópias de teste),
`falta=4`. O GWI mostra um índice com 6 rótulos autorais ("Features",
"N1-655 GenAI", "Flagship Platform", "Why Edge AI?", "Target Applications",
"Macnica Americas Support"). A migrada mostrava UM item, "The N1 Family
At-a-Glance", que não está no índice do GWI.

**Causa:** dois erros encadeados em `bloco_de`/`_resolver_anchorlinks`. (1) Os
itens de `fixedListItems` eram lidos como `text`/`linkId` — os nomes do
componente do DESTINO. O diálogo do GWI grava `./label` e `./id` (60 de 60
itens do corpus). A lista saía vazia em todo modo `static`. (2) Com a lista
vazia e `useHeadings` ausente (default `true`), o motor caía no fallback
"headings com id da própria página" e inventava o índice.

**Regra:** ler `label`/`id` (com `text`/`linkId` como reserva). Em
`listingMode=static`, itens vazios ficam vazios e viram pendência
`anchorlink_sem_itens` — nunca fallback. O fallback por headings é só do
modo `automatic`.

**E o inverso também:** `fixedListItems` só vale em `static`. A primeira
versão desta regra lia os fixos em qualquer modo, e a página de teste
`TEST-AUTOGENERATE-LIST-…` (modo `automatic`, com 6 fixos RESIDUAIS copiados
da `n1-soc`) ganhou "Features"/"N1-655 GenAI" num índice em que o GWI mostra
os 6 headings da própria página (`#1`…`#6`). A varredura final pegou
(`sobra=2`). É o mesmo padrão do `pages` na R11: propriedade residual de um
modo que o componente ignora no outro. Única página do escopo com a
combinação; corrigido no código, entra no servidor com o próximo lote.

**Artefato de origem aceito:** na `/ambarella` (modo `automatic`), o GWI lista
9 âncoras: as 3 da própria página e 6 headings com `id` numérico da
página-filha de teste `TEST-AUTOGENERATE-LIST-ambarella-n1-soc-html`
(`#1..#6`, que na landing apontam para o lugar errado ou para nada). É
comportamento do modelo Java do GWI varrendo abaixo do `parentPage`; não é
reproduzido — o destino lista as 3 âncoras reais. Ficam 6 unidades de `falta`
na `/ambarella` com esta explicação.

**Como detectar:** `pagesectionlisting` com `fixedListItems` na origem e
`anchorlink` do destino com número de itens diferente. Os 14 nós do escopo:
11 `static`, 3 `automatic` (`/renesas`, `/ambarella`, a página de teste).

---

## R11 — `pages` só vale em `listFrom=static`; em `children` manda o `orderBy`

**Onde apareceu:** `/canon`, `falta=7`. O GWI mostra 13 cards (os 13 filhos);
a migrada mostrava 4. E `/altera/altera-stratix-10` e
`/altera/development-kits`, que passavam com `faltando=0 sobrando=0` e tinham
os cards **fora de ordem** (NX antes de AX; M-Series antes de 065B) — o ponto
cego clássico: ordem não é conteúdo.

**Causa:** (1) o `productlisting` da `/canon` está em `listFrom=children` mas
carrega um `pages` residual com 6 caminhos (2 já são 404 no próprio GWI). O
GWI ignora `pages` nesse modo; `resolver_related` devolvia `pages` antes de
olhar o modo, gravava os 6, e só 4 existiam (R5). (2) O driver calculava a
`chave` do `orderBy` e ordenava sempre por `jcr:title`. O `productlisting`
ordena por `pageTitle`; o `relatedsuggestions` por `title` (= jcr:title).
Conferido nas 10 listagens `children` do escopo: a ordem do GWI é
`sort(pageTitle.lower())` para `productlisting`.

**Regra:** `pages` só é usado quando `listFrom=static`. Em `children`, a
lista é sempre resolvida contra o `parentPage` do GWI, ordenada pela chave
que o `orderBy` nomeia (`pageTitle` → pageTitle; `title`/vazio → jcr:title),
cortada em `maxItems` e, para `related`, sem a própria página (R8).

**Como detectar:** `productlisting`/`relatedsuggestions` com
`listFrom=children` E `pages` preenchido na origem (só a `/canon` no escopo;
6 na sony, fora dele). Para a ordem: comparar a sequência dos
`cmp-teaser__title` do GWI com a dos `cmp-list__anchor` do destino — o
comparador de conteúdo não vê isso.

---

## R12 — `list` do destino imprime navTitle; o teaser do GWI imprimia pageTitle

**Onde apareceu:** as 6 páginas `/sitime/*` ("SiTime Oscillators (XO, TCXO,
OCXO, 32 kHz)" faltando; "SiTime Oscillators" sobrando) e `/altera/agilex`
("Altera Agilex 5 FPGA & SoC | AI Tensor Block | Macnica Americas" ×
"Altera Agilex 5 FPGA and SoC Overview").

**Causa:** o `relatedsuggestions`/`productlisting` do GWI desenha cards com o
teaser do core (título = pageTitle → jcr:title, mais a descrição). O `list`
do global2 (core list v2) imprime `${item.title}` = navTitle → pageTitle →
jcr:title, e não tem opção de diálogo, policy ou design que troque a fonte.
Diverge exatamente quando `navTitle ≠ pageTitle` na página-alvo — 198 páginas
do GWI têm essa divergência; no escopo aparecem 2 casos, mas vai reaparecer em
massa quando as listas apontarem para `/sony-image-sensors/*` (nav "IMXnnn"
× pageTitle "Sony IMXnnn …").

**Regra (limitação aceita):** não mexer no `navTitle` do destino (alimenta
breadcrumb e navegação, e o GWI é a fonte da verdade); não trocar `list` por
`cardlist`/teaser (fora do dialeto da Anion: `list` em 201 de 202). O
comparador casa esses itens pelo ALVO do link e conta na coluna
`titulo_lista`, para a divergência ficar visível sem virar "faltando".

**O que se perde de verdade:** a **descrição** do card (`cmp-teaser__description`)
não existe no `list`. O comparador não vê `div`, então isso só aparece no
print. Decisão do time se quiser recuperar (exigiria `cardlist`).

**Como detectar:** para cada `list` gravado, `GET <alvo>/jcr:content.json` e
sinalizar `navTitle` não vazio e diferente de `pageTitle`.

---

## R13 — o que a conferência visual de 12 páginas achou (18/09/2026)

Doze pares GWI × destino, print de página inteira com `--publicado`, um
revisor por página e um cético por página com defeito. Dez defeitos
confirmados que NENHUMA conferência de conteúdo acusava. Seis viraram regra
no motor; quatro ficam abertos (seção seguinte).

> **ESTADO: gravado no lote 3 (18/09/2026)**, junto com a retirada da margem
> (R14). As seis regras foram conferidas offline contra o JCR das 136 páginas
> (64 mudam; nenhum texto some). `/altera` e `/ambarella`, que já tinham sido
> vistas na tela, mudaram de ritmo vertical e merecem print novo. O patch está
> em `patch3-disposicao.diff` e no commit `0760e39`.

### 13a — `imagetext` filho direto do corpo não passava pelo ramo do `imagetext`

**Onde:** `agilex-7-i-series`, bloco "Features" (lista | foto lado a lado no
GWI; foto EM CIMA da lista no destino). `/canon`, "Evaluation Kit" (idem).
**Causa:** `imagetext` está em `WRAPPER_TYPES`. Filho direto do corpo, caía em
"invólucro → `extrair_linhas`", que itera os FILHOS — e o único código que lê
`assetPositionLargeScreen` e `isText`/`isButton`/`isHeading` só roda quando
`_coletar_blocos` recebe o PRÓPRIO nó. A R1 e a R2 ficavam sem efeito para
todo `imagetext` de topo: 19 nós em 8 páginas.
**Regra:** `extrair_linhas` delega ao `_coletar_blocos` quando o nó é
`imagetext` (e `_is_linha` não se aplica a ele).
**Detectar:** seção do destino com `image` + `text` irmãos cuja origem é um
`imagetext` com `assetPositionLargeScreen=left|right`.

### 13b — link de download com espaço no nome do arquivo virava texto morto

**Onde:** `altera-soc-courses` ("WP-14033 - Altera SoC Design Advantages
.pdf") e `altera-stratix-10-gx-soc-fpga`. Na tela, "Download" em cor de texto,
sem link. O JCR TEM o `<a>`.
**Causa:** o HTML rico do `table` passa pelo filtro XSS do AEM, que descarta o
`<a>` inteiro quando o `href` tem espaço cru.
**Regra:** `href` sempre `quote(ref, safe="/")` em `_emitir_tabela_download`.
**Detectar:** `fileReference` com qualquer caractere fora de
`[A-Za-z0-9/_.-]`; conferir no HTML RENDERIZADO (não no JCR) se o `<a>` existe.

### 13c — `hr` colado no bloco de cima

**Onde:** as 6 `/sitime/*`, `/renesas`, `/infineon`… 36 `hr` em 15 páginas,
mais 11 embutidos no fim de um `text` em 7 páginas.
**Causa:** o `hr` ficava como ÚLTIMO bloco do grupo anterior (gap 0 entre
irmãos) e lia como sublinhado do último bullet. Quando vinha embutido
(`…</p><p>&nbsp;</p><hr><p>&nbsp;</p>`), `strip_empty_blocks` apagava os
`&nbsp;` que davam o respiro.
**Regra:** `hr` abre E fecha subseção — fica sozinho no seu container. `<hr>`
no começo/fim de um `text` com conteúdo é destacado como bloco (`_destacar_hr`).
**Detectar:** `text` do destino cujo HTML é `<hr />` e que não é filho único
do seu container.

### 13d — título órfão do bloco que ele introduz

**Onde:** `agilex-7-i-series`: "Features" a 170px do conteúdo e a 90px do
bloco de cima; "Specifications" idem.
**Causa:** em página MISTA/PLANA o heading é folha solta, e o bloco que ele
introduz (table, carousel, imagetext, invólucro) abre seção própria. O título
ficava na seção anterior, e entre os dois somavam-se três paddings.
**Regra:** o título imediatamente anterior acompanha o bloco/invólucro para a
seção nova (mesmo com espaçador no meio). Exceto `tabs`, `related` e `xf`,
cuja seção tem papel próprio que depende de o bloco estar sozinho.
**Detectar:** seção cujo último grupo é só um `title`.

### 13e — três botões lado a lado estouram a coluna

**Onde:** `/renesas`, rodapé: o 3º botão passa 187px da margem e vira rolagem
horizontal entre 1050 e 1337px de janela.
**Causa:** o menor `min-width` de botão da policy é 345px; 3×345 + 2×26 =
1087px numa coluna útil de 900px.
**Regra:** linha de colunas que são SÓ botão quebra quando não cabe na
LARGURA ÚTIL da seção: `cabem = (útil + 26) // (345 + 26)`, em linhas
equilibradas (4 → 2+2). Com margem (fitcontainer 1000 − 2×50 = 900px) cabem 2.
**Sem margem** (diretriz de 18/09/2026: a largura útil passa a ser a da
janela; referência 1366px) cabem 3 — a `/renesas` volta a ter os 3 lado a
lado, como o GWI, e a regra só age de 4 botões para cima (nenhum no escopo).
Medido no navegador com a margem removida: a 1400 e 1920px os 3 cabem; só
estouram na faixa de 1050 a ~1187px de janela (37px a 1100px), porque o flex
só empilha abaixo de 1050px.
**Detectar:** `flexcontainer` cujos itens são só `button` e
`n×345 + (n−1)×26` maior que a largura útil da seção.

### 13f — heading centralizado no GWI saía à esquerda

**Onde:** "Canon CMOS Sensors" e mais 13 headings em 10 páginas.
**Causa:** `alignment` do `heading` nunca era lido; `S_TITLE_CENTER` estava
definido e sem uso.
**Regra:** `alignment=center` → style Center do `title`. (Centralizar TODO
título que abre seção, como a Anion faz, é decisão de dialeto que continua
aberta — aqui só se reproduz o que o GWI já centraliza.)

### Não é nosso: o bloco de contato empilhado com vãos de 140–200px

Apontado em 8 das 12 páginas. Os dois botões do XF `products-contact-block`
ficam lado a lado no GWI e empilhados no destino, com ~600px de altura. A
causa está no XF da copia-teste (`root/containerpy/button_N_wrap`, containers
sem style, cada um com `padding: 50px 25px`) — o mesmo XF do documento
aninhado. Corrigir lá acerta ~106 páginas de uma vez.

---

## R14 — páginas SEM MARGEM: a largura útil é a da janela

**Diretriz (18/09/2026):** não colocar margem nas páginas. As da Anion (sony,
deepx) vão mudar igual depois — não são nossas e não são tocadas.

**O que era a margem:** o style `fitcontainer` (max-width 1000px,
centralizado) mais o padding lateral "large" (50px) em toda seção, no painel
de cada aba e na camada interna das faixas coloridas — 900px úteis.

**Regra:** `COM_MARGEM = False`. Seção sem `fitcontainer`, com o padding
padrão do container (25px no desktop, 15px abaixo de 1050px). Painel de aba e
camada interna da faixa não somam padding lateral.

**O que muda na conferência:** a migrada fica mais larga que o GWI (que tem
~976px de coluna), e isso é esperado. O que tem de bater é a DISPOSIÇÃO — o
que está ao lado, em cima e embaixo de quê, a ordem, e os vãos verticais
entre título e texto. Largura diferente não é defeito.

**Consequências medidas** (margem removida por CSS no navegador, antes de
gravar): parágrafo chega a 1820px numa janela de 1920; vídeo
`layout=responsive` sozinho numa seção chega a 1820×1024; imagem NÃO estica
além do tamanho natural; 3 botões lado a lado cabem de ~1140px de janela
para cima (13e virou função da largura útil).

**Como detectar regressão:** `cq:styleIds` com `1717410661180`
(fitcontainer) ou `1717498053499` (LR large) em qualquer container de
`semiconductors-remigration`.

---

## R15 — `<p>` que o GWI desenha colado no bloco de cima ganha `margin-top:0`

**Onde apareceu:** `/ambarella`. (1) Card "CV72S": vão grande entre o título e
o texto — o exemplo que o Hazael mostrou. (2) Os 7 blocos de "Why Choose
Ambarella Products?" ("Image Quality" etc.): o mesmo vão entre o `h3` e o
parágrafo. (3) O FAQ do topo: no GWI pergunta e resposta andam coladas e há
uma linha em branco entre os pares; no destino TODAS as linhas ficavam
equidistantes e o agrupamento pergunta→resposta sumia. Era o "Aberto D".

**Causa:** uma só. No GWI `p{margin:unset}`: dentro de um rich text o vão
entre dois blocos é 0, e a linha em branco é um `<p>&nbsp;</p>` que o autor
digita. No destino `.cmp-text p`, `.cmp-table p` e `.cmp-textwithimage
.paragraph p` têm `margin-top:30px` (menos o `:first-child`), o `h3` tem
`padding-bottom:20px`, e o `<p>&nbsp;</p>` é apagado por
`strip_empty_blocks`. Medido (1400px, `?wcmmode=disabled`):

```
                         GWI    destino antes   destino depois
h3 "CV72S" -> <p>         0         50              20
h3 "Image Quality" -> <p> 0         50              20
<p><b>pergunta</b> -> <p> 0         30               0
```

**Regra:** `colar_paragrafos` — `<p>` com texto cujo vizinho IMEDIATO de cima
(só espaço em branco entre os dois) é um `<p>`/`<h1-6>` com conteúdo recebe
`style="margin-top:0"`. Depois de um espaçador fica como está: os 30px do
destino fazem o papel da linha em branco (28px) do GWI. Roda sobre o HTML cru
de cada `text`/`table` da origem, ANTES de `strip_empty_blocks` (que apaga a
evidência) e antes de `_fundir_textos` — a emenda entre dois `text` nunca é
colada, porque o espaçador entre eles pode ter sido um nó à parte, já
descartado. Estilo inline sobrevive ao filtro XSS do AEM (conferido na tela).

**Alcance:** 146 `<p>` em 24 páginas — 62 depois de heading, 57 depois de
`<p>`, 27 dentro de célula de tabela (`altera-soc-courses`, `arria-10`,
`agilex-7`…).

**Como detectar:** `ferramentas/vao.py <caminho> "Texto do título"` dos dois
lados — campo `vao`. No JCR: rich text com `</h3>\s*<p>` ou `</p>\s*<p>` sem
`<p>&nbsp;</p>` no meio e sem `margin-top:0` no destino.

---

## R16 — tabela de LAYOUT (ícone centrado) perde a moldura, e continua `table`

**Onde apareceu:** `/analog-devices` e `/analog-devices/macnica-and-adi`, os
três cards "Streamlined Inventory Management" / "Flexible Financing" /
"Quality Assurance". Era o "Aberto A"; o Hazael apontou de novo na revisão
manual ("ugly table borders around the icons"). Sem a margem o ícone deixou
de ter 3px, mas a grade continuava: seis células vazias com borda roxa em
volta do ícone e a legenda numa caixa, em roxo.

**Causa:** o GWI usa `<table border="0">` de 7 células só para centrar o
ícone, mais uma linha `colspan=7` com a legenda. No destino
`.cmp-table td{border:2px solid #7f1080;color:#7f1080}` desenha tudo.

**Regra:** tabela com `border="0"`, com `<img>` e sem `<th>` é `de_layout`:
sai com os styles da policy **Black** (texto #4d4d4d), **No Background**,
**No Rounded Corner** e **No Frame** (`border:none`).

**Por que NÃO virou `image` + `text`** (a primeira versão desta regra): os
ícones são PNGs de **1042×1042** — é a célula da tabela que os segura em
~100px. Como `image` sairiam com ~430px, a largura da coluna. E exigiria
copiar os 3 arquivos para `/content/dam/copia-teste`, fora da árvore. Medir o
asset antes de trocar de componente.

**Alcance:** 6 tabelas em 2 páginas. As 3 tabelas `border="0"` SEM imagem da
`agilex-5` são tabelas de dados (zebradas no GWI) e ficam com moldura. As
outras 3 tabelas com `<img>` têm `border="1"` no GWI: grade de verdade.

**Como detectar:** `table` do destino cujo HTML tem `border="0"` e `<img`, sem
o styleId `1722858697098`.

---

## R17 — href para página do escopo leva o nome NORMALIZADO

**Onde apareceu:** o print do destino de
`/canon/canon-li8030SA-410mp-…` saiu com "Loading…" e 1000px de altura. Não
era a página: era o 404. O driver normaliza o nome do nó (`li8030SA` →
`li8030sa`) e `prints.sh` usava o nome do GWI.

**O defeito de verdade por trás:** 5 páginas do escopo mudam de nome no
destino (`sulfur-som---carrier-board`, `toe200G-…`, `canon-li8030SA-…` e as
duas `TEST-…`). A `list` já grava o nome novo. O `href` dentro de rich text só
troca o prefixo (`rewrite_links_in_html`) e continuava com o nome antigo —
404 no go-live. Dois links reais: o card e a linha da tabela da `/canon`, e o
item da `/design-gateway`.

**Regra:** `normalizar_links_do_escopo` no driver (e no `diff_payload.py`,
para o dry-run continuar real): todo caminho sob a raiz de destino dos links
que esteja NO ESCOPO tem cada segmento passado por `normalize_name`.
sony/deepx ficam como estão — os nomes lá são os que a Anion deu.

**Como detectar:** na origem, href interno cujo caminho muda sob
`normalize_name`. Na tela: print de 1000px de altura com "Loading…" = 404.

---

## R18–R24 — conferência visual por arquétipo (18/09/2026, 3ª sessão)

Quatorze páginas, uma por arquétipo/família, um revisor por página com print
GWI | destino lado a lado (`ferramentas/lado.py`), medição e JCR dos dois
lados. Todas já SEM margem. Gravado no lote 4 (72 páginas, 72 sem falha) e
no lote 5 (as 3 `/analog-devices*`: R16 e R25).

### R18 — a última linha da grade e o card órfão mantêm a largura da coluna

**Onde:** `/ambarella`, H32AQ/A12AQ: última linha com 2 cards numa grade de 3
— no GWI sob as duas primeiras colunas, no destino 50% cada. `/canon`,
LI8030SA/LI7030SA/LI5030SA: card sozinho (`width=5`) virava faixa de 1350px,
a foto centrada na PÁGINA e o título na borda esquerda. Era o "Aberto C".
**Causa:** `flexcontaineritem` é `flex:1`; e "coluna sozinha não é coluna"
descartava a largura.
**Regra:** `_completar_grades` — linha IMEDIATAMENTE abaixo de uma linha de
colunas uniformes da mesma largura, com menos colunas, ganha
`flexcontaineritem` VAZIOS até igualar. Vale entre seções consecutivas (cada
linha da grade da `/ambarella` é um `resizablecontainer` de topo) e para o
invólucro cujo único filho é uma coluna.
**Detectar:** `flexcontainer` com menos itens que o `flexcontainer` irmão de
cima; `image`+`text` soltos num container logo abaixo de uma grade.

### R19 — a grade de 12 do AEM QUEBRA a linha

**Onde:** `/i-chips/i-chips-scaler-lsi` (6 cards `width=4`: GWI 3+3, destino
6 numa linha, 40% menores numa página mais larga); `/toppan` (4×`width=6`:
2×2 → 1×4); `macnica-and-adi` "Who We Serve" (`width=3` com `offset` 0,1,1:
3×2 → 1×6, textos de 175px); 6 `design-gateway/*nvme*`, `/i-chips`.
**Causa:** `_linha_de` punha todos os filhos numa Row; ninguém somava larguras.
**Regra:** `_quebrar_por_largura` — fecha a Row quando `offset + width`
acumulado passa de 12. O `offset` passou a ser lido (`offset_of`).
**Detectar:** soma de `width`+`offset` dos filhos de um invólucro > 12.

### R20 — título logo depois de título é subtítulo

**Onde:** `ambarella-n1-soc` (h2 "Leading the Family…" + h3, 3×), aba 4 da
`/altera`, `/altera/agilex`, a landing (dois h1). GWI 16px, destino 60px — o
h2 boiava a meio caminho do bloco de cima.
**Regra:** em `_quebrar_em_subsecoes`, `title` não abre subseção quando o
grupo atual só tem `title`.

### R21 — `imagetext` left/right COM heading é `textwithimage`

**Onde:** `canon-li8030sa` (3 blocos), `altera-arria-10` (3),
`altera-holoscan`, `agilextm-5-…-premium`. No GWI título+parágrafo à esquerda
e foto de 415×277 à direita; no destino título, FOTO de 1280×967 e texto
empilhados — num deles a foto ENTRE o título e o texto. Respondia por 52%
dos +2.849px de altura da página.
**Causa:** o ramo do `imagetext` só emitia `textwithimage` quando os filhos
eram só imagem+texto; o `heading` (isHeading=true) virava `title`, a condição
falhava e caía em `return filhos`.
**Regra:** o título entra no rich text do `textwithimage`, como `<hN>` em
cima do parágrafo (com o `id`, se tiver), e o `<p>` seguinte é colado (R15).
**Detectar:** `imagetext` com `assetPositionLargeScreen=left|right`, filho
`heading` com texto e `isHeading≠false`.

### R22 — `id` de âncora em `text` ESPAÇADOR passa para o título seguinte

**Onde:** as 3 `/sitime/*` com índice. Os 4–5 botões do índice existem e não
rolam a página. **Nenhum print mostra isso** — o revisor clicou.
**Causa:** o alvo não é o heading: é o `text` vazio antes dele,
`{id:"xos", text:"<p>&nbsp;</p>"}` ou `{id:"tcxos", text:"…<hr>…"}`. O motor
descarta o espaçador e emite o `hr` sem `id`.
**Regra:** `_ids_de_espacador_para_titulo` (pré-passo numa cópia do JCR): o
`id` de um `text` sem texto visível vai para o próximo irmão renderizável, se
for heading/title sem `id` — ou o primeiro renderizável dele, quando o irmão
é um invólucro (`#whysitimebuffers`). Os 14 links das 3 páginas voltam.
Censo: todo `anchorlink` do escopo tem alvo, menos as duas páginas de teste
`test-277-*` (`label1..3`, sem alvo também no GWI).
**Detectar:** `href="#x"` do `anchorlink` sem `id="x"` no HTML renderizado.

### R23 — o título acompanha a linha de COLUNAS que ele introduz

**Onde:** `/altera` "Leading Altera FPGAs…" (59px contra 25), `macnica-and-adi`
"Why Engage…" (79 contra 31), h3 de "Focus Markets" da `agilex-5`
(equidistantes do bloco de cima e das colunas), `/canon`.
**Causa:** a 13d cobria tabela/carousel/invólucro; para linha de colunas o
título ficava num sub-container e o `flexcontainer` no seguinte (30+30).
**Regra:** `_titulo_com_colunas` — Row só de títulos seguida de Row de colunas
vira `cabecalho` dela: mesmo container, título em cima do `flexcontainer`.

### R24 — respiro texto↔mídia só onde o GWI tinha o espaçador (era o "Aberto B")

**Onde:** "Why Macnica?" das 26 `design-gateway` (último bullet → imagem: GWI
44px, destino 0), `/toppan` ×2, aba 4 da `/altera`, `/namuga` (em cima E
embaixo da imagem), `ambarella-n1-soc` (texto → índice de âncoras).
**Causa:** o respiro era `<p>&nbsp;</p>` no FIM do texto (ou no começo do
texto que vem depois da imagem); `strip_empty_blocks` apaga; gap entre irmãos
é 0.
**Regra:** o `text` guarda `respiro_antes`/`respiro_depois` lidos do HTML
cru; na transição texto→(image|embed|carousel|anchorlink) com
`respiro_depois`, ou mídia→texto com `respiro_antes`, abre subseção (60px).
Sem o espaçador na origem o GWI também cola — e continua colado.
**Limite:** dentro de coluna (`flexcontaineritem`) não há subseção; o caso
"título colado no texto de cima dentro da coluna" da `/toppan` fica.

---

### R25 — dois filhos de imagem com o mesmo arquivo num `imagetext` são UMA imagem

**Onde:** `/analog-devices/analog-devices-multimodal-sensor-front-ends`
(revisão manual do Hazael): a foto do ADPD4100 aparecia DUAS vezes, e o texto
em cima e embaixo dela em vez de à esquerda.
**Causa:** o `imagetext` guarda `resizableimage` E um `image` residual, os
dois com o mesmo `fileReference`. O GWI desenha um asset só. O motor emitia
os dois e, com `len(img)==2`, desistia do `textwithimage` (caía em
`return filhos`, empilhado). Único nó assim no escopo.
**Regra:** dentro de um `imagetext`, `image` com `fileReference` repetido é
descartado antes de decidir a disposição. E `textwithimage` passou a contar
como mídia na R24 (o texto de baixo começa com `<p>&nbsp;</p>`).
**Detectar:** `imagetext` com 2+ filhos com `fileReference`.

---

## Aberto (achado na conferência visual, NÃO corrigido)

| # | padrão | onde / quanto | causa | proposta |
|---|---|---|---|---|
| F | **vídeo sozinho vira 1350×759** (MÉDIA) | `i-chips-scaler-lsi` ×2 (GWI 569×390, `width=7 offset=3`), `/altera/agilex` (651×390, `width=8 offset=2`) | "coluna sozinha não é coluna" + `layout=responsive` sem teto; a origem é `layout=fixed` | coluna única `width<12` com `embed` → `flexcontainer` com item vazio (≈50%); ou `layout=fixed` só para embed fora de coluna. Testar numa página antes |
| G | **somatório de paddings entre seções** (MÉDIA, sistêmico) | `/renesas` (fronteira de seção no MEIO da série de 5 `textwithimage`: 179px contra ~99), `/altera/agilex` (texto→tabela 130 contra 16; tabela→botão 170 contra 13: o botão agrupa com a série SEGUINTE), `/canon` (linhas da grade a 110/80/60), título da página→1º bloco 90 contra 17–49, barra de abas→painel 103 contra 25 | seção 50 + sub-container 30 + margin do componente (`.cmp-table` 20, `.cmp-textwithimage` 30, `.link-button` 40); `_marcar_papeis` alterna small/default por ÍNDICE; em página PLANA `table` é MAJOR e ganha seção própria | seção que continua uma série homogênea (mesmos kinds) herda `pad_tb=small`/none; botão logo depois de tabela fica na seção dela. Em `_secoes`, `so_pageproperties(ch)` vem ANTES do ramo do spacer e o torna código morto |
| H | **título longe das abas** | `/namuga` 152px contra 80 | a 13d exclui `tabs` de propósito (seção com faixa cinza) | título dentro da seção das abas, acima do `tabs` |
| I | **botão sempre centralizado** | `/altera` ×2 | `S_BTN_CENTER` fixo; o GWI tem `width=3 offset=0` (à esquerda) | decisão de dialeto |
| J | imagem do `textwithimage` no tamanho natural | `/renesas` "Reality AI" 401×226 contra 200×113 | `width`/`height` do `resizableimage` não é levado | sem campo alvo no `textwithimage`; redimensionar o asset ou aceitar |
| K | título órfão do formulário + 3 botões `#contact-form` | `macnica-and-adi` | `form/container` não migra (sem backend); o título que o introduz e os links ficam | decisão do time: tirar o título / apontar para a página de contato |
| E | cabeçalho de tabela quebrando palavra | — | — | **FECHADO sem mexer:** sem a margem a quebra sumiu (`/canon` conferida) |
| — | CSS do site: `td` alinha no topo (GWI no meio); índice de âncoras quebra 3+1; fio sob os h3 do GWI não existe | várias | clientlib do global2 | fora do motor |

Fechados nesta sessão: A (R16 — sem moldura, continua `table`), B (R24),
C (R18), D (R15), E (sumiu sem a margem).

### `supplierlist` da landing — o que o GWI realmente mostra

O nó só tem configuração (`listFrom=children`, `orderBy=productManufacturerRanking`,
`maxItems=20`). Cada item vem do `jcr:content` da página-FILHA: nome =
`navTitle`, logo = nó `manufacturerlogo`, blurb = `jcr:description`. Na tela é
uma grade 4×4 de cards (logo 120px + nome), o card inteiro é link. **O blurb é
`display:none` e só aparece no hover** — as "16 unidades faltando" são
hover-only. As filhas do destino não têm `productManufacturerRanking`, e
sony/deepx não estão na árvore: um `list` em `children` erraria a ordem, traria
as 2 helio-view e perderia 2 fabricantes. Alvo que reproduz a tela: grade
estática de 16 imagens-com-link + `navTitle`, 4 por linha, na ordem do ranking.


## Achado fora do nosso escopo de escrita: os dois XFs da copia-teste aninham um documento inteiro

Os fragmentos `/content/experience-fragments/copia-teste/americas/mai/en/site/
products-contact-block/master` e `signup-and-contact-experience-fragment/
master` têm `jcr:content/sling:resourceType = macnicaglobal2/components/page`
em vez de `macnicaglobal2/components/xfpage`. O componente `experiencefragment`
do global2 inclui o fragmento com o seletor `content`, que só existe no
`xfpage`; no `page` o Sling cai no `page.html` e devolve `<!DOCTYPE html>…
</html>` INTEIRO dentro da página. Resultado: 110 das 135 páginas remigradas
(106 com o contact-block, 4 com o signup) carregam um segundo `<html>`,
`<head>` e `<body>` aninhados — visível no HTML servido (`</body> </html>
</div>` logo antes do "Similar Products"). O texto está certo, então o
comparador não acusa nada.

A correção é no XF (`sling:resourceType` do `master/jcr:content`), fora de
`semiconductors-remigration` — **não foi tocada**, pela regra 2. Fica para o
time. Como conferir: `GET <xf>/master.content.html` deve começar com
`<div class="cmp-container">`, nunca com `<!DOCTYPE`.

## O comparador também tinha pontos cegos (fechados em 18/09/2026)

Nenhum destes é defeito de migração; eram erros de MEDIÇÃO que inflavam
`falta`/`sobra` e escondiam os defeitos reais no meio do ruído:

| sintoma | causa | correção em `aem_fidelidade_render.py` |
|---|---|---|
| `falta=2` "Previous"/"Next" em 26 páginas | botões do carousel de 1 slide do GWI, que o destino colapsa em `textwithimage` | `[class*="carousel__action"]` excluído |
| rótulo do download "sobrando" | o título do `download` do GWI é `<a class="cmp-download__property--filename">`, fora do seletor | seletor inclui esse `a` |
| "…opens in a new tab" sobrando | span oculto que o destino injeta em todo `target=_blank` | removido em `norm()` |
| `th` Title/Download e `td` Download sobrando | células que o formato tabela inventa | filtradas SÓ por tag+texto exato |
| "Features" em dobro (falta=1) | botão mobile do índice de âncoras, criado por JS e oculto acima de 1025px | `.cmp-pagesectionlisting__button` excluído |
| "Have a question for the Macnica Team?" / "Get in touch" faltando | coluna do XF com `cq:responsive/default/behavior=hide` — o visitante não vê | `.aem-GridColumn--default--hide` excluído (por classe, não por display:none) |
| título de item de lista faltando + versão curta sobrando | pageTitle no teaser do GWI × navTitle no `list` do destino (R12) | casados pelo alvo do link; coluna `titulo_lista` |

Regra geral: quando `falta`/`sobra` se repete com o MESMO texto em dezenas de
páginas, desconfiar da medição antes do motor. Uma página conferida à mão
(HTML da origem × HTML do destino) resolve em minutos.

## Ainda em aberto

- **`supplierlist`** — a landing `/semiconductors` mostra 16 blurbs de
  fabricante que não têm componente alvo mapeado. São as 16 unidades que
  faltam naquela página.
- **`relatedsuggestions` modo `search` (9 pendências)** — a policy do `list`
  tem `disableSearch='true'`; as consultas apontam para `sony-image-sensors`,
  fora do escopo. Resolver exige renderizar a página do GWI e ler os cards.
- **`form/container`** na `macnica-and-adi` (5 unidades: "Send message",
  "Success"…) — precisa de backend; sem alvo.
- **Descrição dos cards de lista** (R12) — perdida por construção no `list`;
  decisão do time.
- **XFs da copia-teste com `page` em vez de `xfpage`** — fora do nosso escopo
  de escrita; ver acima.

Fechados nesta rodada: `pagesectionlisting` → `anchorlink` (R10), título da
página (R6), downloads (R7), `maxItems` e auto-exclusão (R8), nós fora da
structure (R9), `pages` residual e `orderBy` (R11).

---

## Como conferir uma página nova

```bash
# 1. o conteúdo chegou inteiro? (texto renderizado, não JCR)
python3 aem_fidelidade_render.py --origem <gwi> --destino <dest>

# 2. e a DISPOSIÇÃO? isto o passo 1 não vê — precisa de olho humano
python3 aem_screenshot.py <gwi>  -o antes.png --full --publicado
python3 aem_screenshot.py <dest> -o depois.png --full --publicado
```

O passo 1 dá `faltando=0 sobrando=0` em todos os quatro defeitos acima. Texto
no lugar errado continua sendo texto presente. **Disposição só se confere
olhando.**
