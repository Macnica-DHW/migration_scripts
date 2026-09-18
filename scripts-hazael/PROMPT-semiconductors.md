Vamos migrar a família `semiconductors` do AEM da Macnica. O repositório é
`~/projects/migration_scripts`. Leia antes de começar: `scripts-bruno/HANDOFF.md`,
`scripts-bruno/README.md` e `scripts-hazael/README.md`. A lógica compartilhada
(autenticação, travas, tradução de componentes, cópia de asset do DAM) está em
`scripts-bruno/aem_lib.py` — 2134 linhas. **Não reimplemente nada que já esteja lá.**

## O problema — a premissa NÃO se confirmou, comece por aqui

Me disseram que as 355 páginas de `semiconductors` em `copia-teste` estariam
erradas porque "a migração rodou duas vezes e cada página ficou com todo o
conteúdo em dobro". **Uma amostra de 20 páginas em 17/09/2026 não sustenta
isso:**

    com algum trecho repetido : 5 de 20  (e só 1-3 trechos por página,
                                          não o conteúdo inteiro em dobro)
    sem repetição nenhuma     : 14 de 20

Exemplos com repetição: `/renesas` (3 trechos repetidos em 55 containers),
`/altera/altera-questa-fpga-edition` (1 em 24). Se a migração tivesse mesmo
rodado duas vezes gravando com nomes de nó diferentes, esperava-se ~50% de
repetição — cada bloco duas vezes. 1 trecho em 24 containers parece outra
coisa (um nome de produto que aparece no título E na tabela, por exemplo).

Achado possivelmente mais relevante: **várias páginas têm só 1 container**
(quase todas as `sony-image-sensors/*` da amostra). Isso cheira a conteúdo
DE MENOS, não a mais. Lembre que `sony-image-sensors` está duplicado dentro
de si mesmo no GWI (184 páginas fantasmas vazias) — pode ser isso.

E convivem esquemas de nome diferentes: 6 de 20 usam `*_wrap` (migrador
antigo), 13 usam outro esquema. Ou seja, mais de um script já passou por aqui.

**Primeira tarefa, antes de qualquer plano:**

1. Renderize com `scripts-hazael/aem_screenshot.py` 3 páginas: uma das
   "com repetição" (`/renesas`), uma das "sem" (`/canon/canon-li7070sa-cmos-sensor`)
   e uma das de 1 container (`/sony-image-sensors/sony-imx174lqj-c`).
   **Olhe.** A duplicação aparece na tela ou não?
2. Compare com o GWI equivalente (`aem_diff_conteudo.py` + screenshot).
3. Me diga qual é o problema DE VERDADE antes de propor conserto.

Pode ser que o sintoma relatado exista só em algumas páginas, ou que o
problema real seja o oposto (conteúdo faltando). Remigrar 355 páginas em cima
de uma premissa errada destrói o que está funcionando.

## Situação levantada em 17/09/2026

    GWI            18 fabricantes; 3 templates (250x mae-product-page,
                   76x product-detail-page, 17x manufacturer-detail-page)
    copia-teste    355 páginas, todas com conteúdo (DUPLICADO), nenhuma soft-deleted
    macnicaglobal2 217 páginas — só 'Titles', 'deepx', 'sony', 'sony-test'

Faltam em produção fabricantes inteiros: `altera`, `ambarella`, `analog-devices`,
`canon`, `design-gateway`, `genesys-logic`, `i-chips`, `infineon`, `microchip`,
`namuga`, `on-semiconductor`, `renesas`, `sitime`, `toppan`.

