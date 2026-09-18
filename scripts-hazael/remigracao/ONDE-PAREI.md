# Remigração — onde parei (18/09/2026)

## Estado

```
136 páginas em /content/copia-teste/americas/mai/en/products/semiconductors-remigration
lote 3 de 18/09/2026: R1–R13 + páginas SEM MARGEM (R14) — 136/136, conferido no servidor
lote 4 de 18/09/2026: R15, R17–R24 — as 72 páginas que mudam   72/72 sem falha
lote 5 de 18/09/2026: R16 (tabela de layout sem moldura) e R25 — 3/3
lote 6 de 18/09/2026: R26 (vídeo sozinho) — 20 páginas          20/20 sem falha

conferência de conteúdo (sobre o lote 2): 132 limpas, 27 faltando em 3
páginas conhecidas. NÃO foi refeita depois dos lotes 3 e 4.
conferência visual: 16 de 136, uma por arquétipo — ver HANDOFF.md.
```

O motor no disco é o que está no servidor (HEAD do branch
`migration/semiconductors-remigration`). Próximo passo em
`HANDOFF.md`.

## Para reexecutar

```bash
cd scripts-hazael
python3 aem_remigrar.py --executar                  # as 136
python3 aem_remigrar.py --so /altera --executar     # uma subárvore
python3 aem_remigrar.py --inicio 82 --executar      # retomar de onde parou
python3 aem_remigrar.py --paginas /canon /altera --executar   # só estas (o que o cmp_motor lista)
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

- **Os dois XFs da copia-teste** (`page` em vez de `xfpage`; botões empilhados):
  fora do nosso escopo de escrita, atinge ~110 páginas.
- **Formulário da `macnica-and-adi`** — viável com os componentes do global2;
  decisão e riscos em `PESQUISA-formulario.md`.
- **Abertos G–K** em `REGRAS-disposicao.md` (somatório
  de paddings entre seções, título longe das abas, botão sempre centralizado…).
- **`supplierlist`**: o blurb é hover-only; o que se VÊ é uma grade 4×4 de
  logo+nome com link (descrição em REGRAS).
- **Centralizar título que abre seção** (dialeto da Anion) — hoje só se
  centraliza o que o próprio GWI centraliza.
- **`relatedsuggestions` modo `search` (9)**: a policy do `list` tem
  `disableSearch='true'`; resolver exige renderizar a página do GWI.
