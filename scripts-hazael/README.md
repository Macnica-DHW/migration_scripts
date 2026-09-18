# scripts-hazael — diagnóstico e correção pós-migração (AEM)

Complementam os scripts de `../scripts-bruno`, que fazem a migração em si.
Todos importam o `aem_lib.py` de lá — não há biblioteca duplicada aqui, nem
autenticação própria: `.env`, travas de escrita e sessão são os mesmos.

Nasceram de problemas reais encontrados em 17/09/2026 no `tq-systems`. Cada
docstring conta o problema que o script resolve, porque em praticamente todos
os casos a causa não tinha nada a ver com o sintoma.

```
DIAGNOSTICAR (só leitura)
  aem_diff_conteudo.py          conteúdo migrado x origem no GWI
  aem_workflow_audit.py         workflows por payload
  aem_screenshot.py             RENDERIZA a página e salva imagem
  aem_conteudo_sobrando.py      texto que o destino mostra e o GWI não tem
  aem_fidelidade_render.py      texto RENDERIZADO: o que falta e o que sobra

CONSERTAR (padrão: diagnóstico; escreve só com --executar)
  aem_soft_delete.py            páginas invisíveis (deleted/deletedBy)
  aem_fix_canonical.py          cq:canonicalUrl depois de um clone
  aem_restaurar_specs.py        seção Specifications perdida
  aem_corrigir_divergencia.py   texto do destino diferente do GWI
  aem_reconstruir_blocos.py     recria blocos de topo que não existem
  aem_corrigir_lixo_markup.py   marcação quebrada virada texto visível
  aem_corrigir_alinhamento.py   text-align:center indevido em tabela
  aem_largura_ordering.py       largura da 1ª coluna do Ordering
  aem_padronizar_textwithimage.py  Text with Image pelo design de referência
  aem_deduplicar_containers.py  conteúdo gravado 2x ou 3x na mesma página
  aem_corrigir_layout_blocos.py coluna achatada, aba colada, logo no corpo

COPIAR
  aem_clone_subtree.py          substitui o conteúdo de uma subárvore

REMIGRAR (árvore nova, dialeto Anion)
  aem_remigrar.py               GWI -> semiconductors-remigration
  ../scripts-bruno/aem_layout.py   o motor de layout (IR + emissor)
```

## Convenções (as mesmas do scripts-bruno)

- **Diagnóstico é o padrão.** Nada escreve sem `--executar`.
- **Trava de escrita.** Só `copia-teste`. Para `macnicaglobal2`,
  `--permitir-escrita-global2 <caminho>` tem que bater **exatamente** com o
  alvo — libera aquele caminho, naquela execução.
- **Idempotentes.** Rodar de novo no que já está certo não reescreve.
- **CSV sempre**, com o valor antigo, para dar para desfazer.
- **O GWI é somente leitura.** Nenhum script escreve lá, e a trava aborta o
  processo se alguém tentar.

## A regra de conteúdo (definida pelo time em 17/09/2026)

> O GWI é a fonte da verdade. Se o conteúdo do GWI está errado, o problema é
> do GWI — migra-se fielmente assim mesmo. Se o GLOBAL2 diverge do GWI, o erro
> é nosso e se corrige. Layout pode (e deve) diferir; conteúdo, não.

Duas exceções conscientes, ambas em `aem_corrigir_lixo_markup.py`: marcação
quebrada que aparece para o visitante é corrigida no destino mesmo existindo
igual no GWI. Isso cria divergência proposital — uma remigração traz o lixo de
volta, e aí é só rodar o script de novo.

---

## Diagnóstico

### `aem_diff_conteudo.py` — o conteúdo chegou inteiro?
O `aem_verify.py` responde "a página existe e tem conteúdo?". Este responde "é
o **mesmo** conteúdo?". Achou página com dois blocos `Features` no GWI e só um
no destino — para o verify, migração bem-sucedida.

Compara **texto visível**, não componentes: o destino usa outro vocabulário
(`title`, `textwithimage`, `flexcontainer`) e os fixes de layout reorganizam
blocos de propósito. Extrai por propriedade, concatena o texto do destino e
pergunta se cada bloco da origem está contido ali — o que absorve fusão e
quebra de blocos. Abaixo de `--limiar` (0.85) vira "ausente".

