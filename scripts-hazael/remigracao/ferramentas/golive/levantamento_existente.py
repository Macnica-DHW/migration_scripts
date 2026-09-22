#!/usr/bin/env python3
"""
levantamento_existente.py — copia-teste x global2 x GWI quando o DESTINO JÁ EXISTE. SOMENTE LEITURA (só GET).

Nasceu para /products/macnica-products (22/09/2026): o Bruno já tinha copiado as 7 páginas para o global2
de manhã e continuou editando a copia-teste à tarde. O `inventario.py` do go-live de /semiconductors só
responde "colide ou não"; aqui a pergunta é "o que difere, e o que a cópia precisa reescrever":

  1. inventário dos três lados (criador, carimbo, template, soft-delete, publicada, hideInNav, canonical)
  2. diff do jcr:content de cada página T x G, fora carimbos e com o prefixo copia-teste -> global2
     trocado antes de comparar (diferença que sobra é conteúdo/disposição, não prefixo)
  3. censo das referências gravadas em T (asset, página, XF), por classe
  4. cada asset de T: par no DAM do global2 (pelo NOME do arquivo, querybuilder) e sha1 T x G x GWI
  5. cada link de página de T: alvo candidato no global2 (troca de prefixo + tabela FIXOS) e o HTTP dele

    python3 levantamento_existente.py --t /content/copia-teste/americas/mai/en/products/macnica-products \
        --g /content/macnicaglobal2/americas/mai/en/products/macnica-products
    (--gwi é deduzido de --t trocando copia-teste por macnicagwi; --nome dá o nome do JSON em dados/golive/)

Rodar IMEDIATAMENTE antes de qualquer gravação: os dois lados têm outros editores (Bruno, Anion).
"""
import argparse
import collections
import datetime
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

_RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, build_session  # noqa: E402

DADOS = Path(__file__).resolve().parents[2] / "dados" / "golive"
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE     # cookie só vai para o author
sessao, _ = build_session(verbose=False)

MAI = "/content/macnicaglobal2/americas/mai/en"
DAM_MAI = "/content/dam/macnicaglobal2/americas/mai/en"
# o que trocar prefixo NÃO resolve (mesma tabela de _reescrita.py, mais o que macnica-products trouxe)
FIXOS = [(f"{MAI}/contact/form", f"{MAI}/contact-us"), (f"{MAI}/contact", f"{MAI}/contact-us"),
         ("/content/macnicaglobal2/europe/atd-europe", "/content/macnicaglobal2/eu/atd-europe"),
         (f"{MAI}/technology/Broadcast-ProAV-Solutions", f"{MAI}/solutions/broadcast-proav-solutions"),
         (f"{MAI}/technology", f"{MAI}/solutions")]
CARIMBO = {"jcr:created", "jcr:createdBy", "cq:lastModified", "cq:lastModifiedBy", "jcr:lastModified", "jcr:lastModifiedBy",
           "jcr:uuid", "cq:lastReplicated", "cq:lastReplicatedBy", "cq:lastReplicationAction", "cq:lastRolledout", "cq:lastRolledoutBy"}
IGNORAR = {"sling:resourceType", "sling:resourceSuperType", "jcr:primaryType", "jcr:mixinTypes", "cq:template", "jcr:createdBy",
           "cq:lastModifiedBy", "jcr:lastModifiedBy", "jcr:uuid", "cq:lastReplicatedBy", "cq:lastReplicationAction", "cq:policy"}
ATTR = re.compile(r'\b(href|src|data-src|poster|action)\s*=\s*(["\'])(.*?)\2', re.I | re.S)
PROPS = ("jcr:path jcr:createdBy jcr:created jcr:content/jcr:title jcr:content/cq:lastModified jcr:content/cq:lastModifiedBy "
         "jcr:content/cq:lastReplicationAction jcr:content/cq:template jcr:content/deleted jcr:content/deletedBy "
         "jcr:content/cq:redirectTarget jcr:content/hideInNav jcr:content/cq:canonicalUrl")


def get(caminho, sufixo="", **params):
    return sessao.get(BASE + quote(unquote(caminho), safe="/:") + sufixo, params=params or None, timeout=120, allow_redirects=False)


