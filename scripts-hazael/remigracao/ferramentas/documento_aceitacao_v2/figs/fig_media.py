"""Figures for images, videos and the phone view (guidelines G10, G11, G12, G18).

Desktop panels: page frame from x=6 to x=294 (288 units ~ 1,400px, 1 unit ~ 4.9px);
content runs from L=20 to R=280 so the heading tags (H2) stay inside the frame.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from svgkit import Panel, figure, ORANGE, RED, FRAME, TEXT_D, GREEN, INK

L, R = 20, 280          # content edges of a desktop panel
W = R - L               # content width (~1,270px)


def outline(p, x, y, w, h, name):
    """Dashed outline marking one AEM component, its name in italics at the top right (as in Figures 13, 14, 17)."""
    p.rect(x, y, w, h, stroke=TEXT_D, sw=0.7, dash='3,2', rx=2)
    p.label_text(x + w - 3, y + 7.5, name, size=6.5, fill=TEXT_D, anchor='end', italic=True)


def guide(p, x1, y1, x2, y2, color=ORANGE):
    """Thin dashed extension line that ties a measurement to the edge it measures."""
    p.line(x1, y1, x2, y2, stroke=color, sw=0.6, dash='2,1.5')


# ---------------------------------------------------------------- fig-twi (Figure 9)
def fig_twi():
    PW, PH = 300, 170

    # 1. Accepted: image fills its column, gap to text <= 60px, bottoms aligned
    a = Panel(PW, PH, 'ok')
    a.page()
    a.heading(L, 46, 120, level=2)
    ix, iw, iy, ih = L, 92, 58, 60                 # image column ~ 36% of the content
    tx = ix + iw + 12                               # 12 units ~ 58px
    a.image(ix, iy, iw, ih)
    a.text(tx, iy + 1, R - tx, lines=9)             # ends at ~iy+56: same height as the image
    guide(a, ix + iw, iy + ih, ix + iw, 131)
    guide(a, tx, iy + 56, tx, 131)
    a.dim_h(131, ix + iw, tx, '≤ 60px', above=False)

    # 2. Accepted - Wrap: long text continues under the image
    b = Panel(PW, PH, 'ok', label='Accepted — Wrap')
    b.page()
    b.heading(L, 46, 120, level=2)
    ix, iw, iy, ih = L, 92, 58, 50
    tx = ix + iw + 12
    b.image(ix, iy, iw, ih)
    b.text(tx, iy + 1, R - tx, lines=8, last=1)     # beside the image
    y_under = iy + 1 + 8 * 6.5
    b.text(L, y_under, W, lines=6)                  # continues full width under it (Wrap)
    b.callout(R, 158, 'text continues under the image', color=GREEN, anchor='end')

    # 3. Not accepted: small image centred in a wide column; far taller than its text
    c = Panel(PW, PH, 'bad')
    c.page()
    c.heading(L, 46, 120, level=2)
    col_w, iy = 112, 58
    iw, ih = 42, 50
    c.hatch(L, iy, col_w, ih)
    c.image(L + (col_w - iw) / 2, iy, iw, ih)
    tx = L + col_w + 12
    t_end = c.text(tx, iy + 1, R - tx, lines=3)     # 3 lines end ~24 units below the top
    img_bot = iy + ih
    dx = tx + 10
    guide(c, L + (col_w + iw) / 2, img_bot, dx + 3, img_bot)
    c.dim_v(dx, t_end, img_bot, '+160px')   # 33 units ~ 160px
    c.callout(L + 4, iy + ih + 10, 'empty column space', color=RED, size=6.8)

    return figure([
        (a.svg('Text with Image: image on the left filling its column, text beside it'),
         'Image on the left fills its column; image to text ≤ 60px; image at most 60px or a quarter of the text height taller than the text, whichever is larger.'),
        (b.svg('Text with Image with Wrap: long text continues under the image'),
         'Text taller than the image by more than 120px or half the image height, whichever is larger: Wrap, so the text continues under the image.'),
        (c.svg('Text with Image: small image centred in a wide column, taller than its text'),
         'Small image centred in a wide column (more than 60px to the text); image 160px taller than its text.'),
    ], caption='Figure 9. Image beside text (Text with Image, image on the left).', fid='fig-twi')


# ---------------------------------------------------------------- fig-standalone-image (Figure 10)
def fig_standalone_image():
    PW, PH = 300, 170
    iy, ih = 76, 60
    mid_w = 110                                     # mid-size image, ~540px

    def top(p):
        p.page()
        p.heading(L, 46, 120, level=2)
        p.text(L, 58, W, lines=2)

    # 1. Not accepted: mid-size image alone, centred, empty space both sides
    a = Panel(PW, PH, 'bad')
    top(a)
    a.hatch(L, iy, W, ih)
    mx = L + (W - mid_w) / 2
    a.image(mx, iy, mid_w, ih)
    for cx in (L + (mx - L) / 2, mx + mid_w + (R - mx - mid_w) / 2):
        a.cross_mark(cx, iy + ih / 2, r=9)
    a.dim_h(iy + ih + 8, mx, mx + mid_w, '≈ 540px', above=False)

    # 2. Accepted: wide file fills the content width (Expand to Fit Width)
    b = Panel(PW, PH, 'ok')
    top(b)
    b.image(L, iy, W, ih)
    b.label_text(R - 4, iy + 9, 'file ≥ 900px wide', size=6.8, fill=INK, anchor='end')
    b.label_text(R - 4, iy + 18, 'Expand to Fit Width (≤ 1.5×)', size=6.8, fill=INK, anchor='end', italic=True)
    b.dim_h(iy + ih + 8, L, R, '≈ 1,300px', above=False)

    # 3. Accepted: the same mid-size image beside the text it illustrates
    c = Panel(PW, PH, 'ok')
    c.page()
    c.heading(L, 46, 120, level=2)
    ty = 69
    outline(c, L - 4, 56, W + 8, ty + ih + 6 - 56, 'Text with Image')
    c.image(L, ty, mid_w, ih)
    tx = L + mid_w + 12
    c.text(tx, ty + 1, R - tx, lines=9)

    return figure([
        (a.svg('A mid-size image alone, centred, with empty space on both sides'),
         'An image narrower than 900px, alone and centred, with wide empty space on both sides.'),
        (b.svg('A wide image filling the content width'),
         'An image whose file is at least 900px wide fills the content width, enlarged at most 1.5×.'),
        (c.svg('The mid-size image beside the text it illustrates'),
         'An image that GWI shows next to a paragraph goes beside it (Text with Image, G11 rule 3); without such a paragraph it is shown at its file width, aligned left (rule 4).'),
    ], caption='Figure 10. Images without text beside them.', fid='fig-standalone-image')


# ---------------------------------------------------------------- fig-video (Figure 11)
def fig_video():
    PW, PH = 300, 220

    # 1. Not accepted: video across the full content width
    a = Panel(PW, PH, 'bad')
    a.page()
    a.heading(L, 46, 120, level=2)
    a.text(L, 57, 200, lines=1)
    a.callout(R, 51.5, 'full width', color=RED, anchor='end')
    a.dim_h(73, L, R, '≈ 1,300px')
    a.video(L, 78, W, PH - 6 - 2 - 78)

    # 2. Accepted: two-item Flex Container, text beside the video
    b = Panel(PW, PH, 'ok')
    b.page()
    fy = 55
    vw = 126                                        # ~ 615-660px, about half of 1,300px
    vx = R - vw
    vh = vw * 9 / 16                                # 16:9
    tx = L + 10                                     # item padding keeps the H2 tag inside the outline
    outline(b, L - 4, 43, W + 8, fy + vh + 5 - 43, 'Flex Container, 2 items')
    b.heading(tx, fy, 90, level=2)
    b.text(tx, fy + 12, vx - 8 - tx, lines=9)
    b.video(vx, fy, vw, vh)
    b.dim_h(fy + vh + 9, vx, R, '637px', above=False)
    # the page continues with the next section
    ny = 154
    b.heading(L, ny, 110, level=2)
    b.text(L, ny + 12, W, lines=4)

    return figure([
        (a.svg('A video spanning the full width of the page'),
         'Video spanning the full width of the page.'),
        (b.svg('A video in a two-item Flex Container beside its text'),
         'Video in one of two equal Flex Container items (637px), beside its text (order as on GWI).'),
    ], caption='Figure 11. Videos.', fid='fig-video')


# ---------------------------------------------------------------- fig-phone (Figure 15)
def fig_phone():
    PW, PH = 300, 220
    PX, PY, PWD, PHT = 90, 26, 120, 188

    def phone(p):
        x0, y0, x1, y1 = p.phone(PX, PY, PWD, PHT)
        p.dim_h(PY - 5, x0, x1, '390px')
        return x0, y0, x1, y1

    # 1. Accepted: blocks stacked, everything inside the screen
    a = Panel(PW, PH, 'ok')
    x0, y0, x1, y1 = phone(a)
    cl, cr = x0 + 6, x1 - 6
    a.heading(cl, y0 + 6, 70, level=2, tag=False)
    a.image(cl, y0 + 16, cr - cl, 52)
    a.text(cl, y0 + 74, cr - cl, lines=5)
    a.button((x0 + x1) / 2 - 48, y0 + 110, 96, 12, text='Contact Us')
    a.heading(cl, y0 + 132, 60, level=3, tag=False)
    a.text(cl, y0 + 142, cr - cl, lines=2)

    # 2. Not accepted: squeezed columns and content wider than the screen
    b = Panel(PW, PH, 'bad')
    x0, y0, x1, y1 = phone(b)
    cl, cr = x0 + 6, x1 - 6
    b.heading(cl, y0 + 6, 70, level=2, tag=False)
    cw = (cr - cl - 6) / 2
    b.image(cl, y0 + 16, cw, 26)
    b.text(cl, y0 + 47, cw, lines=6, gap=5.5)
    b.text(cl + cw + 6, y0 + 16, cw, lines=11, gap=5.5)
    # overflow past the right edge
    oy = y0 + 84
    ox1 = PX + PWD + 46
    b.hatch(PX + PWD + 1, oy - 4, ox1 - PX - PWD + 3, 42)
    b.image(cl, oy, ox1 - cl, 34)
    b.button(cl + 4, oy + 42, cr - cl - 8, 12, text='Request a Quote')
    b.callout(PX + PWD + 3, oy - 8, 'scrolls sideways', color=RED)
    b.callout(PX - 4, y0 + 36, 'columns', color=RED, anchor='end')
    b.callout(PX - 4, y0 + 45, 'side by side', color=RED, anchor='end')

    return figure([
        (a.svg('Phone view: blocks stacked, image and button inside the screen'),
         'At 390px, side-by-side blocks stack; images and videos fit the screen.'),
        (b.svg('Phone view: two squeezed columns and content wider than the screen'),
         'Columns kept side by side and an image wider than the screen.'),
    ], caption='Figure 15. Phone view at 390px.', fid='fig-phone')


FIGS = {
    'fig-twi': fig_twi,
    'fig-standalone-image': fig_standalone_image,
    'fig-video': fig_video,
    'fig-phone': fig_phone,
}
