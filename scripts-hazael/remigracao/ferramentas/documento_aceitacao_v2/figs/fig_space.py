"""Space figures: side padding (Figure 6), vertical spacing (Figure 7), background bands (Figure 8)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from svgkit import Panel, figure, ORANGE, RED


# ---------- small local annotation helpers (compose Panel primitives, svgkit colours) ----------
def ext(p, x1, x2, y):
    """Dashed extension line: carries an element's edge out to a measurement."""
    p.line(x1, y, x2, y, stroke=ORANGE, sw=0.5, dash='1.5,1.5')


def guide_v(p, x, y1, y2):
    """Dashed vertical guide marking where the content starts or ends."""
    p.line(x, y1, x, y2, stroke=ORANGE, sw=0.6, dash='2,2')


def zero_mark(p, x, y, label='0px', lx=None, ly=None):
    """Two orange arrowheads meeting on line y (a 0px gap), label beside them."""
    p.line(x, y - 8, x, y - 3.5, stroke=ORANGE, sw=0.9)
    p.add(f'<path d="M{x-2.3:.1f},{y-4:.1f} L{x+2.3:.1f},{y-4:.1f} L{x:.1f},{y:.1f} Z" fill="{ORANGE}"/>')
    p.line(x, y + 3.5, x, y + 8, stroke=ORANGE, sw=0.9)
    p.add(f'<path d="M{x-2.3:.1f},{y+4:.1f} L{x+2.3:.1f},{y+4:.1f} L{x:.1f},{y:.1f} Z" fill="{ORANGE}"/>')
    p.callout(x + 5 if lx is None else lx, y + 2.5 if ly is None else ly, label)


# ---------- Figure 6: side padding ----------
def _padding_panel(verdict, label, pad, pad_lbl, width_lbl):
    p = Panel(300, 170, verdict, label)
    x0, y0, x1, _ = p.page()
    cx0, cx1 = x0 + pad, x1 - pad
    cw = cx1 - cx0
    guide_v(p, cx0, 42, 146)
    guide_v(p, cx1, 42, 146)
    p.heading(cx0, 46, 130, level=2, tag=False)
    p.text(cx0, 58, cw, lines=2)
    p.table(cx0, 74, cw, rows=4, cols=3)
    p.text(cx0, 117, cw, lines=2)
    # side padding, both sides
    p.dim_h(136, x0, cx0, '')
    p.callout(cx0 + 3, 138.5, pad_lbl)
    p.dim_h(136, cx1, x1, '')
    p.callout(cx1 - 3, 138.5, pad_lbl, anchor='end')
    # content width
    p.dim_h(154, cx0, cx1, width_lbl, above=True)
    return p


def side_padding():
    a = _padding_panel('opt', 'Option A', 10, '50px', 'content 1,300px')
    b = _padding_panel('opt', 'Option B', 5, '25px', 'content 1,350px')

    c = Panel(300, 170, 'bad')
    x0, y0, x1, _ = c.page()
    cx0, cx1 = x0 + 5, x1 - 5
    c.heading(cx0, 46, 130, level=2, tag=False)
    c.text(cx0, 58, cx1 - cx0, lines=2)
    c.table(x0, 76, x1 - x0, rows=4, cols=3)          # table from window edge to window edge
    c.hatch(x0 - 3, 73, 7, 42)
    c.hatch(x1 - 4, 73, 7, 42)
    c.callout(x0 + 6, 123, '0px')
    c.callout(x1 - 6, 123, '0px', anchor='end')
    c.text(cx0, 131, cx1 - cx0, lines=2)
    c.callout((x0 + x1) / 2, 155, 'table touches the window edge', color=RED, anchor='middle')

    return figure([
        (a.svg('Option A: 50px side padding'),
         'Container Padding Left/Right: Large — 50px each side; content 1,300px wide in a 1,400px page area (R2).'),
        (b.svg('Option B: 25px side padding'),
         'Default padding (Medium) — 25px each side; content 1,350px wide.'),
        (c.svg('Not accepted: table touching the window edge'),
         'Content touching the window edge (no padding) is never accepted.'),
    ], caption='Figure 6. Side padding: the space between the content and the edge of the window (question A1).',
        fid='fig-side-padding')


# ---------- Figure 7: vertical spacing ----------
TX0, TW = 22, 184            # text column
DX = 222                     # measurement column


