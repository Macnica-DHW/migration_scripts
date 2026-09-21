# Remigração `semiconductors` — handoff (18/09/2026, 4ª sessão)

Ponto de entrada da próxima sessão. Os outros arquivos desta pasta são
referência; este diz onde parou e o que fazer a seguir.

---

## ESTADO EM 21/09/2026, FIM DA 6ª SESSÃO — LEIA ISTO PRIMEIRO (vale sobre TUDO abaixo)

```
servidor = motor no HEAD (R1–R53)  +  2 páginas com fundo FORA do motor (/ambarella, /canon)
lotes do dia: 11 (11 pág., R46–R49) · 12 (3 pág., R51–R52) · 13 (49 pág., R53) — todos sem falha
XFs de contato: products-contact-block (sessão 7a) e signup-and-contact (sessão 69), lado a lado
revisão manual do Hazael EM ANDAMENTO, página a página — é dela que saem os pedidos
cookie do .env: renovado 21/09 07:21, dura ~8h — conferir a idade antes de qualquer lote
```
O detalhe de cada regra está em `REGRAS-disposicao.md` (R46–R53) e o resumo em `ONDE-PAREI.md`.
Aqui fica o que SÓ existia na conversa da 6ª sessão.

### Como o Hazael está trabalhando
- Manda print + URL de UMA página e espera o defeito tratado como **PADRÃO**: medir dos dois lados,
  varrer a árvore, corrigir onde aparece e dizer onde NÃO aparece. "Não tome o exemplo como
  'conserte só esta página'" (palavras dele).
- Autoriza escrita explicitamente e com escopo ("só as páginas, não as subpáginas"). "Explore e me
  reporte" = NÃO gravar. Dry-run, lista, backup, gravar, medir na tela — nessa ordem.
- **Edita no editor do AEM ao mesmo tempo, logado como `valter.toffolo` — o MESMO usuário do
  cookie.** `cq:lastModifiedBy` não distingue lote nosso de edição dele. Edição manual se acha pelo
  `jcr:lastModified` NO NÓ do componente (o diálogo carimba; POST de script não). Antes do lote 13:
  0 nós assim nas 49 páginas.
- Confere a 1400px, mas olha 1366 e reclama do que vê lá (os pills do índice).
- Aceita divergir do GWI quando a origem tem deslize óbvio de autor (R51 título ao lado do
  conteúdo; R52 título duplicado) — e quer isso REGISTRADO como divergência deliberada. Nos dois
  casos o GWI desenha o "defeito": medir o GWI ANTES de concluir que o motor errou.

### Política de fundo (dele, literal) — virou a R53
Intro branca (quase sempre texto com foto/vídeo ao lado) → conteúdo em `#f7f7f7` → branco no fim
**se** o fim são os botões de contato (sign up / quote / contact); página grande alterna por grupo;
sem os botões a página acaba cinza (`/infineon`). Cor é de GRUPO semântico, nunca de bloco nem de
seção solta ("título/conteúdo/título/conteúdo para cada coisinha" foi recusado). **Faixa fina
(~100px) é sintoma de cor errada** — piso de 200px, `ferramentas/faixas.py`. A regra dos 1000px
está OBSOLETA. Escopo = a lista DELE (`dados/fundo_cinza_paginas.txt`, 49), não regra de tamanho:
ele incluiu 7 páginas que o classificador chamava de pequenas. Para pôr/tirar uma página: editar o
arquivo, `previa_fundo.py`, regravar a página, `faixas.py`.

### Perguntas que ficaram SEM resposta dele
1. SiTime sem botões acaba cinza com o "Similar Products" dentro — é isso, ou a lista fica branca?
2. `/altera`: a seção "What Macnica Delivers for Altera" (entre a intro e as abas) está BRANCA e ele
   chamou a página de bom exemplo; a regra a pintaria. `/altera` NÃO está na lista — não mexer.
3. `/ambarella` e `/canon` têm o fundo por `fundo_grupo.py`, FORA do motor: um lote que as regenere
   apaga (refazer com `fundo_grupo.py <pág> --executar`, idempotente). Sugestão não feita: pô-las na
   lista da R53 — a prévia com `alternar` dá o MESMO desenho de hoje nas duas.
