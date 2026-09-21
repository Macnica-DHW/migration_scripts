#!/usr/bin/env python3
"""gerar_abrir_abas.py <paginas.json> <saida.html> — página de artifact com botões que abrem as páginas em
abas novas, FORA do editor (`.html?wcmmode=disabled` no author), em lotes. Não fala com o AEM.

Entrada: lista de {"rel", "titulo"} (ex.: dados/golive/tq-systems_paginas_corrigidas.json). A raiz e o
texto do cabeçalho são as constantes abaixo — trocar para outra árvore. Marcas de "aberta"/"conferida"
ficam no localStorage de quem abre (conveniência; não volta para o Claude).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "golive"))

AUTHOR = "https://author-p53812-e590634.adobeaemcloud.com"
RAIZ = "/content/macnicaglobal2/americas/mai/en/products/boards-modules/tq-systems"
GRUPOS = {"": "Landing", "tq-embedded-arm-modules": "Arm modules", "tq-embedded-x86-modules": "x86 modules",
          "tq-embedded-qoriqr-layerscape": "QorIQ Layerscape", "tq-embedded-power-modules": "Power modules"}

HTML = r"""<title>TQ-Systems Tab Opener</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --ground:#fbfafc; --surface:#f4f1f6; --line:#ddd6e1; --ink:#1e1826; --muted:#6c6473;
  --accent:#7f1080; --accent-ink:#ffffff; --accent-soft:#f1e3f2; --ok:#1f7a3f; --ok-bg:#e3f3e8; --warn:#9a5206; --warn-bg:#fbeedb;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --ground:#15111a; --surface:#1e1925; --line:#3a3344; --ink:#ece7f0; --muted:#a59db0;
  --accent:#c77fca; --accent-ink:#1a0f1c; --accent-soft:#33213a; --ok:#5fc784; --ok-bg:#1c3324; --warn:#e6a24a; --warn-bg:#3a2a12; } }
:root[data-theme="dark"]{
  --ground:#15111a; --surface:#1e1925; --line:#3a3344; --ink:#ece7f0; --muted:#a59db0;
  --accent:#c77fca; --accent-ink:#1a0f1c; --accent-soft:#33213a; --ok:#5fc784; --ok-bg:#1c3324; --warn:#e6a24a; --warn-bg:#3a2a12; }
*{box-sizing:border-box}
body{background:var(--ground);color:var(--ink);font:400 15px/1.5 var(--sans);padding-inline:20px;padding-block:28px 64px}
.wrap{max-width:920px;margin-inline:auto;display:flex;flex-direction:column;gap:22px}
h1{font-size:26px;font-weight:600;line-height:1.2;margin:0;text-wrap:balance}
.lede{color:var(--muted);margin:6px 0 0;max-width:68ch}
.lede code,.hint code{font:500 13px var(--mono);color:var(--ink)}
.bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:2;background:var(--ground);border-bottom:1px solid var(--line);padding-block:12px;display:flex;flex-wrap:wrap;gap:12px 16px;align-items:center}
button{font:500 14px var(--sans);border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--ink);padding:8px 16px;cursor:pointer}
button:hover{border-color:var(--accent)}
button:focus-visible,a:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
button.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink);font-size:15px;font-weight:600;padding:11px 22px}
button.primary:disabled{opacity:.45;cursor:default}
label.size{display:flex;gap:8px;align-items:center;color:var(--muted);font-size:13px}
select{font:500 14px var(--sans);color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:6px 8px}
.progress{margin-left:auto;font:500 13px var(--mono);color:var(--muted);font-variant-numeric:tabular-nums;text-align:right}
.progress b{color:var(--ink);font-weight:500}
.note{border:1px solid var(--line);border-left:3px solid var(--warn);background:var(--warn-bg);color:var(--ink);padding:10px 14px;border-radius:4px;font-size:14px}
.hint{color:var(--muted);font-size:13px;margin:0;max-width:72ch}
#groups{display:flex;flex-direction:column;gap:30px}
section{display:flex;flex-direction:column;gap:6px}
.ghead{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 12px;border-bottom:1px solid var(--line);padding-bottom:8px}
.ghead h2{font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;margin:0;color:var(--muted)}
.ghead .n{font:400 12px var(--mono);color:var(--muted)}
.ghead button{margin-left:auto;padding:4px 12px;font-size:13px}
ul{list-style:none;margin:0;padding:0}
li{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:4px 10px;align-items:start;padding:7px 0;border-bottom:1px solid color-mix(in srgb,var(--line) 55%,transparent)}
li input{margin:4px 0 0;width:16px;height:16px;accent-color:var(--accent)}
li a{color:var(--ink);text-decoration:none;font-weight:500;overflow-wrap:anywhere}
li a:hover{color:var(--accent);text-decoration:underline}
li .path{grid-column:2;font:400 12px var(--mono);color:var(--muted);overflow-wrap:anywhere}
li .tag{grid-row:1;grid-column:3;font:500 11px var(--mono);padding:2px 8px;border-radius:999px;background:var(--accent-soft);color:var(--accent);white-space:nowrap}
li.done a{color:var(--muted)}
li.done .tag{background:var(--ok-bg);color:var(--ok)}
@media (max-width:520px){ .progress{margin-left:0;text-align:left;width:100%} }
</style>

