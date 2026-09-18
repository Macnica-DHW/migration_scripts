# Scripts de migração AEM — GWI → GLOBAL2

Três scripts sobre uma biblioteca compartilhada. Substituem os 14 scripts
soltos da pasta `files (1)`, que duplicavam a mesma lógica em cada arquivo.

```
aem_lib.py      biblioteca compartilhada (não se roda direto)
aem_tree.py     EXPLORAR   — árvore completa de qualquer caminho
aem_migrate.py  MIGRAR     — criar páginas + conteúdo + clonar
aem_verify.py   CONFERIR   — comparar origem vs destino
```

## Antes de começar

A autenticação vem do `.env` na pasta acima (`../.env`), campo `AEM_COOKIES`.
Se estiver vazio, os scripts pedem o cookie via prompt, como antes.

```bash
# conferir o que está configurado (não toca na rede)
python3 aem_lib.py
```

Para pegar o cookie: logar no AEM → F12 → Network → "Preserve log" → abrir
uma página → clicar numa requisição 200 do domínio do AEM → botão direito →
Copy → **Copy as cURL (bash)** → copiar só o que vem depois de `-b`, sem as
aspas. Expira em algumas horas.

---

## 1. `aem_tree.py` — explorar

Passa **um** caminho, ele desce tudo sozinho. Só leitura.

```bash
# o que existe na instância inteira, 2 níveis
python3 aem_tree.py /content --max-depth 2

# tudo do GWI
python3 aem_tree.py /content/macnicagwi

# uma categoria, contando tipos de componente
python3 aem_tree.py /content/macnicagwi/americas/mai/en/products/semiconductors --componentes
```

Saída: árvore no terminal, CSV por nó, e um resumo com templates em uso,
tipos de componente encontrados e os filhos diretos da raiz.

`--componentes` é o que responde *"que componentes existem aqui que o
migrate ainda não sabe tratar?"* — compare o ranking com a lista de tipos
suportados.

| Flag | Para quê |
|---|---|
| `--max-depth N` | Limita quantos níveis descer |
| `--so-paginas` | Pula pastas (mas continua descendo nelas) |
| `--componentes` | Conta os `sling:resourceType` de cada página |
| `--sem-arvore` | Só CSV e resumo, sem o desenho |

---

## 2. `aem_migrate.py` — migrar

Três modos, porque criar, migrar conteúdo e clonar são a mesma operação
com origens diferentes.

```bash
# SEMPRE simular primeiro
python3 aem_migrate.py --source /content/macnicagwi/.../semiconductors --dry-run

# conferir o CSV, então rodar de verdade
python3 aem_migrate.py --source /content/macnicagwi/.../semiconductors
```

| Modo | Comando | O que faz |
|---|---|---|
| completo (padrão) | *(sem flag)* | Lê do GWI, traduz componentes, cria página + conteúdo |
| estrutura | `--so-estrutura` | Só página + título + nome + template |
| clone | `--modo-clone` | Origem já é GLOBAL2: copia fiel, troca só o template |

**Destino**: derivado automaticamente — troca o prefixo do site por
`copia-teste` e preserva o resto. Sobrescreva com `--target`.

**Reescrita de links** (ligada por padrão): troca só o prefixo, o resto do
caminho fica igual.

```
/content/macnicagwi/americas/mai/en/x  →  /content/macnicaglobal2/americas/mai/en/x
```

Aponta para `macnicaglobal2` — o destino **final** — para as páginas já
nascerem com os links definitivos, não para `copia-teste`. Muda com
`--link-para`, desliga com `--sem-reescrever-links`.

