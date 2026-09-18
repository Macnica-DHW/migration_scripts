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
no lote 5 (as 3 `/analog-devices*`: R16 e R25) e no lote 6 (20 páginas: R26).

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

### R26 — vídeo sozinho ocupa metade da linha, não a página

**Onde:** `i-chips-scaler-lsi` ×2 (GWI 569×390, `width=7 offset=3`),
`/altera/agilex` (651×390, `width=8 offset=2`) — e, no censo, **20 páginas**
(todas as folhas `/i-chips/*/i-chips-ip00c*`, `/infineon`, 2 da `/canon`).
No destino: 1350×759 numa janela de 1400, três quartos da tela, dois buracos
brancos de uma tela cada no print. Era o "Aberto F".
**Causa:** "coluna sozinha não é coluna" + `layout=responsive` sem teto.
**Regra:** `embed` cujo nó de origem tem `width ≤ 8` e que NÃO está dentro de
um `flexcontaineritem` é emitido dentro de um `flexcontainer` de dois itens,
o segundo vazio: 662×372. Fica à ESQUERDA (o GWI centra com `offset`; item
`flex:1` não centra sem encolher para 1/3).
**Conferido na tela** (`measure.py`): `cmp-embed` colw=662 h=372. O item
vazio segura a largura — o que também valida a R18 (`/ambarella` H32AQ/A12AQ
433px; órfãos da `/canon` 662px).
**Detectar:** `measure.py` com `cmp-embed` de `colw` > 700.

---

### R27 — o Core Form Container migra (action `macnicadefault`)

**Onde:** `/analog-devices/macnica-and-adi`, "Request a Quote or Get in Touch"
(revisão manual do Hazael). O form virava pendência `tipo_nao_reconhecido`,
o título ficava órfão no rodapé e os 3 botões `#contact-form` rolavam até ele.
**O que é:** proxy do Core (`form/container/v2`) com a action customizada
`macnicadefault` (reCAPTCHA + e-mail) e DOIS Experience Fragments de popup
(`successFragmentPath`, `errorFragmentPath`). O global2 tem os mesmos proxies
e a mesma action, e a policy do template permite `form/container` no corpo
(não dentro de `flexcontaineritem`). Levantamento completo em
`PESQUISA-formulario.md`.
**Regra:** `_bloco_form` → `Block("form")` → `macnicaglobal2/components/form/
container` com `macnicadefault_subject`, `macnicadefault_mailto[]`, os campos
(`jcr:title/name/type/required/usePlaceholder/helpMessage/constraintMessage/
rows`) e o botão. Campos SEM `cq:responsive`: uma coluna, como todo form do
global2 (o GWI tinha duas). `from`, `redirect` e `action` do GWI não têm campo
no destino. Outra `actionType` vira pendência `form_action_sem_alvo`.
**Os XFs:** criados por `ferramentas/criar_xf_popups.py` em
`<AEM_EF_ROOT>/popups/form-success|form-error` (espelho da copia-teste,
autorizado em 18/09/2026), com a estrutura dos da APAC e `xfpage` — conferido:
`master.content.html` NÃO começa com `<!DOCTYPE`. **No go-live** o caminho vira
`/content/experience-fragments/macnicaglobal2/americas/mai/en/site/popups`
(`AL.XF_FORM_POPUPS`, definido no driver).
**Conferido na tela:** 9 campos + "Send message"; `:formstart` aponta para o
nó; o POST vai para a própria página. **NÃO testado: o envio** — dispara
e-mail real para 4 endereços. Na copia-teste o `<form>` sai sem
`data-is-recaptcha-enabled`/site key (a config context-aware só existe sob
`/conf/macnicaglobal2/americas/mai`): o comportamento fiel só aparece na
árvore final. O vão abaixo do botão (2×100px dos contêineres de popup + 120px
de margem do `.cmp-form`) é do componente.

---

