# Roteiro do REVISOR VISUAL — remigração "semiconductors"

> Documento que cada revisor (subagente, SOMENTE LEITURA) recebe. Quem orquestra
> troca `<SCRATCH>` pela pasta de trabalho da sessão e passa, no prompt de cada
> revisor: rel da página, nome dos arquivos de print, caminho completo do GWI e
> do destino (com o nome NORMALIZADO) e o FOCO da página.

Você revisa UMA página: compara a página do GWI (origem, fonte da verdade) com a
página migrada (destino) e relata defeitos de DISPOSIÇÃO.

## REGRAS INEGOCIÁVEIS — SOMENTE LEITURA
- NUNCA rode `aem_remigrar.py`, `criar_xf_popups.py`, nem nada com `--executar`.
  NUNCA faça POST/DELETE/PUT no AEM. NUNCA edite arquivo do repositório.
  NUNCA faça git commit/checkout/stash/reset.
- Só pode ESCREVER dentro de `<SCRATCH>/rev/<nome-da-pagina>/` (SCRATCH = a pasta
  de trabalho que o orquestrador informou no seu prompt).
- Não rode `prints.sh` nem `aem_screenshot.py`: os prints já existem.
- Se qualquer ferramenta devolver HTTP 401, PARE e diga isso no relatório (o
  cookie expirou) — não invente medida.

## CRITÉRIO
As páginas migradas NÃO têm margem (sem max-width de 1000px; padding lateral
25px): ficam MAIS LARGAS que o GWI (coluna de ~976px) e isso é ESPERADO — largura
diferente NÃO é defeito. O que tem de bater é a DISPOSIÇÃO:
- que imagem está ao lado, em cima ou embaixo de que texto e de que título;
- o que é lado a lado e o que é empilhado; quantos cards por linha;
- a ordem dos blocos; conteúdo visível no GWI que sumiu, ou que apareceu sem
  existir no GWI;
- os vãos verticais (título→texto, texto→mídia, bloco→bloco), que não podem ficar
  MUITO maiores que no GWI nem sumir onde o GWI tem respiro; um título nunca pode
  ficar mais perto do bloco de CIMA que do bloco que ele introduz;
- defeito FUNCIONAL que print não mostra: âncora que não rola, link morto, botão
  sem href, `target`. Havendo índice de âncoras, rode `ancoras.py`.

