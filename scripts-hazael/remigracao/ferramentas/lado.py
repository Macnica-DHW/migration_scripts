# lado.py <dir-prints> <nome> [escala] — compõe GWI | destino lado a lado, reduzido, em fatias
import sys, os
from PIL import Image
d, nome = sys.argv[1], sys.argv[2]
esc = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
g = Image.open(f"{d}/{nome}__gwi.png").convert("RGB"); t = Image.open(f"{d}/{nome}__dest.png").convert("RGB")
def red(im): return im.resize((int(im.width*esc), int(im.height*esc)), Image.LANCZOS)
g, t = red(g), red(t)
H = max(g.height, t.height); W = g.width + t.width + 12
c = Image.new("RGB", (W, H), (255, 0, 0)); c.paste((255,255,255), (0,0,g.width,H)); c.paste((255,255,255), (g.width+12,0,W,H))
c.paste(g, (0, 0)); c.paste(t, (g.width+12, 0))
out = os.path.join(d, "..", "lado"); os.makedirs(out, exist_ok=True)
passo = 1400; n = 0
for y in range(0, H, passo):
    n += 1; c.crop((0, y, W, min(y+passo, H))).save(f"{out}/{nome}__{n:02}.png")
print(nome, "->", n, "fatias lado a lado; alturas", g.height, t.height)