## R28–R35 — conferência visual, 4ª sessão (18/09/2026): 10 páginas, 6 do lote 4 + 4 famílias novas

Um revisor por página (print lado a lado, `measure.py`, `vao.py`, `jcr.py` dos
dois lados) e um cético por página com defeito, que mediu de novo por conta
própria. **Todas as regras do lote 4 conferidas NA TELA passaram** (R15, R17,
R18, R19, R21, R22 — com clique —, R23, R24, R26, R7, R8, R11, 13a, 13c, 13f).
Nenhum defeito de gravidade alta de DISPOSIÇÃO; o que dominou foi o aberto G,
medido em 9 de 10 páginas. Antes de mexer no motor nasceu
`ferramentas/vaos_estruturais.py`, que calcula o vão entre componentes
consecutivos direto do payload, OFFLINE, nas 136 — o "medir em lote
antes/depois" que o G pedia.

> **ESTADO: GRAVADO no lote 8 (18/09/2026, 134 de 134 sem falha).** Antes do
> lote: conferido offline que nenhum texto some nem muda de ordem nas 136
> (`conf_texto`: só o `linkTarget` de 13 páginas, a R31); os dois styleIds
> novos conferidos na policy por GET; a R36 validada em 2 páginas, a 1400 e a
> 375px. O patch passou por revisão adversarial offline (3 lentes + verificador
> por achado): 10 achados reais, nenhum grave, todos corrigidos ANTES de gravar
> — estão marcados nas regras abaixo (R24b 60px→30, R35 legenda centrada, R28c
> depois de título e antes de botão, `related` a 30px…).
>
> **Conferido NA TELA depois do lote:** `/altera/agilex` (`measure.py`):
> título da página→h2 0, texto→tabela 20 (+ a linha em branco mantida),
> tabela→botão 60 (era 170), botão→série seguinte 80 (era 60 — o botão voltou
> a pertencer à tabela dele). Altura da página a 1400px, destino × GWI:
> `/altera/agilex` 5120 × 5036 (era 5730), `ip00c787` 5514 × 5516 (era 5894),
> `canon-li8030sa` 8010 × 7254 (era 8504), `udp10g` 3342 × 3852. Print:
> "Product Lineup" dentro da faixa das abas da `/design-gateway`; "Complete The
> System" da `canon-li8030sa` com a foto do tamanho do GWI e o texto centrado
> nela.

### R28 — o respiro é de UM container só (era o aberto G)

**Onde:** sistêmico. Título da página→1º bloco 60–90px contra 16–33 no GWI
(9 de 10 páginas); hero→seção seguinte 140 contra 16–127 (36 páginas:
design-gateway, sitime, canon); `/altera/agilex` texto→tabela 130 contra 16 e
tabela→botão 170 contra 13 (o botão "Product Overview" agrupava com a série
SEGUINTE); `/renesas` série de 5 `textwithimage` partida no meio (170 contra
90); `/canon` texto→product listing 135 contra 47; barra de abas→painel 103
contra 25.

**Causa:** o padding T/B dos styles do container é simétrico e ACUMULA: seção
(30|50) + sub-container (30) + margem própria do componente (`.cmp-table` 20,
`.cmp-textwithimage` 30, `.link-button` 40, `ul.cmp-list` 55). Toda fronteira
de seção custava 110–140px onde o espaçador do GWI dá 56–84. E três decisões
antigas fabricavam fronteira onde o GWI não tem nenhuma.

**Regra (cinco partes, um princípio — paga-se o respiro uma vez):**

