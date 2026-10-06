"""Render every FIGS entry of the given figure modules to PNGs for visual checking.
usage: python3 render_figs.py figs/fig_x.py [more...]  -> dados/mapas/page-acceptance-guidelines/png/<name>.png"""
import sys, os, importlib.util, asyncio
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
CSS = open(os.path.join(HERE, 'fig.css')).read()
OUT_DIR = os.path.join(HERE, '..', '..', 'dados', 'mapas', 'page-acceptance-guidelines')  # outputs stay out of git
async def main(paths):
    items = []
    for p in paths:
        spec = importlib.util.spec_from_file_location(os.path.basename(p)[:-3], p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        for k, fn in m.FIGS.items():
            items.append((k, fn()))
    async with async_playwright() as pw:
        br = await pw.chromium.launch()
        pg = await br.new_page(viewport={'width': 1000, 'height': 800}, device_scale_factor=1.5)
        for k, html in items:
            await pg.set_content(f'<html><head><meta charset="utf-8"><style>{CSS}</style></head><body style="width:940px;padding:10px">{html}</body></html>')
            el = await pg.query_selector('figure')
            os.makedirs(os.path.join(OUT_DIR, 'png'), exist_ok=True)
            out = os.path.join(OUT_DIR, 'png', k + '.png')
            await el.screenshot(path=out)
            print(out)
        await br.close()
asyncio.run(main(sys.argv[1:]))
