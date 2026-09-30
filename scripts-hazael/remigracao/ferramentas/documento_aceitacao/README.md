# documento_aceitacao — Page Acceptance Guidelines (HTML e PDF)

Gera o documento **Page Acceptance Guidelines** enviado à Anion e à Macnica Americas (versão 1.0, 30/09/2026):
critérios de aceite das páginas migradas do GWI para o global2, perguntas com opções fechadas, folha de respostas,
checklist do revisor e os comentários de revisão da Anion (21 a 28/09) com onde cada um é tratado.
SOMENTE LEITURA: nada aqui fala com o AEM.

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
