#!/usr/bin/env python3
"""
Fatia cada print de página inteira em blocos de 1400x1500 (sobreposição 100px).

Print de página inteira a 1400px tem 2.000 a 10.000px de altura; reduzido para
caber na tela (ou no contexto de um revisor) fica ilegível. Em fatias dá para
comparar GWI x destino bloco a bloco.

  python3 fatiar.py <pasta-com-os-png>      ->  <pasta>/fatias/<nome>__NN.png
"""
import glob, os, sys
from PIL import Image
src = sys.argv[1]; dst = os.path.join(src, 'fatias'); os.makedirs(dst, exist_ok=True)
H, OV = 1500, 100
for f in sorted(glob.glob(os.path.join(src, '*.png'))):
    im = Image.open(f); w, h = im.size; base = os.path.basename(f)[:-4]
    y, i = 0, 1
    while y < h:
        im.crop((0, y, w, min(y + H, h))).save(os.path.join(dst, f'{base}__{i:02d}.png'))
        if y + H >= h: break
        y += H - OV; i += 1
    print(base, h, '->', i, 'fatias')
