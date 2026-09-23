#!/usr/bin/env python3
"""
lista_migrada.py LISTA [--nome NOME] — de uma lista de páginas do GWI, quais NÃO estão migradas no global2? SOMENTE LEITURA
(só GET, no GWI e no global2).

Pedido do Hazael (23/09/2026): "From this list of pages that exist in GWI, which ones have not been migrated to
macnicaglobal2? Test pages and empty pages in global2 don't count as migrated. Do not extensively check for content
parity yet." LISTA = um caminho por linha, relativo a /content/macnicagwi/americas (ex.: `mai/en/products/…/`).

Para cada página: estado no GWI (existe, publicada, redirect, soft-deleted, nº de componentes, texto) e o PAR no global2:
  1. caminho com cada segmento normalizado (normalize_name), sem diferença de caixa;
  2. trocas de árvore conhecidas (`technology` → `solutions`, sony aninhada — as de gwi_faltando.py);
  3. página do global2 com o mesmo título (jcr:title ou pageTitle) debaixo do MESMO pai — "provável par com outro
     nome" (ex.: `-0` que a Anion tirou), para conferir à mão.
Fica o 1º candidato COM conteúdo: o par pelo caminho pode ser pasta vazia e o conteúdo estar em outra página do mesmo
título (sony-image-sensors do GWI = semiconductors/sony no global2).
O par NÃO conta como migrado se: soft-deleted (`deleted`), teste (nome ou título), ou vazio (nenhum componente de
conteúdo sob jcr:content/root além de `title` — container, grade, breadcrumb, XF, flex, abas e acordeão são estrutura, e
um `title` sozinho só repete o nome da página: a landing de boards-modules no global2 é assim, x heading + texto +
supplierlist no GWI). Par com conteúdo, mas
com menos de 1/4 do texto do GWI, sai como MIGRADA com aviso "RALA" — é só um sinal, não conferência de paridade.

    python3 lista_migrada.py lista.txt --nome lista_hazael_2026-09-23
"""
import argparse
import collections
import concurrent.futures as cf
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gwi_faltando import TESTE, TROCAS, chave, paginas  # noqa: E402
from levantamento_existente import DADOS, fundo, jsn  # noqa: E402

GWI = "/content/macnicagwi/americas"
G = "/content/macnicaglobal2/americas"
ESTRUTURA = {"container", "responsivegrid", "breadcrumb", "experiencefragment", "flexcontainer", "flexcontaineritem",
             "tabs", "accordion"}
TEXTO = {"text", "jcr:title", "title", "description", "linkText", "label", "subtitle", "pretitle", "heading",
         "buttonText", "caption", "alt"}