def spacing():
    H = 182
    # 1. accepted
    a = Panel(300, H, 'ok')
    a.page()
    a.heading(TX0, 46, 110, level=2)
    a.text(TX0, 60, TW, lines=3)                      # 60 .. 76
    a.image(TX0, 98, 90, 36)                          # 98 .. 134
    a.text(TX0, 140, TW, lines=2)                     # 140 .. 149.5
    ext(a, TX0 + 110 + 2, DX + 3, 52)
    ext(a, TX0 + TW + 2, DX + 3, 60)
    a.dim_v(DX, 52, 60, '≤ 45px')
    ext(a, TX0 + TW * 0.62 + 2, DX + 3, 76)
    ext(a, TX0 + 90 + 2, DX + 3, 98)
    a.dim_v(DX, 76, 98, '≤ 125px')
    ext(a, TX0 + 90 + 2, DX + 3, 134)
    ext(a, TX0 + TW + 2, DX + 3, 140)
    a.dim_v(DX, 134, 140, '≥ 20px')

    # 2. not accepted: empty line under the heading, 180px between blocks
    b = Panel(300, H, 'bad')
    b.page()
    b.heading(TX0, 46, 110, level=2)
    b.hatch(TX0, 53.5, TW, 11)
    b.callout(TX0 + TW / 2, 61.5, 'empty line', color=RED, anchor='middle', size=6.5)
    b.text(TX0, 66, TW, lines=3)                      # 66 .. 82
    b.hatch(TX0, 84, TW, 33)
    b.callout(TX0 + TW / 2, 103, 'empty space', color=RED, anchor='middle', size=6.5)
    b.image(TX0, 119, 90, 36)                         # 119 .. 155
    b.text(TX0, 161, TW, lines=2)                     # 161 .. 170.5
    ext(b, TX0 + TW + 2, DX + 3, 52)
    ext(b, TX0 + TW + 2, DX + 3, 66)
    b.dim_v(DX, 52, 66, '≈ 100px')
    ext(b, TX0 + TW + 2, DX + 3, 82)
    ext(b, TX0 + TW + 2, DX + 3, 119)
    b.dim_v(DX, 82, 119, '180px')

    # 3. not accepted: image touching the next paragraph
    c = Panel(300, H, 'bad')
    c.page()
    c.heading(TX0, 46, 110, level=2)
    c.text(TX0, 60, TW, lines=3)
    c.image(TX0, 98, 90, 36)                          # 98 .. 134
    c.text(TX0, 134, TW, lines=2)                     # starts exactly at the image bottom
    c.rect(TX0 - 4, 128, 98, 12, stroke=RED, sw=1, dash='3,2', rx=3)
    ext(c, TX0 + TW + 2, DX - 4, 134)
    zero_mark(c, DX, 134)
    c.callout(DX + 5, 147, 'touching', color=RED)

    return figure([
        (a.svg('Accepted vertical spacing'),
         'Title to its text ≤ 45px (Title component); block to block ≤ 125px; blocks never touch (≥ 20px).'),
        (b.svg('Not accepted: empty line and large gap'),
         'Empty line under a Title: about 100px from title to text (limit 45px); 180px of empty space between two blocks.'),
        (c.svg('Not accepted: image touching the next block'),
         'Image touching the next block (0px).'),
    ], caption='Figure 7. Vertical spacing between headings, text and blocks.', fid='fig-spacing')


# ---------- Figure 8: background bands ----------
BX0, BX1 = 20, 280


def bands():
    H = 210
    # 1. accepted
    a = Panel(300, H, 'ok')
    a.page()
    a.heading(BX0, 45, 150, level=1)
    a.text(BX0, 58, BX1 - BX0, lines=2)               # 58 .. 67.5
    a.band(76, 92, tag='grey band')                   # 76 .. 168
    a.heading(BX0, 84, 100, level=2)                  # 84 .. 90
    ext(a, BX0 + 100 + 1, 126, 84)
    a.dim_v(128, 76, 84, '30–60px')
    a.text(BX0, 96, BX1 - BX0, lines=3)               # 96 .. 112
    a.heading(BX0, 122, 100, level=2)                 # 122 .. 128
    a.image(BX0, 134, 60, 26)                         # 134 .. 160
    a.text(BX0 + 68, 135, BX1 - BX0 - 68, lines=4)
    a.button(80, 180, 66, 11, text='Contact Us')
    a.button(154, 180, 66, 11, text='Request a Quote')

    # 2. not accepted: one-line band, text touching the edge, buttons on grey
    b = Panel(300, H, 'bad')
    b.page()
    b.heading(BX0, 45, 150, level=1)
    b.text(BX0, 58, BX1 - BX0, lines=2)
    b.band(80, 10)                                    # thin strip 80 .. 90
    b.text(BX0, 80, 150, lines=1)                     # touches the band top
    zero_mark(b, 176, 80, lx=181, ly=75.5)
    b.callout(BX1 + 4, 87.5, 'one block', color=RED, anchor='end')
    b.heading(BX0, 100, 100, level=2)
    b.text(BX0, 112, BX1 - BX0, lines=3)              # 112 .. 128
    b.heading(BX0, 138, 100, level=2)
    b.text(BX0, 150, BX1 - BX0, lines=2)              # 150 .. 159.5
    b.band(168, 30)                                   # 168 .. 198
    b.button(80, 177, 66, 11, text='Contact Us')
    b.button(154, 177, 66, 11, text='Request a Quote')
    b.callout(BX1 + 4, 185, 'buttons on grey', color=RED, anchor='end')

    # 3. not accepted: grey on a text-only page
    c = Panel(300, H, 'bad')
    c.page()
    c.heading(BX0, 45, 150, level=1)
    c.text(BX0, 60, BX1 - BX0, lines=3)               # 60 .. 76
    c.text(BX0, 84, BX1 - BX0, lines=3)               # 84 .. 100
    c.band(108, 54)                                   # 108 .. 162
    c.callout(BX1 + 4, 117, 'grey on a page without images or tables', color=RED, anchor='end')
    c.text(BX0, 122, BX1 - BX0, lines=3)              # 122 .. 138
    c.text(BX0, 145, BX1 - BX0, lines=2)              # 145 .. 154.5
    c.text(BX0, 170, BX1 - BX0, lines=3)              # 170 .. 186
    c.text(BX0, 194, BX1 - BX0, lines=1)

    return figure([
        (a.svg('Accepted grey band'),
         'White title and introduction; grey band around the main content (two or more blocks, 30–60px inside); contact buttons on white.'),
        (b.svg('Not accepted: thin band and buttons on grey'),
         'A band with one block, under 200px tall; text touching the grey edge (0px); end buttons on grey.'),
        (c.svg('Not accepted: grey band on a text-only page'),
         'Grey band on a page without images, videos or tables (legal notice, policy, glossary). News, press and event items have no band either.'),
    ], caption='Figure 8. Background bands: grey around the main content; white for the title, the end buttons, pages without images, videos or tables, and news, press and event items.',
        fid='fig-bands')


FIGS = {'fig-side-padding': side_padding, 'fig-spacing': spacing, 'fig-bands': bands}
