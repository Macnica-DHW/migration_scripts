#!/usr/bin/env python3
"""
reprocessar_asset.py <asset> [<asset>...] [--executar] — asset do DAM que NUNCA foi processado.

SINTOMA (macnica-products/macnica-cv75, 21/09/2026): imagem quebrada na tela — o
`<img>` tem 21px de altura e mostra o alt. O binário está certo (GET do asset dá
200 image/png, 615.700 bytes), mas o nó está SEM `dam:processingId`, com
`metadata` vazio (sem `dc:format`, sem `tiff:ImageWidth`) e só a rendition
`original`. Sem `dc:format` o servlet do Image (`.coreimg.png`)
devolve 200 com 1 byte de text/html. O `textwithimage` cai do mesmo jeito.

CAUSA: o asset foi criado por outro script e o processamento não rodou. O nosso
`copy_asset` é idempotente — achou o arquivo no lugar e não subiu de novo — então
herdou o asset morto. `conferir` o asset é olhar o `metadata`, não o HTTP 200.

O QUE FAZ: a mesma ação do botão "Reprocess Assets" do console (POST em
/bin/asynccommand, operation=PROCESS, perfil full-process). Não apaga nem
recria o nó — o asset pode ser de outra pessoa. Depois espera `processed`.

Sem `--executar` só mostra o estado. Trava de escrita: só `dam/copia-teste`.

  python3 remigracao/ferramentas/reprocessar_asset.py /content/dam/copia-teste/.../ienso-cv75.png
  python3 remigracao/ferramentas/reprocessar_asset.py <asset> --executar
"""
import sys, time
from pathlib import Path
_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import build_session, get_json, assert_target_is_safe, CONFIG


def estado(s, auth, base, asset):
    d, st = get_json(s, f"{base}{asset}.3.json", auth)
    if st != 200 or not isinstance(d, dict):
        return None
    jc = d.get("jcr:content") or {}
    md = jc.get("metadata") or {}
    return {
        "assetState": jc.get("dam:assetState"),
        "processingId": jc.get("dam:processingId"),
        "dc:format": md.get("dc:format"),
        "dims": (md.get("tiff:ImageWidth"), md.get("tiff:ImageLength")),
        "renditions": sorted(k for k, v in (jc.get("renditions") or {}).items()
                             if isinstance(v, dict)),
    }


def saudavel(e):
    # `dam:assetState` NÃO serve de critério aqui: na copia-teste os assets bons
    # (metadata completo, 11 renditions, renderizam) também dizem `unProcessed`.
    # O que quebra a tela é faltar `dc:format` — e o morto só tem a `original`.
    return bool(e and e["dc:format"] and len(e["renditions"]) > 1)


def main():
    args = sys.argv[1:]
    executar = "--executar" in args
    assets = [a for a in args if not a.startswith("--")]
    if not assets:
        sys.exit(__doc__)
    s, auth = build_session(prompt_if_missing=False, verbose=False)
    base = CONFIG["base_url"]
    if "author-" not in base:                      # o cookie só vai para o author
        sys.exit(f"[erro] base_url inesperada: {base}")

    pendentes = []
    for a in assets:
        e = estado(s, auth, base, a)
        if e is None:
            print(f"  [não existe] {a}"); continue
        marca = "ok        " if saudavel(e) else "NÃO PROC. "
        print(f"  [{marca}] {a}\n               state={e['assetState']} dc:format={e['dc:format']} "
              f"dims={e['dims']} renditions={len(e['renditions'])}")
        if not saudavel(e):
            pendentes.append(a)

    if not pendentes:
        print("\n  nada a reprocessar."); return 0
    if not executar:
        print(f"\n  (diagnóstico — {len(pendentes)} a reprocessar; use --executar)"); return 1

    for a in pendentes:
        assert_target_is_safe(a)
        r = s.post(f"{base}/bin/asynccommand", timeout=90, data={
            "_charset_": "utf-8", "operation": "PROCESS",
            "description": "reprocessar_asset.py", "profile-select": "full-process",
            "runPostProcess": "false", "asset": a})
        print(f"  POST reprocess {r.status_code}  {a.rsplit('/', 1)[-1]}  {r.text[:120]!r}")

    falhou = 0
    for a in pendentes:
        e = None
        for _ in range(36):                        # até ~3 min
            time.sleep(5)
            e = estado(s, auth, base, a)
            if saudavel(e):
                break
        ok = saudavel(e)
        falhou += 0 if ok else 1
        print(f"  [{'processed' if ok else 'AINDA NÃO'}] {a.rsplit('/', 1)[-1]}  "
              f"dc:format={e and e['dc:format']} dims={e and e['dims']} "
              f"renditions={e and len(e['renditions'])}")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