| | regra | alcance |
|---|---|---|
| a | **Título da página** (`title` vazio, R3/R6) entra como `cabecalho` da 1ª linha da 1ª seção — mesmo container, largura cheia, fora de qualquer coluna (o mecanismo da R23). Seção própria só quando a 1ª seção é faixa de abas/CTA/related. `AL.inserir_titulo_da_pagina`, usado pelo driver, `diff_payload` e `cmp_motor` | 134 |
| b | **Container com sub-containers não tem padding T/B próprio**: seção com 2+ linhas e painel de aba com 2+ linhas saem `Pad T/B None`; o respiro é o dos sub-containers (30+30) | 99 |
| c | **O espaçador de topo corta a corrida** — em `_secoes` o ramo era CÓDIGO MORTO (`so_pageproperties` devolve True para nó sem conteúdo e vinha antes). O corte fica PENDENTE até o próximo bloco e tem as exceções da R24 estendida: não corta DEPOIS de título (`namuga-vicon-lite`: heading, espaçador, imagem) nem ANTES de botão (`/toppan`: tabela, espaçador, botão do datasheet — 140 → 60). E **`table` e `productlist` saem de `MAJOR`**: com espaçador de topo antes, ele já corta; sem ele ficam na corrida do texto que os apresenta. Texto↔tabela com a linha em branco na origem (no fim do `text` ou como nó): UMA linha em branco mantida no `text` (30+20 = 50px; GWI 16+28) — 24 lugares | 14 |
| d | Seção só de `productlist` → `pad_tb=none`, como `related` (o `<ul>` traz 55px). E `related` só fica `none` depois do XF; senão `small` — com a (b), "Similar Products" ficava a 30px do texto de cima e a 55 da própria lista (4 `/sitime`, `canon-li8030sa`) | 4 + 6 |
| e | Seção que é SÓ um `textwithimage` → `pad_tb=none` (o componente traz 30/30); {título + `textwithimage`} → `small` (o título precisa do respiro de cima) | 39 |

**Medido offline (vão estrutural, 136 páginas, antes → depois):** transições
com 130px ou mais: 83 → 8 (com 110 ou mais: 153 → 27, de 1.797); `texto→tabela` mediana 100 → 20; `tabela→botão`
140 → 60; `título→título` 60 → 0; `textwithimage→título` 140 → 90. A `/canon`
fica uniforme em 60–80 (era 60/80/110) e a `/renesas` em 90 (era 90/170) —
por isso NÃO se criou a regra "série homogênea herda small" que o G propunha
(o cético mediu: o GWI tem 44–100px entre linhas da grade).

**Como detectar:** `vaos_estruturais.py --cache <pkl> --antes <motor antigo>`
— histograma e mediana por transição; `--ver /pagina` lista componente a
componente. Na tela: `measure.py`, coluna `gap`.

### R29 — coluna SOLITÁRIA reentra na corrida que interrompeu

**Onde:** as 7 `design-gateway/*nvme*`, `quic10gc`, `sata`: título "Resources"
num sub-container e o botão que ele introduz (`width=4`) no seguinte — 89px do
título, 90 do título de baixo: boiando. Mais 4 folhas `/i-chips` (título
"Technical Demo" → vídeo) e 3 `/canon`.
**Causa:** `extrair_linhas` fechava a corrida na CHEGADA da 1ª coluna, antes
de saber se haveria 2ª. Coluna sozinha "não é coluna" e voltava à corrida —
mas já na Row seguinte.
**Regra:** a corrida interrompida fica guardada e só fecha em
`fechar_colunas`, se forem 2+ colunas (ou card órfão da R18). Coluna solitária
entra na MESMA corrida. 15 páginas.
**Efeito colateral tratado:** na `canon-li3030sa` o GWI tem tabela, NÓ
ESPAÇADOR, vídeo — e a corrida única colava o vídeo na tabela. Daí a extensão
da R24: espaçador como nó à parte (`espaco_antes`) também abre subseção —
menos depois de título, entre dois textos, antes do XF, e onde as margens
próprias dos dois componentes já somam 40px. 3 transições em 3 páginas (uma é
o "infográfico→índice de âncoras 56→0" que o revisor da `canon-li8030sa`
achou).

### R30 — TODOS os títulos do fim da corrida acompanham o bloco (R20 na fronteira de seção)