Filtra o boilerplate que os scripts de layout removem de propósito (`--sem-filtro`
mostra cru) e pula páginas soft-deleted. Sem esses dois filtros o relatório
acusava 160 de 173 páginas e escondia os 17 buracos reais.

**Limitação conhecida:** acha o que FALTA, não o que está SOBRANDO. Texto de
outra página só aparece se tiver deslocado o texto certo. Para isso, ver
`aem_corrigir_divergencia.py`.

### `aem_conteudo_sobrando.py` — o destino mostra o que a origem não mostra
O `aem_diff_conteudo.py` varre os blocos da ORIGEM e pergunta se chegaram; a
docstring dele avisa que "acha o que FALTA, não o que está SOBRANDO". Este faz
a pergunta invertida.

O caso que o motivou: `4-helio-view-hardware` abre com "Transform your approach
to FPGA with our Helio View hardware vWorkshop..." — texto que não existe em
lugar nenhum da página do GWI. É o `jcr:description` do GWI, a META
DESCRIPTION, que o migrador pôs no corpo como texto visível. O mesmo bug tem
um segundo sintoma: a description não foi para o lugar dela. Em
`semiconductors` (17/09/2026): **155 páginas com a meta description no corpo,
348 sem `jcr:description`** — de 353 que o GWI tem.

Nem toda sobra é bug. Em 144 páginas (133 sony, 11 design-gateway) a sobra é
o rótulo do `download`, que no GWI não tem `jcr:title` e o migrador gera do
nome do arquivo ("Technology guide Sony Pregius Pregius S"). O arquivo é o
mesmo dos dois lados; só o rótulo foi inventado. Por isso o CSV separa a
coluna `meta_description_no_corpo`.

**A coluna `hideInNav` não é assunto de outro script.** `hideInNav=true` tira
a página da navegação E da própria trilha de breadcrumb. Contraste controlado
no mesmo lugar da árvore:

```
hideInNav=None  sony-imx174lqj-c  ... / Sensor List & Specs / Sony IMX174LQJ-C
hideInNav=true  canon-li7070sa    ... / Semiconductor Solutions        (para aqui)
```

O `aem_migrate.py` liga `hideInNav` por padrão ("diretriz do cliente"), então
são 131 páginas assim. Cuidado ao concluir: em `copia-teste` a trilha também
é curta porque `/en` e `/en/products` **não existem** lá (404); em
`macnicaglobal2` existem, com navTitle "Products" e "Semiconductors". Essa
metade se resolve sozinha no destino real; o `hideInNav`, não.

### `aem_fidelidade_render.py` — o que o visitante vê, dos dois lados
O `aem_diff_conteudo.py` compara o JCR. Este compara a TELA: renderiza origem e
destino com `?wcmmode=disabled`, extrai o texto visível em ordem de documento e
diz o que **falta**, o que **sobra** e o que está **fora de ordem**.

Existe porque o JCR tem dois pontos cegos que a remigração não pode ter:
conteúdo que está no JCR e não renderiza (o `containerpy` de 111 páginas), e
blocos trocados de lugar, que um comparador de conjunto dá como idênticos.

Casa por **contenção**, não por igualdade — o destino funde e quebra blocos de
propósito, e exigir igualdade exata acusaria diferença em página correta.

Duas armadilhas já resolvidas, que valem para qualquer comparador de tela:

1. **Excluir o chrome do site pela ESTRUTURA, não por palavra.** O mega-menu do
   GWI sozinho tem centenas de `<li>`: a primeira versão comparou 1698 unidades
   na origem contra 315 no destino, quase tudo navegação. Agora descarta por
   `closest()` em `header/footer/nav` + classes de navegação. O rodapé do GWI
   não tem `<footer>` nem classe `footer__` — é um experience fragment, e só o
   `id*="copyright"` o identifica.
2. **O botão tem markup diferente nos dois mundos.** GWI é
   `a.cmp-button > span.cmp-button__text`; global2 é `a.link-button__anchor`.
   Sem os dois seletores o botão da origem não é capturado e o do destino
   aparece como conteúdo INVENTADO — falso positivo caro.

Usa `textContent` e não `innerText`: aba inativa tem `display:none` e o
`innerText` volta vazio, o que acusaria as abas 2..N como conteúdo perdido.