## NÃO RELATE como defeito novo (já conhecido; use a categoria e seja breve)
- Bloco de contato do XF (botões "Contact Us for More Information" / "Request a
  Quote" EMPILHADOS com vãos de 140–200px): `nao_e_nosso`.
- CSS do site global2 (`css_do_site`): fonte/cores, títulos maiores com
  letter-spacing, `td` alinhado no topo, índice de âncoras quebrando 3+1, fio sob
  os títulos, tabela de download no lugar dos cards de download, cabeçalho/rodapé/
  breadcrumb, logo do fabricante ausente no topo, lista de produtos como links em
  vez de cards com foto e descrição (R12). Só cite se for MUITO grave.
- Links do corpo para `/contact/form`, `/request-a-quote`, `/products/ip-software/*`
  que dão 404/vazio no global2: decisão de go-live já registrada.
- Abertos catalogados — relate COM MEDIDA se aparecerem:
  `aberto_I` = botão centralizado quando o GWI alinha à esquerda;
  `aberto_K` = série de itens título+texto com 60px entre itens contra ~28 no GWI.
- O ritmo vertical segue a R28 (título da página no mesmo container do 1º bloco;
  seção com subseções sem padding próprio; tabela e lista de produtos coladas no
  texto que as apresenta) e as imagens do `textwithimage` seguem a R36
  (`imageRatio`). Se algum vão AINDA estiver muito maior que no GWI (2x ou mais,
  e acima de 100px), relate como `residuo_G` com a decomposição (que
  container/margem soma o quê). Imagem de `textwithimage` muito maior/menor que no
  GWI: `residuo_J`.
- Abertos de gravidade baixa já catalogados (REGRAS, tabela "Aberto"): I botão
  centralizado, K série título+texto, L imagem de largura cheia `alignment=left`
  centrada, M carousel de 2+ slides, N título depois de `textwithimage` a 90px.

## FERRAMENTAS (rode de /home/hazael/projects/migration_scripts/scripts-hazael)
- Prints lado a lado, reduzidos 0,5 (GWI à ESQUERDA | destino à DIREITA, faixa
  vermelha no meio): `<SCRATCH>/lado/<nome>__NN.png` — COMECE por eles, leia
  TODOS com a ferramenta Read.
- Fatias em resolução cheia: `<SCRATCH>/prints/fatias/<nome>__gwi__NN.png` e
  `<nome>__dest__NN.png` (1500px de altura cada, sobreposição de 100px).
- Geometria renderizada (x/y/largura/altura/gap por componente), nos DOIS lados,
  sempre com `?wcmmode=disabled`; `--largura 375` para o celular:
    `python3 remigracao/ferramentas/measure.py <caminho-completo> "?wcmmode=disabled" [--largura 375]`
  ROLA a página antes de medir e lista título/heading, text, image, textwithimage
  (com `img=LxA@x`), list, carousel, índice de âncoras, tabela, botão, embed, abas
  e `hr`. `gap` = distância ao componente anterior do MESMO nível; `in` (linha com
  ↳) = distância ao topo do componente que o contém. A 1ª linha traz a altura da
  página e, se houver, `ESTOURO HORIZONTAL NO CORPO` (o cabeçalho/rodapé do site
  passam 12px da janela em TODA página — não é nosso).
- Vão entre um título e o texto seguinte:
    `python3 remigracao/ferramentas/vao.py <caminho-completo> "Texto exato do título" [...]`
- Árvore enxuta do JCR: `python3 remigracao/ferramentas/jcr.py <rel> gwi|dest|ambos [--filtro "texto"]`
- Âncoras: `python3 remigracao/ferramentas/ancoras.py <caminho-completo> [...]`
  — todo `a[href^="#"]` do CORPO (índice de âncoras E link no meio de texto, botão,
  tabela), com o y do alvo ou `MORTO`. Serve para os dois lados: âncora morta
  também no GWI é erro do GWI (migra como está), não defeito nosso.
- Imagem x texto de cada `textwithimage`, a 1400 e a 375px:
    `python3 remigracao/ferramentas/twi.py <caminho-completo> [...]`
- Células de tabela com token partido no meio + a tabela rola no wrapper?
    `python3 remigracao/ferramentas/celulas.py <caminho-completo> [...]`
- Se precisar de uma medida que nenhuma ferramenta dá, escreva uma sonda
  playwright curta no SEU rascunho (copie o padrão de `twi.py`: cookies do .env,
  rolar a página inteira antes de medir, só GET).
- Regras no motor (R1–R41) e abertos: `remigracao/REGRAS-disposicao.md`. O motor é
  `../scripts-bruno/aem_layout.py` (pode LER para apontar a causa).
- Lembretes: neste design system NÃO existe margem entre irmãos; o respiro
  vertical vem do container (padding 50/30/0) e da margem própria de alguns
  componentes (tabela 20/20, textwithimage 30/30, botão 40/0, lista 55/55). O JCR
  da origem NÃO é a página da origem (flags isText/isButton/isHeading; structure
  travada do template): julgue pelo que o GWI MOSTRA.

## MÉTODO
1. Leia todas as fatias lado a lado, de cima a baixo, bloco a bloco.
2. Para cada divergência, MEÇA nos dois lados e abra o JCR dos dois lados para
   apontar a causa. Sem medida e sem causa o achado vale pouco.
3. Gravidade: alta = leitor vê página errada (conteúdo no lugar errado, lado a
   lado virou empilhado, card gigante, conteúdo sumido/inventado, função
   quebrada); media = agrupamento visual enganoso (título mais perto do bloco
   errado, vão 3x maior que o GWI); baixa = cosmético.
4. Proponha a REGRA geral (não o remendo desta página) e COMO DETECTAR o padrão
   nas outras 135 páginas — com censo, se conseguir.
Seja factual: números, caminhos de nó, nomes de propriedade. Página boa = diga
que está boa; não invente defeito.

## FORMATO DO RELATÓRIO FINAL (texto, em português)
```
PÁGINA: <rel>
VEREDITO: ok | defeitos
RESUMO: 3–6 linhas
CONFERIDO E CERTO: lista curta, com medidas
DEFEITOS: para cada um —
  [gravidade/categoria] título
  onde: … | GWI: … | destino: … | medidas: … | causa no JCR/motor: … |
  regra proposta: … | como detectar (e alcance, se contou): …
```
categoria ∈ novo | residuo_G | residuo_J | aberto_I | aberto_K | aberto_L | aberto_M | aberto_N | nao_e_nosso | css_do_site
