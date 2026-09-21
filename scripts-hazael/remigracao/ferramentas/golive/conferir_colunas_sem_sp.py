"""Colunas de texto SEM 'Design for SP' a 375px + releitura das 2 páginas que deram timeout. SOMENTE LEITURA."""
import sys, json, collections
sys.path.insert(0, "/home/hazael/projects/migration_scripts/scripts-hazael/remigracao/ferramentas/golive"); sys.path.insert(0, "/home/hazael/projects/migration_scripts/scripts-bruno")
import conferir_mobile as cm
from _comum import BASE, DADOS
from aem_lib import parse_cookie_string
from playwright.sync_api import sync_playwright
env = dict(l.strip().split("=", 1) for l in open("/home/hazael/projects/migration_scripts/.env") if l.startswith("AEM_COOKIES="))
cookies = parse_cookie_string(env["AEM_COOKIES"].strip().strip('"').strip("'")); host = BASE.split("//", 1)[1]
R = "/content/macnicaglobal2/americas/mai/en/products/boards-modules"
d = json.load(open(DADOS / "mobile_boards-modules_escopo.json"))["paginas"]
fora = collections.defaultdict(list)
for r in d:
    for b in r.get("375", {}).get("botoes", []):
        if b["fora"]: fora[r["path"][len(R):]].append((b["t"][:22], b["x"], b["dir"]))
print("páginas com botão além da borda a 375px:"); [print("   ", p, v) for p, v in fora.items()]
C = json.load(open(DADOS / "boards-modules_escopo_achados_jcr.json"))["C"]
pagsC = sorted({c["pag"] for c in C})
JS = """() => { const W=document.documentElement.clientWidth, out=[];
  document.querySelectorAll('.flexcontainer').forEach(fc => { if (fc.closest('header,footer') || fc.className.includes('sp-flex-direction')) return;
    const its=[...fc.querySelectorAll(':scope > .flex_container > .cmp-container > div')].map(e=>{const r=e.getBoundingClientRect();return {x:Math.round(r.x),d:Math.round(r.right),y:Math.round(r.y+scrollY),w:Math.round(r.width),t:(e.innerText||'').trim().slice(0,24)}});
    if (its.length) out.push(its); });
  return {W, scrollW: document.documentElement.scrollWidth, grupos: out}; }"""
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
    c = b.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
    c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in cookies.items()])
    print("\ncolunas sem Design for SP, a 375px:")
    for pg in pagsC:
        p = c.new_page()
        try: p.goto(f"{BASE}{pg}.html?wcmmode=disabled", wait_until="networkidle", timeout=45000)
        except Exception: pass
        p.wait_for_timeout(800); r = p.evaluate(JS)
        print(f"   {pg[len(R):]}  rolagem=+{r['scrollW'] - r['W']}")
        for g in r["grupos"]:
            lado = len(g) > 1 and abs(g[0]["y"] - g[1]["y"]) < 20
            print(f"       {'LADO A LADO' if lado else 'empilhado  '} {len(g)} colunas, larguras {[i['w'] for i in g]}, x {[(i['x'], i['d']) for i in g]}  «{g[0]['t']}»")
        if pg.endswith("/connect-tech"): p.screenshot(path=sys.argv[1], full_page=True, clip={"x": 0, "y": max(0, r["grupos"][0][0]["y"] - 40) if r["grupos"] else 0, "width": 375, "height": 560})
        p.close()
    c.close()
    print("\nreleitura das 2 que deram timeout:")
    for rel, w in (("/terasic/altera-agilex-7-fpga-f-series-transceiver-soc-development-kit", 375), ("/hitek-systems/hitek-systems-ip-cores/800g-ethernet-fpga-ip-core-solution", 768)):
        c = b.new_context(viewport={"width": w, "height": 900}, is_mobile=True, has_touch=True)
        c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in cookies.items()])
        p = c.new_page()
        try: p.goto(f"{BASE}{R}{rel}.html?wcmmode=disabled", wait_until="load", timeout=90000)
        except Exception as e: print("   ", rel, "ERRO", str(e)[:60]); continue
        p.wait_for_timeout(2500); r = p.evaluate(cm.JS)
        print(f"    {w}px {rel[-50:]}: rolagem=+{r['scrollW'] - r['W']} lado a lado={len(r['lado'])} fora={sum(x['fora'] for x in r['botoes'])} botões={[(x['x'], x['dir']) for x in r['botoes']]}")
        c.close()
    b.close()
