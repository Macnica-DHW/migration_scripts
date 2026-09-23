#!/usr/bin/env python3
"""
levantamento_escopo.py — copia-teste (T) x global2 (G) x GWI para um ESCOPO de várias raízes e páginas soltas,
com exclusões. SOMENTE LEITURA (só GET no author; o GWI é só referência).

Nasceu em 22/09/2026 (pedido do Hazael): levar para o global2 o que o Bruno montou na copia-teste debaixo de
`mai/en` — about-us (menos events-archive, em revisão pela Luiza), contact, error, search, request-a-quote,
terms-conditions-mep100…, a landing /products e products/macnica-products — sem sobrescrever nada.
O `levantamento_existente.py` só compara páginas que existem dos dois lados; aqui a maioria é nova, então:

  1. inventário de T (página a página, com nº de componentes) e o ALVO no global2 = caminho com cada segmento
     normalizado (normalize_name — regra do projeto, mesmo quando G tem casca com MAIÚSCULA)
  2. estado do alvo em G: livre | gêmeo (mesmo nome em outra grafia) | casca (0 componentes) | com conteúdo
     (de quem, quando) | soft-deleted | pasta; e o que só existe em G debaixo das mesmas raízes
  3. par no GWI (mesmo caminho relativo de T, com a grafia de T): existe, publicado, redirect; e o que só
     existe no GWI
  4. referências gravadas em TODAS as páginas de T: assets (par no DAM do global2 pelo nome), XFs (par em
     experience-fragments/macnicaglobal2) e links de página (alvo no global2: dentro do escopo = nasce com a
     migração; fora = GET agora, com a tabela FIXOS)

    python3 levantamento_escopo.py --raiz about-us --raiz contact --raiz products/macnica-products \
        --pagina error --pagina search --pagina request-a-quote --pagina products \
        --excluir about-us/news-events/events-archive --nome mai-en-escopo

Rodar IMEDIATAMENTE antes de qualquer gravação: T e G têm outros editores (Bruno, Luiza, Anion).
"""
import argparse
import collections
import datetime
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from levantamento_existente import (DADOS, FIXOS, MAI, c, classe, fundo, get, jsn,  # noqa: E402
                                    meta, par_no_dam_global2, refs_de)
from aem_lib import normalize_name  # noqa: E402

T_BASE = "/content/copia-teste/americas/mai/en"
G_BASE = MAI
W_BASE = "/content/macnicagwi/americas/mai/en"
XF_T = "/content/experience-fragments/copia-teste/"
XF_G = "/content/experience-fragments/macnicaglobal2/"
ESTRUTURA = {"container", "responsivegrid", "flexcontainer", "flexcontaineritem", "tabs", "accordion"}
PROPS = ("jcr:path jcr:primaryType jcr:createdBy jcr:created jcr:content/jcr:title jcr:content/pageTitle "
         "jcr:content/cq:lastModified jcr:content/cq:lastModifiedBy jcr:content/cq:lastReplicationAction "
         "jcr:content/cq:template jcr:content/deleted jcr:content/deletedBy jcr:content/cq:redirectTarget "
         "jcr:content/hideInNav jcr:content/cq:canonicalUrl")


def componentes(jc):
    """(conteúdo, estrutura) debaixo de jcr:content/root — o que o autor põe na página."""
    cont = estr = 0

    def anda(no):
        nonlocal cont, estr
        for k, v in no.items():
            if isinstance(v, dict):
                if v.get("sling:resourceType"):
                    if v["sling:resourceType"].rsplit("/", 1)[-1] in ESTRUTURA:
                        estr += 1
                    else:
                        cont += 1
                anda(v)
    if isinstance(jc, dict) and isinstance(jc.get("root"), dict):
        anda(jc["root"])
    return cont, estr


def resumo(path):
    """Estado de uma página/pasta: primaryType, carimbos, flags e nº de componentes. None se 404."""
    st, no = jsn(path, ".json")
    if st != 200:
        return {"http": st}
    jc = fundo(f"{path}/jcr:content") if no.get("jcr:primaryType") == "cq:Page" else None
    cont, estr = componentes(jc)
    jc = jc or {}
    return {"http": 200, "tipo": no.get("jcr:primaryType"), "criador": no.get("jcr:createdBy", ""),
            "criado": no.get("jcr:created", ""), "titulo": jc.get("jcr:title", ""), "pageTitle": jc.get("pageTitle", ""),
            "mod": jc.get("cq:lastModified", ""), "por": jc.get("cq:lastModifiedBy", ""),
            "template": str(jc.get("cq:template", "")).rsplit("/", 1)[-1], "deleted": bool(jc.get("deleted")),
            "redirect": jc.get("cq:redirectTarget", ""), "publicada": jc.get("cq:lastReplicationAction") or jc.get("cq:lastReplicationAction_publish", ""),
            "hideInNav": jc.get("hideInNav", ""), "canonical": jc.get("cq:canonicalUrl", ""),
            "conteudo": cont, "estrutura": estr, "_jc": jc}


