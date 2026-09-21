# Remigração — onde parei (21/09/2026, 6ª sessão)

> **Servidor = motor (HEAD) = R1–R53**, mais três coisas gravadas FORA do motor
> por ferramenta de uma propriedade só (ver abaixo). Revisão manual do Hazael em
> andamento, página a página, no artifact "Conferência da remigração"
> (https://claude.ai/artifact/CTjAuafxrCas9xAVJe8rDR — status e nota por página
> ficam no banco do artifact; ler de lá em vez de pedir o relatório).

## 6ª sessão (21/09/2026) — o que mudou

**Regras novas no motor** (todas em `REGRAS-disposicao.md`, todas nascidas de
print do Hazael):
- **R46** teto do `imagetext` (480/277) vale mesmo com `width` autoral — 2 pares
  da `/ambarella` saíam sem `imageRatio` (foto 655×437). O driver passou a
  consultar o DAM também quando há largura autoral.
- **R47 revoga a R34**: `elementsPositionVerticalAlignCenter` está no JCR do GWI
  e o template do GWI o ignora (medido: título a 11/−3/26/29px do topo da foto).
- **R48** todo `anchorlink` com Text Size Small — pills uniformes a 1400/1366.
- **R49** `alt` nunca vazio (heading da dupla › título acima › título da página)
  **e** `altValueFromDAM='false'` no `textwithimage`: sem a flag o componente
  ignora o alt do nó e serve o metadata do DAM (`alt="544581870"`).
