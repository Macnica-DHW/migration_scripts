#!/usr/bin/env python3
"""
Compara o payload de DUAS versões do motor para todas as páginas, OFFLINE.

Responde "que páginas este patch muda, e como?" sem tocar no AEM: monta o
payload com o motor antigo e com o atual sobre o mesmo JCR (cache em disco) e
lista as páginas que mudam, o delta de blocos e, opcionalmente, o diff do
esboço da árvore. Foi assim que se viu que o patch 3 muda 64 de 136 páginas e
não perde texto.

COMO RODAR (de scripts-hazael/)
  git show 137790a:scripts-bruno/aem_layout.py > /tmp/motor_antes.py
  python3 remigracao/ferramentas/cmp_motor.py --antes /tmp/motor_antes.py
  python3 remigracao/ferramentas/cmp_motor.py --antes /tmp/motor_antes.py --ver /altera /renesas

O cache de JCR (--cache, padrão jcr_cache.pkl) é criado na 1ª execução com
136 GETs; apague-o para reler a origem.
"""
import argparse, pickle, importlib.util, re, copy, difflib
import sys
from pathlib import Path
_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
def carregar(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, caminho); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
ap = argparse.ArgumentParser()
ap.add_argument('--antes', required=True, help='arquivo .py com a versão ANTIGA do aem_layout')
ap.add_argument('--depois', default=str(_RAIZ / 'scripts-bruno' / 'aem_layout.py'))
ap.add_argument('--cache', default='jcr_cache.pkl')
ap.add_argument('--ver', nargs='*', default=[], help='sufixos de página para mostrar o diff do esboço')
args = ap.parse_args()
OLD = carregar('al_old', args.antes)
NEW = carregar('al_new', args.depois)


def carregar_jcrs(cache):
    import os
    if os.path.exists(cache):
        return pickle.load(open(cache, 'rb'))
    import aem_remigrar as R
    from aem_lib import CONFIG, build_session, crawl_tree, get_json
    session, auth = build_session(verbose=False)
    out = {}
    for o in crawl_tree(session, CONFIG['base_url'], R.GWI_ROOT, auth, only_pages=True, quiet=True):
        if not R.em_escopo(o):
            continue
        j, st = get_json(session, f"{CONFIG['base_url']}{o}/jcr:content.infinity.json", auth)
        if st == 200 and isinstance(j, dict):
            out[o] = j
    pickle.dump(out, open(cache, 'wb'))
    return out


jcrs = carregar_jcrs(args.cache)
def montar(AL, j, o):
    page = AL.extract_tree(copy.deepcopy(j), o)
    if AL.precisa_title_vazio(page):
        cab = AL.Section(o, -1, role="header"); cab.pad_tb = "small"
        l = AL.Row("single"); c = AL.Column(o, width=12); c.blocks = [AL.Block("title_vazio", o)]; l.columns = [c]; cab.rows = [l]; page.sections.insert(0, cab)
    for b in page.blocks:
        if b.kind in ('related', 'productlist') and not b.props.get('pages'): b.props['pages'] = ['/x/placeholder']
    payload, cont = AL.build_layout_payload(page, reescrever_listas=False)
    return page, payload, cont
def esboco(payload):
    """árvore de resourceTypes, indentada"""
    nos = sorted(k[:-len('/sling:resourceType')] for k in payload if k.endswith('/sling:resourceType'))
    out = []
    for n in nos:
        rel = n.replace('jcr:content/root/container', '', 1)
        if not rel: continue
        prof = rel.count('/') - 1
        rt = payload[n + '/sling:resourceType'].rsplit('/', 1)[-1]
        extra = ''
        if rt == 'title': extra = ' "%s" %s %s' % ((payload.get(n + '/jcr:title') or '(pageTitle)')[:40], payload.get(n + '/type', ''), 'CENTER' if '1717668113714' in (payload.get(n + '/cq:styleIds') or []) else '')
        if rt == 'text': extra = ' ' + re.sub(r'<[^>]+>', ' ', payload.get(n + '/text', ''))[:50].strip()
        if rt == 'button': extra = ' "%s"' % payload.get(n + '/jcr:title', '')
        if rt == 'table': extra = ' ' + re.sub(r'\s+', ' ', payload.get(n + '/text', ''))[:120]
        out.append('  ' * prof + rel.rsplit('/', 1)[-1] + ' [' + rt + ']' + extra)
    return out
mudou = []
for o, j in jcrs.items():
    _, po, co = montar(OLD, j, o); _, pn, cn = montar(NEW, j, o)
    if po != pn: mudou.append((o, co, cn, po, pn))
print(f'páginas cujo payload muda: {len(mudou)} de {len(jcrs)}')
for o, co, cn, po, pn in mudou:
    d = {k: cn.get(k, 0) - co.get(k, 0) for k in set(co) | set(cn) if cn.get(k, 0) != co.get(k, 0)}
    print('  ', (o.split('semiconductors', 1)[1] or '/')[:70].ljust(70), 'nós', sum(1 for k in po if k.endswith('resourceType')), '->', sum(1 for k in pn if k.endswith('resourceType')), d or '')
if args.ver:
    for alvo in args.ver:
        for o, co, cn, po, pn in mudou:
            if o.endswith(alvo):
                print('\n' + '#' * 30, alvo)
                for l in difflib.unified_diff(esboco(po), esboco(pn), 'antes', 'depois', lineterm='', n=1): print(l)
