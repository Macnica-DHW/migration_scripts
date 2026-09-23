#!/usr/bin/env python3
"""
mapa_completo.py [--saida NOME] — SOMENTE LEITURA. Mapa de links COMPLETO do que temos no macnicaglobal2
(americas/mai/en), numa página só, no estilo do global2_link_map.html e sem rodapé:

  1. as raízes do global2_link_map (lista_links.py): solutions, a landing products, boards-modules, semiconductors e
     services — páginas nossas, com par no GWI, sem soft-deleted, recalculadas AO VIVO (querybuilder);
  2. o go-live de mai/en (lista_migradas_mai_en.py --revisao): contact, páginas de topo, about-us e o XF do form de
     evento — as páginas do staging (inclui contact/download e contact/watch) mais /contact-us e a casca Careers.

Pedido do Hazael (23/09/2026): "complete link map of what we have now" a partir do global2_link_map (2).html e do
global2_link_map_2026-09-23.html. Cada parte mantém os grupos que já tinha; os links "open in new tabs" valem para
todo grupo. Só GET (querybuilder, títulos e estado das páginas); nenhum link é conferido.

    python3 mapa_completo.py        # -> dados/mapas/global2_link_map_complete_<data>.html
"""
import argparse
import datetime
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lista_links as ll  # noqa: E402
import lista_migradas_mai_en as lm  # noqa: E402

SEM_PAR_NO_GWI = {"contact-us"}


def main():
    hoje = datetime.date.today().isoformat()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--saida", default=f"global2_link_map_complete_{hoje}.html", help="nome do arquivo em dados/mapas")
    a = ap.parse_args()

    soltas = [ll.solta(p) for p in ll.SOLTAS]
    escolhidas, fora = ll.escolher(ll.RAIZES)
    corpo_a, nav_a, nomes_a = ll.secoes_html(escolhidas, ll.RAIZES, soltas)
    d = lm.dados()
    # /contact-us é só do global2 (casca do admin virada redirect para /contact/form) — sem par no GWI, fora do mapa
    # (pedido do Hazael, 23/09); a casca Careers fica: o GWI tem Careers
    d["extras"] = [e for e in d["extras"] if e["rel"] not in SEM_PAR_NO_GWI]
    corpo_b, nav_b, total_b = lm.grupos_html(d)

    total = len(escolhidas) + len(soltas) + total_b
    escopo = ", ".join(nomes_a) + ", About Us, Contact and top-level pages"
    quando = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    pagina = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Macnica global2 — link map</title><style>{ll.CSS}{lm.CSS_REVISAO}</style></head><body><main>
<h1>Macnica global2 — link map</h1>
<p class="sub">Americas / MAI / EN — {html.escape(escopo)}. {total} pages and 1 experience fragment. Links open the page as a
visitor sees it (outside the editor) in a new tab; the links beside each group open its pages in new tabs, one set at a time
(the browser may ask you to allow pop-ups the first time). You must be logged in to the AEM author. Generated {quando}.</p>
<div class="barra"><input id="q" type="search" placeholder="Filter by title or path…" autocomplete="off">
<label class="tam">Open in sets of<select id="tam"><option>5</option><option selected>10</option><option>20</option><option value="0">all</option></select></label>
<nav>{''.join(nav_a + nav_b)}</nav></div>
{''.join(corpo_a)}
<h2 id="about-contact">About Us, Contact and top-level pages<span class="n">{ll._n(total_b)}</span></h2>
{''.join(corpo_b)}
</main><script>{ll.JS}{lm.JS_REVISAO}</script></body></html>
"""
    saida = lm.SAIDA.with_name(Path(a.saida).name)                       # sempre em dados/mapas
    saida.write_text(pagina, encoding="utf-8")

    for raiz in ll.RAIZES:
        print(f"{raiz}: {len([e for e in escolhidas if e['rel'] == raiz or e['rel'].startswith(raiz + '/')])}")
    print(f"landings avulsas: {[e['rel'] for e in soltas]}")
    for motivo, rels in fora.items():
        print(f"  fora — {motivo}: {len(rels)}")
    print(f"mai/en (go-live): {total_b}")
    print(f"{total} páginas + 1 XF -> {saida}")


if __name__ == "__main__":
    main()