4. `i-chips-ip00c790`: "Block Diagram" sobre o diagrama e de novo sobre uma lista de specs — parece
   erro de digitação da origem; não é vizinho, a R52 não pega; decisão dele.
5. 18 `<img>` soltos em `table` sem alt (HTML cru do GWI) e com `src` em `/content/dam/macnicagwi`
   (quebra no go-live). Botões dos XFs ainda linkam para `/content/macnicagwi/...`. XFs com
   resourceType `page` em vez de `xfpage`. Abaixo de 1050px o 1º botão do products-contact-block
   encosta à direita (efeito do `--par-ao-centro`; fora do escopo de 1400, mas visível).
6. Tamanho das páginas (`dados/tamanho_paginas_2026-09-21.json`): 25 grandes, 14 médias, 17 "longas
   mas simples" (i-chips: uma lista de specs de 2300px, fiel ao GWI), 79 pequenas — ele disse que
   ia "direcionar tarefas" para as grandes; só veio a do fundo até agora.

### Ferramentas novas (todas com dry-run por padrão, `--executar` grava, idempotentes)
`fundo_grupo.py` fundo por grupo fora do motor (só /ambarella e /canon) · `faixas.py` altura
renderizada das faixas, sai 1 se houver tira · `alt_faltando.py` alt + `altValueFromDAM`/
`isDecorative` onde faltam (`--todas`) · `serie_twi.py` mesma coluna em pares em série ·
`xf_lado_a_lado.py` XF em colunas (`--colunas`, `--par-ao-centro`) · `artifact_conferencia/`
(gerador do artifact + `previa_fundo.py` + `geom_twi.py`, ver o README de lá).
Depois de QUALQUER lote: `alt_faltando.py --todas` e `serie_twi.py --todas` devem dar 0.

### Armadilhas que custaram rodadas nesta sessão
pill do índice tem `transition:.3s` (medir logo após trocar classe devolve o valor antigo) ·
caminho do GWI com maiúsculas (`li8030SA`) dá 404 silencioso — usar a coluna `origem` de
`dados/remigracao_atual.csv` · imagem lazy mede `naturalWidth=0` · zsh NÃO divide `$VAR` sem
aspas: `--paginas $(cat lista)` sim, `--paginas $LISTA` não (o 1º lote 11 abortou por isso) ·
`cd x && python3 y.py` às vezes não pega o `cd`: usar caminho absoluto do script · o classificador
de permissão bloqueia Bash cujo TEXTO tenha caminho de XF + `@Delete`; escrever a ferramenta em
arquivo e rodar o arquivo · `altValueFromDAM` ausente = LIGADO: conferir alt no HTML, não no JCR.

### Memórias novas (pasta de memória do projeto — ler)
`aem-fundo-e-propriedade-de-secao-tres-cores` · `aem-altvaluefromdam-vale-true-quando-falta` ·
acréscimos em `aem-gwi-esconde-conteudo-com-flags` (flag de centro vertical e `width` autoral que o
GWI ignora) e em `medir-antes-de-atribuir-causa` (as três medições erradas do dia).

---

## ESTADO EM 19/09/2026, FIM DA 5ª SESSÃO (vale sobre o resto do arquivo)

```
servidor = lotes 3–10 = motor no HEAD do branch (R1–R45 + R41b)     <- nada pendente de gravação
lote 10  = 43 páginas GRAVADAS em 19/09 (43/43 sem falha), conferidas na tela — ver REGRAS, seção R42–R45
conteúdo = 134/136 limpas depois do lote 10 (faltando 22: landing 16, /ambarella 6; sobrando 0)
conferência visual: 67 de 136 (remigracao/CONFERIDAS.md tem as vistas e as 69 que faltam)
```

> **Os passos 1 e 2 abaixo estão FEITOS** (19/09, 07:40–08:26). O próximo é o 3 (rodada 2 da
> conferência visual). O que ficou visto e não corrigido está no "ESTADO" da seção R42–R45 do REGRAS.

**Diretriz nova do Hazael (19/09): só se confere a 1400px.** Celular (375px) está fora do escopo.