## Componentes: o que o migrador ainda não traduz

    core/wcm/.../image/v3      441  -> image       OK
    table                      309  -> table       OK
    pageproperties             273  -> ignorado (config)
    relatedsuggestions         251  -> PENDÊNCIA, não traduz   <<< o maior buraco
    carousel                   233  -> carousel    OK
    video                      230  -> embed       OK
    tabs                       211  -> tabs        OK
    experiencefragment         124  -> PENDÊNCIA, não traduz
    imagetext                  123  -> invólucro (desce dentro)
    button                      53  -> button      OK
    form/*                      36  -> NÃO MAPEADO (precisa backend, fora de escopo)
    pagesectionlisting          14  -> NÃO MAPEADO (índice de âncoras)
    productlisting              10  -> list        OK

**426 ocorrências sem tradução.** `relatedsuggestions` sozinho são 251 — em
tq-systems eram 3, aqui é estrutural. O README (itens 3 e 4 das "Pendências
conhecidas") sugere o caminho: `productlisting` já virou `list` e o
`relatedsuggestions` usa as mesmas propriedades.

## As páginas NÃO seguem um padrão

Diferente de tq-systems, as páginas de semiconductors são bem diferentes umas
das outras — script único que conserte o layout de todas provavelmente não
existe. Conte com trabalho página a página para o layout, mesmo que a extração
de conteúdo (que é por componente, não por layout) dê para automatizar.

## VOCÊ CONSEGUE VER AS PÁGINAS RENDERIZADAS

    python3 scripts-hazael/aem_screenshot.py /content/.../uma-pagina -o antes.png

Playwright + Chrome já instalados; a página do AEM abre com GET autenticado em
`<caminho>.html`, sem chrome do editor. Confirmado em 17/09/2026. Use para
fechar o ciclo sozinho: renderiza origem, renderiza destino, compara, corrige,
renderiza de novo.

**Limite real:** cada screenshot custa bastante contexto — ~30-50 páginas por
sessão. Trabalhe em lotes e registre onde parou.

## Regras inegociáveis

1. **O GWI é SOMENTE LEITURA.** Nunca escreva em `/content/macnicagwi`.
2. **O GWI é a fonte da verdade do conteúdo.** Conteúdo errado no GWI migra
   fielmente assim mesmo. Divergência no destino é bug nosso. Layout PODE
   diferir; conteúdo, não.
3. **Escrita fora de `copia-teste` exige `--permitir-escrita-global2 <caminho>`**
   batendo EXATAMENTE com o alvo, senão `assert_target_is_safe()` aborta.
4. **Dry-run primeiro, sempre.**
5. **Me mostre o que vai mudar antes de escrever.** Em produção, sempre; em
   copia-teste, pelo menos o resumo.

## Autenticação

Cookie de sessão no `.env` da raiz
(`AEM_COOKIES=login-token=login%3a...%3acrx.default`), tirado do **Firefox no
Windows**: F12 → Storage → Cookies → host do AEM → copiar o `login-token`.
(O README ensina pelo Chrome e não bate.) Expira em poucas horas.

    python3 scripts-bruno/aem_lib.py     # confere sem tocar na rede

Extrair cookie por script não funciona: é cookie de sessão, nunca vai ao disco.

## Armadilhas que já custaram horas

1. **Sling POST faz MERGE** — é provavelmente a causa da duplicação. Apague
   `jcr:content/root` antes de regravar.
2. **Colisão de maiúsculas.** GWI tem nós com maiúscula, o destino normaliza
   para minúscula; copiar sem casar cria página nova e deixa a antiga órfã
   (29 assim em tq-systems). Use `normalize_name()`.
3. **Soft-delete.** Página que sumiu do console mas cujo nome continua ocupado
   tem `deleted`/`deletedBy` — não foi apagada. Ver `aem_soft_delete.py`.
4. **Canonical.** Todo clone copia o `cq:canonicalUrl` da ORIGEM. Rode
   `scripts-hazael/aem_fix_canonical.py` depois de qualquer clone. Sempre.
5. **DAM do global2 é todo minúsculo** e o `nodename` do QueryBuilder é
   sensível a maiúscula — buscar asset pelo nome do GWI falha em silêncio.
   Se o asset não existir no destino, use `copy_asset()` do `aem_lib`
   (portado e testado em 17/09/2026: baixa o binário e sobe em
   `<pasta>.createasset.html`, criando as pastas; idempotente; passa pela
   trava de segurança).
6. **`sony-image-sensors` está duplicado dentro de si mesmo no GWI** (184
   páginas fantasmas). O `AEM_SKIP_PATH_CONTAINS` do `.env` já trata — não remova.

## Conferência

- `scripts-bruno/aem_verify.py` — a página existe e tem conteúdo?
- `scripts-hazael/aem_diff_conteudo.py` — é o MESMO conteúdo do GWI? (achou 17
  páginas com buraco em tq-systems que o verify dava como migradas)
- `scripts-hazael/aem_screenshot.py` — e o layout, como ficou?

## O que NÃO reaproveitar de tq-systems

Os scripts `aem_fix_tq_*` e `aem_tq_*`, os nomes `container_imagem`/
`container_features`, a convenção `<h3>Features</h3>`, o container fundido
Specifications+Ordering e o `imageRatio=40`. Em `scripts-hazael`, os que
assumem esse layout (`aem_restaurar_specs`, `aem_reconstruir_blocos`,
`aem_corrigir_divergencia`, `aem_padronizar_textwithimage`) precisam ter as
premissas reconferidas. Os agnósticos (`aem_diff_conteudo`, `aem_soft_delete`,
`aem_fix_canonical`, `aem_corrigir_alinhamento`, `aem_screenshot`,
`aem_workflow_audit`) servem como estão.

`scripts-luiza/aem_create_and_migrate_semiconductors.py` é uma implementação
paralela de 1291 linhas que duplica o `aem_lib` e está desatualizada (estrutura
de container de 3 níveis, tags "fora de escopo", `title` não mapeado, `.env`
próprio). A única parte com valor único — cópia de asset do DAM — já foi
portada para o `aem_lib`. **Não use esse script como base.**

A favor: a taxonomia de tags (`manufacturer`, `businessCategories`, `pd_*`) foi
validada contra 3 páginas Sony REAIS desta família — ver
`scripts-bruno/TAGS-taxonomia-achados.md`.

## Como começar

1. Diagnostique a duplicação em 2-3 páginas e me mostre o mecanismo.
2. Proponha a estratégia (limpar e remigrar? deduplicar?) com dry-run.
3. Só depois escrevemos.

Não escreva nada antes do passo 1.