| Flag | Para quê |
|---|---|
| `--dry-run` | Simula sem escrever. **Rode sempre antes** |
| `--sem-hide-in-nav` | NÃO marca "Hide in Navigation" (por padrão marca — diretriz do cliente) |
| `--template-title` | Título do template (buscado em `/conf`) |
| `--sem-reescrever-links` | Mantém links apontando para o GWI |
| `--skip-path-contains` | Ignora caminhos com esse texto |
| `--sem-tags` | Não copia/corrige tags de taxonomia (manufacturer, businessCategories...) |
| `--sem-seo` | Não copia o SEO curado da origem (pageTitle, navTitle, keywords) |
| `--inicio N` / `--limite N` | Processa só uma fatia da árvore — ver abaixo |

### Árvores grandes: rodar em fatias

`products` tem centenas de páginas e uma execução única pode estourar o
tempo (ou a sessão do cookie expira no meio). A ordem das páginas é
determinística, então dá para fatiar:

```bash
python3 aem_migrate.py --source .../products --inicio 0   --limite 150 --output p1.csv
python3 aem_migrate.py --source .../products --inicio 150 --limite 150 --output p2.csv
python3 aem_migrate.py --source .../products --inicio 300 --limite 150 --output p3.csv
```

Cada fatia gera o seu CSV. Se uma falhar, só ela precisa ser repetida.

Componentes traduzidos: `text`, `image`, `heading→title`, `title→title`,
`button`, `download`, `table`, `video→embed`, `relatedsuggestions`
(modo static), `tabs→tabs` (com o conteúdo de cada aba),
`productlisting→list`, `supplierlist→list`, `carousel→carousel`,
`imagepack→flexcontainer`, `downloadlist→downloadlist`.

### Conferência de cobertura (100% do conteúdo)

Todo run conta o conteúdo da **origem** e compara com o que foi migrado,
por tipo. O resumo termina com:

```
>>> COBERTURA DO CONTEÚDO: 100.0% <<<
    785 de 785 blocos de conteúdo da origem chegaram ao destino
    ✓ TODAS as páginas com 100% do conteúdo migrado
```

O CSV principal ganha as colunas `conteudo_origem`, `conteudo_migrado` e
`pct_conteudo`. Se alguma página ficar abaixo de 100%, sai um
`*_cobertura_incompleta.csv` dizendo exatamente que tipo faltou.

O excesso num tipo nunca compensa a falta em outro — a conta usa o
mínimo entre origem e migrado por tipo, então 100% significa mesmo que
nada se perdeu.

### Reescrita de links

Normaliza qualquer link interno para o caminho do destino:

| Antes | Depois |
|---|---|
| `https://author-p53812-….adobeaemcloud.com/sites.html/content/macnicagwi/x` | `/content/macnicaglobal2/x` |
| `/content/macnicagwi/x.html` | `/content/macnicaglobal2/x` |
| `https://www.macnica.com/americas/…` | `/content/macnicaglobal2/americas/…` |

Links de **imagem e vídeo** (`fileReference`, `youtubeVideoId`) e o DAM
(`/content/dam/…`) **não são tocados**. Âncoras (`#`), `mailto:` e
domínios externos passam intactos.

---

## 3. `aem_verify.py` — conferir

Roda **depois** do migrate. Só leitura.

```bash
python3 aem_verify.py --source /content/macnicagwi/.../semiconductors

# conferindo também os links
python3 aem_verify.py --source /content/macnicagwi/.../semiconductors --links
```

Responde: faltou página? sobrou (duplicata de maiúscula)? alguma nasceu
vazia? o template está certo? sobrou link apontando para o GWI?

---

## Fluxo completo

```bash
# 1. ver o que tem lá
python3 aem_tree.py /content/macnicagwi/americas/mai/en/products/semiconductors --componentes

# 2. simular
python3 aem_migrate.py --source /content/macnicagwi/.../semiconductors --dry-run

# 3. migrar (hide-in-nav, tags e SEO já vão por padrão)
python3 aem_migrate.py --source /content/macnicagwi/.../semiconductors

# 4. conferir
python3 aem_verify.py --source /content/macnicagwi/.../semiconductors --links
```

---

## Segurança