**Onde:** `/canon`: h2 "Canon Image Sensors" sozinho numa seção, a 80px do h3
"Ultra-High Resolution Industrial Sensors" que ele encabeça (GWI 16px).
**Causa:** `titulo_que_introduz()` tirava UM título da corrida.
**Regra:** devolve a lista de títulos consecutivos do fim. E `tabs` deixou de
ser exceção: o título entra na faixa das abas, em cima da barra —
`_marcar_papeis` aceita `{title, tabs}` (era o **aberto H**: `/namuga` 152
contra 80, `/design-gateway` 150).
**Detectar:** container de topo cujo único filho é `title`, seguido de
container cujo 1º filho é `title`.

### R31 — `linkTarget` do botão vem da origem

17 botões em 13 páginas abrem em aba nova no GWI (datasheet externo, PDF) e
saíam `_self`. Função, não disposição: print nenhum mostra.

### R32 — `<br>` pendurado no fim de célula de tabela

12 tabelas em 12 páginas (`altera-stratix-10-dx`: linha 15px mais alta que as
vizinhas). É espaçador do autor, da família do `<p>&nbsp;</p>`, só que DENTRO
do bloco — `strip_empty_blocks` não vê. Pega também o `<br>` dentro de
`<b>`/`<span>` (`…Count'<br> <br></b></td>` na `cyclone-10-lp`). `<br>` entre
textos fica.

### R33 — inline solto na raiz do rich text vai para um `<p>`

`canon-li8030sa`: `<h4>…</h4><h4>&nbsp;</h4><span>Macnica pairs…</span>`. Fora
de `<p>` o texto não pega `.cmp-text p`: sai 14px com letter-spacing 1,4px e
colado no h4 (1px contra 27). `embrulhar_inline_da_raiz`, por lista BRANCA de
inline: HTML que não fecha direito, comentário ou qualquer tag fora das listas
(`<center>`, `<form>`…) volta como veio. 1 nó no escopo — a regra é barata e o próximo lote de
páginas pode ter mais.

### R34 — `elementsPositionVerticalAlignCenter` → style Vertical Center do `textwithimage`

4 `imagetext` em 2 páginas. Sem ele o texto sobe para o topo da foto e sobra
o buraco embaixo (0 em cima / 231 embaixo). styleId `1783061491236` (confere
com o README, `aem_padronizar_textwithimage`), gravado na forma posicional
`['', '', id]` — [Image Position, Text Wrapping, Vertical Alignment].

### R24b — respiro DENTRO de coluna volta como linha em branco

**Onde:** `/toppan`, coluna do C11U: h3 "Key Features…" colado no parágrafo de
cima (0 contra 28) e a 24px da lista que introduz; 2 abas da `/infineon`.
**Causa:** dentro de `flexcontaineritem` não há subseção (R24, "Limite").
**Regra:** com a evidência do espaçador na origem, UMA linha em branco é
mantida no `text` vizinho (entra depois de `strip_empty_blocks`). 3 nós em
coluna, mais os 24 de texto↔tabela da R28c. A linha é
`<p style="margin-top:0">&nbsp;</p>`: sem o `margin-top:0` ela rende **60px**
(30 de margem de todo `<p>` que não é o 1º + 30 de altura), não 30 — medido
em render local pelo revisor do patch.

### R35 — foto de card alinhada com a legenda

**Onde:** `/toppan`, 4 cards: foto de 512px centrada numa coluna de 662,
legenda na borda — 75px de desalinhamento. `/i-chips` e `i-chips-scaler-lsi`
fazem o mesmo de 1920px para cima.
**Regra:** `image` em coluna que tem `title`/`text`, com `alignment=left`
EXPLÍCITO na origem e legenda NÃO centrada, ganha Display Position **Left**
(`1726800547211`, policy do `image` — **conferir no dry-run**). Os cards
centrados na origem (`/ambarella`, `/canon`, `/renesas`) e os 6 da
`i-chips-scaler-lsi` (sem `alignment`, legenda `text-align:center`: alinhar a
foto CRIARIA o defeito acima de ~1950px) continuam. 10 nós em 2 páginas.

