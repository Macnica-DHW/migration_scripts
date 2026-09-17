# Taxonomia de tags — achados (11/09/2026)

Investigação disparada por 3 páginas de exemplo que o Bruno passou
(`semiconductors/sony`, `.../sony-image-sensors/sony-imx174llj-c`,
`.../sony-image-sensors/sony-imx273llr-c`) + a página de referência de
Color Grading. Tudo abaixo é lido direto da API (`.json`), nada foi
escrito em nenhum lado.

**Correção ao handoff anterior**: a seção 5.7 do documento de handoff
dizia que "a taxonomia de tags nova do GLOBAL2 ainda não existe". Isso
está errado, ou mudou desde então — **a taxonomia existe, está populada,
e já está em uso em centenas de páginas**, tanto em GWI quanto em
GLOBAL2. Ver seção 1.

---

## 1. A taxonomia existe e é usada em 2 namespaces por região

| Região | Namespace | Onde | Categorias |
|---|---|---|---|
| Americas | `mai:` | `/content/cq:tags/mai/` | 14: `business-categories`, `manufacturers`, `page-type`, `product-category`, `resolution`, `shutter-type`, `sensor-type`, `optical-format`, `interface`, `Pixel-size`, `product-families`, `technology`, `years`, `tbd` |
| Europa | `macnica-atd-europe:` | `/content/cq:tags/macnica-atd-europe/` | 18: as mesmas + `sensor-category`, `ar-coating`, `optic-type`, `location-type`, `artificial-intelligence`, `type` |

**O GWI já usa o namespace `mai:`** nas suas próprias páginas — não é algo
que o GLOBAL2 inventou. Isso significa que, para a região Americas, a
migração de tags pode em grande parte ser **cópia direta** de
`cq:tags`/`manufacturer`/`businessCategories`/etc. do GWI para o
destino, sem tradução — desde que a tag de origem seja válida (ver seção
3, porque nem sempre é).

`macnica-atd-europe:` tem 4 categorias que `mai:` não tem
(`sensor-category`, `ar-coating`, `optic-type`, `location-type`). Migrar
conteúdo de Europa para `mai:` vai perder essas 4 categorias — não há
correspondência.

`product-families` e `technology` em `mai:` são **duas categorias
paralelas com os mesmos 4 filhos** (`pregius`, `pregius-s`, `starvis`,
`starvis-ii`) — parece duplicação por renomeação incompleta em algum
momento, não dois conceitos diferentes. As páginas de produto usam
`product-families` (ex: `pd_productFamilyText`, `productFamily`); a
página de categoria (`sony`, o nó pai) tem as duas.

## 2. Variação por template / resourceType — não é universal

Nem toda página tem as mesmas propriedades de taxonomia. Varia por
**resourceType da página**, que por sua vez é definido pelo template:

| resourceType | Template(s) associados | Tem propriedades de taxonomia? |
|---|---|---|
| `macnicaglobal2/components/maeproductpage` | `mai-mae-product-page`, `atd-europe-mae-product-page` | **Sim** — `manufacturer`, `businessCategories`, e (Americas) `interface`, `pixelsize`, `resolution`, `shuttertype`, `opticalformat`, `sensorcategory`/`sensortype` |
| `macnicaglobal2/components/page` | `mai-page-content`, `mai-page-top`, `atd-europe-page-content`, `atd-europe-page-top` | **Não** — nenhuma tag, é página de conteúdo genérico/categoria |
| `macnicaglobal2/components/technicalarticlepage` | `mai-technical-article-page`, `atd-europe-technical-article-page` | **Parcial** — só `cq:tags` (ex: `['macnica-atd-europe:business-categories/image-sensors', 'macnica-atd-europe:manufacturers/sony']`), sem as propriedades dedicadas (`interface`, `resolution` etc.) |

**Amostragem real, por árvore:**

| Árvore | Total páginas | Template dominante | % com template de produto |
|---|---|---|---|
| `macnicaglobal2/.../semiconductors` | 217 | `mai-mae-product-page` (215x) | 99% |
| `macnicaglobal2/.../boards-modules/tq-systems` | 143 | `mai-page-content` (142x) | 0,7% (pendência já conhecida do handoff) |
| `macnicaglobal2/eu/atd-europe` (5 níveis) | 356 | `atd-europe-technical-article-page` (235x) | 16% (57x mae-product-page) |

**Implicação prática**: a taxa de "página tem tag" não é sobre a árvore
de produto em si, é sobre qual template ela usa. `tq-systems` está quase
toda sem tags não porque falte dado, mas porque está com o template
errado (Content Page em vez de Product Page) — mesma causa raiz já
documentada no handoff para o problema de conteúdo.

## 3. Bug sistemático: tags gravadas erradas na ORIGEM (GWI)

