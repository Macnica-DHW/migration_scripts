Continuar a remigração de `semiconductors` no AEM da Macnica — CONFERÊNCIA VISUAL
página a página (5ª sessão). Você não tem memória das sessões anteriores: tudo o
que precisa está no repositório.
Repositório: ~/projects/migration_scripts   (branch migration/semiconductors-remigration)

ATENÇÃO — ESTE PROMPT É DA 5ª SESSÃO E FICOU DESATUALIZADO NO MEIO DELA (19/09/2026). O que vale agora está no
TOPO do HANDOFF.md: servidor = motor no HEAD (lote 10 GRAVADO e conferido em 19/09),
a conferência visual está em 67 de 136 (remigracao/CONFERIDAS.md lista as 69 que faltam), SÓ se confere a 1400px
(celular fora do escopo — ignore todo "375px" abaixo), a próxima regra é a R46, e as tarefas 2 e 3 abaixo estão
FEITAS. Revisor NUNCA manda o cookie do AEM para host externo (está no ROTEIRO).

LEIA PRIMEIRO, nesta ordem:
  scripts-hazael/remigracao/HANDOFF.md            estado, próximo passo, método, armadilhas
  scripts-hazael/remigracao/REGRAS-disposicao.md  R1–R41 + tabela "Aberto" (I, K, L, M, N) + pontos cegos do comparador
  scripts-hazael/remigracao/ROTEIRO-revisor.md    o roteiro que cada revisor (subagente) recebe

CONTEXTO EM TRÊS LINHAS. 136 páginas do GWI (origem, SOMENTE LEITURA, fonte da
verdade) foram remigradas para
/content/copia-teste/americas/mai/en/products/semiconductors-remigration.
O CONTEÚDO está conferido nas 136 (134 limpas; as 2 restantes têm causa conhecida).
A DISPOSIÇÃO foi conferida por print em 40 das 136; faltam 96.

ESTADO (fim da 4ª sessão, 18/09/2026): servidor = lotes 3–9 = motor no HEAD do
branch (R1–R41). Nada pendente de gravação. Antes de qualquer coisa, confirme:
  cd ~/projects/migration_scripts && git log -5 --format='%h %ad %s' --date=relative && git status --short
  ps -eo pid,lstart,args | grep -E "[a]em_remigrar|[c]laude"        # outra sessão ativa? commit que não é seu? PARE e avise
  ls -la .env && cd scripts-hazael && python3 remigracao/ferramentas/jcr.py /infineon dest | head -1   # tem de dar HTTP 200
O login-token dura ~8h. Com 401, ou com o .env com mais de ~6h antes de uma
rodada longa, peça ao Hazael para renovar AEM_COOKIES no .env da raiz (Firefox
no Windows: F12 > Storage > Cookies > login-token) e, enquanto isso, faça só o
que é offline.

TAREFA
1. Seguir a amostra da conferência visual: GWI × destino, por print, um revisor
   por página, e corrigir no motor (scripts-bruno/aem_layout.py) o que for REGRA.
   Famílias ainda sem NENHUMA página vista (comece por elas): /microchip,
   /genesys-logic, /on-semiconductor, /infineon (abas), /altera/altera-cyclone-10-fpga
   (tabela de 15 colunas — conferir a R41 a 375px), /altera/altera-quartus-prime,
   /altera/altera-questa-fpga-edition, /altera/opencl-software-technology,
   /altera/development-kits e as 4 folhas dela, namuga-vicon-lite (54 blocos),
   /i-chips/i-chips-fpga-evaluation-board (R37), as folhas de curso /altera/[1-6]-*,
   /altera/sulfur-som---carrier-board, as 3 folhas curtas da /analog-devices
   (3d-time-of-flight, lidar, smartmesh), /ambarella/ambarella-cv72s-soc.
   dados/arquetipos.json e dados/remigracao_atual.csv ajudam a escolher uma por assinatura.
2. Print novo (o OLHO; as medidas já foram conferidas) das páginas onde as regras
   do lote 9 têm de aparecer: altera-arria-10 (R41), canon-120mxs (R40),
   sitime-clock-buffers (R38), altera-holoscan (R37), /design-gateway (R39), /i-chips (R35).