### R36 — `imageRatio`: a imagem do `textwithimage` no tamanho que o GWI desenha (era o aberto J)

**Onde:** o defeito mais visível que sobrou. `canon-li8030sa`: 3 fotos de
640–655px de largura contra 415×277 no GWI, texto de 178–199px de altura ao
lado: **231–317px de buraco** embaixo do texto, +527px de página. As 7 folhas
`i-chips-ip00c*` com largura autoral (600×600 contra 345×277): 397px entre o
parágrafo e "Application Uses" (GWI 16). Hero das 26 `design-gateway` e das 6
`/sitime` 1,7× maior: o índice de âncoras sai da 1ª dobra (y=840 → 1172).
**Causa:** o `textwithimage` dá 50% da linha à imagem e só o tamanho natural a
limita; no GWI `.cmp-image-text img{max-height:277px}`, o `resizableimage` tem
`width` autoral e o carousel de coluna 6 tem 380px úteis. O REGRAS dizia "sem
campo alvo" — **o campo existe**: `./imageRatio` ("Image Width (%)") no diálogo,
que o HTL passa ao CSS como `--textwithimage-image-ratio`. Há precedente no
projeto (`aem_padronizar_textwithimage.py`, `imageRatio=40`; 187 nós na
copia-teste).
**Regra:** `_image_ratio` — largura-alvo em px = a que o GWI DESENHA (largura
autoral; ou `min(480, 277 × L/A)` no imagetext; 380 no carousel de 1 slide;
a coluna, ou a natural se menor, na linha 6/6), dividida pela largura útil
(1316), entre 25 e 50; 50 é o padrão e não é gravado. `L/A` vem do DAM
(`tiff:ImageWidth/Length`), lido pelo driver em `aplicar_dimensoes_de_imagem`
ANTES de `copiar_assets`; sem metadado assume 3:2.
**Alcance:** 100 `textwithimage` em 75 páginas (offline, sem o DAM: 40 com 32,
36 com 29, 12 com 25).
**Validado na tela antes do lote** (`canon-li8030sa`, `i-chips-ip00c787`): a
1400px as fotos saem com 419×280, 419×279 e 367×277 (GWI 415×277, 416×277,
366×277) e 341×341 na ip00c787 (GWI 345×277 — lá o GWI CORTA a foto quadrada
com `pixelation=cover`; o destino mostra inteira, e sobra ~200px sob o texto,
contra ~400 antes). **A 375px a imagem ocupa a largura toda** (345px): a
variável só vale no desktop, o celular não quebra.
**Detectar:** `textwithimage` sem `imageRatio` cuja imagem renderizada é mais
alta que 1,5× o `.paragraph` ao lado.

### Achados que NÃO são de motor

- **FUNCIONAL, gravidade alta — links para página que não existe no global2.**
  `canon-li8030sa`: o botão "Contact Us" e 3 CTAs apontam para
  `/content/macnicaglobal2/americas/mai/en/contact/form` → **404** (o global2
  tem `contact-us` e `request-a-quote`, vazias). `rewrite_links` só troca o
  prefixo. A Anion apontou para `https://www.macnica.com/americas/mai/en/contact/form/`.
  Decisão do time + tabela de redirecionamento; falta o censo nas 136
  (href interno do HTML renderizado → GET → lista de 404).
- **Os dois XFs da copia-teste**: além de `page` em vez de `xfpage` e dos
  botões empilhados, os `href` deles apontam para `/content/macnicagwi/…`.

---

## R37–R41 — rodada 2 da conferência visual (18/09/2026, depois do lote 8): 14 páginas

