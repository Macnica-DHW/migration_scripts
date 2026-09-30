"""Print the built document to an A4 PDF with page numbers in the footer."""
import asyncio, os, sys
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, '..', '..', 'dados', 'mapas', 'page-acceptance-guidelines')  # outputs stay out of git
DOC = os.path.join(OUT_DIR, 'Page-Acceptance-Guidelines.html')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT_DIR, 'Page-Acceptance-Guidelines.pdf')
FOOT = ('<div style="width:100%;font-family:Arial,Helvetica,sans-serif;font-size:7.5px;color:#6B6B6B;'
        'padding:0 15mm;display:flex;justify-content:space-between">'
        '<span>Page Acceptance Guidelines · Macnica Americas migration to global2 · Version 1.0 · 30 September 2026</span>'
        '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>')
async def main():
    async with async_playwright() as pw:
        br = await pw.chromium.launch()
        pg = await br.new_page()
        await pg.goto('file://' + DOC, wait_until='networkidle')
        await pg.evaluate('document.fonts.ready')
        fonts = await pg.evaluate("[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight)")
        print('fonts loaded:', sorted(set(fonts)))
        await pg.emulate_media(media='print')
        await pg.pdf(path=OUT, format='A4', print_background=True, display_header_footer=True,
                     header_template='<div></div>', footer_template=FOOT,
                     margin={'top': '22mm', 'bottom': '20mm', 'left': '15mm', 'right': '15mm'})
        await br.close()
    print(OUT)
asyncio.run(main())
