#!/usr/bin/env python3
"""
Nenhum texto some, aparece ou muda de ORDEM entre duas versões do motor? — OFFLINE.

Para cada uma das 136 páginas do cache, monta o payload com o motor antigo e
com o novo e compara o multiconjunto (e a sequência) de textos visíveis,
títulos, links, assets e rótulos de aba. É a rede de segurança de um patch que
mexe em agrupamento (R28–R30 mudaram 134 payloads; aqui deu 0 texto perdido e
0 mudança de ordem).

  python3 remigracao/ferramentas/conf_texto.py <motor_antes.py> <motor_depois.py> <jcr_cache.pkl>
"""
import sys, pickle, re, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vaos_estruturais as V
A=V.carregar('a',sys.argv[1]); B=V.carregar('b',sys.argv[2])
jcrs=pickle.load(open(sys.argv[3],'rb'))
def textos(pl):
    out=[]
    for k,v in pl.items():
        if k.rsplit('/',1)[-1] in ('text','jcr:title','linkURL','fileReference','cq:panelTitle','pages','youtubeVideoId','linkTarget') and not k.endswith('@TypeHint'):
            s=re.sub(r'</?span\b[^>]*>','',str(v))          # R41b: span nowrap em volta de palavra não é fronteira de texto
            t=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',s).replace('&nbsp;',' ')).strip()
            if t: out.append(t)
    return out
ruim=0; ordem=0
for o,j in jcrs.items():
    ta,tb=textos(V.montar(A,j,o)),textos(V.montar(B,j,o))
    ca,cb=collections.Counter(ta),collections.Counter(tb)
    if ca!=cb:
        ruim+=1; print('DIFERE', o.split('semiconductors',1)[1]); 
        for t in (ca-cb): print('    sumiu :',t[:120])
        for t in (cb-ca): print('    surgiu:',t[:120])
    elif ta!=tb:
        ordem+=1
        # ordem dos textos mudou — mostrar o primeiro ponto
        i=next(i for i,(x,y) in enumerate(zip(ta,tb)) if x!=y)
        print('ORDEM ', o.split('semiconductors',1)[1][:60], '| antes:', ta[i][:40], '| depois:', tb[i][:40])
print('páginas com texto diferente:',ruim,' | só ordem:',ordem,' de',len(jcrs))
