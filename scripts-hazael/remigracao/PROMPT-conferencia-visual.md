Continuar a remigração de `semiconductors` no AEM da Macnica — agora a
CONFERÊNCIA VISUAL página a página.
Repositório: ~/projects/migration_scripts   (branch migration/semiconductors-remigration)

LEIA PRIMEIRO, nesta ordem:
  scripts-hazael/remigracao/HANDOFF.md            estado, critério, método, exemplos
  scripts-hazael/remigracao/REGRAS-disposicao.md  R1–R13 + o que está ABERTO + pontos cegos do comparador

Contexto em uma linha: 136 páginas do GWI migradas para
/content/copia-teste/americas/mai/en/products/semiconductors-remigration.
O CONTEÚDO está conferido (132 de 136 limpas; as 4 restantes têm causa
conhecida). A DISPOSIÇÃO só foi conferida em 12 páginas — e antes de a
margem sair.

TAREFA: conferir a disposição das páginas migradas contra o GWI, por print,
e corrigir no motor (scripts-bruno/aem_layout.py) o que for regra.

CRITÉRIO. As páginas migradas NÃO têm margem (sem max-width de 1000px,
padding lateral de 25px): ficam mais largas que o original, e isso é
esperado. O que tem de bater é a DISPOSIÇÃO: que imagem está ao lado, em cima
ou embaixo de que texto e de que título; o que é lado a lado e o que é
empilhado; a ordem dos blocos; e os vãos verticais entre título e texto, que
não podem ficar muito maiores que no original.

COMECE POR:
1. Confirmar no print que "Image Quality" da /ambarella saiu lado a lado
   (bug 13a, corrigido e gravado no lote 3).
2. O vão título→texto do card "CV72S" da /ambarella (aberto; diagnóstico e
   caminho de correção no HANDOFF).
3. Os abertos A–E do REGRAS, começando pela tabela de layout com ícone da
   /analog-devices (gravidade alta).
4. Amostra por arquétipo (dados/arquetipos.json), um revisor por página e um
   cético por página com defeito — foi o que funcionou.

REGRAS INEGOCIÁVEIS
1. macnicagwi e macnicaglobal2 são SOMENTE LEITURA. Não tocar em sony/deepx:
   são da Anion (vão perder a margem depois, mas não por nós).
2. Só escrever em semiconductors-remigration. Não tocar em /semiconductors
   (o Bruno tem edições manuais lá) nem nos XFs da copia-teste.
3. Dry-run primeiro: `ferramentas/cmp_motor.py` e `ferramentas/diff_payload.py`
   mostram o que muda nas 136 ANTES de escrever. Mostrar e só então gravar.
4. Conferência de conteúdo NÃO detecta erro de layout. Print com --publicado.
5. Todo defeito de disposição novo entra em REGRAS-disposicao.md com onde
   apareceu, a causa, a regra e COMO DETECTAR.
6. Commits ao longo do trabalho, no branch, SEM co-author. Quando o código
   estiver à frente do que foi gravado no AEM, dizer isso no commit.

Se aparecer 401, o cookie expirou: renovar AEM_COOKIES no .env da raiz
(Firefox no Windows: F12 > Storage > Cookies > login-token) e retomar com
`--inicio <n>`.