O handoff já documentava 1 bug (sufixo `-1` espúrio em
`relatedsuggestions`). Esta investigação achou outros, num lugar
diferente: as **propriedades dedicadas** de página de produto
(`manufacturer`, `sensorcategory` etc.), não os arrays `cq:tags`.

**Importante**: dentro do array `cq:tags` propriamente dito, a varredura
completa das 355 páginas de `semiconductors` (GWI) não achou nenhuma
categoria inválida — as 10 categorias usadas ali batem 100% com a lista
oficial. O problema está nas propriedades soltas (`manufacturer`,
`sensorcategory`, etc.), que ficam fora do array `cq:tags`.

### 3.1 — `manufacturer` no singular (o mais frequente)

A categoria válida é `mai:manufacturers` (plural). Amostra de
`boards-modules` (11 fabricantes, GWI):

| Fabricante | Valor gravado | Válido? |
|---|---|---|
| iei | `mai:manufacturer/iei` | ❌ singular |
| ibase | `mai:products/ibase` | ❌ namespace errado (`products` não existe) |
| reflex-ces | `mai:manufacturers/reflex-ces` | ✅ |
| mpression | `mai:manufacturer/mpression` | ❌ singular |
| hitek-systems | `mai:manufacturers/hitek-systems` | ✅ |
| terasic | `mai:manufacturers/terasic` | ✅ |
| tq-systems | `mai:manufacturer/tq-systems` | ❌ singular |
| connect-tech | `mai:manufacturer/connect-tech` | ❌ singular |
| silex | `mai:manufacturer/silex` | ❌ singular |
| ienso | `mai:manufacturer/ienso` | ❌ singular |
| transcend | `mai:manufacturer/transcend` | ❌ singular |

**7 de 11 (64%) quebrados** nessa amostra — é o bug mais frequente
encontrado. Correção é mecânica: `manufacturer/` → `manufacturers/`
(exceto o caso `ibase`, que precisa reescrever o namespace inteiro).

### 3.2 — `sensorcategory` sempre aponta para uma categoria que só existe no OUTRO namespace

Toda página de sensor de imagem Sony amostrada (15/15, 100%) tem:

```
sensorcategory: mai:sensor-category/area-sensors
```

`mai:sensor-category` **não existe** — a categoria correta chamada
`sensor-category` existe, mas só em `macnica-atd-europe:` (namespace de
Europa), não em `mai:`. Parece que o valor foi copiado do lado europeu
sem trocar o prefixo do namespace.

Todas essas mesmas páginas **já têm** a propriedade `sensortype`
(sem "category") preenchida corretamente: `mai:sensor-type/cmos`. A
correção mais simples e segura é **descartar `sensorcategory` inteira
e usar só `sensortype`** — não há perda de informação, é redundante.

**Confirmado no GLOBAL2 real**: a página já migrada
`sony/sony-image-sensors/sony-imx174llj-c` (que tem histórico de
replicação, foi migrada por alguém do time) **não tem `sensorcategory`**
— foi corretamente descartada, não "consertada". Isso valida a estratégia:
tag inválida = omitir, não adivinhar.

### 3.3 — Segmento errado dentro do mesmo namespace

```
shuttertype: mai:shutter-type/polarization   <- inválido
```

`polarization` é filho de `mai:sensor-type` (existe, é um tipo de
sensor), não de `mai:shutter-type` (que só tem `global-shutter` e
`rolling-shutter`). Mesma categoria de bug do `sensor-category`/
`sensor-type`: o valor certo existe na taxonomia, só está pendurado no
segmento pai errado.

Também achados, sem correspondência em NENHUM namespace:
```
sensortype: mai:sensor-type/cmos             <- não existe (nem cmos nem "CMOS" como filho)
sensortype: mai:sensor-type/cmos-polarized   <- não existe
```
Esses dois não têm conserto óbvio — `cmos` não é um "tipo de sensor" na
taxonomia atual (os filhos reais de `sensor-type` são `polarization`,
`sensswir`, `time-of-flight-(tof)`, `ultraviolet-(uv)` — são todos tipos
*especiais*, "CMOS comum" parece não ter tag própria porque é o padrão
implícito). Precisa decisão humana: criar a tag, ou tratar "CMOS padrão"
como ausência de tag.

## 4. Resumo dos 4 padrões de bug encontrados

