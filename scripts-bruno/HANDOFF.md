# Handoff — Migração AEM GWI → GLOBAL2

Este documento é o ponto de entrada para quem está assumindo o projeto agora.
Leia isto primeiro; o [`README.md`](README.md) ao lado documenta os 3 scripts
originais (`aem_tree`, `aem_migrate`, `aem_verify`) em detalhe — não repito
aqui o que já está lá.

## O que é este projeto

Migração de conteúdo do AEM **GWI** (site antigo) para o **GLOBAL2** (site
novo), passando sempre por uma área de teste (**copia-teste**) antes do
destino final. Objetivo secundário: medir que fração da migração dá para
automatizar por script vs. o que precisa de trabalho manual.

Três ambientes AEM, cada um com uma regra de acesso que os scripts aplicam
via trava de código (`assert_target_is_safe()` em `aem_lib.py`), não por
disciplina:

| Ambiente | Papel | Escrita? |
|---|---|---|
| `macnicagwi` | conteúdo original, fonte da verdade | **NUNCA** |
| `macnicaglobal2` | destino final, produção | só com exceção pontual explícita (ver abaixo) |
| `copia-teste` | área de teste | sim, livre |

## O que já foi feito

1. **Migração de conteúdo** GWI → copia-teste, várias famílias de produto
   (`semiconductors`, `macnica-products`, `boards-modules/tq-systems`, blog).
   Motor: `aem_migrate.py` (ver README).
2. **Correção de layout em `semiconductors`** (copia-teste): estrutura de
   containers, padding, título, largura máxima (`cq:responsive`), SEO,
   tags — via `aem_fix_pages.py`.
3. **`tq-systems` completo**, em duas etapas:
   - Todas as correções de layout/SEO em **copia-teste** primeiro.
   - Clonagem fiel de copia-teste → **`macnicaglobal2/.../boards-modules/
     tq-systems-embedded`** (nome escolhido para não colidir com as várias
     cópias de teste antigas que já existem em `boards-modules`:
     `tq-systems`, `tq-systems0-4`, `tq-systems-test` — **não mexer
     nelas**, origem desconhecida, não foram criadas nesta sessão).
   - As mesmas correções de layout/SEO reaplicadas em cima da cópia do
     GLOBAL2 (o clone preserva estrutura, mas alguns ajustes finos exigem
     reprocessar depois, documentado script a script abaixo).
4. Achado sistemático (não específico de TQ, confirmado também em
   `semiconductors`): as páginas migradas nascem com
   `sling:resourceType` genérico (`macnicaglobal2/components/page`) em vez
   do específico de produto (`macnicaglobal2/components/maeproductpage`),
   o que esconde a aba "Product Hierarchy Details" do Page Properties.
   Corrigido em `tq-systems` (copia-teste e GLOBAL2); **ainda não
   verificado nas outras famílias**.

## Scripts, na ordem em que normalmente se usa

### Base (ver README.md para uso detalhado)

| Script | Papel |
|---|---|
| `aem_lib.py` | biblioteca compartilhada — não roda direto, todo o resto importa dela |
| `aem_tree.py` | EXPLORAR uma árvore qualquer, só leitura |
| `aem_migrate.py` | MIGRAR/CLONAR — criar páginas + conteúdo, 3 modos (completo / `--so-estrutura` / `--modo-clone`) |
| `aem_verify.py` | CONFERIR origem vs. destino, só leitura |

### Correção pós-migração (criados depois do README, não documentados lá)

Todos seguem o mesmo padrão: **dry-run sempre primeiro**, leem o CSV de
saída, só escrevem o que está faltando (nunca sobrescrevem o que já está
certo), e são **idempotentes** — rodar de novo numa página já corrigida
reporta "já correto" sem reescrever.

| Script | O que corrige | Escopo original |
|---|---|---|
| `aem_fix_pages.py` | estrutura 3→2 níveis, padding, título roxo, SEO, tags, `hideInNav`, largura máxima (`cq:responsive`) | qualquer família |
| `aem_fix_containers.py` | **legado**, superado por `aem_fix_pages.py` — mantido só por referência histórica, não usar em trabalho novo |
| `aem_fix_resourcetype_maeproductpage.py` | troca `sling:resourceType` de `page` (genérico) para `maeproductpage` (expõe a aba Product Hierarchy Details) | qualquer família |
| `aem_fix_seo_final.py` | Page Properties completo: Description (do GWI ou, se não existir lá, extraído do 1º parágrafo da própria página), Canonical URL (derivado do caminho), Business Categories/Manufacturer (do GWI) | qualquer família |
| `aem_fix_tq_layout.py` | regras específicas de TQ: container de título no início, background em Specifications/Ordering, bloco de botões padrão, padding do penúltimo, largura máxima | só tq-systems |
| `aem_tq_merge_specs_ordering.py` | funde Specifications + Ordering Information num único container | só tq-systems |
| `aem_tq_remove_button_text.py` | remove o texto de apoio ("Stay up to date...") de dentro do bloco de botões | só tq-systems |
| `aem_fix_tq_image_swap.py` | inverte texto/imagem (H1 vai para o `textwithimage`, Features vira `text` puro com background), Image Position Left, padding do bloco de imagem | só tq-systems |
| `aem_fix_tq_merge_buttons.py` | move o flexcontainer de botões para dentro do container "known for", apaga o container antigo vazio | só tq-systems |

Os scripts `_tq_`/`tq_` são específicos do layout de produto de TQ Systems
(confirmado com o Bruno olhando páginas de referência editor-a-editor) —
**antes de reusar em outra família, confirme se o layout-alvo é o mesmo**,
comparando uma página de referência da nova família com o que esses
scripts fazem.

## Escrever em `macnicaglobal2`

