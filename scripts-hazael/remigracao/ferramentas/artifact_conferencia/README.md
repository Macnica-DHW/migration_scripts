# Artifact "Conferência da remigração"

https://claude.ai/artifact/CTjAuafxrCas9xAVJe8rDR — checklist das 135 páginas de
`semiconductors-remigration` com o par no GWI, links para o author e status/nota por página.

**O status e a nota ficam no banco do artifact** (capability `db`), coleção `verificacao`,
um documento por página, id = caminho relativo com `/` -> `__` (ex.: `altera__agilex`),
campos `{status: ''|ok|corrigir|duvida, nota, quando}`. Ler com a ferramenta ArtifactData
(`action: list`, `collection: verificacao`) em vez de pedir o relatório ao Hazael.

## Regerar e republicar

    export CONF_SP=<pasta de trabalho>          # padrão: ./_trabalho (ignorada pelo git)
    set -a; . ../../../../.env; set +a
    python3 puxar.py             # baixa o jcr:content das 135 (apagar $CONF_SP/remigcache antes, senão reusa)
    python3 dados_artefato.py    # -> paginas.json  (arquétipo, seções, faixa, spec, vista, fundo)
    python3 gerar_html.py        # -> conferencia.html

Publicar com a ferramenta Artifact passando `url` (a sessão que criou foi a 69; de outra
conversa é obrigatório ler o artifact antes — `action: read` — e publicar com `url`, senão
nasce um artifact novo). NÃO passar `capabilities`: omitido, o `db` declarado é mantido.

## O que a página faz (e um bug que já teve)
- filtros por texto, arquétipo, spec e status; "abrir N páginas (remig)" abre as linhas À MOSTRA;
  "abrir as 49 com fundo novo" abre a lista da R53. Acima de 20 abas pede 2º clique
  (`confirm()` não funciona no iframe). O navegador bloqueia pop-up até o Hazael permitir.
- BUG corrigido em 21/09: o objeto que vem do snapshot do banco é CONGELADO; gravar nele falhava
  calado e o select voltava atrás. Hoje copia o dado e a edição local manda até o servidor
  devolver o mesmo valor (`pend`). Script em `'use strict'`.

`previa_fundo.py <rel do GWI>…` ou `--lista`: sequência de cor por seção que o motor EMITIRIA
(payload real, sem gravar) — usar antes de mexer em `dados/fundo_cinza_paginas.txt`.
`geom_twi.py <caminho completo> 1400,1366`: geometria dos pares texto|foto e dos pills do índice.
