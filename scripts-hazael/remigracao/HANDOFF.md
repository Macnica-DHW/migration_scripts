# Remigração `semiconductors` — handoff (18/09/2026, 4ª sessão)

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

## Estado (18/09/2026, fim da 4ª sessão)

```
servidor = lotes 3–7 (R1–R27), como no fim da 3ª sessão. NADA foi gravado na 4ª.
motor    = HEAD do branch migration/semiconductors-remigration = R1–R36
           >>> O CÓDIGO ESTÁ À FRENTE DO SERVIDOR: R28–R36 NÃO gravadas <<<
           (o login-token expirou às 19h, no meio da rodada de revisores)
ponto de retorno do que está no servidor: commit ad63475
```

**Conferência VISUAL: 26 de 136 páginas** (16 da 3ª sessão + 10 desta: as 6
prioritárias do lote 4 e 4 famílias novas — `i-chips-ip00c787` ×12,
`toe10g` ×11, `altera-stratix-10-dx` ×8, `nvme-ip` ×7). Um revisor e um
cético por página.

- **Todas as regras do lote 4 passaram NA TELA**: R15, R17, R18, R19, R21,
  R22 (com clique: 4 de 4 âncoras rolam), R23, R24, R26, e R7/R8/R11/13a/13c/13f.
- Nenhum defeito grave de disposição. O que dominou foi o **aberto G**
  (9 de 10 páginas) — fechado no código pela **R28**; o **H** pela R30; o **J**
  pela **R36** (`imageRatio` — o campo alvo EXISTE).
- Regras novas, todas em `REGRAS-disposicao.md`: R28 (respiro de um container
  só), R29 (coluna solitária reentra na corrida), R30 (títulos consecutivos;
  título entra na faixa das abas), R31 (`linkTarget`), R32 (`<br>` em célula),
  R33 (inline na raiz), R34 (centro vertical), R24b (respiro em coluna), R35
  (foto de card à esquerda), R36 (`imageRatio`).
- Conferido OFFLINE nas 136 (`conf_texto.py`): nenhum texto some nem muda de
  ordem; 134 payloads mudam (a R28 mexe no ritmo de quase todas).
  `vaos_estruturais.py`: transições com 130px+ caem de 83 para 8.

---

## PRÓXIMO PASSO

0. **Renovar o cookie** (`AEM_COOKIES` no `.env` da raiz) e conferir:
   `python3 remigracao/ferramentas/jcr.py /infineon dest | head -1` → `HTTP 200`.
1. **Conferir os dois styleIds lidos por revisor** na policy (GET):
   `1726800547211` (image, Display Position Left — R35) em
   `/conf/macnicaglobal2/settings/wcm/policies/macnicaglobal2/components/content/image/policy_589419553064100`;
   `1783061491236` (textwithimage, Vertical Center — R34) já bate com o README.
2. **Validar a R36 em UMA página antes do lote** (`canon-li8030sa` e/ou
   `i-chips-ip00c787`): gravar só ela, medir a 1400px (imagem ~415/345px,
   sem buraco sob o texto) **e a 375px** (a imagem NÃO pode ficar com 30% da
   tela). Se o celular quebrar: tirar a R36 do lote (uma linha em
   `_emitir_bloco`, o `imageRatio`) e devolver o J à lista de abertos.
3. **Dry-run real e lote 8** — as 134 páginas:
   ```bash
   cd scripts-hazael
   git show ad63475:scripts-bruno/aem_layout.py > /tmp/antes.py
   python3 remigracao/ferramentas/cmp_motor.py --antes /tmp/antes.py --lista /tmp/lote8.txt
   python3 remigracao/ferramentas/diff_payload.py /altera/agilex /canon /design-gateway/udp10g-ip-10g-udp-offload
   python3 aem_remigrar.py --paginas $(cat /tmp/lote8.txt) --executar
   ```
   Depois: `aem_fidelidade_render.py` nas 136 (conteúdo) e print novo de
   `/altera/agilex`, `/renesas`, `/canon`, `/design-gateway` (abas),
   `nvme-ip`, `canon-li3030sa`, `canon-li8030sa`, `/toppan`, `/ambarella`
   (o `espaco_antes` age no índice de âncoras dela) — é onde cada regra nova
   tem de aparecer.
4. **Rodada 2 da conferência visual** — os prints GWI × destino de 13 páginas
   já estavam tirados quando o cookie caiu, mas são de ANTES do lote 8:
   refazer o lado destino. Páginas: `/4-helio-view-hardware`, `ip00c241`,
   `/altera/altera-arria-10` (+`-gt`), `/altera/altera-stratix-10`,
   `/altera/altera-max-10`, `/altera/altera-holoscan`, `/sitime`,
   `sitime-clock-buffers`, `/design-gateway`, `/i-chips`, `canon-li5030sa`,
   `canon-120mxs`, `analog-devices-radar-development-kit`.
5. **Abertos I e K** do REGRAS (botão centralizado — 10 páginas de evidência a
   favor de "esquerda quando `width<12 offset=0`"; série de itens título+texto
   a 60px contra 28).

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

Cinco coisas que as sessões ensinaram: (1) **print de 1000px de altura com
"Loading…" é 404**, não página quebrada (R17); (2) **não gravar enquanto os
revisores medem** — o driver apaga `jcr:content/root` antes de escrever;
(3) **defeito funcional não aparece em print** (âncora morta, link 404,
`target`): peça ao revisor para clicar; (4) **o cookie dura ~8h** — olhar a
idade do `.env` antes de rodada longa, e deixar o trabalho offline para quando
ele cair; (5) **respiro se paga UMA vez**: padding de container é simétrico e
acumula — medir o vão estrutural nas 136 antes de mexer.

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