def jsn(path, sufixo=".json"):
    r = get(path, sufixo)
    try:
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except ValueError:
        return r.status_code, None


def fundo(path):
    """jcr:content inteiro, contornando o HTTP 300 (profundidade recusada)."""
    st, j = jsn(path, ".infinity.json")
    if st == 200:
        return j
    if st != 300:
        return None
    r = get(path, ".infinity.json")
    d = max(int(m.group(1)) for o in r.json() if (m := re.search(r"\.(\d+)\.json$", str(o))))
    st, j = jsn(path, f".{d}.json")

    def desce(no, p, nivel):
        for k, v in list(no.items()):
            if isinstance(v, dict):
                if nivel + 1 >= d:
                    no[k] = fundo(f"{p}/{k}") or v
                else:
                    desce(v, f"{p}/{k}", nivel + 1)
    desce(j, path, 0)
    return j


def paginas(raiz):
    r = get("/bin/querybuilder.json", path=raiz, type="cq:Page", **{"p.limit": "-1", "p.hits": "selective", "p.properties": PROPS})
    if r.status_code != 200:
        return {}
    return {h["jcr:path"][len(raiz):] or "/": h for h in r.json()["hits"]}


def c(h, k):
    return (h.get("jcr:content") or {}).get(k, "")


# ---------- 2. diff ----------
def _norm(v):
    if isinstance(v, str):
        return (v.replace("/content/dam/copia-teste/", "/content/dam/macnicaglobal2/").replace("/content/copia-teste/", "/content/macnicaglobal2/")
                 .replace("/content/experience-fragments/copia-teste/", "/content/experience-fragments/macnicaglobal2/"))
    return [_norm(x) for x in v] if isinstance(v, list) else v


def _limpa(no):
    return {k: (_limpa(v) if isinstance(v, dict) else _norm(v)) for k, v in no.items() if k not in CARIMBO}


def diff(a, b, cam, out):
    for k in sorted(set(a) | set(b)):
        va, vb = a.get(k), b.get(k)
        if isinstance(va, dict) and isinstance(vb, dict):
            diff(va, vb, f"{cam}/{k}", out)
        elif isinstance(va, dict):
            out.append(["SO-T", f"{cam}/{k}", None, None])
        elif isinstance(vb, dict):
            out.append(["SO-G", f"{cam}/{k}", None, None])
        elif va != vb:
            out.append(["prop", f"{cam}/{k}", va, vb])
    ka = [k for k, v in a.items() if isinstance(v, dict)]
    kb = [k for k, v in b.items() if isinstance(v, dict)]
    if ka != kb and sorted(ka) == sorted(kb):
        out.append(["ORDEM", cam, ka, kb])


# ---------- 3. censo ----------
def classe(u):
    u = unquote(u)
    if u.startswith("/content/dam/copia-teste"): return "DAM-copia-teste"
    if u.startswith("/content/dam/macnicagwi"): return "DAM-gwi"
    if u.startswith("/content/dam/macnicaglobal2"): return "DAM-global2"
    if u.startswith("/content/experience-fragments/"): return "XF"
    if u.startswith("/content/copia-teste"): return "PAGINA-copia-teste"
    if u.startswith("/content/macnicagwi"): return "PAGINA-gwi"
    if u.startswith("/content/macnicaglobal2"): return "pagina-global2"
    if "macnica.com" in u: return "publico-macnica.com"
    return "externo"


def refs_de(no, caminho, saida):
    for k, v in no.items():
        if isinstance(v, dict):
            refs_de(v, f"{caminho}/{k}", saida)
            continue
        if k in IGNORAR:
            continue
        for s in (v if isinstance(v, list) else [v]):
            if not isinstance(s, str) or not s:
                continue
            if "<" in s and ("href" in s or "src" in s):
                for m in ATTR.finditer(s):
                    u = html.unescape(m.group(3)).strip()
                    if u.startswith(("/content/", "http", "//", "www.")):
                        saida.append({"no": caminho, "prop": k, "url": u, "classe": classe(u)})
            elif s.startswith(("/content/", "http://", "https://")) and k != "text":
                saida.append({"no": caminho, "prop": k, "url": s.strip(), "classe": classe(s)})


