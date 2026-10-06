"""svgkit: small wireframe vocabulary for the Page Acceptance Guidelines figures.

Every figure panel is a schematic of a global2 page (or a slice of one) at a reduced
scale. Panels share one visual language so a reader learns it once:

  purple bar ............ a heading (thicker = higher level)
  grey rounded bars ..... lines of body text
  lilac box with a sun .. an image
  purple pill ........... a button (outlined pill = download button)
  light grey full-width . a grey band (section background)
  orange arrows ......... a measurement, with its value
  green / red chip ...... Accepted / Not accepted verdict (or a purple Option chip)

Usage:
    p = Panel(360, 230, verdict='ok', label='Accepted')
    p.page()                       # browser-like frame with header strip
    p.heading(20, 40, 180, level=1)
    p.text(20, 60, 300, lines=3)
    svg = p.svg(title='Short accessible title')

All coordinates are in panel units (viewBox), origin top-left.
"""

from html import escape

PURPLE = '#7F1084'
PURPLE_L = '#E9DDEB'
TEXT = '#B9B4BC'
TEXT_D = '#8C8590'
IMG = '#DCCFE0'
IMG_D = '#B79CBF'
BAND = '#EDEDED'
FRAME = '#CFC7D3'
ORANGE = '#C25A17'
GREEN = '#2E7D32'
RED = '#B00020'
INK = '#3A3A3A'
FONT = "Noto Sans, Arial, Helvetica, sans-serif"


