# Layout de `semiconductors` no copia-teste — achados de 18/09/2026

Levantamento a partir da `/altera`, que o Hazael apontou como exemplo. As
cinco queixas dele saem de **três defeitos**, e os três têm a mesma raiz.

Só a `/altera` (página-raiz) foi alterada, como piloto, com backup. **Nada
mais foi escrito.** As páginas do `sony` ficaram de fora por pedido dele.

---

## A raiz: neste design system o respiro vertical vem do `container`

O CSS do global2 (`clientlib-site`) não dá margem nenhuma entre componentes
irmãos. O que separa um bloco do outro é o componente **container**:

```css
.container > .cmp-container            { padding: 50px 25px }   /* padrão */
.container.container-padding-height_small  > .cmp-container { padding-top:30px; padding-bottom:30px }
.container.container-padding-height_large  > .cmp-container { padding-top:50px; padding-bottom:50px }
.container.container-padding-height0       > .cmp-container { padding-top:0;    padding-bottom:0 }
```

Ou seja: **todo container já rende 50px em cima e 50px embaixo por padrão**, e
os styles de 【Padding - Top/Bottom】 só mudam esse número. Onde o migrador não
cria container, não existe 1px de separação.

Medido na `/altera` com `?wcmmode=disabled` — importante, porque o modo de
autoria injeta placeholders de 29px que inflam tudo e enganam a medição:

```
nível de página, entre blocos ....... 100px   (dois containers, 50+50)
dentro das abas ..................... 0px     (não há container nenhum)
```

Isto não é bug do CSS nem do template: é o preço de o migrador embrulhar uns
blocos e outros não. As duas páginas autorais de referência do global2
(`deepx` e `sony`, feitas pela Anion) usam containers de SEÇÃO — um container
com vários componentes dentro — e não um container por componente.

---

## Os três defeitos

### 1. Coluna do GWI achatada — o botão e o vídeo no lugar errado

No GWI a largura mora em `cq:responsive/default/width` do container que
embrulha o bloco, e **uma coluna pode ter vários componentes dentro**:

```
resizablecontainer_903354025                 (a linha)
  resizablecontainer_c    width=6            <- coluna 1
    text_copy             (intro)
    button_copy           (Request a Quote)
  resizablecontainer      width=6            <- coluna 2
    video_copy            (vídeo do YouTube)
```

O migrador lê a largura da **coluna** e carimba em cada **componente folha**
separadamente. A coluna de 6 com "texto + botão" virou dois blocos de 6 lado a
lado, e o vídeo — que devia ser a segunda coluna — foi empurrado para a linha
seguinte:

```
ANTES (copia-teste)          DEPOIS (corrigido)         GWI
[ intro   ][ botão  ]        [ intro   ][ vídeo  ]      [ intro   ][ vídeo ]
[         ][ vídeo  ]        [ botão   ][        ]      [ botão   ][       ]
```

Confirmado por medição, não por olho:

```
antes   text colx=50 w=600 y=515 | button colx=750 y=555 | embed colx=750 y=712
depois  text colx=50 w=600 y=515 | embed  colx=750 y=515 | button colx=50 y=795
```

### 2. Seções coladas dentro das abas

Os componentes dentro de `tabs/item_N` são filhos **diretos** do container da
aba — o migrador não cria `_wrap` ali. Sem container, sem padding, e
"Portfolio At-a-Glance", "Where these devices fit" e "Why Macnica?" encostam
no parágrafo de cima.

```
antes   gap = 0px   entre todos os elementos da aba
depois  gap = 60px  (container com 【Padding T/B】 Small = 30px+30px)
```

Usei 【Padding - Left/Right】 = **No Padding** de propósito: o padrão do
container é `50px 25px`, e esses 25px empurrariam o texto da aba para dentro,
desalinhando com o resto. Só o eixo vertical muda.

### 3. Logo do fabricante virou imagem gigante no fim da página

No GWI o logo **não é conteúdo**: é a propriedade de página
`jcr:content/manufacturerlogo`, que o template do GWI rende no cabeçalho, ao
lado do `pageTitle`. O migrador não traduz propriedade de página — tratou o
logo como imagem e pendurou no fim do corpo, em largura cheia. Na `/altera`
eram **405px** de logo fechando a página.

As duas páginas de referência concordam entre si: `manufacturerlogo`
preenchido e **zero** logo no corpo.

> **Ponto para a reunião.** O template `mai-mae-product-page` **não rende**
> `manufacturerlogo` na página — conferido no HTML servido do `deepx`, que tem
> a propriedade preenchida: zero ocorrência do logo no HTML. Então, depois da
> correção, o logo **some da página** (fica igual ao `deepx` e ao `sony`) e
> **não** reaparece no cabeçalho como no GWI. Se o time quiser o logo visível,
> isso é decisão de layout e precisa de um bloco de conteúdo próprio — a
> propriedade sozinha não resolve.

Na gravação a referência passa a apontar para o DAM de `copia-teste` quando o
gêmeo existe lá (existe na maioria); senão fica a do GWI, que ao menos
renderiza.

---

## As outras duas queixas: não são defeito, são o design system