- Só se escreve em `/content/copia-teste/...`. `macnicagwi` e
  `macnicaglobal2` são **somente leitura**.
- Toda escrita passa por `assert_target_is_safe()`, que aborta o processo
  se o caminho não estiver na área de teste. É trava de código, não
  disciplina.
- `--dry-run` em tudo que escreve.
- A sessão expira: após 5 respostas 401/403 seguidas o script para e marca
  o restante como "NÃO TENTADO (sessão expirou)" no CSV, sem perder o que
  já fez.

## Pendências conhecidas

Herdadas dos scripts antigos, ainda sem solução:

1. ~~**`navTitle`**~~ — confirmado em 11/09/2026 com exemplo autoral real
   (`sony-imx174llj-c` no GLOBAL2, migrada pelo time). Agora é copiado
   da origem, que o tem curado.
2. **`download`** — a propriedade `fileReference` é inferida por padrão.
3. ~~**`relatedsuggestions` modo `children`**~~ — mapeado para `list`
   em 17/09/2026, reusando o caminho do `productlisting` (as props são as
   mesmas: `listFrom`, `parentPage`, `orderBy`, `sortOrder`, `maxItems`,
   `childDepth`). Não era só perda de semântica: o componente não gerava
   NADA no destino. Em `sitime-clock-buffers` sumiam as 3 páginas irmãs
   com título e descrição. Eram 44 páginas em `semiconductors`.
4. **`relatedsuggestions` modo static** — vira botões soltos, perdendo a
   semântica de lista. Mesma observação do item 3.
8. **`separator`** — existe nos dois lados com o mesmo nome e sem
   propriedade nenhuma, mas o Bruno preferiu deixar como pendência até
   conferir (decisão de 13/09/2026).
9. **`pagesectionlisting`** — índice de âncoras (`fixedListItems` com
   `id`+`label`). Candidatos: `tableofcontents` ou `anchorlink`.
   Pendência por decisão do Bruno (13/09/2026).
10. ~~**`title` do GWI**~~ — mapeado em 13/09/2026 ("title é title").
    Eram 70 ocorrências perdidas em silêncio (16 em products, 54 no blog).
    Guarda o texto em `jcr:title`, não em `text` como o heading.
11. ~~**`carousel`, `imagepack`, `supplierlist`, `downloadlist`**~~ —
    mapeados em 13/09/2026: `carousel→carousel`, `imagepack→flexcontainer`
    (com `flexcontaineritem` para cada filho), `supplierlist→list`
    (`cardlist` fica reservado para páginas de template technical
    article), `downloadlist→downloadlist`. Achado durante os testes:
    `carousel` pode ter um slide de VÍDEO, não só imagem
    (`sony-imx277cqt-c` tinha um `embed` de YouTube dentro do carousel) —
    tratado, vira `embed` dentro do carousel de destino.
12. ~~**Product Hierarchy Details / `pd_*`**~~ — implementado em
    13/09/2026 (`build_tag_props` + `build_pd_props`), confirmado
    propriedade-por-propriedade contra 3 pares reais Sony
    (imx277cqt-c, imx174llj-c, imx273llr-c). Ver `TAGS-taxonomia-achados.md`.
    - Tags dedicadas (`manufacturer`, `businessCategories`, `interface`,
      `resolution`, `pixelsize`, `opticalformat`, `shuttertype`,
      `productcategory`...): copiadas com o MESMO NOME de propriedade,
      valor validado contra a taxonomia real antes de gravar.
    - `pd_description`, `pd_interface`, `pd_resolution`, `pd_pixelSize`:
      derivados das propriedades já migradas (mesmo valor).
    - `pd_modelName`: nome do nó da página SEM o prefixo do fabricante
      (a partir da tag `manufacturer` já migrada), maiúsculo —
      `sony-imx277cqt-c` + fabricante `sony` → `IMX277CQT-C`. Sem o
      fabricante batendo o prefixo, usa o nome inteiro (nunca corta um
      hífen "no chute", já que nomes fora do padrão Sony têm múltiplos
      hífens no próprio modelo).
    - `pd_isModelNameLinkToPage`: sempre `'true'`, confirmado nos 3
      exemplos.
