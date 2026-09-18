# Remigração — onde parei (18/09/2026)

## Estado

```
136 de 136 páginas gravadas, 0 falhas        (lote 2 desta sessão)
/content/copia-teste/americas/mai/en/products/semiconductors-remigration

pendências: 27 (nenhuma bloqueia o lote)
conferência de conteúdo: 133 limpas, 27 faltando (3 páginas, todas
conhecidas), 0 sobrando
```

**O motor no disco está UM PATCH À FRENTE do que está no servidor.** O
patch 3 (regras 13a–13f, da conferência visual; commit `0760e39`) está
aplicado em `scripts-bruno/aem_layout.py` e muda 64 páginas, mas o lote não foi
rodado — espera decisão. Ver "DECISÃO PENDENTE" no `HANDOFF.md`. Rodar
`aem_remigrar.py --executar` agora GRAVA esse patch. Para rodar com o motor
que está no servidor: `git checkout 137790a -- scripts-bruno/aem_layout.py`.

Trabalho versionado no branch `migration/semiconductors-remigration`.

Doze regras de disposição (R1–R13) em `REGRAS-disposicao.md`, cada uma com a
causa, a regra e como detectar. Nenhuma foi pega por conferência de conteúdo
sozinha: metade veio de abrir UMA página e comparar o HTML dos dois lados, a
outra metade de olhar o print.

## Para reexecutar

```bash
cd scripts-hazael
python3 aem_remigrar.py --executar                  # as 136
python3 aem_remigrar.py --so /altera --executar     # uma subárvore
python3 aem_remigrar.py --inicio 82 --executar      # retomar de onde parou
```

É seguro reexecutar por cima: o driver apaga `jcr:content/root` antes de
gravar (o Sling POST faz MERGE, e sem apagar os nós velhos e novos convivem —
foi assim que nasceram as 136 páginas com conteúdo em dobro no `/semiconductors`).

Se aparecer 401, o cookie expirou: renovar `AEM_COOKIES` no `.env` da raiz
(Firefox no Windows: F12 → Storage → Cookies → `login-token`) e retomar com
`--inicio <n>`.

## Antes do go-live

```bash
# os itens de `list` apontam para a árvore de rascunho, para renderizarem agora.
# Quando as páginas existirem no global2, regravar apontando para lá:
python3 aem_remigrar.py --executar --links-de-lista global2
```

## Pendências conhecidas (27, nenhuma bloqueia o lote)

```
10  tag                   TAG INVÁLIDA na origem (ex: 'mai:manufacturer/toppan',
                          'mai:sensor-type/cmos'). Erro do GWI, não nosso.
 9  related_nao_resolvido relatedsuggestions com listFrom=static e SEM 'pages':
                          tem query/searchIn apontando para sony-image-sensors,
                          que está fora de escopo. Busca disfarçada de estática.
 4  fora_da_structure     nós da LIDAR fora das regiões editable do template:
                          o GWI não renderiza, então NÃO migram (R9).
 2  tipo_nao_reconhecido  supplierlist (landing) e form/container (precisa backend)
 2  imagem_quebrada       resizableimage sem fileReference na origem
```

Saíram da lista nesta sessão: `pagesectionlisting` (12) — agora vira
`anchorlink` com os rótulos `label`/`id` do GWI (R10).

## Decisões ainda abertas

- **Gravar ou não o patch 3** (13a–13f) — ver `HANDOFF.md`.
- **Os dois XFs da copia-teste** (`page` em vez de `xfpage`; botões empilhados):
  fora do nosso escopo de escrita, atinge ~110 páginas.
- **Tabela de layout com ícone, imagem colada no texto, card órfão, `<p>` por
  linha** — abertos A–D em `REGRAS-disposicao.md`, com censo e proposta.
- **Centralizar título que abre seção** (dialeto da Anion) — hoje só se
  centraliza o que o próprio GWI centraliza.
- **`relatedsuggestions` modo `search` (9)**: a policy do `list` tem
  `disableSearch='true'`; resolver exige renderizar a página do GWI.
