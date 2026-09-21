#!/usr/bin/env python3
"""
conferir_direto.py <csv do driver>... — confere o que o `--alvo-global2` gravou. SOMENTE LEITURA.

Para cada par (origem no GWI, destino no global2) dos CSVs do `aem_remigrar.py`:
  texto     o que se VÊ dos dois lados (comparador do aem_fidelidade_render): faltando / sobrando
  imagens   todo <img> do corpo devolve imagem de verdade? (asset não processado devolve 1 byte)
  refs      sobrou no JCR gravado alguma referência a GWI ou copia-teste?
  links     todo alvo interno (/content/...) existe? (GET só no author)
Saída: dados/golive/conferencia_direto_<data>.json + resumo na tela. Sai 1 se houver defeito.
"""
import csv, datetime, json, os, re, sys
from pathlib import Path
from urllib.parse import unquote
_RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import aem_fidelidade_render as FR
import direto as DIR
from aem_lib import CONFIG, build_session, get_json, parse_cookie_string
from playwright.sync_api import sync_playwright


def refs_do_jcr(jc):
    out = {}

    def anda(n, cam):
        for k, v in n.items():
            if isinstance(v, dict):
                anda(v, cam + "/" + k)
                continue
            for x in (v if isinstance(v, list) else [v]):
                if not isinstance(x, str):
                    continue
                if k in ("linkURL", "link", "fileReference", "fragmentVariationPath", "pages") and x.startswith("/content/"):
                    out.setdefault(x, cam.rsplit("/", 1)[-1] + "." + k)
                for m in re.finditer(r'(?:href|src)="(/content/[^"]+)"', x):
                    out.setdefault(m.group(1).replace("&amp;", "&"), cam.rsplit("/", 1)[-1] + ".html")
    anda(jc, "")
    return out


def main():
    pares = []
    for arq in sys.argv[1:]:
        for r in csv.DictReader(open(arq)):
            if r["destino"].startswith(DIR.MAI) and r["status"] == "ok":
                pares.append((r["origem"], r["destino"]))
    pares = sorted(set(pares), key=lambda x: x[1])
    s, auth = build_session(prompt_if_missing=False, verbose=False)
    base = CONFIG["base_url"]
    assert "author-" in base
    host = base.split("//", 1)[1].rstrip("/")
    cookies = parse_cookie_string(os.environ.get("AEM_COOKIES", "").strip())
    existe = {}
    res = []
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = nav.new_context(viewport={"width": 1400, "height": 1000})
        ctx.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in cookies.items()])
        pag = ctx.new_page()
        for i, (o, d) in enumerate(pares, 1):
            l = {"origem": o, "destino": d}
            uo = FR.extrair(pag, base, o, 1500)
            ud = FR.extrair(pag, base, d, 1500)
            falt, sobr, fora, _tl = FR.comparar(uo, ud)
            l["un_gwi"] = sum(1 for u in uo if not FR.e_ruido(u.get("txt", "")))
            l["un_g2"] = sum(1 for u in ud if not FR.e_ruido(u.get("txt", "")))
            l["faltando"] = [re.sub(r"\s+", " ", u.get("txt", ""))[:90] for u in falt]
            l["sobrando"] = [re.sub(r"\s+", " ", u.get("txt", ""))[:90] for u in sobr]
            l["ordem"] = fora
            # imagens do corpo (a página do destino está aberta em `pag`)
            pag.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,100));}}")
            pag.wait_for_timeout(1200)
            imgs = pag.evaluate("""()=>[...document.querySelectorAll('main img, .root img')].filter(i=>!i.closest('header,footer'))
                .map(i=>({src:i.currentSrc||i.src, nw:i.naturalWidth, w:Math.round(i.getBoundingClientRect().width)}))""")
            l["imgs"] = len(imgs)
            l["imgs_quebradas"] = [x["src"].rsplit("/", 1)[-1][:60] for x in imgs if x["nw"] == 0 and "/content/" in x["src"]]
            # refs no JCR gravado
            jc, _ = get_json(s, f"{base}{d}/jcr:content.infinity.json", auth)
            if not isinstance(jc, dict):
                jc, _ = get_json(s, f"{base}{d}/jcr:content.50.json", auth)
            refs = refs_do_jcr(jc.get("root", {}))
            l["refs_proibidas"] = [u for u in refs if DIR.PROIBIDO.search(u)]
            mortos = []
            for u, onde in refs.items():
                p = unquote(u.split("#")[0].split("?")[0])
                p = p[:-5] if p.endswith(".html") else p
                if p not in existe:
                    _j, st = get_json(s, f"{base}{p}.0.json", auth)       # só o author recebe o cookie
                    existe[p] = st
                if existe[p] != 200:
                    mortos.append((p, onde, existe[p]))
            l["links"] = len(refs)
            l["alvos_inexistentes"] = mortos
            res.append(l)
            marca = "OK " if not (l["faltando"] or l["sobrando"] or l["imgs_quebradas"] or l["refs_proibidas"]) else "VER"
            print(f"  [{i:2}/{len(pares)}] {marca} {d[len(DIR.MAI):][:74]:74} texto {l['un_gwi']:3}->{l['un_g2']:3} falta={len(falt):2} sobra={len(sobr):2} "
                  f"img={l['imgs']:2} quebr={len(l['imgs_quebradas'])} refsGWI={len(l['refs_proibidas'])} alvo404={len(mortos)}")
        nav.close()
    saida = DIR.DADOS / f"conferencia_direto_{datetime.date.today().isoformat()}.json"
    saida.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"\n  {saida}")
    ruim = [l for l in res if l["faltando"] or l["sobrando"] or l["imgs_quebradas"] or l["refs_proibidas"]]
    return 1 if ruim else 0


if __name__ == "__main__":
    sys.exit(main())