3. Melhorias de ferramenta que custaram tempo aos revisores: `ancoras.py` só olha
   o índice (ampliar para `main a[href^="#"]` sem `getElementById`, fora `#page-top`);
   `measure.py`/`probe.js` não rolam a página nem listam textwithimage, list e hr.
4. Abertos I, K, L, M, N do REGRAS — todos de gravidade baixa. I e L são decisão
   de dialeto (seguir o GWI e alinhar botão/imagem à esquerda?): NÃO decida
   sozinho; pergunte ao Hazael com as opções e a evidência (ele decide rápido assim).

CRITÉRIO. As páginas migradas NÃO têm margem (sem max-width de 1000px, padding
lateral de 25px): ficam mais largas que o GWI, e isso é esperado. O que tem de
bater é a DISPOSIÇÃO: que imagem está ao lado, em cima ou embaixo de que texto e
de que título; lado a lado × empilhado; cards por linha; ordem dos blocos; vãos
verticais (um título nunca mais perto do bloco de cima que do que ele introduz);
e FUNÇÃO que print não mostra (âncora, link, target, aba) — mande o revisor clicar.
sony-image-sensors e deepx são da Anion: fora do escopo, não tocar.

MÉTODO (de scripts-hazael/; use a pasta de rascunho da SUA sessão como <W>)
  # prints GWI x destino (--publicado, rola a página). ~50s por página; rode 2–3 em paralelo
  remigracao/ferramentas/prints.sh <W>/prints /microchip /infineon …      # SIDE=dest|gwi para um lado só
  python3 remigracao/ferramentas/lado.py <W>/prints <nome> 0.5           # escreve em <W>/lado/<nome>__NN.png
  python3 remigracao/ferramentas/fatiar.py <W>/prints                    # <W>/prints/fatias/ — só depois de TODOS os prints prontos
  # <nome> = rel sem a 1ª barra e com / -> __   (/altera/agilex -> altera__agilex)
  # um revisor por página, em paralelo, SOMENTE LEITURA: ferramenta Agent (general-purpose,
  # em segundo plano), prompt = "leia remigracao/ROTEIRO-revisor.md" + <W> + rel + nome dos
  # prints + caminho completo do GWI e do DESTINO + FOCO da página. 10–14 por rodada funcionou.
  # O nome do nó no destino é NORMALIZADO (minúsculas, sem ---): li8030SA->li8030sa,
  # toe200G->toe200g, sulfur-som---carrier-board->sulfur-som-carrier-board, as 2 TEST-*.
  # Workflow multiagente só se o Hazael pedir ("use a workflow"/ultracode); aí vale
  # um cético por página com defeito, que mede de novo e faz o censo do alcance.
  # ferramentas de medida: measure.py, vao.py, jcr.py, ancoras.py, twi.py (textwithimage a 1400 e 375),
  # celulas.py (token partido em tabela, a 1400 e 375)   — precisam do cookie no ambiente: set -a; . ../.env; set +a

  # ANTES DE GRAVAR — offline, sobre o cache de JCR das 136 (o cmp_motor cria com 136 GETs se não existir):
  git show HEAD:scripts-bruno/aem_layout.py > <W>/antes.py
  python3 remigracao/ferramentas/cmp_motor.py --antes <W>/antes.py --cache <W>/jcr_cache.pkl --ver /pagina
  python3 remigracao/ferramentas/vaos_estruturais.py --cache <W>/jcr_cache.pkl --antes <W>/antes.py      # vãos antes x depois
  python3 remigracao/ferramentas/conf_texto.py <W>/antes.py ../scripts-bruno/aem_layout.py <W>/jcr_cache.pkl   # tem de dar 0 texto perdido, 0 ordem
  # dry-run REAL (online) nas 136 -> a lista do lote (o cmp_motor SUBCONTA quando a regra depende do DAM):
  python3 -c "import pickle;[print(o.split('/products/semiconductors',1)[1] or '/') for o in pickle.load(open('<W>/jcr_cache.pkl','rb'))]" > <W>/rels.txt
  python3 remigracao/ferramentas/diff_payload.py $(cat <W>/rels.txt) > <W>/dry.txt   # ~10 min; mudam as páginas com "chaves: +a -r ~c" != 0
  # validar a regra nova em 1–2 páginas (desktop E 375px se mexe em largura), e só então:
  python3 aem_remigrar.py --paginas $(cat <W>/lote.txt) --executar      # SEMPRE com a lista; ~6s por página
  # depois do lote: medir/clicar nas páginas da regra, e a conferência de conteúdo (~25 min, saída em buffer):
  python3 aem_fidelidade_render.py --raiz-origem /content/macnicagwi/americas/mai/en/products/semiconductors \
     --raiz-destino /content/copia-teste/americas/mai/en/products/semiconductors-remigration \
     --pular-contendo sony-image-sensors deepx --output <W>/fidelidade.csv
  # esperado: 134/136, faltando 22 (landing 16 hover-only, /ambarella 6 do índice automático), sobrando 0.
  # copie o csv para remigracao/dados/fidelidade_atual.csv (*.csv e jcr_cache*.pkl estão no .gitignore)

