"""Structure figures: heading hierarchy, heading sizes, heading inside Text with Image, text lines.

FIGS: fig-headings (Figure 4), fig-heading-size (Figure 16), fig-heading-in-twi (Figure 17),
      fig-text-lines (Figure 5).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from svgkit import Panel, figure, PURPLE, TEXT, TEXT_D, FRAME, ORANGE, RED, GREEN

W = 300


# ---------- local helpers (compose Panel primitives only) ----------
def sized_heading(p, x, y, w, th, level, px):
    """Heading bar with an explicit thickness (to show a font size) plus its H tag and px size."""
    p.rect(x, y, w, th, fill=PURPLE, rx=1.5)
    p.label_text(x - 3, y + th / 2 + 2.3, f'H{level}', size=6.5, fill=PURPLE, anchor='end', weight=700)
    p.callout(x + w + 5, y + th / 2 + 2.5, px, color=ORANGE, size=7)


def component_outline(p, x, y, w, h, name):
    """Dashed outline marking one AEM component, with its name at the top right."""
    p.rect(x, y, w, h, stroke=TEXT_D, sw=0.7, dash='3,2', rx=2)
    p.label_text(x + w - 3, y + 7.5, name, size=6.5, fill=TEXT_D, anchor='end', italic=True)


def line_break_icon(p, x, y, color=PURPLE):
    """Small 'return' arrow drawn at the end of a line (a line break)."""
    p.add(f'<path d="M{x+5:.1f},{y-2.5:.1f} L{x+5:.1f},{y+1.5:.1f} L{x:.1f},{y+1.5:.1f} '
          f'M{x+2:.1f},{y-0.5:.1f} L{x:.1f},{y+1.5:.1f} L{x+2:.1f},{y+3.5:.1f}" '
          f'stroke="{color}" stroke-width="0.9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')


# ---------- Figure 4 ----------
def fig_headings():
    H = 180
    a = Panel(W, H, 'ok')
    a.page()
    a.heading(24, 44, 150, level=1)
    a.text(24, 57, 250, lines=3)
    a.heading(24, 84, 110, level=2)
    a.text(24, 96, 250, lines=2)
    a.heading(24, 114, 125, level=2)
    for cx in (20, 154):
        a.rect(cx, 127, 126, 39, fill='#FFFFFF', stroke=FRAME, sw=0.8, rx=3)
        a.heading(cx + 16, 134, 70, level=3)
        a.text(cx + 16, 146, 100, lines=2)

    b = Panel(W, H, 'bad')
    b.page()
    b.heading(24, 44, 150, level=1)
    b.heading(24, 58, 95, level=3)
    b.callout(126, 63, 'H1 → H3 skips H2', color=RED)
    b.text(24, 70, 250, lines=2)
    b.bold_para(24, 92, 100)
    b.callout(131, 97, 'bold text, not a heading', color=RED)
    b.text(24, 104, 250, lines=2)
    b.heading(24, 126, 120, level=1)
    b.callout(151, 132, 'second H1', color=RED)
    b.text(24, 140, 250, lines=3)

    return figure([
        (a.svg('Heading hierarchy: one H1, H2 sections, H3 inside a section'),
         'One H1 (the page title), H2 for each section, H3 inside a section.'),
        (b.svg('Heading hierarchy broken: two H1s, bold text as a title, skipped level'),
         'Several H1s, a section title typed as bold text, and a skipped level.'),
    ], caption='Figure 4. Heading hierarchy.', fid='fig-headings')


# ---------- Figure 16 ----------
ROLES = ['page title', 'section title', 'subsection title']


def _size_panel(label, sizes):
    """sizes: list of (level, px_label, thickness, width) for H1, H2, H3."""
    p = Panel(W, 170, 'opt', label)
    p.page()
    y = 46
    for i, (level, px, th, w) in enumerate(sizes):
        sized_heading(p, 24, y, w, th, level, px)
        p.label_text(232, y + th / 2 + 2.3, ROLES[i], size=6.5, fill=TEXT_D, italic=True)
        y = p.text(24, y + th + 7, 250, lines=2) + 14
    return p


def fig_heading_size():
    a = _size_panel('Option A', [(1, '25px', 7.5, 130), (2, '29px', 9.5, 165), (3, '22px', 6.0, 112)])
    b = _size_panel('Option B', [(1, '25px', 7.5, 130), (2, '22px', 6.0, 112), (3, '18px', 4.5, 94)])
    return figure([
        (a.svg('Option A: theme heading sizes, H2 larger than H1'),
         'Theme sizes: section titles (H2, 29px) are larger than the page title (H1, 25px). '
         'Works the same for headings typed inside text.'),
        (b.svg('Option B: Font Size style, sizes decrease down the hierarchy'),
         'Title components set one size step down: H2 22px, H3 18px. '
         'Headings inside Text with Image cannot take this setting.'),
    ], caption='Figure 16. Heading sizes (question A2).', fid='fig-heading-size')


# ---------- Figure 17 ----------
def fig_heading_in_twi():
    a = Panel(W, 170, 'opt', 'Option A')
    a.page()
    a.heading(28, 44, 140, level=1)
    component_outline(a, 11, 60, 278, 82, 'Text with Image')
    a.image(28, 72, 88, 60)
    a.heading(134, 72, 100, level=2)
    a.text(134, 85, 140, lines=8)

    b = Panel(W, 170, 'opt', 'Option B')
    b.page()
    b.heading(28, 44, 140, level=1)
    component_outline(b, 11, 60, 278, 20, 'Title')
    b.heading(28, 68, 100, level=2)
    component_outline(b, 11, 84, 278, 76, 'Text with Image')
    b.image(28, 94, 88, 60)
    b.text(134, 96, 140, lines=9)

    return figure([
        (a.svg('Option A: section title inside the Text with Image text'),
         'The section title is the first line of the Text with Image text, beside the image.'),
        (b.svg('Option B: section title as a separate Title component'),
         'The section title is a separate Title component above the image and text.'),
    ], caption='Figure 17. Where the section title goes with an image beside text (question A3).',
        fid='fig-heading-in-twi')


# ---------- Figure 5 ----------
ADDRESS = [92, 120, 78, 104]   # widths of 4 short lines (street, city, phone, email)
PARA_GAP = 9                   # empty space between two paragraphs (one empty line)


def fig_text_lines():
    H = 150
    a = Panel(W, H, 'ok')
    a.page()
    a.heading(24, 46, 90, level=2)
    y0 = 62
    for i, w in enumerate(ADDRESS):
        yy = y0 + i * 6
        a.text(24, yy, w, lines=1)
        if i < len(ADDRESS) - 1:
            line_break_icon(a, 24 + w + 4, yy + 1.5)
    a.line(166, y0, 166, y0 + 21, stroke=GREEN, sw=0.8)
    a.callout(172, y0 + 13, 'line breaks (Shift+Enter)', color=GREEN)
    a.text(24, y0 + 3 * 6 + 3 + PARA_GAP, 250, lines=3)

    b = Panel(W, H, 'bad')
    b.page()
    b.heading(24, 46, 90, level=2)
    for i, w in enumerate(ADDRESS):
        yy = y0 + i * 12
        if i < len(ADDRESS) - 1:
            b.hatch(22, yy + 4.5, 126, 6)
        b.text(24, yy, w, lines=1)
    b.callout(160, y0 + 20, 'gap GWI does not show', color=RED)
    b.text(24, y0 + 3 * 12 + 3 + PARA_GAP, 250, lines=3)

    return figure([
        (a.svg('Address lines as one paragraph with line breaks'),
         'Lines that GWI shows with no space between them (an address, a contact block) are one paragraph with line breaks.'),
        (b.svg('Address lines as separate paragraphs with empty lines'),
         'The same lines typed as separate paragraphs: a paragraph gap appears that GWI does not show.'),
    ], caption='Figure 5. Lines that GWI shows together (address, phone and e-mail).', fid='fig-text-lines')


FIGS = {
    'fig-headings': fig_headings,
    'fig-heading-size': fig_heading_size,
    'fig-heading-in-twi': fig_heading_in_twi,
    'fig-text-lines': fig_text_lines,
}