# ---------- 4. assets ----------
def meta(p):
    st, j = jsn(p, "/jcr:content/metadata.json")
    if st != 200:
        return None
    return {"sha1": j.get("dam:sha1"), "bytes": j.get("dam:size"), "w": j.get("tiff:ImageWidth"), "h": j.get("tiff:ImageLength")}


def par_no_dam_global2(nome):
    r = get("/bin/querybuilder.json", path=DAM_MAI, type="dam:Asset", nodename=nome, **{"p.limit": "10", "p.hits": "selective", "p.properties": "jcr:path"})
    return [h["jcr:path"] for h in r.json().get("hits", [])] if r.status_code == 200 else []


# ---------- 5. links ----------
def candidatos(u, t_raiz, g_raiz, gwi_raiz):
    u = unquote(u).split("#")[0].split("?")[0]
    u = re.sub(r"\.html$", "", u).rstrip("/")
    u = u.replace("https://www.macnica.com/americas/mai/en", MAI).replace("/content/macnicagwi/americas/mai/en", MAI)
    u = u.replace(t_raiz, g_raiz)
    outs = [u]
    for de, para in FIXOS:
        if u == de or u.startswith(de + "/"):
            outs.append(para + u[len(de):])
    return list(dict.fromkeys(outs))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--t", required=True, help="raiz na copia-teste (origem da cópia)")
    ap.add_argument("--g", required=True, help="raiz no global2 (destino, que já existe)")
    ap.add_argument("--gwi", default=None, help="raiz no GWI (referência; só GET)")
    ap.add_argument("--nome", default=None)
    a = ap.parse_args()
    T, G = a.t.rstrip("/"), a.g.rstrip("/")
    W = (a.gwi or T.replace("/content/copia-teste/", "/content/macnicagwi/")).rstrip("/")
    nome = a.nome or T.rsplit("/", 1)[-1]
    out = {"quando": datetime.datetime.now().isoformat(timespec="seconds"), "T": T, "G": G, "GWI": W}

    # 1. inventário
    inv = {}
    for rot, raiz in (("T", T), ("G", G), ("GWI", W)):
        pg = paginas(raiz)
        inv[rot] = pg
        print(f"\n===== {rot} {raiz}: {len(pg)} páginas (raiz incluída quando é cq:Page)")
        for rel in sorted(pg):
            h = pg[rel]
            flags = [f for f, ok in (("SOFT-DELETED", c(h, "deleted")), ("redirect", c(h, "cq:redirectTarget")),
                                     ("PUBLICADA", c(h, "cq:lastReplicationAction") == "Activate"), ("hideInNav", c(h, "hideInNav")),
                                     ("canonical", c(h, "cq:canonicalUrl"))) if ok]
            print(f"  {rel:48} cri={h.get('jcr:createdBy', '?').split('@')[0]:14} {h.get('jcr:created', '')[4:20]:16} "
                  f"mod={c(h, 'cq:lastModified')[4:25]:21} por={c(h, 'cq:lastModifiedBy').split('@')[0]:14} "
                  f"tpl={c(h, 'cq:template').rsplit('/', 1)[-1]:28} {' '.join(flags)}")
    out["inventario"] = inv
    so_t = sorted(set(inv["T"]) - set(inv["G"])); so_g = sorted(set(inv["G"]) - set(inv["T"]))
    print(f"\n  só em T: {so_t}\n  só em G: {so_g}\n  só no GWI: {sorted(set(inv['GWI']) - set(inv['T']))}")

    # 2. diff T x G
    print("\n===== diff jcr:content T x G (fora carimbos; prefixo copia-teste->global2 trocado antes)")
    diffs, arvores = {}, {}
    for rel in sorted(set(inv["T"]) & set(inv["G"])):
        sub = "" if rel == "/" else rel
        ta, ga = fundo(f"{T}{sub}/jcr:content"), fundo(f"{G}{sub}/jcr:content")
        if ta is None or ga is None:
            print(f"  {rel}: não li um dos lados"); continue
        arvores[rel] = ta
        d = []
        diff(_limpa(ta), _limpa(ga), "", d)
        diffs[rel] = d
        tipos = collections.Counter(x[0] for x in d)
        so_pref = sum(1 for x in d if x[0] == "prop" and isinstance(x[2], str) and x[3] is not None and unquote(x[2]).rsplit("/", 1)[-1].lower() == unquote(str(x[3])).rsplit("/", 1)[-1].lower() and "/content/" in x[2])
        print(f"  {rel:48} {len(d):3} diferenças {dict(tipos)}  (só caminho de asset/canonical: {so_pref})")
    out["diff"] = diffs

    # 3. censo de T
    refs = []
    for rel, ta in arvores.items():
        sub = "" if rel == "/" else rel
        r = []
        refs_de(ta, f"{T}{sub}/jcr:content", r)
        for x in r:
            x["pagina"] = rel
        refs += r
    print(f"\n===== referências gravadas em T: {len(refs)}  por classe: {dict(collections.Counter(x['classe'] for x in refs))}")
    out["refs_T"] = refs

    # 4. assets
    print("\n===== assets de T -> par no DAM do global2 (por nome) e sha1 T x G x GWI")
    assets = {}
    for u in sorted({unquote(x["url"]) for x in refs if x["classe"].startswith("DAM")}):
        nm = u.rsplit("/", 1)[-1]
        mt = meta(u)
        pares = par_no_dam_global2(nm) if not u.startswith("/content/dam/macnicaglobal2") else [u]
        mg = meta(pares[0]) if pares else None
        gw = u.replace("/content/dam/copia-teste/", "/content/dam/macnicagwi/")
        mw = meta(gw) if "/content/dam/macnicagwi/" in gw else None
        ig = "=" if mt and mg and mt["sha1"] == mg["sha1"] else ("≠" if mg else "SEM PAR")
        iw = "=" if mt and mw and mt["sha1"] == mw["sha1"] else ("≠" if mw else "?")
        assets[u] = {"T": mt, "G": pares, "G_meta": mg, "G_igual": ig, "GWI": gw if mw else None, "GWI_meta": mw, "GWI_igual": iw}
        print(f"  [{ig:7}|GWI {iw}] {u[len('/content/dam/'):][:70]:70} -> {[p[len(DAM_MAI):] for p in pares][:2]}"
              + (f"   G={mg['w']}x{mg['h']} T={mt['w']}x{mt['h']}" if ig == "≠" and mg and mt else ""))
    out["assets"] = assets
    print(f"  {len(assets)} assets; sem par no global2: {sum(1 for v in assets.values() if v['G_igual'] == 'SEM PAR')}; "
          f"par diferente do de T: {sum(1 for v in assets.values() if v['G_igual'] == '≠')}; "
          f"T diferente do GWI: {sum(1 for v in assets.values() if v['GWI_igual'] == '≠')}")

    # 5. links
    print("\n===== links de página de T -> alvo no global2")
    links = {}
    cont = collections.Counter(x["url"] for x in refs if x["classe"] in ("PAGINA-gwi", "pagina-global2", "PAGINA-copia-teste", "publico-macnica.com"))
    for u, n in sorted(cont.items(), key=lambda x: -x[1]):
        res = []
        for cd in candidatos(u, T, G, W):
            st, j = jsn(cd, ".json")
            if st == 200:
                _, jc = jsn(cd, "/jcr:content.json")
                res.append({"alvo": cd, "http": st, "criador": (jc or {}).get("jcr:createdBy", ""), "deleted": bool((jc or {}).get("deleted"))})
            else:
                res.append({"alvo": cd, "http": st})
        links[u] = {"refs": n, "candidatos": res}
        vivo = next((r for r in res if r["http"] == 200 and not r.get("deleted")), None)
        print(f"  {n:2}x {u[:95]:95} -> " + (f"{vivo['alvo'][len(MAI):] or '/'} ({vivo['criador'].split('@')[0]})" if vivo else f"SEM ALVO {[(r['alvo'][len(MAI):], r['http']) for r in res]}"))
    out["links"] = links
    print(f"  {len(links)} alvos distintos; sem alvo vivo no global2: "
          f"{sum(1 for v in links.values() if not any(r['http'] == 200 and not r.get('deleted') for r in v['candidatos']))}")

    DADOS.mkdir(parents=True, exist_ok=True)
    arq = DADOS / f"levantamento_{nome}.json"
    json.dump(out, open(arq, "w"), indent=1, ensure_ascii=False)
    print(f"\nJSON: {arq}")


if __name__ == "__main__":
    main()
