#!/usr/bin/env python3
"""
varredura_pendencias.py [COLETA.json] — procura, nas páginas do mapa final, pendências que a comparação de LINKS não pega.
Lê o cache da coleta do links_vs_gwi (jcr:content dos dois lados + lista do DAM do global2); só confirma por GET o asset
que a lista do DAM não tem (o índice atrasa depois de cópia). Nada gravado.

  imagem_gwi       fileReference no DAM do GWI (a imagem sai do site antigo)
  imagem_sem_asset fileReference no DAM do global2 que não existe (imagem quebrada)
  imagem_vazia     image/textwithimage/bannerimage sem fileReference (o /products tinha 4 — caixa vazia na tela)
  link_gwi         href/linkURL apontando para /content/macnicagwi
  lista_deletadas  list de filhas que inclui página soft-deleted (sai duplicada no author)
  aba_vazia        painel de tabs sem nenhum componente
  pouco_texto      texto visível do global2 < 60% do texto do GWI (com o GWI > 600 caracteres) — candidato, rever à mão:
                   o JCR do GWI tem texto escondido por flag (isText/isHeading=false), então isto É ruído em parte

Pedido do Hazael (25/09/2026): "if you find other pending pages, add them to the report".

    python3 varredura_pendencias.py ../../dados/mapas/global2_links_vs_gwi_2026-09-25_final.json
"""
import collections
import html
import json
import pickle
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corrigir_links as C  # noqa: E402
import links_vs_gwi as LV  # noqa: E402

M = C.M
SEM_IMAGEM_OK = {"spImage", "cq:featuredimage", "manufacturerlogo", "productlinelogo", "image_sp"}
HREF = re.compile(r'''href\s*=\s*(["'])(.*?)\1''', re.I | re.S)


def nos(no, cam=""):
    for k, v in no.items():
        if isinstance(v, dict):
            yield f"{cam}/{k}" if cam else k, k, v
            yield from nos(v, f"{cam}/{k}" if cam else k)


def texto_visivel(jc, gwi=False):
    partes = []
    for cam, k, v in nos(jc):
        rt = str(v.get("sling:resourceType", ""))
        if gwi and v.get("isText") == "false":
            continue
        for p in ("text", "jcr:title") if rt.endswith(("/title", "/heading", "/button")) else ("text",):
            if isinstance(v.get(p), str):
                partes.append(v[p])
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", " ".join(partes)))).strip()


def main():
    rel = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    b = pickle.loads(LV.CACHE.read_bytes())
    assert b["quando"] == rel["quando"], "o cache não é desta coleta"
    idx = LV.Indice(b)
    dam = {unquote(p) for p in b.get("dam_g2", [])}
    filhos = collections.defaultdict(list)
    for p, h in idx.g2.items():
        filhos[p.rsplit("/", 1)[0]].append((p, bool(LV.Indice._morta(h))))
    achados = collections.defaultdict(list)                   # tipo -> [(pagina_rel, detalhe)]
    confirmar = {}
    for r in rel["paginas"]:
        g2 = r["g2"]
        jc = b["jcr"].get(g2)
        if not isinstance(jc, dict):
            continue
        p = g2[len(M) + 1:] if g2 != M else ""
        for cam, k, v in nos(jc):
            rt = str(v.get("sling:resourceType", ""))
            fr = v.get("fileReference")
            if isinstance(fr, str) and fr:
                if "/macnicagwi/" in fr:
                    achados["imagem_gwi"].append((p, f"{cam}: {fr}"))
                elif fr.startswith("/content/dam/macnicaglobal2/") and unquote(fr) not in dam:
                    confirmar[fr] = confirmar.get(fr, []) + [(p, cam)]
            elif rt.endswith(("/image", "/textwithimage", "/bannerimage")) and k not in SEM_IMAGEM_OK and not cam.startswith("cq:"):
                achados["imagem_vazia"].append((p, cam))
            for campo in ("linkURL", "text"):
                val = v.get(campo)
                if isinstance(val, str) and "macnicagwi" in val:
                    hs = [h[1] for h in HREF.findall(val)] if campo == "text" else [val]
                    for h in hs:
                        if "/content/macnicagwi" in h:
                            achados["link_gwi"].append((p, f"{cam}: {h}"))
            if rt.endswith("/list") and v.get("listFrom", "children") == "children":
                pai = v.get("parentPage") or g2
                mortas = [x for x, m in filhos.get(pai, []) if m]
                if mortas:
                    achados["lista_deletadas"].append((p, f"{cam}: {len(mortas)} soft-deleted of {len(filhos[pai])} "
                                                          f"({', '.join(x.rsplit('/', 1)[-1] for x in mortas[:4])}{'…' if len(mortas) > 4 else ''})"))
            if rt.endswith("/tabs"):
                for ik, iv in v.items():
                    if isinstance(iv, dict) and not any(isinstance(x, dict) and kk != "cq:responsive" for kk, x in iv.items()):
                        achados["aba_vazia"].append((p, f"{cam}/{ik} “{iv.get('cq:panelTitle', '')}”"))
        w = idx.par(g2)
        jw = b["jcr"].get(w) if w else None
        if isinstance(jw, dict):
            tg, tw = len(texto_visivel(jc)), len(texto_visivel(jw, gwi=True))
            if tw > 600 and tg < 0.6 * tw:
                achados["pouco_texto"].append((p, f"global2 {tg} characters of visible text, GWI {tw} ({round(100 * tg / tw)}%)"))
    for fr, onde in confirmar.items():                            # índice do DAM atrasa: GET antes de acusar
        st, _ = C.ler(fr, ".0.json")
        if st == 404:
            achados["imagem_sem_asset"] += [(p, f"{cam}: {fr}") for p, cam in onde]
    out = LV.MAPAS.parent / "golive" / f"varredura_pendencias_{rel['quando'][:10]}.json"
    out.write_text(json.dumps({"quando": rel["quando"], "achados": achados}, ensure_ascii=False, indent=1), encoding="utf-8")
    for t, xs in achados.items():
        print(f"{t}: {len(xs)} em {len({p for p, _ in xs})} páginas")
        for p, d in xs[:12]:
            print(f"    /{p} — {d[:150]}")
    print("->", out)


if __name__ == "__main__":
    main()
