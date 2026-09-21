#!/usr/bin/env python3
"""
Dry-run REAL: monta o payload novo de cada página (mesmo fluxo do driver,
sem escrever) e compara com o que está gravado hoje em jcr:content/root do
destino. SOMENTE LEITURA.

O dry-run do driver só diz QUANTOS blocos sairiam. Este mostra O QUE muda no
JCR: chaves adicionadas, removidas e alteradas, mais um resumo (nós, tabelas,
itens de lista, title vazio). É o "me mostre antes de escrever em lote".
Atenção: inserir ou tirar uma seção renumera os container_N seguintes, então
um +/- grande costuma ser só deslocamento — olhe o resumo primeiro.

COMO RODAR (de scripts-hazael/)
  python3 remigracao/ferramentas/diff_payload.py /altera /canon /
  python3 remigracao/ferramentas/diff_payload.py --origem <raiz GWI> --destino <raiz copia-teste> /macnica-cv75
"""
import json, re
import sys
from pathlib import Path
_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
import aem_remigrar as R
import aem_layout as AL
from aem_lib import build_session, get_json, CONFIG

IGN = ('jcr:created', 'jcr:createdBy', 'cq:lastModified', 'cq:lastModifiedBy',
       'jcr:lastModified', 'jcr:lastModifiedBy', 'jcr:mixinTypes', 'cq:lastReplicat',
       'cq:isDelivered')

def achatar(node, base, out):
    for k, v in node.items():
        if isinstance(v, dict):
            achatar(v, f"{base}/{k}", out)
        else:
            if any(k.startswith(i) for i in IGN):
                continue
            out[f"{base}/{k}"] = v

def normv(v):
    if isinstance(v, list): return tuple(str(x) for x in v)
    if isinstance(v, bool): return "true" if v else "false"
    return str(v)

def payload_novo(session, base_url, auth, origem, cache_dc, cache_asset):
    jcr, st = get_json(session, f"{base_url}{origem}/jcr:content.50.json", auth)
    if st != 200: return None, None, f"GET {st}"
    page = AL.extract_tree(jcr, origem)
    R.aplicar_titulos_download(page, session, base_url, auth, cache_dc)
    R.aplicar_dimensoes_de_imagem(page, session, base_url, auth, cache_dc)
    for b in page.blocks:
        if b.kind in ("related", "productlist"):
            res = R.resolver_related(session, base_url, auth, b, origem)
            if not res: continue
            res = [R.destino_de(x) if x.startswith(R.GWI_ROOT) else x for x in res]
            b.props["pages"] = res; b.props["listFrom"] = "static"
    R.copiar_assets(page, session, base_url, auth, cache_asset, dry_run=True)
    AL.inserir_titulo_da_pagina(page, origem)
    payload, contagens = AL.build_layout_payload(
        page, template_path=R.TEMPLATE, link_de=CONFIG["gwi_prefix"],
        link_para=CONFIG["global2_prefix"], reescrever_listas=False)
    R.normalizar_links_do_escopo(payload, CONFIG["gwi_prefix"], CONFIG["global2_prefix"])
    return payload, contagens, page

def resumo(flat):
    tabelas = sum(1 for k, v in flat.items() if k.endswith('/sling:resourceType') and str(v).endswith('/table'))
    listas = [k[:-len('/sling:resourceType')] for k, v in flat.items() if k.endswith('/sling:resourceType') and str(v).endswith('/list')]
    itens_lista = sum(len(flat.get(f"{l}/pages", ()) or ()) for l in listas)
    titles = [k[:-len('/sling:resourceType')] for k, v in flat.items() if k.endswith('/sling:resourceType') and str(v).endswith('/title')]
    vazios = sum(1 for t in titles if f"{t}/jcr:title" not in flat)
    nos = sum(1 for k in flat if k.endswith('/sling:resourceType'))
    return dict(nos=nos, tabelas=tabelas, listas=len(listas), itens_lista=itens_lista, title_vazio=vazios)

def main():
    rels = sys.argv[1:]
    # outra família: --origem <raiz no GWI> --destino <raiz na copia-teste>
    for flag, attr in (("--origem", "GWI_ROOT"), ("--destino", "DEST_ROOT")):
        if flag in rels:
            i = rels.index(flag)
            setattr(R, attr, rels[i + 1].rstrip("/"))
            del rels[i:i + 2]
    session, auth = build_session(verbose=False)
    base_url = CONFIG["base_url"]
    cache_dc, cache_asset = {}, set()   # set: ensure_dam_folder faz cache.add()
    for rel in rels:
        origem = R.GWI_ROOT + ("" if rel in ("", "/") else "/" + rel.strip("/"))
        destino = R.destino_de(origem)
        payload, contagens, page = payload_novo(session, base_url, auth, origem, cache_dc, cache_asset)
        if payload is None:
            print(f"\n### {rel}: {page}"); continue
        novo = {k: normv(v) for k, v in payload.items() if '@TypeHint' not in k}
        atual_json, st = get_json(session, f"{base_url}{destino}/jcr:content/root.infinity.json", auth)
        atual = {}
        if st == 200 and isinstance(atual_json, dict):
            tmp = {}; achatar(atual_json, "jcr:content/root", tmp)
            atual = {k: normv(v) for k, v in tmp.items()}
        add = sorted(set(novo) - set(atual)); rem = sorted(set(atual) - set(novo))
        chg = sorted(k for k in set(novo) & set(atual) if novo[k] != atual[k])
        rn, ra = resumo(novo), resumo(atual)
        print(f"\n### {rel or '/'}   [{'novo' if st != 200 else 'existe'}]  blocos: {' '.join(f'{k}={v}' for k,v in sorted(contagens.items()))}")
        print(f"    atual: {ra}")
        print(f"    novo : {rn}")
        print(f"    chaves: +{len(add)} -{len(rem)} ~{len(chg)}  (idênticas: {len(set(novo)&set(atual))-len(chg)})")
        def mostra(titulo, ks, n=8):
            if not ks: return
            print(f"    {titulo}:")
            for k in ks[:n]:
                a = atual.get(k); b = novo.get(k)
                def sh(x): 
                    x = '' if x is None else (str(x) if not isinstance(x, tuple) else f"[{len(x)} itens] " + ", ".join(y.rsplit('/',1)[-1] for y in x[:4]))
                    return re.sub(r'\s+',' ',x)[:90]
                if titulo.startswith('~'): print(f"      {k[17:]}\n         era: {sh(a)}\n         fica: {sh(b)}")
                else: print(f"      {k[17:]} = {sh(b if titulo.startswith('+') else a)}")
            if len(ks) > n: print(f"      ... e mais {len(ks)-n}")
        mostra('+ adicionadas', [k for k in add if not k.endswith('jcr:primaryType')])
        mostra('- removidas', [k for k in rem if not k.endswith('jcr:primaryType')])
        mostra('~ alteradas', chg)
        for pd in page.pendencias: print(f"    pendência: {pd.categoria} {pd.motivo[:70]}")

if __name__ == '__main__':
    main()
