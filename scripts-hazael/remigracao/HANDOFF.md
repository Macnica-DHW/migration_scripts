# Remigração `semiconductors` — handoff (18/09/2026, 2ª sessão)

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

## Estado (18/09/2026, fim da segunda sessão)

```
136/136 páginas gravadas, 0 falhas            (lote 2, motor com R6–R12)
27 pendências (nenhuma bloqueia o lote)       eram 35

conferência de conteúdo, varredura completa sobre o que ESTÁ no servidor:
                       antes    agora
   páginas limpas         53      133
   unidades faltando     165       27
   unidades sobrando     744        0
   titulo_lista            -        6   (item presente, rótulo diferente — R12)
```

As 27 unidades que faltam estão em 3 páginas e são todas conhecidas:
landing `/semiconductors` 16 (`supplierlist`, sem componente alvo),
`/ambarella` 6 (artefato da origem, R10), `macnica-and-adi` 5 (formulário,
precisa de backend).

**O diagnóstico do handoff anterior estava errado num ponto que importa:** as
~660 unidades "sobrando" NÃO eram a tabela de download repetida. Eram ~22 por
página do `relatedsuggestions` ignorando `maxItems=3` (R8); a tabela respondia
por 4 a 8. E boa parte do resto era ruído do próprio comparador. Ver a memória
`medir-antes-de-atribuir-causa`.

---

## DECISÃO PENDENTE — há um patch no motor que NÃO foi gravado

A conferência visual de 12 páginas achou 10 defeitos de disposição que nenhuma
conferência de conteúdo acusa (R13). Seis viraram código em `aem_layout.py`:

| | o quê | tipo | alcance |
|---|---|---|---|
| 13a | `imagetext` de topo pulava `assetPosition` e as flags `isText`/`isButton`/`isHeading` | **bug de conteúdo** (fura a R1) | 19 nós, 8 páginas |
| 13b | link de download com espaço no nome vira texto morto (filtro XSS) | **bug de conteúdo** | 2 páginas |
| 13c | `hr` colado no bloco de cima | disposição | 15 páginas |
| 13d | título órfão do bloco que introduz | disposição | a maior parte das 64 (não contado à parte) |
| 13e | botões lado a lado que não cabem na largura útil da seção quebram em linhas (com margem: 3→2+1; sem margem: só 4+) | disposição | `/renesas` |
| 13f | heading centralizado no GWI saía à esquerda | disposição | 10 páginas |

O patch muda o payload de **64 das 136 páginas**, inclusive `/altera` e
`/ambarella`, que já tinham sido conferidas na tela. Foi verificado offline
contra o JCR das 136 (nenhum texto some), mas **o lote não foi executado**:
vai além do que foi pedido e mexe no ritmo vertical de páginas aprovadas. O
que está no servidor é o motor SEM o patch.

Branch `migration/semiconductors-remigration`. O motor que gravou o lote 2 é
o commit `137790a`; o patch 3 é o commit `0760e39`, logo acima dele.

```bash
# ver exatamente o que muda
git show 0760e39 -- scripts-bruno/aem_layout.py
#   (o mesmo diff, fora do git: remigracao/patch3-disposicao.diff)

# aceitar: gravar e re-varrer
cd scripts-hazael && python3 aem_remigrar.py --executar

# recusar: voltar o motor ao estado que está no servidor
git checkout 137790a -- scripts-bruno/aem_layout.py
```

Recomendação: aceitar 13a e 13b de qualquer forma (são perda/ressurreição de
conteúdo); 13c–13f são melhoria visível e de baixo risco, mas merecem um print
de `/altera` e `/ambarella` depois de gravar.

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
| **tabela de layout com ícone** | 9 tabelas, 5 páginas | gravidade ALTA: `/analog-devices` mostra grade com borda e ícone de 3px. Aberto A em REGRAS |
| imagem colada no texto de cima | 65 ocorrências, 46 páginas | todo "Why Macnica?" de design-gateway. Aberto B |
| card órfão vira faixa cheia | `/canon` ×3 | Aberto C |
| `<p>` por linha vira parágrafo | sistêmico em rich text | Aberto D |
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
patch3-disposicao.diff  o patch do motor que está no código e NÃO foi gravado
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