Mais seis pontos cegos fechados em 18/09/2026 (detalhe e prova em
`remigracao/REGRAS-disposicao.md`, seção "O comparador também tinha pontos
cegos"). A lição de todos: **quando o MESMO texto falta ou sobra em dezenas de
páginas, desconfie da medição antes do motor.**

3. Botões de carousel ("Previous"/"Next") e o botão mobile do índice de
   âncoras (`.cmp-pagesectionlisting__button`, criado por JS) são chrome —
   excluídos por classe.
4. O rótulo do `download` do GWI é `a.cmp-download__property--filename`,
   fora do seletor original: a origem não contava o arquivo e a célula do
   destino saía como "sobrando". Entrou no seletor.
5. "opens in a new tab" é um span oculto que o destino injeta em todo
   `target=_blank` — removido na normalização.
6. Cabeçalho `Title`/`Download` e a célula "Download" da tabela de download
   são formato, não conteúdo — filtrados só por tag + texto exato.
7. Coluna de grid com `cq:responsive/default/behavior=hide`
   (`.aem-GridColumn--default--hide`) é invisível ao visitante — excluída
   por classe, nunca por `display:none` genérico (isso esconderia as abas).
8. Item de lista com o mesmo alvo e rótulo diferente (teaser do GWI imprime
   `pageTitle`; `list` do destino imprime `navTitle`) é casado pelo `href` e
   contado na coluna `titulo_lista`, em vez de virar "faltando".

O que ele **continua não vendo**: ordem de cards numa lista (só `fora_de_ordem`
grosseiro), nível de heading (h1 × h2), descrição de card perdida no `list`, e
qualquer coisa de disposição. Print da tela é insubstituível.

Resultado na `/altera` em 18/09/2026 (49 unidades na origem, 46 no destino):

```
FALTA  <span> Contact Us for More Information   <- experiencefragment não traduzido
SOBRA  <h1>   Buy Altera Semiconductor, ...     <- jcr:title promovido a h1 de conteúdo
```

Ou seja: confirma por medição independente que o `experiencefragment` (124
ocorrências na família) é **perda de conteúdo real**, e que o h1 injetado é
**conteúdo inventado**.

**Limite honesto:** página com muita imagem carrega significado que nenhum
comparador de texto vê. Reduz o trabalho do olho humano, não substitui.

### `aem_screenshot.py` — ver a página de verdade
**Use `--publicado`** para medir layout: sem ele a página abre em modo de
autoria, que injeta um placeholder de 29px por bloco e infla o espaçamento —
em 18/09/2026 isso fez "seções coladas" parecer menos grave do que era. E o
`networkidle` não assenta no author (o editor mantém polling aberto): o
script cai para `load` + espera fixa.

Todo o resto aqui lê o JCR, e JCR não mostra como a página FICA. Os problemas
de 17/09/2026 que só apareceram quando um humano olhou a tela: coluna do
Ordering espremida quebrando o part number no meio, Specifications
centralizado, imagem do Text with Image fora do lugar. Nenhum foi pego por
diagnóstico automático.

A página abre com um GET autenticado normal em `<caminho>.html`, sem o chrome
do editor — então Playwright + Chrome + os cookies do `.env` bastam. Fecha o
ciclo: renderiza origem, renderiza destino, compara, corrige, confere.

Cada screenshot custa bastante contexto: ~30-50 páginas por sessão.

### `aem_workflow_audit.py` — existe workflow vivo mesmo?
`GET /var/workflow/instances.json` devolve **200 com zero filhos** para quem
não é admin: parece vazio e não está. O QueryBuilder achou 16.898 instâncias,
3.121 `RUNNING`, algumas presas desde jan/2024. E `payload` é propriedade do
nó, mas `p.properties` devolve `None` para ela — filtre com
`property.operation=like` ou leia a instância direto.

---

## Correção

### `aem_soft_delete.py` — "sumiu do console mas o nome continua ocupado"
O fluxo *Request for Page Deletion* **não apaga**: grava `deleted` e
`deletedBy` em `jcr:content`, e o console filtra quem tem essa propriedade.
A página some da árvore, não dá para criar outra com o mesmo nome (vira
`nome0`, `nome1`...), o *restore* não faz nada e o editor mostra o banner do
workflow — às vezes sem workflow nenhum vivo.

O marcador está em **cada página da subárvore**, não só na raiz: em
`tq-systems` eram 144.

### `aem_fix_canonical.py` — canonical apontando para a origem
Clonar copia o `cq:canonicalUrl` junto, então a página clonada nasce dizendo
que a versão boa é a **outra** — tirando do índice do Google exatamente a
página recém-publicada. Foram 143 assim depois de um clone.

Mexe **só** nessa propriedade (o `aem_fix_seo_final.py` do scripts-bruno faz o
pacote de SEO inteiro).

### `aem_restaurar_specs.py` — seção Specifications sumida
8 páginas tinham o bloco no GWI e não no destino. A perda é antiga, de
`copia-teste`, e foi propagada fielmente por todos os clones. Insere
`title` + `table` no início do container que já tem o Ordering, via `:order`
do Sling, produzindo o layout-alvo
`Specifications -> tabela -> Ordering -> tabela`.

### `aem_corrigir_divergencia.py` — destino com texto de outra página
`mba8mpxl` tinha o h1 e a introdução do `boxpc-abox-6ulxl`, com a imagem certa.
O texto "Extended temperature range..." aparecia em 4 páginas diferentes.

Não é padronização: das 131 páginas com bloco Features, 115 têm texto
**distinto**. Corrige `textwithimage/text` e o `text` do Features a partir do
GWI. **Só corrige campo que EXISTE** — se o componente não existe, use o
`aem_reconstruir_blocos.py`.

### `aem_reconstruir_blocos.py` — o componente nem existe
Em `tqmt1022` não havia `textwithimage` nem Features: sumiram H1, introdução,
lista e a imagem. Essas páginas usam `resizablecontainer` aninhado no GWI, em
vez de `imagetext`, e a migração não tratou o formato.

Acha o conteúdo achatando o `jcr:content` do GWI em ordem de documento (serve
para os dois formatos) e **cria** os containers na convenção das páginas
irmãs.

**A imagem:** o `nodename` do QueryBuilder é SENSÍVEL A MAIÚSCULA e o DAM do
global2 guardou tudo em minúscula (`TQMT10xx.jpg` -> `tqmt10xx.jpeg`).
Procurar com o nome do GWI não acha nada — daí as variantes normalizadas. Se
não achar, a página fica **sem** imagem e é reportada: melhor sem foto do que
com a foto de outro produto.

**Cuidado:** "não tem textwithimage" nem sempre quer dizer "falta conteúdo".
Algumas páginas (`mbls1028a-ind`, `lboxls1012al`) usam o layout ANTIGO
(`title_wrap`, `text_intro_wrap`, `image_1_wrap`...) e já têm tudo, só em
outro formato. Confira a estrutura antes de rodar.

### `aem_corrigir_lixo_markup.py` — marcação virada texto
Um `</strong>` perdeu o `<` e foi escapado: a célula mostra
`TQMa3359-AA/strong>` para o visitante. Outro caso tinha dois part numbers
fundidos (`TQMTQMLX2080A-AALX2120A-AA`), corrigido por **lista explícita** e
conferido contra a 2ª coluna da própria linha — reconstruir part number por
heurística é jeito de inventar peça que não existe.

Os dois existiam iguais no GWI. Ver "exceções conscientes" acima.

### `aem_corrigir_alinhamento.py` — tabela centralizada
GWI: 251 tabelas, **0** com `text-align:center`. Destino: 88 ocorrências em 5
páginas. Centralizar dentro de célula larga joga o marcador da lista para
longe do texto e estica a linha. Remove só essa declaração; esquerda é o
padrão do CSS, não precisa escrever nada no lugar.

### `aem_largura_ordering.py` — 1ª coluna espremida
A coluna nascia **sem largura**, então a 2ª (descrições longas) tomava o
espaço e o part number quebrava no meio, inclusive no hífen.

A largura cabe o maior **token separado por ESPAÇO**, não a maior célula:
`TQMa8MSNL-AA` é um token só (o hífen faz parte do nome); já
`Starterkit STKa8MxNL set` pode quebrar nos espaços. Assim nome com várias
palavras não infla a coluna.

Mede por largura de caractere (Helvetica-Bold), não por contagem: `W` ocupa
3,4x o que ocupa `I` e part number é cheio de maiúscula — é por isso que uma
largura fixa única servia para uns e cortava outros. **`--fonte 18` é o valor
calibrado no navegador**, já é o default.

### `aem_padronizar_textwithimage.py` — Text with Image fora do padrão
A página de referência da migração (`tqmls1088a-embedded-octal-cortex`, em
`tq-systems-embedded`) difere das outras 133 em três coisas. Os styleIds têm
nome na policy do componente:

```
1718154328384  【Image Position】     Left
1783061491236  【Vertical Alignment】 Center
1718154382437  【Text Wrapping】      Wrap

referência : ['1718154328384']                  imageRatio='40'   spImage preenchido
demais     : ['1718154328384','1783061491236']  sem imageRatio    spImage vazio
```

Aplica os três da referência no **primeiro** `textwithimage` de cada página.

### `aem_deduplicar_containers.py` — a página inteira aparece duas vezes
Em `semiconductors`, 136 das 355 páginas de copia-teste renderizavam o
conteúdo todo duas vezes: em `/renesas` a segunda cópia começava no pixel
15.171 de 31.467. Causa: a armadilha nº 1 (Sling POST faz merge) somada a
mais de uma passada de migrador, cada uma com seu esquema de nome. Nada foi
sobrescrito — foi tudo empilhado.

Onde o conteúdo pode estar:

```
root/containerpy             esquema *_wrap  — INVISÍVEL, nunca renderiza
root/container/<filhos>      cópia A         — renderiza
root/container/content_area  cópia B         — renderiza
```

**Só `root/container` renderiza** (confirmado lendo o HTML servido: os `src`
das imagens citam `/root/container/...` e `/root/container/content_area/...`,
nunca `/root/containerpy/...`). Então `containerpy` é lixo no JCR, sem efeito
na tela; A + B convivendo é a duplicação que o visitante vê. A forma
saudável, que 216 páginas já têm, é `root/container/content_area` e mais
nada.

Antes de apagar, confere bloco a bloco se a cópia que FICA contém tudo o que
a cópia que SAI tem; se não contiver, marca `REVISAR` e não toca. Foi assim
que apareceram 19 páginas em que as cópias divergem de verdade (12 do canon,
onde a cópia A tem o layout trabalhado e a B é a migração plana) e a página
`/canon`, cujo intro e as descrições dos 8 sensores estão **só** no
`containerpy` — conteúdo que ninguém vê e que um faxina cega destruiria.

Comparar asset usa só o nome do arquivo **sem separador**: a mesma imagem
aparece sob três prefixos de DAM e com separadores diferentes conforme a
passada que a gravou (`dg-ab17-m2fmc-320`, `dg-ab17-m2fmc_320`,
`dg-tls1.3-block`). E o texto colapsa espaço depois de tirar pontuação —
sem isso `Its’ compact` e `Its compact` contam como divergência e a página
vai para REVISAR à toa.

A comparação é por **contenção**, não por conjunto: um migrador guardou a
introdução em `text_intro` sozinho e o outro a concatenou dentro de
`text_1`. Por conjunto isso parece bloco exclusivo; por contenção, não.

**Não desempatar por número de componentes.** Em `/altera` a cópia direta
tem 99 componentes contra 57 do `content_area` e é a PIOR: ela é o resultado
de um migrador que achatou as 4 abas do GWI em texto corrido. Mais nós =
mais estrutura perdida.

**Nem sempre o `content_area` é o que fica.** Nas páginas do canon é a cópia
DIRETA que segue o GWI — tem o layout de 2 colunas e os dois botões de
rodapé (que vêm de um `experiencefragment` no GWI e o migrador não traduz).
Daí o `--manter direto`.

**Backup obrigatório.** Apagar subárvore é irreversível e o CSV só guarda o
caminho, então toda execução grava antes o JSON inteiro dos nós em
`<output>_backup.json`. Se algum nó não puder ser lido, nada é apagado.

**`copia-teste` tem mais de um editor.** Conferir `cq:lastModifiedBy` antes
de rodar lote e blindar com `--pular-contendo` a subárvore de quem está
trabalhando nela.

### `aem_corrigir_layout_blocos.py` — os três defeitos de layout do BlockBuilder
Neste design system **o respiro vertical vem do componente `container`**:
`.container > .cmp-container { padding: 50px 25px }`. Os styles de
【Padding - Top/Bottom】 só MUDAM esse valor. Onde o migrador não cria
container, não existe separação nenhuma — e é daí que saem os três casos.

Medido na `/altera` em 18/09/2026, sempre com `?wcmmode=disabled`: o modo de
autoria injeta placeholders de 29px que inflam tudo e enganam a medição.

`--colunas-gwi` — no GWI uma coluna é um `resizablecontainer` com width<12 que
pode ter **vários componentes dentro**. O migrador lê a largura da coluna e
carimba em cada folha separadamente: a coluna de 6 com "intro + botão" virou
dois blocos de 6 lado a lado e empurrou o vídeo para a linha de baixo. Relê o
agrupamento na origem e refaz. Casa por texto normalizado e, se algum membro
não casar de forma inequívoca, **pula e reporta** — remontar coluna no chute
troca conteúdo de lugar.

`--espaco-abas` — dentro de `tabs/item_N` os componentes são filhos diretos,
sem `_wrap`, logo sem padding: as seções ficam coladas (gap 0px, medido).
Embrulha cada filho num container. Usa 【Padding L/R】 = No Padding de
propósito, senão os 25px do padrão empurram o texto da aba para dentro.

`--logo` — o logo do fabricante no GWI não é conteúdo, é a propriedade de
página `manufacturerlogo` (o template do GWI rende no cabeçalho). O migrador
pendurou como imagem no fim do corpo, em largura cheia: 405px de logo na
`/altera`. As duas páginas autorais de referência (`deepx`, `sony`) têm a
propriedade preenchida e **zero** logo no corpo.

> **O template `mai-mae-product-page` NÃO rende `manufacturerlogo`** —
> conferido no HTML servido do `deepx`, que tem a propriedade: zero
> ocorrência. Depois deste flag o logo some da página e não volta no
> cabeçalho. Logo visível é decisão de layout e pede bloco próprio.

**Ponto cego conhecido:** `--colunas-gwi` e `--logo` olham só
`root/container/*`. As 58 páginas que guardam os blocos em
`root/container/content_area/*` passam sem ser avaliadas (7 logos no corpo
ficaram de fora por isso). `--espaco-abas` percorre a árvore toda e não tem o
problema. Corrigir antes de rodar em lote.

Ver `ACHADOS-layout-semiconductors.md` para os números da família e as
decisões tomadas em 18/09/2026.

### `aem_remigrar.py` + `aem_layout.py` — a remigração
O migrador antigo faz conversão **1-para-1 de componente** e achata a
estrutura. O motor novo (`scripts-bruno/aem_layout.py`) devolve uma ÁRVORE
(Page → Section → Row → Column → Block → Panel) e emite no dialeto das páginas
autorais da Anion. O `aem_remigrar.py` é só o driver.

**Destino:** `/products/semiconductors-remigration` — árvore de rascunho,
criada do zero. `/semiconductors` NÃO é tocada, então as edições manuais do
Bruno no `/canon` ficam onde estão.

**Escopo:** 135 páginas — tudo que a Anion ainda não autorou. Fora:
`sony-image-sensors` (216) e `deepx` (3). Conferido contra o global2: não há
página autoral fora desses dois ramos.

#### A regra que sustenta o motor
> Cada filho de topo do corpo do GWI que carrega conteúdo renderizável vira
> UM container de seção no destino, na mesma ordem.

Testada por falsificação sobre 212 pares origem↔autoral: **precisão 99,3%,
recall 96,3%**. É ela que resolve a contradição que travou o diagnóstico por
horas — a `deepx` tem 1 container e a `sony` tem 4 porque as origens delas têm
1 e 4 blocos de topo. Não há duas gramáticas Anion; há uma regra e duas
origens. **Fronteira de seção é dado da origem, não julgamento estético.**

Os dois preditores "óbvios" foram falsificados e NÃO são caminho principal:
spacer `&nbsp;` (precisão 16,2%) e heading de nível mais alto (16,4%).

#### Quatro bugs que só o piloto revelou
1. **A descida parava cedo demais.** O bloco de `pageproperties` é irmão do
   corpo real em 266 páginas; contá-lo fazia a página inteira virar UMA seção.
2. **`width=12` lido como coluna.** Largura 12 é largura CHEIA; confundir os
   dois fez um item de aba com vários textos virar uma linha de 6 colunas.
3. **Nó com títulos E colunas** era tratado como uma linha só, descartando em
   silêncio tudo que não fosse coluna — a aba renderizava as 3 colunas e
   perdia "Overview", "Portfolio At-a-Glance" e "Why Macnica?".
4. **Aba precisa de `layout=responsiveGrid`** além de `jcr:title` e
   `cq:panelTitle` — e o `cq:panelTitle` do GWI às vezes é `String[]`, o que
   duplicava o rótulo da aba.

#### Onde o respiro vertical nasce
Não existe margem entre irmãos neste design system (gap medido 0px nas duas
referências, em todos os níveis). Tudo vem do `container`
(`padding: 50px 25px` no desktop, 30/15 abaixo de 1050px). Por isso:
- `root/container` nunca recebe style (a policy já carimba padding zero);
- um título abre **subseção**, e cada subseção ganha container com padding só
  no eixo vertical (`Pad L/R = No Padding`, para não deslocar o texto). Sem
  isso os títulos nascem colados — o título tem `padding-bottom` e nenhum
  `padding-top`.

#### Decisões codificadas (time, 18/09/2026)
- **fundo é propriedade de SEÇÃO**, nunca de bloco: a zebra `#fff`/`#f7f7f7`
  por bloco morreu. Seção de apoio usa `rgb(247,247,247)`, como a `sony`;
- **`download` vira tabela** Title/Download, como a Anion fez;
- **`cq:responsive` é proibido**: coluna é `flexcontainer`, sempre com
  `1719484596357` (sem ele as colunas não empilham abaixo de 1050px — medido
  a 390px na própria `deepx`, com botões estourando a viewport);
- **sem `spImage`**: experimento A/B deu 0px de diferença em 32 medições;
- **`sling:resourceType = maeproductpage`**, não `page` — sem isso o diálogo
  das propriedades `pd_*` nem aparece.

#### Resultado no piloto (`/altera`)
```
faltando = 0    sobrando = 0    pendências = 0
```
O `experiencefragment` (109 das 135 páginas) voltou — era a maior perda de
conteúdo — e o `h1` duplicado sumiu.

Varredura nas 135: **0 falhas, 421 seções (3,1/página), 44 pendências**, todas
de origem ou de escopo — `pagesectionlisting`/`productlisting` sem componente
alvo (22), tag inválida no GWI (10), `relatedsuggestions` com
`listFrom=static` mas sem `pages` apontando para `sony-image-sensors` (9),
imagem sem `fileReference` (2), formulário (1).

### `aem_clone_subtree.py` — substituir conteúdo de destino que já existe
O Sling POST faz **merge**: gravar por cima sem limpar deixa o container velho
e o novo na mesma página, renderizando os dois. Por isso cada página passa por
`jcr:content/root :operation=delete` antes de receber o payload.

**Não renomeia** — origem e destino com nomes diferentes (maiúsculas) geram
página nova e deixam a antiga órfã (foram 29 em `tq-systems`). E **não
conserta o canonical**: rode o `aem_fix_canonical.py` depois, sempre.

---

## Ordem recomendada

```bash
# depois de um clone
python3 aem_fix_canonical.py    --raiz <alvo> --executar
python3 aem_diff_conteudo.py    --destino <alvo> --origem <gwi>

# conteúdo
python3 aem_deduplicar_containers.py --raiz <alvo> --executar
python3 aem_restaurar_specs.py       --destino <alvo> --origem <gwi> --executar
python3 aem_corrigir_divergencia.py  --destino <alvo> --origem <gwi> --executar
python3 aem_reconstruir_blocos.py    --destino <alvo> --origem <gwi> --executar

# aparência — nesta ordem: o texto muda o que a largura precisa medir
python3 aem_corrigir_lixo_markup.py  --raiz <alvo> --executar
python3 aem_corrigir_alinhamento.py  --raiz <alvo> --executar
python3 aem_padronizar_textwithimage.py --raiz <alvo> --executar
python3 aem_largura_ordering.py      --raiz <alvo> --executar

# layout dos blocos (depende da origem para reagrupar coluna)
python3 aem_corrigir_layout_blocos.py --raiz <alvo> --todos          # diagnóstico
python3 aem_corrigir_layout_blocos.py --raiz <alvo> --todos --executar
```

A largura vem por último de propósito: consertar os part numbers corrompidos
tirou duas tabelas do teto de 260px para 163px e 137px. Medir antes teria
otimizado em cima do estado quebrado.