| # | Padrão | Exemplo | Frequência observada | Correção |
|---|---|---|---|---|
| 1 | Singular em vez de plural | `manufacturer/x` → devia ser `manufacturers/x` | 7/11 (64%) em boards-modules | Mecânica: trocar o segmento |
| 2 | Namespace da região errada | `mai:sensor-category/...` → só existe em `macnica-atd-europe:` | 15/15 (100%) das páginas Sony testadas | Descartar (há propriedade irmã correta: `sensortype`) |
| 3 | Segmento pai errado, tag existe em outro lugar da mesma taxonomia | `shutter-type/polarization` → é filho de `sensor-type` | 1 caso observado | Mecânica: mover para o pai certo |
| 4 | Tag sem correspondência em nenhum namespace | `sensor-type/cmos`, `sensor-type/cmos-polarized` | 2 casos observados | Decisão humana (criar tag ou omitir) |

Dentro do array `cq:tags` (355 páginas de semiconductors, 118
ocorrências de tag total): **0% de erro**. O problema está concentrado
nas propriedades dedicadas de produto (`manufacturer`, `sensorcategory`,
`shuttertype`...), não no campo de tags genérico.

## 5. Sugestão de tags — como aplicar nas páginas migradas

Com os dados acima, a extração de tags para `aem_migrate.py` pode seguir
esta regra (ainda **não implementada**, conforme pedido):

1. **Copiar direto do GWI** as propriedades que já usam `mai:` e batem
   contra a taxonomia real: `businessCategories`, `interface`,
   `resolution`, `Pixel-size`, `product-category`, a maior parte de
   `manufacturers` já corretos, `technology`/`product-families`.
2. **Corrigir mecanicamente** antes de copiar:
   - `manufacturer/` (singular) → `manufacturers/`
   - `mai:sensor-category/*` → descartar; usar `sensortype` se presente
   - qualquer segmento de `shutter-type` que só exista em `sensor-type`
     → mover de categoria
3. **Validar contra a árvore real** (`/content/cq:tags/mai/...` e
   `/content/cq:tags/macnica-atd-europe/...`) antes de gravar qualquer
   tag — se o valor não existir na taxonomia depois da correção
   mecânica, **omitir e reportar como pendência**, nunca inventar.
4. **Só aplicar em páginas com template de produto**
   (`maeproductpage`/`technicalarticlepage`) — páginas de categoria/
   conteúdo genérico (`components/page`) não usam essas propriedades no
   padrão observado.
5. **Region-aware**: se a origem é Europa, usar `macnica-atd-europe:`;
   se é Americas, usar `mai:`. Não misturar — foi misturar que causou o
   bug #2 acima.

~~Nenhuma tag foi escrita em nenhuma página ainda.~~ **Implementado em
11/09/2026** — ver seção 6 abaixo.

---

## 6. Implementação (11/09/2026)

Feita em `aem_lib.py` (`load_tag_taxonomy`, `build_product_tags`,
`build_tag_props`, `detect_tag_region`) + integração em
`aem_migrate.py` (modo completo, desliga com `--sem-tags`).

**Antes de implementar, confirmado de novo com dado ao vivo** (não só o
documento): lida a árvore real dos dois namespaces, e comparado um par
origem/destino real —
`sony-image-sensors/sony-imx174llj-c` no GWI vs a mesma página **já
migrada por outra pessoa do time** no GLOBAL2 (achado que valida a
estratégia, seção 3.2). Isso corrigiu o modelo original:

- **O nome da propriedade não muda** entre GWI e GLOBAL2
  (`manufacturer`, `businessCategories`, `resolution`, `shuttertype`,
  `pixelsize`, `opticalformat`, `interface`, `productcategory`,
  `productFamily`) — é cópia de propriedade com o mesmo nome, corrigindo
  só o SEGMENTO do valor quando necessário. Não existe remapeamento
  propriedade→categoria com nome novo.
- **O formato do valor não muda** (string solta ou lista) — copiado como
  veio.
- A página de referência confirma os descartes: **`sensorcategory` e
  `sensortype` (com `cmos`) foram omitidas**, não inventadas — bate
  exatamente com o que a implementação produz.

**Dois achados NOVOS, não previstos no levantamento original:**

1. **Propriedades "sujas" com sufixo numérico na origem** —
   `shuttertype1`, `interface1`, `sensortype1`, `opticalformat1`,
   `pixelsize1` — sempre apontando para o namespace da região ERRADA
   (`macnica-atd-europe:` numa página Americas) ou para uma categoria
   com sufixo que não existe em lugar nenhum (`shutter-type-2`,
   `optical-format-1`, `sensor-type-1`). Exemplo real
   (`sony-imx174llj-c`, GWI):
   ```
   shuttertype1: macnica-atd-europe:shutter-type/global-shutter
   interface1:   macnica-atd-europe:interface/lvds-sub-lvds
   sensortype1:  macnica-atd-europe:sensor-type-1/cmos
   ```
   Tratado como resíduo e **ignorado por completo** (nem pendência) — a
   propriedade sem sufixo já carrega o valor correto da região certa.

