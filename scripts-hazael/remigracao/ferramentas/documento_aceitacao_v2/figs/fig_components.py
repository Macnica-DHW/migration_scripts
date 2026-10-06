"""Component figures: tables, end-of-page buttons, download buttons, tabs, card lists.

FIGS: fig-tables (Figure 12), fig-buttons-end (Figure 13), fig-buttons-download (Figure 14),
      fig-tabs (Figure 18), fig-cardlist (Figure 19).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from svgkit import (Panel, figure, PURPLE, PURPLE_L, TEXT, TEXT_D, FRAME, ORANGE, GREEN, RED, INK, BAND)


# ---------- small local compositions (Panel helpers only) ----------
def footer(p, h=12):
    """Site footer strip at the bottom of the page frame."""
    x0, _, x1, y1 = p.box
    p.rect(x0, y1 - h, x1 - x0, h, fill=PURPLE_L, rx=3)
    p.label_text(x0 + 6, y1 - h / 2 + 2.4, 'footer', size=6.5, fill=TEXT_D, italic=True)


def dashed_box(p, x, y, w, h, tag=None, color=TEXT_D):
    """Dashed outline of a component (Container, Experience Fragment) with an optional italic tag.
    Same style as the component outlines in Figures 10, 11 and 17."""
    p.rect(x, y, w, h, stroke=color, sw=0.7, dash='3,2', rx=2)
    if tag:
        p.label_text(x + w - 3, y + 7.5, tag, size=6.5, fill=TEXT_D, anchor='end', italic=True)


def link(p, x, y, w):
    """A text link: purple line of text with an underline."""
    p.rect(x, y, w, 3.2, fill=PURPLE, rx=1.2)
    p.line(x, y + 4.8, x + w, y + 4.8, stroke=PURPLE, sw=0.6)


def faded(p, draw, opacity=0.32):
    p.add(f'<g opacity="{opacity}">')
    draw()
    p.add('</g>')


# ---------- Figure 12: tables ----------
def fig_tables():
    W, H = 300, 156
    TX, TY, TW, ROWS, RH, FCW = 24, 62, 252, 6, 13, 84

    def base(p):
        p.page()
        p.heading(TX, 46, 100, level=2)

    a = Panel(W, H, 'bad')
    base(a)
    a.table(TX, TY, TW, rows=ROWS, cols=3, row_h=RH, header=False, align='left', first_col_w=FCW)
    a.rect(TX - 3, TY - 3, TW + 6, RH + 6, stroke=RED, sw=1.1, dash='3,2', rx=3)
    a.callout(TX + TW, 52, 'no header row', color=RED, anchor='end')

    b = Panel(W, H, 'opt', 'Option A')
    base(b)
    b.table(TX, TY, TW, rows=ROWS, cols=3, row_h=RH, header=True, align='left', rounded=False, first_col_w=FCW)
    b.callout(TX + TW, 52, 'header row · left-aligned · square', color=PURPLE, anchor='end', size=6.5)

    c = Panel(W, H, 'opt', 'Option B')
    base(c)
    c.table(TX, TY, TW, rows=ROWS, cols=3, row_h=RH, header=True, align='center', rounded=False, first_col_w=FCW)
    c.callout(TX + TW, 52, 'header row · centred · square', color=PURPLE, anchor='end', size=6.5)

    return figure([
        (a.svg('Table without a header row'), 'The first row holds column labels but is not a header row: the labels look like data.'),
        (b.svg('Table with a header row, left-aligned body'), "Header row; body cells left-aligned; 'No Rounded Corner' style."),
        (c.svg('Table with a header row, centred cells, square corners'),
         "Header row; all cells centred; 'No Rounded Corner' style."),
    ], caption='Figure 12. Tables: a row of column labels is a header row (G13); the two formats offered in question A4.', fid='fig-tables')


# ---------- Figure 13: end-of-page buttons ----------
def fig_buttons_end():
    W, H = 300, 170
    BW, BH, BY = 76, 12, 112

    def content_band(p):
        """Last section of the page, in a grey band, ending well above the contact block."""
        p.band(38, 50)
        p.heading(24, 48, 110, level=2)
        p.text(24, 60, 252, lines=3)

    def xf(p, tag='Experience Fragment'):
        x0, _, x1, _ = p.box
        dashed_box(p, x0 + 6, 94, (x1 - x0) - 12, 50, tag=tag)
        mid = (x0 + x1) / 2
        p.line(mid, 106, mid, 138, stroke=FRAME, sw=0.8, dash='2,2')
        return x0 + 6, mid, x1 - 6

    a = Panel(W, H, 'ok')
    a.page()
    content_band(a)
    l, mid, r = xf(a)
    a.button((l + mid) / 2 - BW / 2, BY, BW, BH, text='Contact Us')
    a.button((mid + r) / 2 - BW / 2, BY, BW, BH, text='Request a Quote')
    a.callout(mid, 136, 'white background', color=GREEN, anchor='middle', size=6.5)
    footer(a)

    b = Panel(W, H, 'bad')
    b.page()
    content_band(b)
    l, mid, r = xf(b, tag='Flex Container, 2 items')
    b.button(l + 5, BY, BW, BH, text='Contact Us')
    b.hatch(l + 5 + BW + 3, BY - 2, mid - (l + 5 + BW + 3) - 3, BH + 4)
    b.button(mid + 5, BY, BW, BH, text='Request a Quote')
    b.hatch(mid + 5 + BW + 3, BY - 2, r - (mid + 5 + BW + 3) - 3, BH + 4)
    b.callout(mid, 136, 'each button pushed to the left of its column', color=RED, anchor='middle', size=6.5)
    footer(b)

    c = Panel(W, H, 'ok')
    c.page()
    c.heading(24, 46, 190, level=1)
    c.rect(24, 58, 30, 2.8, fill=PURPLE, rx=1.2)          # date line
    c.text(24, 68, 252, lines=4)
    c.text(24, 100, 252, lines=3)
    c.callout(276, 138, 'ends with text, no contact block (as on GWI)', color=GREEN, anchor='end', size=6.5)
    footer(c)

    return figure([
        (a.svg('Contact buttons centred on white'),
         'End-of-page contact block (Experience Fragment) on white: both buttons centred in their halves.'),
        (b.svg('Contact buttons left-aligned in two columns'), 'Contact buttons placed on the page instead of the Experience Fragment, each pushed to the left of its half instead of centred.'),
        (c.svg('News item ending with text'),
         'News, press and event items end without the contact block unless GWI has one.'),
    ], caption='Figure 13. Buttons at the end of the page.', fid='fig-buttons-end')


# ---------- Figure 14: download buttons ----------
def fig_buttons_download():
    W, H = 300, 170
    DW, DH = 88, 12

    def previous(p):
        p.page()
        p.heading(24, 46, 120, level=2)
        p.text(24, 58, 252, lines=2)

    def downloads_title(p, x, y):
        p.heading(x, y, 64, level=3)
        p.label_text(x + 70, y + 5, '“Downloads”', size=6.5, fill=TEXT_D, italic=True)

    a = Panel(W, H, 'ok')
    previous(a)
    dashed_box(a, 16, 74, 268, 82, tag='Container')
    downloads_title(a, 34, 84)
    a.text(34, 96, 190, lines=1)                     # bottom at 99
    a.button(34, 107, DW, DH, kind='download', text='Datasheet (PDF)')
    a.button(34, 123, DW, DH, kind='download', text='User Guide (PDF)')
    a.callout(34 + DW + 8, 105, 'directly below its title', color=GREEN, size=6.5)

    b = Panel(W, H, 'bad')
    previous(b)
    downloads_title(b, 34, 78)
    b.text(34, 90, 190, lines=1)                     # bottom at 93
    b.hatch(24, 96, 252, 38)
    b.dim_v(40, 93, 137, '≈ 215px')
    b.button(150 - DW / 2, 137, DW, DH, kind='download', text='Datasheet (PDF)')
    b.callout(270, 118, 'centred, far from its title', color=RED, anchor='end', size=6.5)

    c = Panel(W, H, 'bad')
    previous(c)
    downloads_title(c, 34, 80)
    c.text(34, 92, 190, lines=1)
    # download (51px) beside a contact button (57px), exaggerated so the difference shows
    dy, dh = 106.5, 11                              # download button: shorter
    cy_, ch = 104, 15                               # contact button: taller
    bx = 34 + DW + 36                               # contact button x, leaves room for the first measurement
    c.line(28, cy_, bx + 78, cy_, stroke=RED, sw=0.7, dash='2,2')
    c.line(28, cy_ + ch, bx + 78, cy_ + ch, stroke=RED, sw=0.7, dash='2,2')
    c.button(34, dy, DW, dh, kind='download', text='Datasheet (PDF)')
    c.dim_v(34 + DW + 5, dy, dy + dh, '51px')
    c.button(bx, cy_, 76, ch, text='Contact Us')
    c.dim_v(bx + 76 + 5, cy_, cy_ + ch, '57px')
    c.callout((28 + bx + 78) / 2, cy_ + ch + 12, 'different heights', color=RED, anchor='middle', size=6.5)

    return figure([
        (a.svg('Download buttons stacked under their title'),
         'Download buttons left-aligned, stacked, in the same container as their title.'),
        (b.svg('Download button centred far below its title'), 'Download button centred and separated from its title.'),
        (c.svg('Download button beside a contact button'),
         'A download button beside a contact button: different heights, never on one row.'),
    ], caption='Figure 14. Download buttons.', fid='fig-buttons-download')


# ---------- Figure 18: tabs ----------
def fig_tabs():
    W, H = 300, 170

    a = Panel(W, H, 'ok')
    a.page()
    # scrollbar: the page is scrolled down
    a.rect(287, 52, 3, 110, fill=BAND, rx=1.5)
    a.rect(287, 96, 3, 30, fill=FRAME, rx=1.5)
    a.tabs(6, 41, 288, n=4, active=1, sticky=True)   # white bar 38..51
    a.label_text(11, 47, 'Sticky Tabs', size=6.5, fill=TEXT_D, italic=True)
    a.heading(24, 63, 120, level=2)
    a.dim_v(268, 48, 63, '≤ 60px', side='left')
    a.text(24, 75, 252, lines=3)
    a.image(24, 99, 80, 46)
    a.text(114, 101, 156, lines=6)
    a.text(24, 152, 252, lines=2, last=0.4)

    b = Panel(W, H, 'bad')
    b.page()

    def above_fold():
        b.tabs(6, 42, 288, n=4, active=1)
        b.heading(24, 72, 120, level=2)
        b.text(24, 84, 252, lines=2)
    faded(b, above_fold)
    b.hatch(24, 51, 252, 19)
    b.dim_v(268, 49, 71, '110px', side='left')
    fold = 104
    b.line(6, fold, 294, fold, stroke=RED, sw=1, dash='4,2')
    b.callout(276, fold - 4, '↑ out of view after scrolling', color=RED, anchor='end', size=6.5)
    b.heading(24, 112, 110, level=2)
    b.text(24, 124, 252, lines=2)
    b.image(24, 138, 64, 22)
    b.text(98, 140, 172, lines=3)

    return figure([
        (a.svg('Sticky tab bar pinned under the header'),
         'Sticky Tabs stay visible while scrolling; content starts ≤ 60px below the tab labels.'),
        (b.svg('Tab menu scrolled out of view, large gap under it'),
         'An in-page menu (links to sections of this page) that scrolls out of view; 110px between the tab labels and the content.'),
    ], caption='Figure 18. Tabs and in-page menus.', fid='fig-tabs')


# ---------- Figure 19: card list ----------
def fig_cardlist():
    W, H = 300, 210

    a = Panel(W, H, 'ok')
    a.page()
    a.heading(24, 46, 150, level=1)
    for row, y in enumerate((60, 132)):
        a.card(24, y, 120, 64, date=True, desc=False)
        a.card(156, y, 120, 64, date=True, desc=False)

    b = Panel(W, H, 'bad')
    b.page()
    b.heading(24, 46, 150, level=1)
    # item 1: large image, link and text beside
    b.image(24, 60, 66, 40)
    link(b, 98, 63, 104)
    b.text(98, 73, 150, lines=2)
    # item 2: small image, tight under item 1
    b.image(24, 104, 32, 20)
    link(b, 64, 107, 84)
    b.text(64, 117, 120, lines=1)
    # big empty gap
    b.hatch(24, 127, 252, 25)
    b.dim_v(262, 124, 155, '150px', side='left')
    b.callout(150, 142, 'sizes and gaps differ item to item', color=RED, anchor='middle', size=6.5)
    # item 3: no image at all
    link(b, 24, 155, 120)
    b.text(24, 164, 180, lines=1)
    # item 4: wide flat image
    b.image(24, 174, 120, 24)
    link(b, 152, 178, 70)

    return figure([
        (a.svg('Card List, two cards per row'),
         'Card List of child pages, two per row, with the fields chosen in question A8.1 (pictured: a list whose GWI version shows images, so image, title and date).'),
        (b.svg('Hand-built list of child pages'), 'A list of child pages with different image sizes and uneven gaps.'),
    ], caption='Figure 19. Lists of child pages.', fid='fig-cardlist')


FIGS = {
    'fig-tables': fig_tables,
    'fig-buttons-end': fig_buttons_end,
    'fig-buttons-download': fig_buttons_download,
    'fig-tabs': fig_tabs,
    'fig-cardlist': fig_cardlist,
}