Treze revisores, somente leitura, sobre 14 páginas nunca vistas (landings
`/sitime`, `/i-chips`, `/design-gateway`; linhas `altera-arria-10`,
`altera-stratix-10`, `altera-max-10`; folhas `helio-view`, `arria-10-gt`,
`ip00c241`, `holoscan`, `clock-buffers`, `li5030sa`, `120mxs`, `radar-kit`).
**Nenhum defeito grave de disposição; todas as regras do lote 8 conferidas na
tela** (R28a–e, R28c texto↔tabela 50px contra 44, R30 título na faixa das abas,
R35, R36 em 9 páginas — imagem a ±8px do GWI —, R22 com clique em
`#whysitimebuffers`). O que saiu:

> **ESTADO: GRAVADO no lote 9 (18/09/2026)** — 108 páginas (dry-run real,
> `diff_payload.py` nas 136). R39 e R41 validadas na tela em 2 páginas ANTES do
> lote: `id="productlineup"` sai no `<div class="cmp-text">`; o
> `white-space:nowrap` sobrevive ao filtro do AEM.
>
> **Conferido NA TELA depois do lote 9** (1400px, `?wcmmode=disabled`):
> R40 `canon-120mxs` título→texto **46px** (era 166; GWI 50) e foto do Eval Kit
> **249×273** (era 327×359; GWI 252×277) · R38 `clock-buffers` h2→h3 **60**
> (era 22; GWI 65) e índice→"Key Features" **90** (era 119; GWI 55) · R37
> `holoscan` frase→1º item **30** (era 90; GWI 28) · R39 `/design-gateway`: o
> clique em "See the full … lineup here" rola 2.197px e o alvo para a 104px do
> topo, sob o cabeçalho fixo · R35 `/i-chips`: herói em x=25, a borda do h1 ·
> R41 `altera-arria-10`: 0 de 209 células quebradas a 1400 e a 375px.

### R37 — `<p><b>&nbsp;</b></p>` é linha em branco

**Onde:** `altera-holoscan`, "Target Applications": 90px entre a frase de
introdução e o 1º item (GWI 28). E `i-chips-fpga-evaluation-board`.
**Causa:** o autor deixou o negrito ligado na linha vazia; `strip_empty_blocks`
e `_P_VAZIO` só aceitam espaço/`&nbsp;`/`<br>` dentro do bloco.
**Regra:** `normalizar_espacadores` — bloco `p|hN` cujo miolo, tiradas as tags
inline, é só espaço vira `<p>&nbsp;</p>` e segue o caminho de todo espaçador.

### R38 — título, NÓ espaçador, título de nível MENOR: abre subseção

**Onde:** 5 `/sitime/*` e `/namuga`: h2 "SiTime Buffer Product Lineup" → h3 do
1º produto a 22px; os outros h3 da série a 71 (GWI 65/64/64/64/64).
**Causa:** a R20 cola título em título sempre; a extensão da R24 não corta
depois de título. As duas ignoravam o espaçador quando o bloco seguinte TAMBÉM
é título. Sem espaçador na origem continua colado (`ambarella-n1-soc`, `/canon`).

### R39 — `id` de âncora em `text` COM conteúdo