2. **`sensor-type/cmos` e `sensor-type/cmos-polarized` EXISTEM em
   `macnica-atd-europe:`**, só não existem em `mai:`. O achado 3.3/#4
   original ("sem correspondência em NENHUM namespace") estava certo
   para Americas mas incompleto de forma geral — é uma pendência
   **só quando a origem é Americas**. Página de Europa com
   `sensortype: macnica-atd-europe:sensor-type/cmos` migra normalmente,
   sem pendência. Também achada uma diferença ortográfica entre regiões:
   `ultraviolet-(uv)` em `mai:` vs `ultraviolet(uv)` (sem hífen antes do
   parêntese) em `macnica-atd-europe:`.

**Comportamento final, testado com `--dry-run` nos dois pares
região/página real:**
- Americas (`sony-imx174llj-c`): 9 propriedades de tag migradas,
  batendo 100% com a página já migrada por outra pessoa do time; 1
  pendência (`sensortype=cmos`, decisão humana, como já previsto).
- Europa (`atd-europe/en/solutions/cv75`): 4 propriedades migradas com
  namespace `macnica-atd-europe:` em todas, sem mistura de região.

**Fora do escopo desta implementação** (não pedido, não confirmado):
campos `pd_*` (`pd_productFamilyText`, `pd_pixelSize`, `pd_resolution`,
`pd_interface`, `pd_description`, `pd_modelName`,
`pd_isModelNameLinkToPage`, `pd_colorMonochrome`) vistos na página já
migrada — parecem duplicar os mesmos dados num formato do componente de
"Product Details" do template, mas isso não foi confirmado e não estava
na regra pedida (seção 5). Fica como pendência conhecida, não
implementada.

---

## 7. Correção: o filtro por template estava errado (13/09/2026)

Achado ao rodar de verdade em `copia-teste/.../macnica-products`.

A regra 4 da seção 5 dizia "só aplicar em páginas com template de
produto (`maeproductpage`/`technicalarticlepage`)", e a primeira
implementação filtrava por `sling:resourceType`. **Isso estava errado** e
descartava tags **em silêncio**:

| Página (GWI) | resourceType | Tags que tinha | Filtro fazia |
|---|---|---|---|
| `streal` | `…/page/productpage` | `manufacturer`, `businessCategories`, `cq:tags` | descartava as 3 |
| `smpte-st-2110-ip-core-package` | `…/page/basepage` | `cq:tags` | descartava |

Levantamento em `macnica-products` + `boards-modules` (200 páginas)
mostra que o template **não** é o critério:

| resourceType | Com tags | Sem tags |
|---|---|---|
| `…/page/productpage` | **168** | 18 |
| `…/page/maeproductpage` | 17 | 0 |
| `…/page/basepage` | 1 | 4 |

Ou seja: `productpage` (que o filtro rejeitava) é **10x mais comum** que
`maeproductpage` entre as páginas com tag. O filtro teria perdido tag em
~90% das páginas dessas árvores, sem avisar — exatamente o que a regra
"nada some em silêncio" existe para impedir.

**Correção**: o porteiro passou a ser o **dado**, não o template — se a
página tem propriedade de tag, migra. `PRODUCT_TAG_RESOURCE_TYPES` ficou
só como informação. A validação contra a taxonomia real continua
igual, então uma tag inválida numa `basepage` continua virando pendência
em vez de ser gravada torta.

Efeito medido em `macnica-products`: de 12 para **19 tags** migradas.

**Lição para o levantamento**: a seção 2 ("variação por template") estava
certa sobre onde a taxonomia é *esperada*, mas virou regra de filtro
sem ter sido testada como tal. Amostra por template ≠ critério de
migração.

---

## Apêndice — Color Grading (achado, implementação adiada a pedido do Bruno)

"Alternative background Color Grading" do `guidelines-to-follow.txt` **não
é uma tag nem propriedade nomeada** — é o campo `backgroundColor` do
componente `container` (não da página), habilitado pela policy do
container:

```
policy: macnicaglobal2/components/content/container/policy_1586276378410700
  backgroundColorEnabled: true
  allowedColorSwatches: [#fbf5f9, #7f1080, #b20080, #3b1e83,
                          #007ab6, #00851c, #ec6e00, #000000]
```

Na página de referência (`test-gigadevice`), vários containers usam
`backgroundColor` com valores RGB que não batem exatamente com o swatch
(`rgb(235,235,235)`, `rgb(255,255,255)`, `rgba(0,0,0,0.1)`), sugerindo
que o campo aceita cor livre além da paleta oficial de 8.

Em aberto para quando isso for retomado: qual container da página recebe
a cor (o pai único? alternar entre blocos?), e qual das cores conta como
"alternative" pro guideline do cliente — branco/vazio parece ser o
default, então "alternative" é provavelmente qualquer uma das outras 7.