Por padrão todo script recusa escrever fora de `copia-teste`
(`assert_target_is_safe()`). Os scripts de correção mais recentes aceitam
uma exceção pontual e explícita:

```bash
python3 aem_fix_seo_final.py \
  --target /content/macnicaglobal2/americas/mai/en/products/boards-modules/tq-systems-embedded \
  --permitir-escrita-global2 /content/macnicaglobal2/americas/mai/en/products/boards-modules/tq-systems-embedded
```

O caminho passado em `--permitir-escrita-global2` precisa bater **exatamente**
com `--target` — não é uma flag "libera tudo", é liberar aquele caminho
específico, naquela execução. Sem essa flag, tentar escrever em
`macnicaglobal2` aborta o processo.

`aem_migrate.py` tem a mesma trava, com a flag equivalente.

## Autenticação (ver README.md e `aem-auth-cookie-sessao` nas memórias)

Cookie de sessão no `.env` (`AEM_COOKIES`), **nunca** por Basic Auth (não
funciona nesta instância). Expira em poucas horas. Para renovar: logar no
AEM no navegador, DevTools → Network → filtrar por `adobeaemcloud.com`,
recarregar, pegar a **primeira requisição com `Type: document`** (não uma
de prefetch/analytics/pixel — já aconteceu de pegar a errada por engano),
Copy → Copy as cURL, colar a string inteira do `-b` no `AEM_COOKIES`. O
cookie certo tem um `-b` bem longo, com um campo `web-p53812-...` grande
no meio — se a string for curta, provavelmente é a requisição errada.

Teste rápido de validade:
```bash
python3 -c "
import sys; sys.path.insert(0,'.')
from aem_lib import build_session
s,at=build_session(prompt_if_missing=False,verbose=False)
r=s.get('https://author-p53812-e590634.adobeaemcloud.com/libs/granite/security/currentuser.json',timeout=15)
print(r.status_code)"
```
200 = válido. 401 = precisa renovar.

## Pendências conhecidas

1. **`starterkit-stka6ulx`** (dentro de `tq-embedded-arm-modules`, em
   copia-teste **e** em `tq-systems-embedded`): tem uma estrutura de
   container-pai duplicado, pré-existente (não introduzida nesta sessão),
   com título e bloco de botões duplicados no HTML renderizado. Nenhum dos
   scripts de correção de TQ mexe nela (detectada e pulada
   automaticamente). Precisa de correção manual no editor.
2. **`mblsa1028a-ind-single-board-computer`** (dentro de
   `tq-embedded-qoriqr-layerscape`): duplicata de nome com erro de
   digitação (a correta é `mbls1028a-...`, sem o "a" extra), pré-existente.
   SEO corrigido manualmente espelhando a irmã correta, mas `pageTitle`/
   `navTitle` continuam vazios — decisão pendente do Bruno (apagar a
   duplicata ou corrigir os dois nomes).
3. **Imagens grandes demais no `textwithimage`**: em algumas páginas a
   imagem do bloco de introdução aparece desproporcional. Correção é
   manual no editor (ajustar o grid da imagem) — não tratado por script,
   ver `checklist-revisao-tqsystems.txt` (não versionado, pedir ao Bruno)
   item 12 se precisar do passo a passo exato.
4. **Tags (`cq:tags`)**: fora do escopo automático por decisão do Bruno —
   ele adiciona manualmente. Achado durante a investigação: nas páginas
   de referência que ele ajustou, `cq:tags` era sempre igual a
   `[manufacturer]`, mas é inferência de poucos exemplos, não confirmada
   como regra geral.
5. **`resourceType maeproductpage`**: corrigido em `tq-systems` (copia-teste
   e GLOBAL2). As outras famílias (`semiconductors`, `macnica-products`,
   blog) provavelmente têm o mesmo problema — rodar
   `aem_fix_resourcetype_maeproductpage.py --dry-run` nelas para confirmar
   antes de aplicar.
6. Pendências herdadas da migração de conteúdo em si (não de layout):
   ver seção "Pendências conhecidas" do `README.md`.

## Memória de contexto (Claude Code)

Se o próximo dev também usa Claude Code, as memórias desta sessão (em
`~/.claude/projects/.../memory/`, não versionadas — são locais da máquina)
têm o histórico de decisões e achados, indexado em `MEMORY.md`. Vale
recriar o equivalente na máquina nova a partir deste documento e do
histórico de commits, já que memória não se copia sozinha entre máquinas.

## Fluxo recomendado para uma família de produto nova

1. `aem_tree.py --componentes` na origem, pra saber o que tem
2. `aem_migrate.py --dry-run`, depois de verdade → copia-teste
3. `aem_verify.py --links` → confirma cobertura
4. `aem_fix_pages.py` (estrutura, padding, título, SEO básico, tags, layout)
5. `aem_fix_resourcetype_maeproductpage.py` (expõe Product Hierarchy Details)
6. `aem_fix_seo_final.py` (Page Properties completo — Description, Canonical, Business Categories/Manufacturer)
7. Pegar 2 páginas de referência do cliente/PM e comparar campo a campo
   antes de assumir que está pronto — os scripts de layout específicos de
   TQ (`aem_fix_tq_*`, `aem_tq_*`) só se aplicam se o layout-alvo for o
   mesmo; senão, escrever um script novo seguindo o mesmo padrão (ver
   docstring de qualquer um deles como referência de estilo)
8. Só depois de tudo validado em copia-teste, `--modo-clone` para
   `macnicaglobal2` com `--permitir-escrita-global2`
9. Reaplicar os passos 4-6 em cima do clone do GLOBAL2 (o clone é fiel,
   mas alguns campos — como Canonical URL — mudam de valor porque
   dependem do caminho de destino)