14. ~~**Layout de coluna achatado**~~ — corrigido em 17/09/2026. A largura
    da coluna não é propriedade do componente: vive em
    `cq:responsive/default/width` (em doze avos) no container que embrulha o
    bloco — três colunas são três `resizablecontainer` irmãos com `width=4`.
    O extrator agora anota `colWidth` ao descer num container que é coluna, e
    a escrita grava o `cq:responsive` no destino, com `phone=12` para empilhar
    em tela estreita, como no GWI.

    **Dois lugares de escrita, não um:** bloco de página recebe a largura no
    `_wrap` que o `BlockBuilder` cria; bloco **dentro de aba** recebe no
    próprio nó, porque o container da aba já é `layout=responsiveGrid` e ali
    não existe `_wrap`. Tratar só o primeiro caso dá a impressão de resolvido
    — as colunas do topo voltam e as das abas continuam empilhadas. Em
    `altera` havia os dois. Eram 53 páginas em `semiconductors`.

    Conferência rápida sem ler JCR: contar `aem-GridColumn--default--N` (N<12)
    no HTML servido; zero = página inteira em largura cheia.

15. **`aem_migrate.py` não normaliza a caixa do nome de destino** — ele
    espelha a origem. Numa página cujo nome tem maiúscula no GWI
    (`toe200G-ip-...`), rodar o migrate CRIA página nova e deixa a antiga
    órfã: é a mesma armadilha das 29 órfãs de tq-systems, agora pelo lado do
    migrador. Até ter decisão, quem roda em página assim precisa mover o
    conteúdo e apagar a duplicata (ver o driver em
    `scripts-hazael/`, que faz isso).

13. **Ainda sem equivalente** (nenhum causa perda de conteúdo — o
    extrator desce dentro deles e captura texto/imagem aninhados):

    | GWI | Qtd em products | Observação |
    |---|---|---|
    | `pagesectionlisting` | 36x | índice de âncoras; pendência por decisão do Bruno |
    | `separator` | 14x | existe nos dois lados, sem props; pendência por decisão do Bruno |
    | `breadcrumb` | 6x | o template já traz um breadcrumb próprio |
    | `form/*` | 37x | fora de escopo (precisa backend) |
    | `embaddedhtml` | 2x | script Marketo de terceiro — precisa decisão |
    | `shareaholic` | 2x | botões de compartilhar |
    | `productlinecontacts` | 2x | |
    | `cardlist` | 1x | reservado para template technical article |
    | `wcm/msm/.../ghost` | 15x | herança MSM, não é conteúdo |

---

## Page Properties (diretriz 2 do cliente)

O que o `aem_migrate.py` já preenche sozinho, no modo completo:

| Propriedade | De onde vem |
|---|---|
| `pageTitle` (SEO title) | copiado da origem; cai no título só se faltar |
| `navTitle` | idem |
| `keywords` | copiado da origem quando existe |
| `jcr:description` (meta description) | copiado da origem |
| `hideInNav` | sempre `true` (desliga com `--sem-hide-in-nav`) |
| tags de taxonomia | ver `TAGS-taxonomia-achados.md` |

**Por que copiar em vez de derivar do título**: nas 6 páginas de
`macnica-products`, 6/6 têm `pageTitle` e `navTitle` curados e
**diferentes** do `jcr:title` — usar o título neles destruía SEO em 100%
dos casos. Exemplo (`macnica-cv75`):

```
jcr:title : CV75 SoM | Edge AI Vision for UAV/UAS and Robotics
pageTitle : iENSO CV75 - Embedded Vision & Edge AI Platform | Macnica Americas
navTitle  : iENSO CV75
```