class Panel:
    def __init__(self, w=360, h=230, verdict=None, label=None):
        """verdict: 'ok' (green), 'bad' (red), 'opt' (purple option chip) or None."""
        self.w, self.h = w, h
        self.verdict, self.label = verdict, label
        self.parts = []

    # ---------- low level ----------
    def add(self, s):
        self.parts.append(s)
        return self

    def rect(self, x, y, w, h, fill='none', stroke='none', sw=1, rx=0, dash=None, opacity=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        o = f' opacity="{opacity}"' if opacity is not None else ''
        return self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w,0):.1f}" height="{max(h,0):.1f}" rx="{rx}" '
                        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{o}/>')

    def line(self, x1, y1, x2, y2, stroke=INK, sw=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        return self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def label_text(self, x, y, s, size=8.5, fill=INK, anchor='start', weight=400, italic=False):
        st = ' font-style="italic"' if italic else ''
        return self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" fill="{fill}" '
                        f'text-anchor="{anchor}" font-weight="{weight}"{st}>{escape(s)}</text>')

    # ---------- page furniture ----------
    def page(self, x=6, y=24, w=None, h=None, header=True):
        """Browser-like frame. Returns content box (x0, y0, x1) for convenience."""
        w = self.w - 2 * x if w is None else w
        h = self.h - y - 6 if h is None else h
        self.rect(x, y, w, h, fill='#FFFFFF', stroke=FRAME, sw=1, rx=3)
        if header:
            self.rect(x, y, w, 9, fill='#F4F1F5', rx=3)
            self.rect(x, y + 9, w, 5, fill=PURPLE)
        self.box = (x, y + (14 if header else 0), x + w, y + h)
        return self.box

    def phone(self, x, y, w=120, h=200):
        """Phone outline; returns inner screen box (x0, y0, x1, y1)."""
        self.rect(x, y, w, h, fill='#FFFFFF', stroke=INK, sw=1.4, rx=12)
        self.rect(x + w / 2 - 14, y + 5, 28, 3, fill=FRAME, rx=1.5)
        self.rect(x + 6, y + 14, w - 12, 6, fill=PURPLE)
        return (x + 6, y + 20, x + w - 6, y + h - 10)

    def band(self, y, h, x=None, w=None, fill=BAND, tag=None):
        """Full-width grey section background (defaults to the page frame width)."""
        x0, _, x1, _ = getattr(self, 'box', (6, 0, self.w - 6, 0))
        x = x0 if x is None else x
        w = (x1 - x0) if w is None else w
        self.rect(x, y, w, h, fill=fill)
        if tag:
            self.label_text(x + w - 4, y + 9, tag, size=6.5, fill=TEXT_D, anchor='end', italic=True)
        return self

    # ---------- content blocks ----------
    def heading(self, x, y, w, level=2, color=PURPLE, tag=True):
        """A heading drawn as a bar; level 1..4 sets thickness. tag=True writes 'H1'..'H4' left of it."""
        th = {1: 7, 2: 6, 3: 5, 4: 4}.get(level, 5)
        self.rect(x, y, w, th, fill=color, rx=1.5)
        if tag:
            self.label_text(x - 3, y + th - 0.5, f'H{level}', size=6.5, fill=color, anchor='end', weight=700)
        return self

    def bold_para(self, x, y, w):
        """A bold paragraph pretending to be a title (dark grey, thick)."""
        return self.rect(x, y, w, 5, fill=TEXT_D, rx=1.5)

    def text(self, x, y, w, lines=3, gap=6.5, last=0.62, color=TEXT):
        """Paragraph of `lines` lines; returns the y after the last line."""
        for i in range(lines):
            lw = w * (last if (i == lines - 1 and lines > 1) else 1)
            self.rect(x, y + i * gap, lw, 3, fill=color, rx=1.5)
        self._last_y = y + (lines - 1) * gap + 3
        return self._last_y

    def image(self, x, y, w, h, fill=IMG, label=None):
        self.rect(x, y, w, h, fill=fill, rx=2)
        # sun + mountains icon, scaled to the box
        s = min(w, h)
        cx, cy = x + w * 0.30, y + h * 0.32
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{max(s*0.08,1.5):.1f}" fill="#FFFFFF" opacity="0.9"/>')
        self.add(f'<path d="M{x+w*0.08:.1f},{y+h*0.9:.1f} L{x+w*0.38:.1f},{y+h*0.52:.1f} L{x+w*0.55:.1f},{y+h*0.72:.1f} '
                 f'L{x+w*0.70:.1f},{y+h*0.46:.1f} L{x+w*0.94:.1f},{y+h*0.9:.1f} Z" fill="{IMG_D}"/>')
        if label:
            self.label_text(x + w / 2, y + h / 2 + 3, label, size=7, fill=INK, anchor='middle')
        return self

    def video(self, x, y, w, h):
        self.rect(x, y, w, h, fill='#2B2B2B', rx=2)
        cx, cy, r = x + w / 2, y + h / 2, min(w, h) * 0.16
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#E53935"/>')
        self.add(f'<path d="M{cx-r*0.35:.1f},{cy-r*0.5:.1f} L{cx+r*0.55:.1f},{cy:.1f} L{cx-r*0.35:.1f},{cy+r*0.5:.1f} Z" fill="#FFFFFF"/>')
        return self

    def button(self, x, y, w=60, h=11, kind='primary', text=None):
        """kind: 'primary' (purple pill), 'white' (outlined), 'download' (outlined, smaller, arrow-down icon)."""
        if kind == 'primary':
            self.rect(x, y, w, h, fill=PURPLE, rx=h / 2)
            fc = '#FFFFFF'
        else:
            self.rect(x, y, w, h, fill='#FFFFFF', stroke=PURPLE, sw=1, rx=h / 2)
            fc = PURPLE
        if kind == 'download':
            ix, iy = x + w - 9, y + h / 2
            self.add(f'<path d="M{ix:.1f},{iy-3:.1f} L{ix:.1f},{iy+2:.1f} M{ix-2.5:.1f},{iy-0.5:.1f} L{ix:.1f},{iy+2:.1f} L{ix+2.5:.1f},{iy-0.5:.1f}" '
                     f'stroke="{PURPLE}" stroke-width="1" fill="none"/>')
        if text:
            self.label_text(x + (w - (10 if kind == 'download' else 0)) / 2, y + h / 2 + 2.6, text, size=6.3, fill=fc, anchor='middle', weight=600)
        return self

    def table(self, x, y, w, rows=4, cols=2, row_h=9, header=True, header_col=False, align='left',
              rounded=True, frame=PURPLE, first_col_w=None):
        """Specification table. align: 'left' | 'center'. header: first row as header cells."""
        rx = 4 if rounded else 0
        h = rows * row_h
        self.rect(x, y, w, h, fill='#FFFFFF', stroke=frame, sw=1, rx=rx)
        if header:
            self.rect(x + 0.5, y + 0.5, w - 1, row_h - 0.5, fill=PURPLE_L, rx=rx)
        cw = [first_col_w or w / cols] + [(w - (first_col_w or w / cols)) / (cols - 1)] * (cols - 1) if cols > 1 else [w]
        cx = x
        for i, c in enumerate(cw[:-1]):
            cx += c
            self.line(cx, y, cx, y + h, stroke=frame, sw=0.8)
        for r in range(1, rows):
            self.line(x, y + r * row_h, x + w, y + r * row_h, stroke=frame, sw=0.8)
        if header_col:
            self.rect(x + 0.5, y + 0.5, cw[0] - 1, h - 1, fill=PURPLE_L, opacity=0.8)
        # cell text stubs
        for r in range(rows):
            cx = x
            for c in cw:
                tw = c * (0.5 if (r == 0 and header) else 0.62)
                tx = cx + (c - tw) / 2 if align == 'center' else cx + 4
                col = PURPLE if (r == 0 and header) else TEXT
                hh = 3.2 if (r == 0 and header) else 2.6
                self.rect(tx, y + r * row_h + row_h / 2 - hh / 2, tw, hh, fill=col, rx=1.2)
                cx += c
        return self

    def tabs(self, x, y, w, n=4, active=0, sticky=False):
        pw = min(46, (w - (n - 1) * 5) / n)
        tot = n * pw + (n - 1) * 5
        sx = x + (w - tot) / 2
        if sticky:
            self.rect(x, y - 3, w, 13, fill='#FFFFFF', stroke=FRAME, sw=0.6)
        for i in range(n):
            px = sx + i * (pw + 5)
            if i == active:
                self.rect(px, y, pw, 7, fill=PURPLE, rx=3.5)
            else:
                self.rect(px, y, pw, 7, fill='#FFFFFF', stroke=PURPLE, sw=0.8, rx=3.5)
        return self

    def card(self, x, y, w, h, date=False, desc=True):
        self.rect(x, y, w, h, fill='#FFFFFF', stroke=FRAME, sw=0.8, rx=3)
        ih = h * 0.5
        self.image(x + 3, y + 3, w - 6, ih)
        yy = y + ih + 8
        self.rect(x + 4, yy, (w - 8) * 0.8, 3.6, fill=INK, rx=1.3)
        yy += 7
        if date:
            self.rect(x + 4, yy, 18, 2.6, fill=PURPLE, rx=1.2)
            yy += 6
        if desc:
            self.text(x + 4, yy, w - 8, lines=2, gap=5)
        return self

    # ---------- annotations ----------
    def dim_v(self, x, y1, y2, label, side='right', color=ORANGE):
        """Vertical measurement between y1 and y2 at x, with label."""
        self.line(x, y1, x, y2, stroke=color, sw=0.9)
        for yy in (y1, y2):
            self.line(x - 3, yy, x + 3, yy, stroke=color, sw=0.9)
        tx = x + 4 if side == 'right' else x - 4
        return self.label_text(tx, (y1 + y2) / 2 + 3, label, size=7, fill=color, anchor='start' if side == 'right' else 'end', weight=600)

    def dim_h(self, y, x1, x2, label, above=True, color=ORANGE):
        self.line(x1, y, x2, y, stroke=color, sw=0.9)
        for xx in (x1, x2):
            self.line(xx, y - 3, xx, y + 3, stroke=color, sw=0.9)
        return self.label_text((x1 + x2) / 2, y - 4 if above else y + 10, label, size=7, fill=color, anchor='middle', weight=600)

    def callout(self, x, y, s, color=ORANGE, anchor='start', size=7):
        return self.label_text(x, y, s, size=size, fill=color, anchor=anchor, weight=600)

    def cross_mark(self, x, y, r=5, color=RED):
        self.line(x - r, y - r, x + r, y + r, stroke=color, sw=1.6)
        return self.line(x - r, y + r, x + r, y - r, stroke=color, sw=1.6)

    def check_mark(self, x, y, r=5, color=GREEN):
        return self.add(f'<path d="M{x-r:.1f},{y:.1f} L{x-r*0.3:.1f},{y+r*0.7:.1f} L{x+r:.1f},{y-r*0.8:.1f}" '
                        f'stroke="{color}" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')

    def hatch(self, x, y, w, h, color=RED):
        """Highlight an empty area that is the problem (red dashed box, light fill)."""
        return self.rect(x, y, w, h, fill='#FDECEE', stroke=color, sw=0.9, dash='3,2', rx=2)

    # ---------- output ----------
    def _chip(self):
        if not self.verdict:
            return ''
        col = {'ok': GREEN, 'bad': RED, 'opt': PURPLE}[self.verdict]
        lab = self.label or {'ok': 'Accepted', 'bad': 'Not accepted', 'opt': 'Option'}[self.verdict]
        mark = {'ok': '✓ ', 'bad': '✕ ', 'opt': ''}[self.verdict]
        tw = 7 + len(mark + lab) * 5.1
        return (f'<rect x="6" y="4" width="{tw:.1f}" height="15" rx="7.5" fill="{col}"/>'
                f'<text x="{6 + tw/2:.1f}" y="14.6" font-family="{FONT}" font-size="8.6" fill="#FFFFFF" '
                f'text-anchor="middle" font-weight="700">{escape(mark + lab)}</text>')

    def svg(self, title=''):
        t = f'<title>{escape(title)}</title>' if title else ''
        return (f'<svg class="fig" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'role="img" aria-label="{escape(title)}" xmlns="http://www.w3.org/2000/svg">{t}'
                + self._chip() + ''.join(self.parts) + '</svg>')


def figure(panels, caption=None, fid=None):
    """panels: list of (svg_string, caption_under_panel). Returns an HTML <figure>."""
    cells = ''.join(f'<div class="fp">{svg}<div class="fpc">{cap}</div></div>' for svg, cap in panels)
    idattr = f' id="{fid}"' if fid else ''
    cap = f'<figcaption>{caption}</figcaption>' if caption else ''
    return f'<figure class="figset"{idattr}><div class="fps">{cells}</div>{cap}</figure>'
