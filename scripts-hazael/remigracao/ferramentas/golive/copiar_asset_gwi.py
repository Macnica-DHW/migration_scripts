#!/usr/bin/env python3
"""
copiar_asset_gwi.py [--executar] — copia ARQUIVOS do DAM do GWI para o DAM do global2 (lista fechada abaixo). Dry-run por padrão.

Pedido do Hazael (24/09/2026): "the 2 PDFs should be copied into global2, and then the links should be updated" — o
linecard (landing /products) e o brochure da IEI (iei-networking-servers). Os links são trocados depois pelo
corrigir_links.py (grupo F), com backup e verificação da página.

REGRA MESTRA: nada é gravado no GWI. A cópia é `<nome>@CopyFrom=<caminho no GWI>` num POST na PASTA DE DESTINO do
global2 (o servidor só LÊ o GWI) — o mesmo do direto.py. A trava da Session do aem_lib barra qualquer não-GET em URL
com `macnicagwi`, e aqui também se confere antes de cada POST.

Antes: o destino tem de dar 404 (nome livre), a pasta tem de existir. Depois: dam:Asset, dam:sha1 igual ao do GWI e o
arquivo baixa (GET 200, mesmo tamanho). Cada cópia vai para dados/golive/manifesto_links.jsonl.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

_RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, build_session  # noqa: E402

DADOS = Path(__file__).resolve().parents[2] / "dados" / "golive"
BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE     # cookie só vai para o author
GWI_DL = "/content/dam/macnicagwi/americas/mai/public/en/downloads"
G2 = "/content/dam/macnicaglobal2/americas/mai/en"
COPIAS = [   # (origem no GWI, destino no global2) — nomes já no padrão do DAM do global2
    (f"{GWI_DL}/macnica-americas-linecard.pdf", f"{G2}/downloads/macnica-americas-linecard.pdf"),
    (f"{GWI_DL}/iei-puzzle-brochure-2024.pdf", f"{G2}/products/boards-modules/iei/pdfs/iei-puzzle-brochure-2024.pdf"),
]

sessao, _ = build_session(prompt_if_missing=False, verbose=False)


def url(p, suf=""):
    return BASE + quote(unquote(p), safe="/:") + suf


def ler(p, suf=".json"):
    r = sessao.get(url(p, suf), timeout=120, allow_redirects=False)
    return r.status_code, (r.json() if r.status_code == 200 and "json" in suf else None)


def sha1(asset):
    st, md = ler(asset + "/jcr:content/metadata")
    return (md or {}).get("dam:sha1"), (md or {}).get("dam:size")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--executar", action="store_true")
    a = ap.parse_args()
    agora = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    for origem, destino in COPIAS:
        pasta, nome = destino.rsplit("/", 1)
        assert destino.startswith(G2 + "/") and "macnicagwi" not in pasta, destino
        o_sha, o_tam = sha1(origem)
        st_d, _ = ler(destino, ".0.json")
        st_p, _ = ler(pasta, ".0.json")
        print(f"{origem.rsplit('/', 1)[-1]}: GWI sha1 {o_sha} ({o_tam} bytes) -> {destino[len(G2):]}  [destino HTTP {st_d}, pasta HTTP {st_p}]")
        if st_d != 404 or st_p != 200 or not o_sha:
            print("   PULA: destino ocupado, pasta inexistente ou origem sem sha1"); continue
        if not a.executar:
            print("   (dry-run) POST na pasta de destino com", f"{nome}@CopyFrom={origem}"); continue
        r = sessao.post(url(pasta), data={f"{nome}@CopyFrom": origem, "_charset_": "utf-8"}, timeout=300)
        st, j = ler(destino, ".1.json")
        d_sha, d_tam = sha1(destino)
        g = sessao.get(url(destino), timeout=300, allow_redirects=False)
        ok = (r.status_code in (200, 201) and st == 200 and (j or {}).get("jcr:primaryType") == "dam:Asset"
              and d_sha == o_sha and g.status_code == 200 and len(g.content) == int(o_tam))
        print(f"   {'COPIADO' if ok else 'FALHOU'}: POST {r.status_code}; dam:Asset {(j or {}).get('jcr:primaryType')}; "
              f"sha1 {'igual' if d_sha == o_sha else d_sha}; GET {g.status_code} {len(g.content)} bytes")
        with open(DADOS / "manifesto_links.jsonl", "a") as f:
            f.write(json.dumps({"grupo": "F-asset", "tipo": "asset", "origem": origem, "destino": destino, "quando": agora,
                                "status": "copiado" if ok else "falhou", "http": r.status_code, "sha1": d_sha},
                               ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