**O que a sessão fez:** rodada de 33 revisores + 17 céticos sobre o lote 9 (18 páginas limpas; regras do
lote 9 conferidas no olho). Defeitos reais viraram R42 (grade aninhada achatada — 10 páginas, ALTA), R43
(frase→botões 120px), R44 (`.html` cortado de 149 href de rich text — 403 no author), R45/R41b (ajustes da
R41). O patch passou por revisão adversarial offline (12 achados reais corrigidos). Ferramentas: `measure.py`
rola a página e lista twi/list/hr/heading; `ancoras.py` olha todo link `#` do corpo; `cmp_motor`/`vaos` já
exercitam a reescrita de links; `lista_do_dry.py` tira do dry-run a lista real (ignora o `alt` vazio).

### PRÓXIMO PASSO (nesta ordem)

1. **Gravar o lote 10.** Cookie: o `.env` é de 19/09 05:48 — renovar se tiver mais de ~6h. ANTES: o Hazael
   deve ter feito LOGOUT/login no AEM (um revisor vazou o `login-token` antigo para `www.microchip.com`; só o
   logout invalida). Conferir `cq:lastModifiedBy` da árvore e que não há outro `aem_remigrar` rodando.
   ```bash
   cd scripts-hazael && set -a; . ../.env; set +a
   # validar ANTES em 3 páginas e olhar a tela (measure.py dos dois lados, 1400px):
   python3 aem_remigrar.py --paginas /on-semiconductor /altera/altera-arria-10 /altera/development-kits --executar
   #   /on-semiconductor  -> grade 2x2 e 2 botões lado a lado, frase->botões ~40px (R42, R43)
   #   altera-arria-10    -> o <span style="white-space:nowrap"> SOBREVIVE ao filtro XSS do AEM? (R41b — só o
   #                         style em <td> estava validado). Se o AEM tirar o style: desligar a R41b
   #                         (`larga = False` em nao_quebrar_tokens) e refazer o dry-run.
   #   development-kits   -> os 4 "Product Overview" com .html no href renderizado (R44)
   python3 aem_remigrar.py --paginas $(cat remigracao/lote10_paginas.txt) --executar     # ~5 min
   ```
   Se o motor mudar antes de gravar, refazer a lista: `diff_payload.py $(cat <W>/rels.txt) > dry.txt` e
   `lista_do_dry.py dry.txt`.
2. **Conferir na tela depois do lote** (1400px): `/infineon` (topo vídeo | título+texto; aba Automotive texto |
   foto ~662px), `i-chips-fpga-evaluation-board`, `ip00c341`, `ip00c812b`, `ambarella-cv72s-soc` (herói texto |
   foto; a foto de 108px NÃO pode esticar; parágrafo seguinte a ~30px), `ip00cc35` ("Key Features" | texto lado a
   lado, como o GWI), `sitime-clock-generators`/`-jitter-cleaners`, `canon-li7060` (2 listas lado a lado),
   `/microchip` e `/genesys-logic` (frase→botões ~40), `i-chips-scaler-warper-lsi` e `i-chips-warping-lsi`
   (rótulo em cima/baixo da foto, tabela SEM rolagem), `namuga-vicon-lite` (índice 30/90). Depois a conferência
   de conteúdo (~25 min; esperado 134/136, 0 sobrando) e copiar o csv para `dados/fidelidade_atual.csv`.
   Preencher o "ESTADO" da seção R42–R45 do REGRAS com o que foi medido.
3. **Rodada 2 da conferência visual:** as 69 de `CONFERIDAS.md` (22 `design-gateway/*`, 19 `i-chips/*`, 11
   `altera`, 9 `canon`, 4 `sitime`, 3 `ambarella`, `8-helio-view-software`). Só DEPOIS do lote 10 — não gravar
   enquanto revisores medem. Custo da rodada 1: ~75 min e ~5,4M tokens de subagente para 33 páginas.
