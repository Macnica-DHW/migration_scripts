# pagina/ — conferir e editar UMA página do global2

Ferramentas de página a página: renderizar o que o visitante vê, comparar com o GWI, editar com trava e provar
que só mudou o que foi planejado. Rodar de `scripts-hazael/`; o cookie (`AEM_COOKIES`) vem do `.env` da raiz
(importar o `aem_lib` carrega) e vai **só** para o author. Saídas em `remigracao/dados/paginas/<nome>/` (fora do
git), com `<nome>` = caminho sem `/content/<site>/americas/mai/en/`, `/` -> `__` (ex.: `products__boards-modules__iei`).

```
SOMENTE LEITURA (só GET no author)
  render.py        o que o visitante vê a 1400px (?wcmmode=disabled): texto, links, imagens, vídeos, abas + print
  comparar_gwi.py  render do global2 x render do GWI: TEXTO, LINK-*, IMAGENS, VÍDEOS, ABAS, REF-GWI
  antes_depois.py  render de antes x render de depois da MESMA página: OK / CONFERIR (não faz requisição)
  pixels.py        print do global2: faixas cinza, respiro dentro delas, vãos, fundo dos botões finais (só lê o PNG)

EDITA (dry-run por padrão)
  pagina.py        classe Pagina: edição pontual pela Session travada do aem_lib + conferir()
```

Caminho da página: relativo a `/content/macnicaglobal2/americas/mai/en` ou absoluto (`/content/...`).

## Um exemplo de cada

```bash
python3 remigracao/ferramentas/pagina/render.py /products/boards-modules/iei                  # g2, etiqueta antes
python3 remigracao/ferramentas/pagina/render.py /products/boards-modules/iei --lado gwi
python3 remigracao/ferramentas/pagina/comparar_gwi.py /products/boards-modules/iei
python3 remigracao/ferramentas/pagina/antes_depois.py /products/boards-modules/iei             # antes x depois
python3 remigracao/ferramentas/pagina/pixels.py remigracao/dados/paginas/products__boards-modules__iei/products__boards-modules__iei__g2__antes.png
```

```python
import sys; sys.path.insert(0, "remigracao/ferramentas/pagina")
from pagina import Pagina, TB0, TBS
p = Pagina("/products/boards-modules/iei")            # executar=False: só imprime o plano e simula
p.cinza("/container_1452989800")                      # nós relativos a jcr:content/root/container
p.left("/container_1135112258/textwithimage")
p.conferir()                                          # conteúdo idêntico e na mesma ordem? (na simulação)
```

Página renomeada (global2 `/solutions/...` era `/technology/...` no GWI; `europe` -> `eu`): o lado GWI recebe o
caminho absoluto e o `--nome` do global2, para os dois renders casarem:

```bash
python3 remigracao/ferramentas/pagina/render.py /content/macnicagwi/americas/mai/en/technology/imaging-and-vision \
        --lado gwi --nome solutions__imaging-and-vision
```

## A sequência de sempre

plano -> blacklist fresca -> backup -> mudança pontual -> conferência -> relato.

1. **Antes:** `render.py <p>` e `render.py <p> --lado gwi` (etiqueta `antes`).
2. **Conteúdo x GWI:** `comparar_gwi.py <p>`. Numa passada de layout as diferenças são **relatadas**, não corrigidas.
3. **Plano em dry-run:** `Pagina(<p>)` + as edições + `conferir()`. Nada é enviado; o JCR lido fica em
   `<nome>__jcr__dryrun.json` e o plano em `<nome>__plano__dryrun.json`.
4. **Gravar:** a MESMA lista com `Pagina(<p>, executar=True, snapshot=".../<nome>__jcr__dryrun.json")`. Página
   mudada desde o dry-run = aborta. A Session travada baixa a blacklist, barra GWI/protegida/XF e faz o backup do
   `jcr:content` antes do 1º POST (`remigracao/dados/backups_aem/auto/`). `conferir()` confere a sequência de
   conteúdo, tira o print (`aem_screenshot.py --full --publicado`), roda os pixels antes x depois e gera
   `<nome>__lado__antes_depois.png`.
5. **Depois:** `render.py <p> --etiqueta depois` e `antes_depois.py <p>` (texto, links, imagens, vídeos, abas,
   headings; teste de estabilidade: dois renders sem gravação no meio dão OK).
6. **Pixels nos dois prints:** `pixels.py <nome>__g2__antes.png <nome>__g2__depois.png` — botões finais no branco,
   respiro de 37–50px dentro da faixa, vãos de 125px ou mais marcados com `!`. E **olhar** o lado a lado.

## Trabalho em andamento

`Pagina(..., bloquear_editadas_min=N)` (ou `AEM_BLOQUEAR_EDITADAS_MIN=N` na linha de comando) não grava em página
com algum nó editado nos últimos N minutos, por qualquer conta. No dry-run a Pagina só avisa; com `executar=True`
a trava da Session do aem_lib barra antes do backup.

## Regras (25/09 — regras, não diretrizes)

- Nunca gravar no GWI. Nunca gravar em página da blacklist do tracker (a única fonte; blacklist vazia = nenhuma
  protegida; sem resposta do tracker, nada grava).
- Blacklist fresca antes de cada rodada e de cada página (cada `Pagina()` abre uma Session nova).
- XF (`/content/experience-fragments`), `/conf` e `/apps` só com "You can edit <caminho exato>" do usuário, na linha
  de comando: `AEM_COMPARTILHADO_AUTORIZADO=<caminho> python3 ...` (nunca no `.env`).
- Backup antes de mudar (automático pela Session do `aem_lib`). `EscritaProibida` = parar e perguntar.
- Conteúdo = GWI; layout pode mudar. Mudar só o que foi pedido.

## Limites

- `pixels.py` só entende print do **global2** (tema roxo); o do GWI dá erro (outro tema).
- O print do `render.py` mostra a aba ativa só; o texto/links/imagens de todas as abas estão no JSON, por painel.
- `comparar_gwi.py` não vê defeito que o texto não mostra (página clonada da irmã, grade de supplierlist, tabela
  duplicada): pôr os prints lado a lado e ler a introdução.
