# Remigração `semiconductors` — handoff (18/09/2026, 3ª sessão)

Ponto de entrada da próxima sessão. Os outros arquivos desta pasta são
referência; este diz onde parou e o que fazer a seguir.

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

## Estado (18/09/2026, fim da 3ª sessão — conferência visual)

```
servidor = lote 3 (136/136, R1–R14, sem margem; conferido: 0 styleIds de margem)
         + lote 4 (72 páginas: R15, R17–R24)                  72/72 sem falha
         + lote 5 (3 páginas /analog-devices*: R16 sem moldura, R25)   3/3 sem falha
motor    = HEAD do branch migration/semiconductors-remigration
Tudo o que está no motor está no servidor.

conferência de CONTEÚDO (medida sobre o lote 2): 132 limpas, 27 faltando em 3
páginas conhecidas. NÃO foi refeita depois dos lotes 3 e 4 — refazer (25 min):
o lote 4 mexe em estrutura (textwithimage, flexcontainer), não em texto, e o
cmp_motor offline não acusa perda de bloco, mas a tela é quem manda.
```

**Conferência VISUAL: 16 de 136 páginas, todas sem margem**, uma por
arquétipo/família (`/ambarella`, `/analog-devices`, `/renesas`, `/altera`,
`/namuga…`, `/canon`, `/altera/agilex`, `i-chips-scaler-lsi`, `agilex-5`,
`canon-li8030sa`, `udp10g` (×26), `sitime-oscillators` (×6), `/toppan`,
`macnica-and-adi`, `ambarella-n1-soc`, a landing). Dez regras novas
(R15–R25), todas em `REGRAS-disposicao.md`. A revisão manual do Hazael
(`multimodal-sensor-front-ends`, `macnica-and-adi`) entrou como R25, R16 e R19 —
conferidas no print depois de gravar. Os dois exemplos do Hazael:

1. "Image Quality" da `/ambarella`: **confirmado lado a lado** no print.
2. Card "CV72S": **corrigido (R15)** — vão título→texto 50px → 20px (GWI 0);
   o `style="margin-top:0"` sobrevive ao filtro do AEM.

---

## PRÓXIMO PASSO

1. **Print novo das páginas do lote 4** e conferir que cada regra fez na tela
   o que fez no JCR (o método abaixo). Prioridade: `canon-li8030sa` (R21),
   `i-chips-scaler-lsi` e `/toppan` (R19), `/canon` (R18), `udp10g` (R24),
   `sitime-oscillators` (R22 — CLICAR no índice, o print não mostra).
2. **Abertos F–K** do REGRAS. Os dois que mais pesam: **F** vídeo sozinho de
   1350×759 e **G** somatório de paddings entre seções (o botão que agrupa
   com a série seguinte na `/altera/agilex`; a série da `/renesas` partida).
3. Seguir a amostra: faltam folhas de produto simples (arquétipo E, 73
   páginas — só `agilex-5` foi vista) e as outras `design-gateway`.
4. Refazer a conferência de conteúdo (`aem_fidelidade_render.py`).

**Método que funcionou** (um revisor por página, em paralelo, SOMENTE LEITURA;
o brief que eles recebem está descrito em REGRAS, R18–R24):

```bash
cd scripts-hazael
remigracao/ferramentas/prints.sh /tmp/prints /ambarella /canon …   # GWI x destino, --publicado, rola a página (lazy-load)
python3 remigracao/ferramentas/lado.py /tmp/prints <nome> 0.5     # GWI | destino lado a lado, para o olho
python3 remigracao/ferramentas/fatiar.py /tmp/prints              # fatias em resolução cheia, para ler
python3 remigracao/ferramentas/measure.py <caminho> "?wcmmode=disabled"
python3 remigracao/ferramentas/vao.py <caminho> "Texto do título"  # vão título->texto e as margens que o explicam
# antes de gravar: o que muda nas 136, offline, e o dry-run real
git show HEAD:scripts-bruno/aem_layout.py > /tmp/antes.py
python3 remigracao/ferramentas/cmp_motor.py --antes /tmp/antes.py --ver /canon
python3 remigracao/ferramentas/diff_payload.py /canon /altera
python3 aem_remigrar.py --paginas /canon /altera --executar        # só as que mudam
```

Três coisas que esta sessão ensinou: (1) **print de 1000px de altura com
"Loading…" é 404**, não página quebrada — o destino normaliza o nome do nó
(R17); (2) **não gravar enquanto os revisores medem** — o driver apaga
`jcr:content/root` antes de escrever; (3) **defeito funcional não aparece em
print** (âncora morta, banner sem link): peça ao revisor para clicar.

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

**Antes do go-live:** regravar com `--links-de-lista global2` (R5).

---

## Arquivos

```
HANDOFF.md              este arquivo
REGRAS-disposicao.md    R1–R13 + o que ficou aberto + os pontos cegos do comparador  <-- LER
patch3-disposicao.diff  o patch 3 (R13a–f) fora do git; já gravado no lote 3
PROMPT-conferencia-visual.md  o prompt para abrir a próxima sessão
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

recon-dossie.md         o levantamento bruto das 7 lentes (200k)
recon-lacunas.md        as investigações que fecharam as lacunas do crítico (115k)
```

Código:
```
scripts-bruno/aem_layout.py    o motor (IR + emissor).  ~1800 linhas
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
