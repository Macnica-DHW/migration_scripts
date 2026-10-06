# documento_aceitacao_v2 — Page Acceptance Guidelines (HTML e PDF), versão 2.0

Cópia de trabalho de `documento_aceitacao/` (v1.0, do Hazael) atualizada em 06/10/2026 a pedido do Bruno:
critérios de aceite das páginas migradas do GWI para o global2, agora com a antiga Section 5 (perguntas para a
Anion) reescrita como **decisões já tomadas e aplicadas** — a Anion não vai responder, então o que era pergunta
virou declaração, no mesmo formato das guidelines G1–G19. Os 3 apêndices da v1.0 foram removidos (`part4.html`).
SOMENTE LEITURA: nada aqui fala com o AEM.

## Pendência conhecida (06/10/2026)

As **figuras SVG** de G13 (Tables), G14 (Buttons) e A3/A4 (`figs/fig_components.py`, `figs/fig_structure.py`)
ainda mostram o padrão visual da v1.0 e **não foram atualizadas** para bater com o texto novo (tabela 20%/80% com
cor de fundo no header de seção; botões em 4 Flex Container items vazio-botão-botão-vazio). O texto está correto;
as figuras ficaram para trás. Atualizar quando houver tempo dedicado a isso — é edição de SVG via `svgkit.py`,
mais trabalhosa que editar texto.

## Gerar

```
python3 build.py        # HTML autocontido (logo, figuras e CSS embutidos)
python3 make_pdf.py     # PDF A4 com rodapé e número de página, a partir do HTML
```

Saídas em `scripts-hazael/remigracao/dados/mapas/page-acceptance-guidelines/` (fora do git, como os demais relatórios).

## Conferir

```
python3 render_figs.py figs/fig_*.py   # uma PNG por figura, em .../page-acceptance-guidelines/png/
python3 shoot_doc.py                   # prints a 1400px e 390px (acusa rolagem lateral) e um PDF de rascunho
```

## Onde fica cada coisa

- `part1.html` a `part4.html`: o texto (inglês). Seções 1–3, diretrizes G1–G19, perguntas e folha de respostas, apêndices.
  `{{fig:<id>}}` insere uma figura; `<span class="figref" data-fig="<id>">` vira o número dela.
- `figs/fig_*.py`: as figuras (wireframes SVG), desenhadas com `svgkit.py`. Regras visuais em `FIGSPEC.md`.
- `style.css` (tela, celular e impressão A4), `fig.css` (só para `render_figs.py`), `logo_small.png`.

## Ao editar o texto

- As citações da Anion são literais (grafia original incluída), conferidas nos arquivos Issues*.docx e no Slack.
- Documento para cliente: sem detalhe de implementação (backup, verificação, "nada gravado no GWI"), sem jargão
  interno, sem contagem de aprovações, sem "agency". Os números de uma diretriz aparecem iguais no checklist
  (apêndice A), nas figuras e nas perguntas.

## Dependências

Python 3 e Playwright com Chromium (`python3 -m playwright install chromium`). A fonte Noto Sans vem do Google Fonts:
sem rede, o PDF sai em Arial.
