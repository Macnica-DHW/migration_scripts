"""Assemble the self-contained Page Acceptance Guidelines HTML.

python3 build.py [out.html]
- parts part1..part4.html, style.css, logo_small.png (base64), figures from figs/fig_*.py
- default output: dados/mapas/page-acceptance-guidelines/Page-Acceptance-Guidelines.html (not versioned)
- {{fig:<id>}} placeholders replaced by the figure HTML; figures renumbered in order of appearance
- <span class="figref" data-fig="<id>"> filled with that figure's number
"""
import base64, glob, importlib.util, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, '..', '..', 'dados', 'mapas', 'page-acceptance-guidelines')  # outputs stay out of git
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUT_DIR, 'Page-Acceptance-Guidelines.html')

figs = {}
for p in sorted(glob.glob(os.path.join(HERE, 'figs', 'fig_*.py'))):
    if p.endswith('fig_example.py'):
        continue
    spec = importlib.util.spec_from_file_location(os.path.basename(p)[:-3], p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for k, fn in m.FIGS.items():
        figs[k] = fn()

body = ''.join(open(os.path.join(HERE, f'part{i}.html'), encoding='utf-8').read() for i in (1, 2, 3, 4))
logo = base64.b64encode(open(os.path.join(HERE, 'logo_small.png'), 'rb').read()).decode()
body = body.replace('{{LOGO}}', 'data:image/png;base64,' + logo)

order, missing = [], []
def put(m):
    fid = m.group(1)
    if fid not in figs:
        missing.append(fid)
        return f'<p class="small muted">[figure {fid} missing]</p>'
    order.append(fid)
    return figs[fid]
body = re.sub(r'\{\{fig:([a-z0-9-]+)\}\}', put, body)

num = {fid: i + 1 for i, fid in enumerate(order)}
def renum(m):
    fid = m.group(1)
    html = m.group(0)
    return re.sub(r'Figure \d+\.', f'Figure {num[fid]}.', html, count=1)
body = re.sub(r'<figure class="figset" id="([a-z0-9-]+)">.*?</figure>', renum, body, flags=re.S)
body = re.sub(r'<span class="figref" data-fig="([a-z0-9-]+)"></span>',
              lambda m: str(num.get(m.group(1), '?')), body)

css = open(os.path.join(HERE, 'style.css'), encoding='utf-8').read()
html = f'''<!doctype html>
<html lang="en-US">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page Acceptance Guidelines</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&display=swap">
<style>
{css}
</style>
</head>
<body>
{body}
</body>
</html>
'''
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, 'w', encoding='utf-8').write(html)
print(out, len(html), 'bytes;', len(order), 'figures placed;', 'missing:', missing or 'none')
unused = sorted(set(figs) - set(order))
if unused:
    print('unused figures:', unused)