def filhos(path):
    st, j = jsn(path, ".1.json")
    return {k: v.get("jcr:primaryType") for k, v in (j or {}).items() if isinstance(v, dict) and k != "jcr:content"}


def paginas_sob(raiz):
    """{rel: primaryType} de toda cq:Page e pasta debaixo de raiz (raiz incluída — o querybuilder só devolve
    descendentes: sem isto as landings ficavam de fora)."""
    out = {}
    st, j = jsn(raiz, ".json")
    if st == 200:
        out[raiz] = j.get("jcr:primaryType")
    for tipo in ("cq:Page", "sling:Folder", "sling:OrderedFolder"):
        r = get("/bin/querybuilder.json", path=raiz, type=tipo, **{"p.limit": "-1", "p.hits": "selective", "p.properties": "jcr:path"})
        if r.status_code != 200:
            sys.exit(f"[erro] HTTP {r.status_code} no querybuilder de {raiz} (cookie?)")
        for h in r.json()["hits"]:
            out[h["jcr:path"]] = tipo
    return out


def alvo_g(rel):
    return "/".join(normalize_name(x) for x in rel.split("/"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", action="append", default=[], help="subárvore de T (relativa a mai/en)")
    ap.add_argument("--pagina", action="append", default=[], help="só a página, sem as filhas")
    ap.add_argument("--excluir", action="append", default=[], help="subárvore de T que NÃO entra")
    ap.add_argument("--nome", default="escopo")
    a = ap.parse_args()
    excl = [e.strip("/") for e in a.excluir]
    fora = lambda rel: any(rel == e or rel.startswith(e + "/") for e in excl)  # noqa: E731
    out = {"quando": datetime.datetime.now().isoformat(timespec="seconds"), "raizes": a.raiz, "paginas": a.pagina,
           "excluir": excl}

    # ---------- 1. T ----------
    t_rels = {}
    for r in a.raiz:
        for p, tipo in paginas_sob(f"{T_BASE}/{r.strip('/')}").items():
            t_rels[p[len(T_BASE) + 1:]] = tipo
    for p in a.pagina:
        t_rels.setdefault(p.strip("/"), None)
    excluidas = sorted(r for r in t_rels if fora(r))
    t_rels = {r: t for r, t in t_rels.items() if not fora(r)}
    print(f"T: {len(t_rels)} nós no escopo ({len(excluidas)} excluídos)")

    linhas = {}
    with ThreadPoolExecutor(6) as ex:
        tr = dict(zip(sorted(t_rels), ex.map(lambda r: resumo(f"{T_BASE}/{r}"), sorted(t_rels))))
        gr = dict(zip(sorted(t_rels), ex.map(lambda r: resumo(f"{G_BASE}/{alvo_g(r)}"), sorted(t_rels))))
        wr = dict(zip(sorted(t_rels), ex.map(lambda r: resumo(f"{W_BASE}/{r}"), sorted(t_rels))))

    # ---------- 2. G: estado do alvo, gêmeos e sobras ----------
    filhos_g = {}
    for rel in sorted(t_rels):
        g_rel = alvo_g(rel)
        pai, nome = (f"{G_BASE}/{g_rel}").rsplit("/", 1)
        if pai not in filhos_g:
            filhos_g[pai] = filhos(pai)
        gemeos = [k for k in filhos_g[pai] if k != nome and normalize_name(k) == nome]
        t, g, w = tr[rel], gr[rel], wr[rel]
        if g["http"] == 404:
            estado = "CRIAR" + ("+GÊMEO" if gemeos else "")
        elif g["http"] != 200:
            estado = f"HTTP{g['http']}"
        elif g["deleted"]:
            estado = "SOFT-DELETED"
        elif g["tipo"] != "cq:Page":
            estado = f"PASTA({g['tipo']})"
        elif g["conteudo"] == 0:
            estado = "CASCA"
        else:
            estado = "COM-CONTEÚDO"
        linhas[rel] = {"g_rel": g_rel, "nome_muda": g_rel != rel, "estado": estado, "gemeos": gemeos,
                       "T": {k: v for k, v in t.items() if k != "_jc"}, "G": {k: v for k, v in g.items() if k != "_jc"},
                       "GWI": {k: v for k, v in w.items() if k != "_jc"}}

    so_g = []
    alvos = {f"{G_BASE}/{v['g_rel']}" for v in linhas.values()}
    for r in a.raiz:
        for p, tipo in paginas_sob(f"{G_BASE}/{alvo_g(r.strip('/'))}").items():
            rel = p[len(G_BASE) + 1:]
            if p not in alvos and not fora(rel):
                h = resumo(p)
                so_g.append({"rel": rel, **{k: v for k, v in h.items() if k != "_jc"}})
    so_w = []
    for r in a.raiz:
        for p, tipo in paginas_sob(f"{W_BASE}/{r.strip('/')}").items():
            rel = p[len(W_BASE) + 1:]
            if rel not in t_rels and not fora(rel):
                h = resumo(p)
                so_w.append({"rel": rel, **{k: v for k, v in h.items() if k != "_jc"}})

    print(f"\n===== inventário: T -> alvo no global2 (estado) | GWI")
    for rel in sorted(linhas):
        L = linhas[rel]; t, g, w = L["T"], L["G"], L["GWI"]
        tt = "PASTA" if t.get("tipo") != "cq:Page" else f"{t['conteudo']:3}c"
        gg = "" if g["http"] != 200 else f"{g['conteudo']:3}c cri={g['criador'].split('@')[0]} por={g['por'].split('@')[0]} {g['mod'][4:21]}" + (" PUBLICADA" if g["publicada"] == "Activate" else "")
        ww = "404" if w["http"] != 200 else ("redirect" if w["redirect"] else ("pub" if w["publicada"] == "Activate" else w["publicada"] or "nunca-pub"))
        print(f"  {L['estado']:14} {rel[:70]:70} T={tt:5} por={t.get('por', '').split('@')[0]:12} {t.get('mod', '')[4:21]}"
              + (f"  -> {L['g_rel']}" if L["nome_muda"] else "") + (f"  G: {gg}" if gg else "")
              + (f"  gêmeos={L['gemeos']}" if L["gemeos"] else "") + f"  GWI={ww}")
    print(f"\n  estados: {dict(collections.Counter(v['estado'] for v in linhas.values()))}")
    print(f"\n  só em G ({len(so_g)}):")
    for h in so_g:
        print(f"    {h['rel'][:80]:80} {h.get('tipo')} {h.get('conteudo', '-')}c cri={h.get('criador', '').split('@')[0]} por={h.get('por', '').split('@')[0]} {h.get('mod', '')[4:21]}" + (" SOFT-DELETED" if h.get("deleted") else ""))
    print(f"\n  só no GWI ({len(so_w)}):")
    for h in so_w:
        print(f"    {h['rel'][:80]:80} {h.get('publicada') or 'nunca-pub'}" + (f" redirect={h['redirect']}" if h.get("redirect") else ""))
    out.update({"linhas": linhas, "so_G": so_g, "so_GWI": so_w, "excluidas_T": excluidas})

    # ---------- 3. referências de T ----------
    refs = []
    for rel in sorted(linhas):
        jc = tr[rel].get("_jc")
        if not jc:
            continue
        r = []
        refs_de(jc, f"{T_BASE}/{rel}/jcr:content", r)      # XF (fragmentVariationPath, popups do form) entra como classe "XF"
        for x in r:
            x["pagina"] = rel
        refs += r
    print(f"\n===== referências em T: {len(refs)}  {dict(collections.Counter(x['classe'] for x in refs))}")
    out["refs_T"] = refs

    # XFs
    xfs = sorted({unquote(x["url"]) for x in refs if x["classe"] == "XF"})
    out["xfs"] = {}
    print(f"\n  XFs ({len(xfs)}):")
    for u in xfs:
        g = u.replace(XF_T, XF_G)
        st, _ = jsn(g, ".json")
        n = sum(1 for x in refs if unquote(x["url"]) == u)
        out["xfs"][u] = {"G": g, "http": st, "refs": n}
        print(f"    {n:3}x {u[len('/content/experience-fragments/'):]:90} -> G {st}")

    # assets
    dam = sorted({unquote(x["url"]).split("?")[0] for x in refs if x["classe"].startswith("DAM")})

    def um_asset(u):
        mt = meta(u)
        pares = [u] if u.startswith("/content/dam/macnicaglobal2") else par_no_dam_global2(u.rsplit("/", 1)[-1])
        mg = meta(pares[0]) if len(pares) == 1 else None
        if u.startswith("/content/dam/macnicaglobal2"):         # já no DAM do destino: só conferir que existe
            return u, {"T": mt, "G": pares, "G_meta": mt, "igual": "JÁ-G2" if mt else "G2-404"}
        igual = ("SEM-PAR" if not pares else "VÁRIOS" if len(pares) > 1 else
                 "=" if mt and mg and mt["sha1"] == mg["sha1"] else "≠")
        return u, {"T": mt, "G": pares, "G_meta": mg, "igual": igual}
    with ThreadPoolExecutor(6) as ex:
        assets = dict(ex.map(um_asset, dam))
    out["assets"] = assets
    cont_a = collections.Counter(v["igual"] for v in assets.values())
    print(f"\n  assets distintos: {len(assets)}  {dict(cont_a)}  (origem: {dict(collections.Counter(classe(u) for u in assets))})")
    for u, v in assets.items():
        if v["igual"] != "=":
            print(f"    [{v['igual']:7}] {u[len('/content/dam/'):][:100]}" + (f" -> {[p[len('/content/dam/'):] for p in v['G']][:3]}" if v["G"] else "")
                  + ("" if v["T"] else "  (T SEM metadata: asset não existe/não processado?)"))

    # links de página
    escopo_g = {f"{G_BASE}/{v['g_rel']}" for v in linhas.values()}
    cont = collections.Counter(x["url"] for x in refs if x["classe"] in ("PAGINA-gwi", "pagina-global2", "PAGINA-copia-teste", "publico-macnica.com"))
    links = {}
    for u, n in sorted(cont.items(), key=lambda x: -x[1]):
        base = unquote(u).split("#")[0].split("?")[0]
        base = re.sub(r"\.html$", "", base).rstrip("/")
        for de, para in (("https://www.macnica.com/americas/mai/en", G_BASE), (W_BASE, G_BASE), (T_BASE, G_BASE)):
            if base.startswith(de):
                base = para + "/" + alvo_g(base[len(de):].strip("/")) if base[len(de):].strip("/") else para
        cands = [base] + [para + base[len(de):] for de, para in FIXOS if base == de or base.startswith(de + "/")]
        res = []
        for cd in dict.fromkeys(cands):
            if not cd.startswith("/content/"):                  # URL pública que não é do mai/en: não se abre daqui
                res.append({"alvo": cd, "estado": "PÚBLICO-NÃO-CONFERIDO"})
                continue
            if cd in escopo_g:
                res.append({"alvo": cd, "estado": "NO-ESCOPO"})
                continue
            st, _ = jsn(cd, ".json")
            res.append({"alvo": cd, "estado": "EXISTE" if st == 200 else f"HTTP{st}"})
        links[u] = {"refs": n, "paginas": sorted({x["pagina"] for x in refs if x["url"] == u}), "candidatos": res}
    out["links"] = links
    publicos = {u: v for u, v in links.items() if all(r["estado"] == "PÚBLICO-NÃO-CONFERIDO" for r in v["candidatos"])}
    print(f"\n  URLs públicas fora do mai/en (não abertas daqui): {[unquote(u) for u in publicos]}")
    sem = {u: v for u, v in links.items() if u not in publicos
           and not any(r["estado"] in ("EXISTE", "NO-ESCOPO") for r in v["candidatos"])}
    print(f"\n  links de página: {len(links)} alvos distintos; sem alvo (nem no global2 hoje, nem no escopo): {len(sem)}")
    for u, v in sem.items():
        print(f"    {v['refs']:3}x {unquote(u)[:110]}  <- {v['paginas'][:3]}{'…' if len(v['paginas']) > 3 else ''}")
    fixos = {u: v for u, v in links.items() if len(v["candidatos"]) > 1}
    if fixos:
        print("  pela tabela FIXOS (prefixo trocado não basta):")
        for u, v in fixos.items():
            print(f"    {v['refs']:3}x {unquote(u)[:80]:80} -> {[(r['alvo'][len(G_BASE):], r['estado']) for r in v['candidatos']]}")

    DADOS.mkdir(parents=True, exist_ok=True)
    arq = DADOS / f"levantamento_{a.nome}.json"
    json.dump(out, open(arq, "w"), indent=1, ensure_ascii=False, default=str)
    print(f"\nJSON: {arq}")


if __name__ == "__main__":
    main()
