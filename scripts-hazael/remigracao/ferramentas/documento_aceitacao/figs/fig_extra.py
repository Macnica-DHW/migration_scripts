"""Figures added after review: a row of images (G3) and alignment (G17)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from svgkit import Panel, figure, PURPLE, TEXT, TEXT_D, GREEN, RED, ORANGE

W, H = 300, 170


def fig_image_row():
    # Accepted: four logos in equal Flex Container items, same displayed width
    a = Panel(W, H, 'ok')
    a.page()
    a.heading(24, 46, 110, level=2)
    a.text(24, 60, 250, lines=1)
    iw, gap, x0, y0 = 56, 8, 24, 76
    for i in range(4):
        x = x0 + i * (iw + gap)
        a.rect(x, y0, iw, 40, stroke='#CFC7D3', sw=0.6, rx=2, dash='2,2')
        a.image(x + 3, y0 + 8, iw - 6, 24)
    a.dim_h(y0 + 50, x0, x0 + iw, 'same width', above=False)
    a.dim_h(y0 + 50, x0 + 3 * (iw + gap), x0 + 3 * (iw + gap) + iw, 'same width', above=False)
    a.callout(150, 150, 'one row: equal Flex Container items, same Image settings', color=GREEN, anchor='middle', size=6.3)

    # Not accepted: the same logos at different widths
    b = Panel(W, H, 'bad')
    b.page()
    b.heading(24, 46, 110, level=2)
    b.text(24, 60, 250, lines=1)
    widths = [34, 70, 46, 58]
    x = 24
    for w in widths:
        h = w * 0.45
        b.image(x, 80 + (32 - h) / 2, w, h)
        x += w + 10
    b.dim_h(122, 24, 58, 'narrower', above=False)
    b.dim_h(122, 68, 138, 'wider', above=False)
    b.callout(150, 150, 'logos in one row at different widths', color=RED, anchor='middle', size=6.5)

    return figure([
        (a.svg('A row of logos at the same width'), 'Images side by side in one row have the same displayed width.'),
        (b.svg('A row of logos at different widths'), 'Images in one row shown at different widths.'),
    ], caption='Figure 3. Images in a row (G3).', fid='fig-image-row')


def fig_alignment():
    # Accepted: one left edge; image and text of a Text with Image share their top
    a = Panel(W, H, 'ok')
    a.page()
    L = 24
    a.line(L, 40, L, 158, stroke=GREEN, sw=0.8, dash='3,2')
    a.heading(L, 44, 120, level=2)
    a.text(L, 57, 250, lines=2)
    a.table(L, 72, 250, rows=3, cols=2, row_h=9, header=True, align='left', rounded=False)
    a.image(L, 108, 78, 38)
    a.text(L + 88, 108, 162, lines=4)
    a.line(L - 2, 108, 280, 108, stroke=GREEN, sw=0.8, dash='3,2')
    a.button(L, 150, 60, 10, text='Learn more')
    a.callout(282, 105, 'same top', color=GREEN, anchor='end', size=6.3)
    a.callout(L + 66, 157, 'one left edge', color=GREEN, size=6.3)

    # Not accepted: three left edges; text starts below the image top
    b = Panel(W, H, 'bad')
    b.page()
    b.heading(24, 44, 120, level=2)
    b.text(36, 57, 238, lines=2)
    b.table(16, 72, 266, rows=3, cols=2, row_h=9, header=True, align='left', rounded=False)
    for x in (16, 24, 36):
        b.line(x, 40, x, 104, stroke=RED, sw=0.8, dash='3,2')
    b.image(24, 108, 78, 38)
    b.text(112, 122, 162, lines=3)
    b.line(104, 108, 280, 108, stroke=RED, sw=0.8, dash='3,2')
    b.line(104, 122, 280, 122, stroke=RED, sw=0.8, dash='3,2')
    b.button(150, 144, 60, 10, text='Learn more')
    b.callout(282, 118, 'text starts lower', color=RED, anchor='end', size=6.3)
    b.callout(24, 165, 'three left edges; button centred for no reason', color=RED, size=6.3)

    return figure([
        (a.svg('Blocks aligned on one left edge'), 'Title, text, table, image and button share one left edge; image and text start at the same top.'),
        (b.svg('Blocks on different left edges'), 'Blocks start at different left edges; text beside the image starts lower; a lone button is centred.'),
    ], caption='Figure 17. Alignment (G17).', fid='fig-alignment')


FIGS = {'fig-image-row': fig_image_row, 'fig-alignment': fig_alignment}