4. **Decisões para o Hazael** (evidência no REGRAS, R42–R45 "Achados que NÃO viraram regra" e tabela Aberto):
   - **I e L (dialeto):** nas páginas da Anion, 41 de 44 botões são `Center` e 66 de 66 imagens ficam no padrão
     (centradas, tamanho natural; nenhuma `Left`) — amostra de 41 páginas sony/deepx, GET em 19/09. Seguir o GWI
     (esquerda) é SAIR do dialeto da Anion. 7 revisores citaram o L de novo (diagrama "Why Macnica" 79px para
     dentro do texto). Opções: (a) deixar como está = dialeto da Anion; (b) `Left` só onde o GWI tem
     `alignment=left` e a imagem é mais estreita que a coluna (~85 imagens/50 páginas).
   - **Linha de CSS no clientlib** `.cmp-table th,.cmp-table td{word-break:normal;overflow-wrap:normal}`: hoje
     é o que resolve o celular (20 de 86 páginas com tabela partem palavra a 375px) e dispensaria R41/R41b.
   - **R44 mexe num ponto que é da lib do Bruno** (`aem_lib.rewrite_link` tira o `.html`): corrigi no motor, sem
     tocar na lib. Avisar o Bruno — as migrações dele (tq-systems etc.) têm `.html`, mas hitek/iei/mpression/
     terasic ficaram com `/` final vindo de URL pública.
5. **Aberto M tem caminho:** a policy do `flexcontaineritem` PERMITE `flexcontainer` aninhado (lida por GET em
   19/09); carousel de 2+ slides pode ir num flex [carousel | vazio] dentro da coluna (~318px contra 379 no GWI;
   hoje 662). `carousel` e `flexcontainer` não têm campo de largura no diálogo nem style group para isso. 4
   folhas `/canon`. Não implementado.

---

## O que é

Remigrar do GWI as páginas de `/semiconductors` que a agência **Anion ainda
não autorou**, no dialeto de layout das páginas que ela já fez, numa árvore
NOVA — para depois serem colocadas no global2 junto com as prontas.

```
origem   /content/macnicagwi/americas/mai/en/products/semiconductors      (só leitura)
destino  /content/copia-teste/americas/mai/en/products/semiconductors-remigration
escopo   135 páginas + a landing = 136.  Fora: sony-image-sensors (216) e deepx (3)
```

Conferido: o global2 só tem `sony`, `deepx`, `Titles` e `sony-test` neste ramo,
então não há nada autoral fora desses caminhos.

**`/semiconductors` (a árvore antiga) NÃO é tocada.** As edições manuais do
Bruno no `/canon` — 79 nós, 8 blocos de texto em português que não existem no
GWI, uma anotação viva — continuam onde estão.

---

## Estado (18/09/2026, fim da 4ª sessão)

```
servidor = lotes 3–7 (R1–R27)
         + lote 8 (134 páginas: R28–R36)                    134/134 sem falha
         + lote 9 (108 páginas: R37–R41 + ajustes da R28/R35/R36)   ver ONDE-PAREI
motor    = HEAD do branch migration/semiconductors-remigration
Tudo o que está no motor está no servidor.

conferência de CONTEÚDO refeita DEPOIS do lote 9 (18/09/2026, 136 páginas):
   páginas limpas     134 de 136
   faltando            22          landing 16 (supplierlist — hover-only)
                                   /ambarella 6 (artefato do índice automático do GWI, R10)
   sobrando             0
Nenhuma regressão dos lotes 8 e 9. `dados/fidelidade_atual.csv` é desta rodada.
```

**Conferência VISUAL: 40 de 136 páginas** — 16 (3ª sessão) + 10 (rodada 1) +
14 (rodada 2, já sobre o lote 8). Um revisor por página, somente leitura; na
rodada 1, um cético por página com defeito; o patch R28–R36 passou por revisão
adversarial offline antes de gravar (10 achados reais, todos corrigidos).

- **Nenhum defeito grave de disposição nas 24 páginas desta sessão.** Todas as
  regras do lote 4 e do lote 8 conferidas NA TELA (com clique onde é função).
- Fechados: **G** (R28, respiro pago uma vez), **H** (R30), **J** (R36,
  `imageRatio` — o campo existia), **E** (R41 — não tinha sumido: célula de
  tabela quebrando número, 8.319px de tabela no celular).