- **R50** pares texto|foto em SÉRIE dividem a mesma coluna (a maior da série).
- **R51** coluna que guarda SÓ título não é coluna (`i-chips-ip00cc35`, "Key
  Features" ao lado da lista) e **R52** dois títulos idênticos em seguida viram um
  (`canon-li7070sa`, `canon-li7060-hdr`) — as duas são **divergência deliberada**:
  o GWI desenha igual (medido); são deslizes do autor da origem. Lote 12, 3/3.
- **R53 — o fundo cinza entrou NO MOTOR.** Política do Hazael: intro branca,
  corpo `#f7f7f7`, botões de contato brancos no fim; página grande alterna por
  grupo de `h2` (faixa mínima de 5 blocos). Escopo = a lista dele, 49 páginas,
  em `dados/fundo_cinza_paginas.txt` (2ª coluna `alternar` nas 19 grandes) —
  para pôr ou tirar uma página, editar esse arquivo e regravar a página. Como a
  cor só pega em seção inteira, o motor CORTA a seção na emissão (intro | corpo |
  contato) sem mexer no IR nem no respiro. Lote 13: 49/49, 57 faixas, a menor
  com 499px; `/design-gateway` com +0px de altura, as folhas com +60px (os
  30/30 do bloco de contato, agora seção própria).
- Slides de `carousel` também saem com alt derivado + `altValueFromDAM`/
  `isDecorative` = false (o dry-run da R52 mostrou que regenerar apagaria as
  flags que o `alt_faltando.py` tinha posto).

**Gravado:** lote 11 (`lote11_paginas.txt`, 11/11) · `alt_faltando.py --todas`
(66 alt em 39 páginas; depois 226 flags em 82) · `serie_twi.py /ambarella` (2
`imageRatio`). Backups: `lote11_backup.json`.

**Gravado FORA do motor — a próxima regeneração da página APAGA:**
- **Fundo por grupo semântico** em `/ambarella` e `/canon` — as DUAS únicas
  páginas com fundo ainda fora do motor (não estão na lista da R53)
  (`ferramentas/fundo_grupo.py`, teste de 2 páginas). Depois de qualquer lote
  que inclua uma delas: `fundo_grupo.py <pág> --executar` (idempotente).
  `ferramentas/faixas.py` confere que nenhuma faixa tem menos de 200px.
- O XF `products-contact-block` (botões lado a lado, par ao centro) — gravado
  pela sessão paralela `migration-scripts-7a` com `xf_lado_a_lado.py`
  (commit 2b5a769). O driver NÃO escreve em experience-fragments, então lote
  não desfaz. `signup-and-contact-experience-fragment` (4 páginas): gravado
  nesta sessão a pedido do Hazael (`--colunas 2`): "Stay up to date…" + Sign up
  numa coluna, "For more information:" + Contact us na outra; texto a 40px do
  botão. Backup `xf_signup-and-contact-experience-fragment_backup_2026-09-21_112523.json`.

**Fundo: o que ficou decidido e o que não.** Cor é de GRUPO, não de seção nem
de bloco (no global2, 0 de 270 seções coloridas têm um bloco só); faixa fina
(<200px) é sintoma de cor errada. **Em aberto, decisão do Hazael:** nas folhas
de produto a spec divide o único nó full-bleed com o herói e/ou o CTA (59
páginas) e 54 páginas têm UMA seção só — ali só o motor resolve, cortando
seção em mudança de papel, contra "fronteira de seção vem da origem". Sem essa
decisão a regra de grupo não entra no motor. Responde Q6 e reformula Q1 do ESPEC.

**Achados sem dono ainda:** 18 `<img>` soltos em `table` sem alt (HTML cru do
GWI) e com `src` em `/content/dam/macnicagwi` (quebra no go-live) · os botões
do XF de contato ainda linkam para `/content/macnicagwi/...` · o cookie do
`.env` autentica como **valter.toffolo**, então `cq:lastModifiedBy` não separa
lote nosso de edição manual dele.

**Armadilhas de medição desta sessão** (custaram rodadas): pill com
`transition:.3s` devolve o valor antigo logo após trocar a classe · caminho do
GWI com maiúsculas (`li8030SA`) dá 404 silencioso · imagem lazy mede
`naturalWidth=0` · zsh não divide `$VAR` sem aspas (o 1º lote 11 abortou).

---

# (5ª sessão, 19/09/2026 — continua valendo)

> **Servidor = motor (HEAD) = R1–R45 + R41b.** O lote 10 (43 páginas, `remigracao/lote10_paginas.txt`)
> foi GRAVADO em 19/09/2026 (43/43 sem falha) e conferido na tela; conteúdo 134/136, 0 sobrando. Conferência visual: 67 de 136 (`CONFERIDAS.md`). Só se confere a 1400px.
> A lista de um lote sai do `diff_payload.py` + `lista_do_dry.py`, nunca do `cmp_motor --lista`.

(o resto deste arquivo é da 4ª sessão e continua valendo)

## Estado

```
136 páginas em /content/copia-teste/americas/mai/en/products/semiconductors-remigration
lotes 3–7: R1–R27
lote 8 de 18/09/2026: R28–R36 — 134/134 sem falha
lote 9 de 18/09/2026: R37–R41 + ajustes — 108 páginas (as que o diff_payload acusou)

conferência de conteúdo REFEITA depois do lote 9: 134 de 136 limpas (22 faltando
nas 2 páginas conhecidas — landing 16, /ambarella 6 —, 0 sobrando).
conferência visual: 40 de 136 — ver HANDOFF.md.
```

O motor no disco é o que está no servidor (HEAD do branch
`migration/semiconductors-remigration`). Próximo passo em `HANDOFF.md`.

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
- **Formulário da `macnica-and-adi`** — migrado (R27). NÃO testar o envio sem
  combinar: manda e-mail real. reCAPTCHA só na árvore final.
- **Abertos I, K, L, M, N** em `REGRAS-disposicao.md` (todos de gravidade baixa).
  G, H, J e E viraram R28, R30, R36 e R41.
- **`supplierlist`**: o blurb é hover-only; o que se VÊ é uma grade 4×4 de
  logo+nome com link (descrição em REGRAS).
- **Centralizar título que abre seção** (dialeto da Anion) — hoje só se
  centraliza o que o próprio GWI centraliza.
- **`relatedsuggestions` modo `search` (9)**: a policy do `list` tem
  `disableSearch='true'`; resolver exige renderizar a página do GWI.