**Onde:** `/design-gateway`: o link "See the full Design Gateway product lineup
here" (`#productlineup`) não rolava — **funcional, print nenhum mostra**. E os 3
alvos do índice das duas `test-277-*` (a R22 os dava como "sem alvo também no
GWI": o alvo existe, é um `text`).
**Regra:** `Block("text")` leva o `id`; o emissor grava `./id` (core text v2
renderiza como `id` do `<div>`); `text` com `id` não se funde no de cima.
**Detectar:** `main a[href^="#"]` sem `getElementById` — o `ancoras.py` só olha
o índice; ampliar o seletor é melhoria pendente da ferramenta.

### R40 — `hr` logo depois de título é o FIO do título

**Onde:** `canon-120mxs`: h1 "120MXS Eval Kits" → `hr` → texto em TRÊS
containers: 166px do título ao texto (GWI 50), o fio boiando num branco de
175px, o título mais perto da tabela de cima. 1 caso nas 136 (de 41 `hr`).
**Regra:** `hr` imediatamente depois de título, sem espaçador, não abre nem
fecha subseção (exceção à 13c).

### R41 — célula de tabela com UM token não quebra no meio (reabre e fecha o aberto E)

**Onde:** `altera-arria-10` (13 colunas): 31 de 209 células quebravam número no
desktop ("101,62/0") e **189 no celular, um caractere por linha — tabela de
8.319px contra 2.258 no GWI**; `/i-chips` ("IP00C33/5"), `helio-view` e
`6-altera-soc…` ("Prerequisite/s"), `stratix-10-ax`. 5 páginas a 1400px; o GWI,
0. O aberto E estava "FECHADO: sem a margem a quebra sumiu" — não tinha sumido.
**Causa:** reset do clientlib do global2: `td,th{word-break:break-word}` — a
célula encolhe até 1 caractere e o wrapper `overflow-x:auto` nunca rola.
**Regra:** `nao_quebrar_tokens` — `td`/`th` cujo texto é um token único de 2–16
caracteres ganha `style="white-space:nowrap"`. A tabela cresce e ROLA dentro do
`.cmp-table.scroll-hint`, como no GWI.
**Conferido na tela:** `altera-arria-10`: 0 de 209 quebradas a 1400 e a 375px;
a 375 a tabela tem 1316px e rola dentro dos 345 do wrapper; altura 3.279px.
**Melhor saída, fora do motor:** uma linha no clientlib —
`.cmp-table th,.cmp-table td{word-break:normal;overflow-wrap:normal}`.

### Ajustes de regras anteriores (mesmo lote)

- **R36:** a largura-alvo do imagetext respeita a largura NATURAL do asset
  (`altera-max-10`: foto de 256px numa coluna de 36%, encostada num canto) e o
  piso caiu de 25 para **15%** (`canon-120mxs`: foto em retrato pedia 19%, saía
  1,3× com 239px de buraco; `/renesas`: `width=200` autoral → 15%).
- **R35:** vale também para a foto SOZINHA na coluna (herói foto | título+texto
  da `/i-chips`: 58px para dentro da borda do h1; 188px a 1920). +5 nós.
- **R28:** seção que é só o XF de contato → `pad_tb=none` (o XF traz 100px+
  próprios; pedido por 3 revisores: lista→botão 245 → 195); subseção que é só
  `textwithimage` → `none` (a R28e por LINHA: vãos em volta dos `hr` da
  `arria-10` 97 → 67, GWI 52); subseção que é só o índice de âncoras → `none`
  (`.anchor-link__list` tem 60px de margem embaixo: índice→título 119 → 90, GWI 55).
- Container de seção VAZIO (o `related` que não resolve) é podado — 9 páginas.
- Comparador (`aem_fidelidade_render.py`): passou a ver texto solto na raiz do
  rich text (a R33 fazia a `canon-li8030sa` acusar `sobra=1`).

---

## Aberto (achado na conferência visual, NÃO corrigido)

| # | padrão | onde / quanto | causa | proposta |
|---|---|---|---|---|
| I | **botão sempre centralizado** | `/altera` ×2; **+ as 7 `design-gateway/*nvme*`** (`width=4 offset=0`: GWI na borda esquerda, destino no centro da página — único elemento centrado do corpo); `/toppan` (botão em coluna: GWI ocupa a coluna, destino centrado nela) | `S_BTN_CENTER` fixo. No GWI: sem `cq:responsive` o botão é centrado na linha (`/altera/agilex`); com `width<12 offset=0` fica à esquerda | decisão de dialeto. Proposta com 10 páginas de evidência: sem `S_BTN_CENTER` quando `width<12` e `offset=0`, ou dentro de coluna |
| J | imagem do `textwithimage` no tamanho natural | — | — | **virou R36** (`imageRatio`), validada na tela e gravada no lote 8 |
| K | série de itens título+texto: 60px entre itens | **recalibrado na rodada 2** — o alvo do GWI não é 28: são 16px fixos entre componentes + 16 de margem do `ul` + a linha em branco = **44 (parágrafo) a 60 (lista)**; na `ip00c241` GWI e destino dão 60/60 (a linha em branco está ANINHADA no último `<li>` e o censo a contava como "zero"). Sobram 12 fronteiras com zero de verdade em 4 páginas (`agilex-9` ×2, `holoscan` ×6, `multimodal` ×3, `fpga-evaluation-board` ×1): 16–32 contra 60 | todo título abre subseção (30+30) | baixa prioridade. Se for mexer: só no zero REAL, e o detector de linha em branco final tem de olhar através de `</li></ul>` |
| L | **imagem de largura cheia com `alignment=left` sai centrada no tamanho natural** | banner da `altera-holoscan` (1280px centrado em 1350: 35px de recuo, cresce com a janela), diagramas "Why Macnica" das `design-gateway` | o `image` do global2 centra por padrão e não amplia; no GWI a imagem ENCHE a coluna e esquerda/centro não se distinguem | decisão de dialeto: Display Position Left para todo `alignment=left` muda ~85 imagens em 50 páginas que ninguém viu assim. A R35 só cobre foto de card e foto sozinha em coluna |
| M | **carousel de 2+ slides ao lado de texto ocupa a coluna inteira** | 4 folhas `/canon` (`li5030sa`, `li5040`, `li5070sa`, `li7070sa`): slide de imagem 662×543 contra 379×311, cortado embaixo pelo `max-height:36vw` do carousel do site; irmãs de 1 slide têm hero de 380px (R36) | só o carousel de 1 slide vira `textwithimage` | antes de dizer "sem campo alvo": ler dialog/policy do `carousel`, `flexcontainer` e `flexcontaineritem` |
| N | título logo depois de `textwithimage`: 90px contra 20–47 | 48 lugares em 46 páginas (todos abaixo de 100px; o agrupamento não engana) | margem 30 do twi + 30 + 30 da subseção que todo título abre | título depois de twi SEM espaçador na origem não abriria subseção (41px). Falta cruzar com a evidência de espaçador |
| E | célula de tabela quebrando palavra/número | 5 páginas a 1400px, muito pior no celular | `word-break:break-word` do clientlib | **virou R41** (`white-space:nowrap` em célula de token único). A correção de raiz é 1 linha de CSS no clientlib |
| — | policy do site: o `embed` do global2 tem `youtubeRelatedVideosEnabled=false` (e mute/loop/autoplay) — o `rel=0` dos 37 vídeos do GWI não tem como migrar; `/altera` e `/analog-devices` têm `youtubeMute=true` | 33 páginas | policy `…/components/content/embed/policy_1719541566086` | fora do motor |
| — | `rewrite_link` deixa a `/` final quando converte URL pública (`…/boards-modules/terasic/`) | `altera-holoscan` (não contado) | `aem_lib.rewrite_link`, lib compartilhada | `rstrip('/')` — entra no censo de links do go-live |
| — | CSS do site: `td` alinha no topo (GWI no meio); índice de âncoras quebra 3+1; fio sob os h3 do GWI não existe | várias | clientlib do global2 | fora do motor |

Fechados na 3ª sessão: F (R26), A (R16 — sem moldura, continua `table`), B (R24),
C (R18), D (R15). **Na 4ª: G (R28), H (R30), J (R36) e E (R41 — não tinha sumido).**

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
| "Success"/"Error" do form faltando (4) com o form migrado | popups do form container: no destino saem `aria-hidden`, no GWI ficam em `.cmp-form-success/.cmp-form-error` sem marca | excluídos dos dois lados (R27) |

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
- **`form/container`** na `macnica-and-adi` — MIGRADO (R27). Falta testar o
  envio (e-mail real; combinar antes) e o reCAPTCHA, que só existe na árvore
  final. Ver `PESQUISA-formulario.md`.
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