def medir(jc):
    """(nº de componentes de conteúdo sob root, nº de caracteres de texto neles, nº de imagens, tipos)."""
    n = chars = imgs = 0
    tipos = collections.Counter()

    def anda(no):
        nonlocal n, chars, imgs
        rt = str(no.get("sling:resourceType", "")).rsplit("/", 1)[-1]
        if rt and rt not in ESTRUTURA:
            n += 1
            tipos[rt] += 1
            for k, v in no.items():
                if k in TEXTO and isinstance(v, str):
                    chars += len(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", v))).strip())
            imgs += bool(no.get("fileReference"))
        for v in no.values():
            if isinstance(v, dict):
                anda(v)
    raiz = (jc or {}).get("root")
    if isinstance(raiz, dict):
        anda(raiz)
    return n, chars, imgs, dict(tipos)


def estado(caminho):
    st, no = jsn(caminho, ".json")
    if st != 200:
        return {"http": st}
    jc = fundo(f"{caminho}/jcr:content") or {}
    n, chars, imgs, tipos = medir(jc)
    return {"http": 200, "titulo": jc.get("pageTitle") or jc.get("jcr:title") or "", "jcr_title": jc.get("jcr:title", ""),
            "publicada": jc.get("cq:lastReplicationAction_publish") or jc.get("cq:lastReplicationAction") or "nunca",
            "redirect": jc.get("cq:redirectTarget", ""), "deleted": bool(jc.get("deleted")),
            "template": str(jc.get("cq:template", "")).rsplit("/", 1)[-1], "criador": no.get("jcr:createdBy", ""),
            "mod": f"{jc.get('cq:lastModified', '')} {jc.get('cq:lastModifiedBy', '')}".strip(),
            "componentes": n, "texto": chars, "imagens": imgs, "tipos": tipos}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lista")
    ap.add_argument("--nome", default="lista")
    a = ap.parse_args()
    rels = list(dict.fromkeys(x.strip().strip("/") for x in open(a.lista) if x.strip()))
    secoes = sorted({"/".join(r.split("/")[:2]) for r in rels})          # mai/en
    print(f"{len(rels)} páginas na lista (sem repetição); raízes {secoes}")

    # índice do global2 (páginas vivas e mortas) por chave normalizada, e por (pai, título)
    Gidx, Gmortas, titulos = {}, {}, collections.defaultdict(list)
    for s in secoes:
        for rel, h in paginas(f"{G}/{s}").items():
            rel = f"{s}/{rel}".rstrip("/")
            jc = h.get("jcr:content") or {}
            (Gmortas if jc.get("deleted") else Gidx)[chave(rel)] = rel
            if not jc.get("deleted"):
                pai = chave(rel.rsplit("/", 1)[0])
                for t in {str(jc.get("jcr:title", "")).strip().lower(), str(jc.get("pageTitle", "")).strip().lower()} - {""}:
                    titulos[(pai, t)].append(rel)
    print(f"global2: {len(Gidx)} páginas vivas, {len(Gmortas)} soft-deleted sob {secoes}")

    def cands(rel):
        k = chave(rel)
        out = [k]
        base, resto = "/".join(k.split("/")[:2]), "/".join(k.split("/")[2:])
        for de, para in TROCAS:
            if resto == de or resto.startswith(de + "/"):
                out.append(f"{base}/{para}{resto[len(de):]}")
        return out

    def um(rel):
        w = estado(f"{GWI}/{rel}")
        linha = {"rel": rel, "gwi": w}
        ks = cands(rel)
        opcoes = [(Gidx[k], "caminho") for k in ks if k in Gidx]
        if w.get("http") == 200:
            for k in ks:
                pai = k.rsplit("/", 1)[0]
                for t in {w["titulo"].strip().lower(), w["jcr_title"].strip().lower()} - {""}:
                    opcoes += [(r, "título (mesmo pai)") for r in titulos.get((pai, t), [])]
        opcoes = list(dict.fromkeys(opcoes))
        linha["morta_em_g"] = next((Gmortas[k] for k in ks if k in Gmortas), None)
        # o par pelo caminho pode ser só pasta (sony/sony-image-sensors guarda os 209 sensores; o conteúdo da landing
        # do GWI a Anion pôs em semiconductors/sony, mesmo título): fica o 1º candidato COM conteúdo
        vistos = []
        for par, como in opcoes:
            g = estado(f"{G}/{par}")
            vistos.append((par, como, g))
            if set(g.get("tipos") or {}) - {"title"}:
                break
        if vistos:
            par, como, g = next((v for v in vistos if set(v[2].get("tipos") or {}) - {"title"}), vistos[0])
            linha.update(par=par, como=como, g=g, outros=[v[0] for v in vistos if v[0] != par])
        return linha

    with cf.ThreadPoolExecutor(8) as ex:
        L = list(ex.map(um, rels))

    grupos = collections.defaultdict(list)
    for x in L:
        w, g = x["gwi"], x.get("g")
        if w.get("http") != 200:
            x["motivo"] = f"não existe no GWI (HTTP {w.get('http')})"
            grupos["NÃO EXISTE NO GWI"].append(x)
            continue
        if not g:
            x["motivo"] = "sem página no global2" + (f" (só soft-deleted: {x['morta_em_g']})" if x["morta_em_g"] else "")
            grupos["NÃO MIGRADA"].append(x)
        elif any(TESTE.search(seg) for seg in x["par"].split("/")) or re.search(r"\btest\b", g["titulo"], re.I):
            x["motivo"] = "par no global2 é página de teste"
            grupos["NÃO MIGRADA"].append(x)
        elif not set(g["tipos"]) - {"title"}:
            x["motivo"] = f"casca vazia no global2 ({g['componentes']} componente(s): {g['tipos'] or 'nenhum'})" \
                + (f" x GWI {w['componentes']}: {w['tipos']}" if w["componentes"] else " — o GWI também não tem nenhum")
            grupos["NÃO MIGRADA"].append(x)
        else:
            if w["texto"] and g["texto"] < w["texto"] / 4:
                x["aviso"] = f"RALA: texto {g['texto']} x {w['texto']} no GWI"
            grupos["MIGRADA"].append(x)

    for nome in ("NÃO MIGRADA", "NÃO EXISTE NO GWI", "MIGRADA"):
        X = grupos.get(nome, [])
        print(f"\n===== {nome}: {len(X)}")
        for x in X:
            w, g = x["gwi"], x.get("g") or {}
            gw = f"GWI {w.get('publicada', '-')[:8]:8} {w.get('componentes', '-'):>3}c {w.get('texto', '-'):>6}t"
            gg = f"G {g.get('componentes', '-'):>3}c {g.get('texto', '-'):>6}t {g.get('criador', '')[:18]:18}" if g else "G  —"
            extra = x.get("motivo") or ""
            if x.get("como") and x["como"] != "caminho":
                extra += f" [par por {x['como']}: {x['par']}]"
            elif x.get("par") and chave(x["par"]) != chave(x["rel"]):
                extra += f" [par: {x['par']}]"
            if x.get("outros"):
                extra += f" [candidato(s) vazio(s): {x['outros']}]"
            if w.get("redirect"):
                extra += f" [GWI redirect -> {w['redirect']}]"
            if x.get("aviso"):
                extra += f" [{x['aviso']}]"
            print(f"  {x['rel'][:96]:96} {gw} | {gg} {extra}")
    arq = DADOS / f"lista_migrada_{a.nome}.json"
    json.dump(grupos, open(arq, "w"), indent=1, ensure_ascii=False)
    print(f"\nJSON: {arq}")


if __name__ == "__main__":
    main()
