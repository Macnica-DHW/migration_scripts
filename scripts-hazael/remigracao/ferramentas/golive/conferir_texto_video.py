"""Texto + vídeo lado a lado: geometria do par a 375/768/1400. SOMENTE LEITURA."""
import sys, json
sys.path.insert(0, "/home/hazael/projects/migration_scripts/scripts-hazael/remigracao/ferramentas/golive"); sys.path.insert(0, "/home/hazael/projects/migration_scripts/scripts-bruno")
from _comum import BASE, DADOS
from aem_lib import parse_cookie_string
from playwright.sync_api import sync_playwright
env = dict(l.strip().split("=", 1) for l in open("/home/hazael/projects/migration_scripts/.env") if l.startswith("AEM_COOKIES="))
cookies = parse_cookie_string(env["AEM_COOKIES"].strip().strip('"').strip("'")); host = BASE.split("//", 1)[1]
R = "/content/macnicaglobal2/americas/mai/en/products/boards-modules"
D = json.load(open(DADOS / "boards-modules_escopo_achados_jcr.json"))["D"]
JS = """() => { const W=document.documentElement.clientWidth, out=[];
  document.querySelectorAll('.flexcontainer').forEach(fc => { if (fc.closest('header,footer') || !fc.querySelector('.cmp-embed, .embed iframe, .embed')) return;
    const itens=[...fc.querySelectorAll(':scope > .flex_container > .cmp-container > div')];
    const g=e=>{const r=e.getBoundingClientRect();return {x:Math.round(r.x),y:Math.round(r.y+scrollY),w:Math.round(r.width),h:Math.round(r.height)}};
    out.push({classes: fc.className.replace(/aem-Grid\\S*/g,'').trim().slice(0,90), W, scrollW: document.documentElement.scrollWidth,
      itens: itens.map(it => { const v=it.querySelector('iframe, video, .cmp-embed'); const t=it.querySelector('.cmp-text, .cmp-title');
        return {...g(it), tipo: v ? 'video' : t ? 'texto' : '?', midia: v ? g(v) : null, texto: t ? (t.innerText||'').trim().slice(0,40) : ''}; })}); });
  return out; }"""
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--disable-dev-shm-usage"])
    res = {}
    for d in D:
        rel = d["pag"][len(R):]; print(f"== {rel}"); res[rel] = {}
        for w, h, mob in ((375, 812, True), (768, 1024, True), (1400, 1000, False)):
            c = b.new_context(viewport={"width": w, "height": h}, is_mobile=mob, has_touch=mob)
            c.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"} for k, v in cookies.items()])
            p = c.new_page()
            try: p.goto(f"{BASE}{d['pag']}.html?wcmmode=disabled", wait_until="networkidle", timeout=60000)
            except Exception: pass
            p.evaluate("async()=>{for(let y=0;y<document.body.scrollHeight;y+=700){scrollTo(0,y);await new Promise(r=>setTimeout(r,80));}scrollTo(0,0);}"); p.wait_for_timeout(900)
            r = p.evaluate(JS); res[rel][w] = r
            for fc in r:
                its = fc["itens"]; lado = len(its) > 1 and abs(its[0]["y"] - its[1]["y"]) < 20
                print(f"   {w:4}px {'LADO A LADO' if lado else 'empilhado  '} rolagem=+{fc['scrollW'] - fc['W']:<3} " + " | ".join(f"{i['tipo']} x={i['x']}..{i['x'] + i['w']} y={i['y']} h={i['h']}" + (f" mídia={i['midia']['w']}x{i['midia']['h']}@x{i['midia']['x']}" if i['midia'] else "") for i in its))
            if rel in ("/transcend", "/iei") or w == 375:
                y = r[0]["itens"][0]["y"] if r and r[0]["itens"] else 0
                hh = 620 if w == 375 else 460
                p.screenshot(path=f"/home/hazael/projects/migration_scripts/scripts-hazael/remigracao/dados/golive/prints/boards-modules/{rel.strip('/').replace('/', '__')}_{w}.png", full_page=True, clip={"x": 0, "y": max(0, y - 60), "width": w, "height": hh})
            c.close()
    json.dump(res, open(DADOS / "boards-modules_escopo_video_render.json", "w"), indent=1)
    b.close()