### Títulos sem negrito

```css
.cmp-title h1 { color:#7f1080; font-weight:500; letter-spacing:.1em }
.black .cmp-title .cmp-title__text { color:#000 }
```

Roxo e peso 500 é o **padrão do global2**, e as duas páginas autorais de
referência usam esse padrão sem mexer. A policy do `title` oferece só **cor**
(Black/White), alinhamento e tamanho de heading — **não existe opção de
negrito**. Aplicar "Black" deixaria preto, mas ainda peso 500.

**Decisão do Hazael (18/09): fica como está**, é o layout novo. Vale a regra do
time — layout pode e deve diferir do GWI; conteúdo, não.

### Dois `h1` na mesma página

A `/altera` tem dois:

```
h1  Buy Altera Semiconductor, SoC, FPGA & Power Products   <- jcr:title, injetado pelo migrador
h1  Leading Altera FPGAs, SoCs, and CPLDs, supported by Macnica   <- o h1 real do GWI
```

No GWI a primeira string aparece só como `pageTitle`, pequena, no cabeçalho —
não é heading. O migrador promoveu a propriedade a bloco de conteúdo.

O `deepx` também abre com o título da página em `h1`, mas lá ele **não é**
duplicata de um segundo heading. Aqui são dois `h1` competindo, o que é
problema de SEO e faz a página abrir com a string de SEO em vez da manchete.

**Decisão do Hazael (18/09): documentar e deixar como está por enquanto.**

---

## Números da família (355 páginas, `sony` fora)

Varredura somente-leitura, `aem_corrigir_layout_blocos.py` em modo diagnóstico:

```
páginas com algo a consertar ....  47
ações .........................  237
    colunas-gwi ...............   98
    espaco-abas ...............   33
    logo ......................   26
páginas puladas por insegurança .  33   (80 grupos)
```

Por fabricante (ações):

```
design-gateway 69 | deepx 19 | altera 16 | ambarella 7 | i-chips 7
infineon 7 | namuga 7 | sitime 6 | canon 6 | renesas 5 | toppan 5 | on-semi 2
```

Estado estrutural (138 páginas não-sony):

```
blocos em root/container/container ....  80
blocos em root/container/content_area .  58
abas sem container interno ............  33 abas em 7 páginas (de 38 abas)
logo como imagem no corpo .............  33 páginas
manufacturerlogo preenchido ...........   1 página (a /altera, já corrigida)
containerpy (nó que nunca renderiza) ..  111 páginas
```

---

## O que ainda NÃO está resolvido

**1. Ponto cego do script: `content_area`.** 58 páginas guardam os blocos em
`root/container/content_area/...` em vez de `root/container/...`. As checagens
de **coluna** e de **logo** olham só o segundo caminho, então essas 58 páginas
passam sem serem avaliadas. Já dá para medir o efeito: a varredura achou 26
logos no corpo, e o levantamento estrutural achou 33 — **as 7 que faltam são
exatamente as de `content_area`**. Tem que ser corrigido antes de qualquer
execução em lote. (A checagem de **abas** percorre a árvore inteira e não tem
esse problema.)

**2. 33 páginas puladas por insegurança.** Quando um membro do grupo de coluna
não casa com a origem de forma inequívoca (ou casa com 3 blocos ao mesmo
tempo, como na `/ambarella`), o script **não adivinha**: pula a página e
reporta. Remontar coluna no chute troca conteúdo de lugar. Concentram-se em
`design-gateway` (18), `canon` (13), `ambarella` (12), `altera` (12),
`renesas` (10). Precisam de conferência manual ou de um critério de
casamento melhor.

**3. `containerpy` em 111 páginas.** Nó irmão que **nunca renderiza** (só
`root/container` chega à tela). É lixo no JCR, sem efeito visual — mas em
algumas páginas ele guarda conteúdo que a cópia visível não tem (na
`agilex-3-fpga-and-soc-overview` o `text_intro` está só ali). Faxina cega
destrói conteúdo; ver `aem_deduplicar_containers.py`.

**4. A causa continua no migrador.** Os três defeitos nascem do `BlockBuilder`
do `aem_lib.py`. Consertar no destino resolve as páginas de hoje; toda
remigração traz tudo de volta. O ideal é corrigir o `BlockBuilder`:
agrupar por coluna da origem, embrulhar o interior das abas e mandar o logo
para `manufacturerlogo`.

---

## O que foi feito

| | |
|---|---|
| Alterado | `/semiconductors/altera` (só a página-raiz) |
| Backup | `altera_root_backup.json` (jcr:content inteiro, antes da escrita) |
| Conferência | medição do layout renderizado, antes e depois, com `?wcmmode=disabled` |
| Reversível | sim — o backup tem o estado anterior completo |

Ferramenta nova: `aem_corrigir_layout_blocos.py` (diagnóstico por padrão,
backup obrigatório, idempotente, trava de escrita só em `copia-teste`).

Dois ajustes no `aem_screenshot.py`: `networkidle` não assenta no author
(polling do editor) — agora cai para `load`; e `--publicado` renderiza com
`?wcmmode=disabled`, sem os placeholders que inflam o espaçamento.
