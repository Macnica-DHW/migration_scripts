"""Render the built document: full-page slices at 1400 and 390, overflow check, and A4 PDF."""
import asyncio, os, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, '..', '..', 'dados', 'mapas', 'page-acceptance-guidelines')  # outputs stay out of git
DOC = os.path.join(OUT_DIR, 'Page-Acceptance-Guidelines.html')
OUT = os.path.join(OUT_DIR, 'shots'); os.makedirs(OUT, exist_ok=True)
async def main():
    async with async_playwright() as pw:
        br = await pw.chromium.launch()
        for w, tag in ((1400, 'd'), (390, 'm')):
            pg = await br.new_page(viewport={'width': w, 'height': 1000}, device_scale_factor=1)
            await pg.goto('file://' + DOC); await pg.wait_for_timeout(800)
            H = await pg.evaluate('document.documentElement.scrollHeight')
            sw = await pg.evaluate('document.documentElement.scrollWidth')
            wide = await pg.evaluate('''() => [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); return r.right > window.innerWidth + 1 && !e.closest('.tw'); }).slice(0,10).map(e => e.tagName + '.' + e.className + ' ' + Math.round(e.getBoundingClientRect().right))''')
            print(f'{tag}: width {w} scrollWidth {sw} height {H}; overflowing elements: {wide}')
            step = 1000 if tag == 'd' else 1400
            if tag == 'm':
                await pg.set_viewport_size({'width': 390, 'height': 1400})
            n = 0
            for y in range(0, H, step):
                await pg.evaluate(f'window.scrollTo(0,{y})'); await pg.wait_for_timeout(80)
                await pg.screenshot(path=os.path.join(OUT, f'{tag}_{n:02d}.png')); n += 1
            print(tag, n, 'slices')
            if tag == 'd':
                await pg.pdf(path=os.path.join(OUT, 'doc.pdf'), format='A4', print_background=True,
                             margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
        await br.close()
asyncio.run(main())