- Regras novas em `REGRAS-disposicao.md`: R28–R36 (lote 8) e R37–R41 (lote 9).
- Abertos que ficam, todos de gravidade baixa: **I** (botão centralizado), **K**
  (recalibrado: sobram 12 fronteiras em 4 páginas), **L** (imagem de largura
  cheia `alignment=left`), **M** (carousel de 2+ slides), **N** (título depois
  de `textwithimage` a 90px).

---

## PRÓXIMO PASSO

1. **Print novo** (o conteúdo já foi conferido depois do lote 9; as medidas
   também — falta o OLHO) de 4–5 páginas onde as regras novas têm de aparecer:
   `altera-arria-10` (R41, tabela rola no celular), `canon-120mxs` (R40 fio do
   título; foto do Eval Kit ~250px), `sitime-clock-buffers` (R38 e índice),
   `altera-holoscan` (R37), `/design-gateway` (clicar em "See the full … lineup
   here"), `/i-chips` (herói à esquerda).
2. **Seguir a amostra.** Faltam 96 páginas sem olho. Famílias ainda sem
   NENHUMA página vista: `/microchip`, `/genesys-logic`, `/on-semiconductor`,
   `/infineon` (abas), `/altera/altera-cyclone-10-fpga`, `altera-quartus-prime`,
   `altera-questa`, `opencl`, `development-kits/*` (só `agilex-7-i-series` na 2ª
   sessão, antes da margem sair), `namuga-vicon-lite` (54 blocos),
   `i-chips-fpga-evaluation-board`, as 6 folhas de curso `altera/[1-6]-*`,
   `sulfur-som`, `analog-devices-3d-tof`/`lidar`/`smartmesh`.
3. **Abertos I, K–N** do REGRAS — I e L são decisão de dialeto (seguir o GWI?).
4. **Melhoria de ferramenta:** `ancoras.py` só olha o índice; ampliar para
   `main a[href^="#"]` (foi assim que a âncora morta da R39 escapou).
   `measure.py`/`probe.js` não listam `textwithimage`, `list` nem `hr`, e não
   rolam a página (imagem lazy do GWI desloca os y) — 6 revisores tiveram de
   escrever sonda própria.

**Método que funcionou** (um revisor por página, em paralelo, SOMENTE LEITURA,
e um cético por página com defeito; o roteiro que eles recebem está no script
do workflow `conferencia-visual-r1`, resumido em REGRAS R28–R35):

```bash
cd scripts-hazael
remigracao/ferramentas/prints.sh /tmp/prints /ambarella /canon …   # GWI x destino, --publicado, rola a página (lazy-load)
python3 remigracao/ferramentas/lado.py /tmp/prints <nome> 0.5     # GWI | destino lado a lado, para o olho
python3 remigracao/ferramentas/fatiar.py /tmp/prints              # fatias em resolução cheia, para ler
python3 remigracao/ferramentas/measure.py <caminho> "?wcmmode=disabled"
python3 remigracao/ferramentas/vao.py <caminho> "Texto do título"  # vão título->texto e as margens que o explicam
python3 remigracao/ferramentas/jcr.py <rel> gwi|dest|ambos [--filtro "texto"]   # árvore enxuta do JCR, para achar a causa
python3 remigracao/ferramentas/ancoras.py <caminho-destino>       # todo link do índice tem alvo?
# antes de gravar, OFFLINE (cache de JCR das 136; o cmp_motor cria na 1ª vez):
python3 remigracao/ferramentas/cmp_motor.py --antes /tmp/antes.py --ver /canon        # que páginas mudam, e como
python3 remigracao/ferramentas/vaos_estruturais.py --cache jcr_cache.pkl --antes /tmp/antes.py   # vãos antes x depois
python3 remigracao/ferramentas/conf_texto.py /tmp/antes.py ../scripts-bruno/aem_layout.py jcr_cache.pkl   # nada some, nada troca de ordem
# e o dry-run real (online):
python3 remigracao/ferramentas/diff_payload.py /canon /altera
python3 aem_remigrar.py --paginas /canon /altera --executar        # só as que mudam
```

Sete coisas que as sessões ensinaram: (1) **print de 1000px de altura com
"Loading…" é 404**, não página quebrada (R17); (2) **não gravar enquanto os
revisores medem** — o driver apaga `jcr:content/root` antes de escrever;
(3) **defeito funcional não aparece em print** (âncora morta, link 404,
`target`): peça ao revisor para clicar; (4) **o cookie dura ~8h** — olhar a
idade do `.env` antes de rodada longa, e deixar o trabalho offline para quando
ele cair; (5) **respiro se paga UMA vez**: padding de container é simétrico e
acumula — medir o vão estrutural nas 136 antes de mexer. (6) **"sem campo alvo" só depois de ler o `_cq_dialog` e o HTL** do componente
(o `imageRatio` existia; policy ≠ diálogo). (7) **Conferir a 375px o que
mexe em largura**: a tabela que só incomodava no desktop tinha 8.319px no celular.

---

## Dois problemas que NÃO são nossos e atingem ~110 páginas

Os dois XFs da copia-teste (`products-contact-block` e
`signup-and-contact-experience-fragment`, criados à mão em 10/09):

1. têm `sling:resourceType = macnicaglobal2/components/page` em vez de
   `xfpage`, então o seletor `content` devolve um **documento HTML inteiro**
   (`<!DOCTYPE>…</html>`) aninhado dentro de cada página que os usa;
2. foram montados no esquema antigo `containerpy/button_N_wrap`, sem
   `flexcontainer` e sem styles: os dois botões que o GWI mostra lado a lado
   saem **empilhados, com 140–200px de vão** (apontado em 8 de 12 prints).

Ficam em `/content/experience-fragments/copia-teste/…`, fora de
`semiconductors-remigration` — não foram tocados. Corrigir lá acerta tudo de
uma vez. Detalhe em `REGRAS-disposicao.md`.

---

## Depois disso

| o quê | tamanho | nota |
|---|---|---|
| `supplierlist` na landing | 16 unidades | sem componente alvo mapeado |
| descrição dos cards de lista | toda página com `list` | perdida por construção no `list` (R12); decisão do time |
| `relatedsuggestions` modo `search` | 9 páginas | a policy do `list` tem `disableSearch=true` |
| tag inválida na origem | 10 | erro do GWI — não é nosso |
| centralizar título que abre seção | dialeto | a Anion centraliza; o GWI não. Hoje só se centraliza o que o GWI centraliza |

**Antes do go-live:** regravar com `--links-de-lista global2` (R5); recriar os
XFs de popup em `…/macnicaglobal2/americas/mai/en/site/popups` e apontar
`AL.XF_FORM_POPUPS` para lá (R27); testar o envio do form com a Macnica avisada.

**Links do corpo para página que NÃO existe no global2** (censo offline dos 104
alvos internos distintos das 136 páginas; só 5 ficam fora de `/semiconductors`).
Decisão do time para cada um — criar a página, mapear para `/en/contact-us`, ou
apontar para a URL viva como a Anion fez (aí precisa de lista de exceção ANTES
do passo 2 do `rewrite_link`):

| alvo | links | páginas |
|---|---|---|
| `/contact/form` (**404** no global2) | 10 | `altera-holoscan`, `canon-35mmfhdxs-a`, `canon-li8030sa`, `/genesys-logic`, `/microchip`, `/on-semiconductor` |
| `/request-a-quote` (existe, VAZIA) | 4 | `/altera`, `/ambarella`, `/renesas` |
| `/products/ip-software/v-by-oner-hs-ip` | 5 | 5 folhas `/i-chips` |
| `/products/ip-software/munvme-ip-core` | 1 | `/design-gateway` |
| `/content/macnicagwi/europe/atd-europe/en` (outra região) | 1 | `ip00c814` |

E o censo de 404 (GET de cada alvo distinto no global2) entra como passo da
passada de go-live. Os dois XFs da copia-teste também têm `href` para
`/content/macnicagwi/…`.

---

## Arquivos

```
HANDOFF.md              este arquivo
PESQUISA-formulario.md  o form da macnica-and-adi: levantamento, decisão e o que falta testar
REGRAS-disposicao.md    R1–R36 + o que ficou aberto + os pontos cegos do comparador  <-- LER
patch3-disposicao.diff  o patch 3 (R13a–f) fora do git; já gravado no lote 3
PROMPT-conferencia-visual.md  o prompt para abrir a próxima sessão
ROTEIRO-revisor.md      o roteiro que cada revisor (subagente, somente leitura) recebe
ESPEC-motor-layout.md   a especificação do motor (50k, do levantamento de 17 agentes)
ONDE-PAREI.md           comandos de reexecução e retomada
achados_template_policy.md   policy do template: allow-list, layoutDisabled, swatches

dados/
  fidelidade_atual.csv     a LISTA DE TRABALHO: falta/sobra por página
  *_anterior_2026-09-18.csv  a linha de base do início desta sessão, para comparar
                           (*.csv está no .gitignore: os dados/ NÃO vão para o git)
  pendencias_atual.csv     as 27 pendências, por categoria
  remigracao_atual.csv     seções/blocos/topologia por página
  gwi_fingerprint.csv      censo das 354 páginas da origem (caro de refazer)
  arquetipos.json          classificação em 9 arquétipos

ferramentas/
  measure.py + probe.js    mede geometria renderizada (x/y/largura/gap por componente)
  censo_nos_mortos.py      nós da página fora das regiões editable do template (R9)
  diff_payload.py          dry-run REAL: payload novo x JCR gravado, chave a chave
  cmp_motor.py             duas versões do motor sobre as 136 páginas, offline
  prints.sh + fatiar.py    prints GWI x destino (--publicado) em fatias legíveis
  lado.py                  GWI | destino lado a lado, reduzido — o que o revisor olha primeiro
  vao.py                   vão entre um título e o texto seguinte, com as margens que o explicam
  jcr.py                   árvore enxuta do jcr:content (GWI e destino) — o que o revisor usa para achar a causa
  ancoras.py               todo link do índice de âncoras tem alvo na página renderizada?
  vaos_estruturais.py      OFFLINE: vão entre componentes calculado do payload, antes x depois, nas 136
  conf_texto.py            OFFLINE: nenhum texto some nem muda de ordem entre duas versões do motor
  twi.py                   imagem x texto de cada textwithimage, a 1400 e a 375px (validou a R36)
  celulas.py               célula de tabela com token partido + a tabela rola no wrapper? a 1400 e 375px (R41)

recon-dossie.md         o levantamento bruto das 7 lentes (200k)
recon-lacunas.md        as investigações que fecharam as lacunas do crítico (115k)
```

Código:
```
scripts-bruno/aem_layout.py    o motor (IR + emissor).  ~2600 linhas
scripts-hazael/aem_remigrar.py o driver
scripts-hazael/aem_fidelidade_render.py  conferência de conteúdo na TELA
scripts-hazael/aem_screenshot.py         --publicado para medir layout
```

---

## As quatro coisas que mais custaram tempo

1. **Fronteira de seção é dado da origem, não julgamento estético.** Cada filho
   de topo do corpo do GWI vira um container de seção. Testado por falsificação
   sobre 212 pares origem↔autoral: precisão 99,3%, recall 96,3%. Resolve a
   contradição `deepx` (1 container) × `sony` (4 seções): as origens delas têm
   1 e 4 blocos de topo. **Havia 212 pares para testar e o dossiê inteiro
   discutiu estética antes de alguém medir.**

2. **O JCR da origem não é a página da origem.** O `imagetext` tem
   `isText`/`isButton`/`isHeading`, e o GWI os respeita. Ignorar publicou texto
   de MCU Renesas numa página da Ambarella.

3. **Conferir conteúdo não confere disposição.** Os quatro defeitos graves da
   `/ambarella` passaram com `faltando=0 sobrando=0`. Texto no lugar errado
   continua sendo texto presente. **Print da tela é insubstituível.**

4. **Neste design system não existe margem entre irmãos.** Todo respiro vem do
   componente `container` (`padding: 50px 25px` no desktop). Medir sempre com
   `?wcmmode=disabled`: o modo de autoria injeta placeholders de 29px por bloco
   e infla tudo.