<div class="wrap">
  <header>
    <h1>TQ-Systems pages, outside the editor</h1>
    <p class="lede">__N__ live pages under <code>…/boards-modules/tq-systems</code> whose contact buttons now stack on small screens. Each opens as <code>.html?wcmmode=disabled</code> on the author, so you need to be logged in to AEM in this browser.</p>
  </header>

  <div class="bar">
    <button class="primary" id="open-next" type="button">Open next 10 pages</button>
    <label class="size" for="batch">per click
      <select id="batch"><option value="5">5</option><option value="10" selected>10</option><option value="25">25</option><option value="9999">all</option></select>
    </label>
    <button id="reset" type="button">Reset marks</button>
    <div class="progress" id="progress"></div>
  </div>

  <div class="note" id="blocked" hidden></div>
  <p class="hint">The browser allows one new tab per click unless pop-ups are allowed for this page — allow them once when the blocked-pop-up icon appears in the address bar, then click again. To see the phone layout in a tab: DevTools → device toolbar (<code>Ctrl+Shift+M</code>), 375px wide. Tick a page when you have checked it; marks stay in this browser only.</p>

  <div id="groups"></div>
</div>

<script>
const BASE = __BASE__, GROUPS = __GROUPS__;
const KEY = "tq-tab-opener-v1";
let state = {opened:{}, checked:{}};
try { state = Object.assign(state, JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} };
const all = GROUPS.flatMap(g => g.pages);
const rows = new Map();

function render() {
  const host = document.getElementById("groups");
  host.replaceChildren();
  GROUPS.forEach((g, gi) => {
    const sec = document.createElement("section");
    sec.innerHTML = `<div class="ghead"><h2></h2><span class="n"></span><button type="button" id="open-group-${gi}">Open this group</button></div><ul></ul>`;
    sec.querySelector("h2").textContent = g.name;
    sec.querySelector(".n").textContent = g.pages.length + (g.pages.length === 1 ? " page" : " pages");
    sec.querySelector("button").addEventListener("click", () => openMany(g.pages));
    const ul = sec.querySelector("ul");
    g.pages.forEach((p, pi) => {
      const li = document.createElement("li");
      const id = `chk-${gi}-${pi}`;
      li.innerHTML = `<input type="checkbox" id="${id}" aria-label="Checked"><a target="_blank" rel="noreferrer"></a><span class="tag"></span><span class="path"></span>`;
      const a = li.querySelector("a"); a.href = BASE + p.url; a.textContent = p.title;
      a.addEventListener("click", () => { state.opened[p.rel] = 1; save(); paint(); });
      li.querySelector(".path").textContent = p.rel;
      const box = li.querySelector("input");
      box.addEventListener("change", () => { if (box.checked) state.checked[p.rel] = 1; else delete state.checked[p.rel]; save(); paint(); });
      rows.set(p.rel, li); ul.appendChild(li);
    });
    host.appendChild(sec);
  });
  paint();
}

function paint() {
  let opened = 0, checked = 0;
  for (const p of all) {
    const li = rows.get(p.rel), o = !!state.opened[p.rel], c = !!state.checked[p.rel];
    opened += o; checked += c;
    li.classList.toggle("done", c);
    li.querySelector("input").checked = c;
    const tag = li.querySelector(".tag");
    tag.textContent = c ? "checked" : o ? "opened" : ""; tag.hidden = !(c || o);
  }
  const left = all.filter(p => !state.opened[p.rel]).length;
  const n = Math.min(+document.getElementById("batch").value, left);
  const btn = document.getElementById("open-next");
  btn.disabled = left === 0;
  btn.textContent = left === 0 ? "All pages opened" : `Open next ${n} page${n === 1 ? "" : "s"}`;
  document.getElementById("progress").innerHTML = `<b>${opened}</b>/${all.length} opened · <b>${checked}</b>/${all.length} checked`;
}

function openMany(pages) {
  let ok = 0, blocked = 0;
  for (const p of pages) {
    let w = null;
    try { w = window.open(BASE + p.url, "_blank"); } catch (e) {}
    if (w) { try { w.opener = null; } catch (e) {} state.opened[p.rel] = 1; ok++; } else blocked++;
  }
  save(); paint();
  const note = document.getElementById("blocked");
  note.hidden = blocked === 0;
  if (blocked) note.textContent = ok
    ? `Opened ${ok}; the browser blocked the other ${blocked}. Allow pop-ups for this page (icon in the address bar) and click again — only the blocked ones will open.`
    : `The browser blocked all ${blocked} tabs. Allow pop-ups for this page and click again, or open pages from the list below with Ctrl+click.`;
}

document.getElementById("open-next").addEventListener("click", () => {
  const n = +document.getElementById("batch").value;
  openMany(all.filter(p => !state.opened[p.rel]).slice(0, n));
});
document.getElementById("batch").addEventListener("change", paint);
document.getElementById("reset").addEventListener("click", () => { state = {opened:{}, checked:{}}; save(); document.getElementById("blocked").hidden = true; paint(); });
render();
</script>
"""


def main():
    paginas = json.load(open(sys.argv[1]))
    grupos = {}
    for p in sorted(paginas, key=lambda p: p["rel"]):
        chave = p["rel"].strip("/").split("/")[0]                # "" = a landing da família
        grupos.setdefault(chave, []).append({
            "rel": p["rel"], "title": p["titulo"] or p["rel"],
            "url": RAIZ + ("" if p["rel"] == "/" else p["rel"]) + ".html?wcmmode=disabled"})
    dados = [{"name": GRUPOS.get(k, k), "pages": v} for k, v in sorted(grupos.items(), key=lambda kv: list(GRUPOS).index(kv[0]) if kv[0] in GRUPOS else 99)]
    js = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    html = HTML.replace("__BASE__", js(AUTHOR)).replace("__GROUPS__", js(dados)).replace("__N__", str(len(paginas)))
    Path(sys.argv[2]).write_text(html)
    print(f"{len(paginas)} páginas em {len(dados)} grupos -> {sys.argv[2]} ({len(html) / 1e3:.0f} KB)")
    for g in dados:
        print("  ", g["name"], len(g["pages"]))


if __name__ == "__main__":
    main()