REGRAS INEGOCIÁVEIS
1. macnicagwi e macnicaglobal2 são SOMENTE LEITURA. Não tocar em sony/deepx.
2. Só escrever em semiconductors-remigration. Não tocar em /semiconductors (o
   Bruno tem edições manuais lá) nem nos XFs da copia-teste (o bloco de contato
   empilhado e o `page` em vez de `xfpage` são deles: categoria "não é nosso").
3. Dry-run primeiro, mostrar, e só então gravar — SEMPRE `--paginas <lista>`.
   `aem_remigrar.py --executar` sem lista é bloqueado pelo classificador de
   permissões; se algo for negado, não contorne: reduza o escopo ou pergunte.
4. NÃO gravar enquanto revisores medem (o driver apaga jcr:content/root antes de
   escrever). Antes de lote: conferir cq:lastModifiedBy da árvore (tem de ser um
   só, a conta do cookie) e que não há outro aem_remigrar rodando.
5. Conferência de conteúdo NÃO detecta erro de layout; print NÃO detecta erro de
   função. "O componente não tem campo para X" só depois de ler o _cq_dialog e o
   HTL dele por GET e grepar o repo (o `imageRatio` existia e ficou 2 sessões como
   "sem campo alvo"). Medir antes de atribuir causa; o GWI é a fonte da verdade —
   erro do GWI migra como está.
6. Todo defeito de disposição novo entra em REGRAS-disposicao.md como regra
   numerada (a próxima é R42): onde apareceu, causa, regra, alcance (censo nas
   136), COMO DETECTAR, e o que foi conferido na tela depois de gravar.
7. Commits ao longo do trabalho, no branch, em português, SEM co-author, um por
   unidade lógica; quando o código estiver à frente do servidor, dizer "NÃO
   gravado no AEM" na mensagem. Não commitar scripts-luiza/. Sem push.
8. Ao terminar: atualizar HANDOFF.md, ONDE-PAREI.md e ESTE arquivo; ferramenta do
   rascunho que valeu a pena vai para remigracao/ferramentas/ e é commitada —
   a próxima sessão não enxerga o seu rascunho.

DECISÕES QUE SÃO DO HAZAEL/DO TIME (não resolva no motor sem perguntar)
- Abertos I e L (alinhar botão e imagem à esquerda como o GWI?).
- Uma linha de CSS no clientlib do global2 resolveria a quebra de palavra em
  tabela de forma mais limpa que a R41:
  `.cmp-table th,.cmp-table td{word-break:normal;overflow-wrap:normal}`.
- Links do corpo para página que não existe no global2 (/contact/form é 404,
  /request-a-quote está vazia…): tabela na seção "Antes do go-live" do HANDOFF.
- Os dois XFs da copia-teste; a policy do `embed` (rel=0 do YouTube desabilitado).
