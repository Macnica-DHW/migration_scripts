#!/usr/bin/env python3
"""
lista_migradas_mai_en.py — página HTML com o link de TODA página que o go-live de mai/en (23/09/2026) pôs no global2,
para conferir: 125 páginas (114 novas + 11 cascas preenchidas, events-archive incluída), os 2 redirects extras
(/contact-us, casca Careers) e o XF do form de evento. SOMENTE LEITURA (só GET no author, para títulos e estado).

Pedido do Hazael (23/09): "links for all pages we migrated ... add a button so that I can open sets of pages in new
tabs at once". Cada seção tem botões "Open 1–10, 11–20…" (tamanho do lote escolhível); no topo escolhe-se o que abrir:
a página do global2 fora do editor, o editor, ou a original do GWI (grafia do GWI: Careers, iENSO-…). Filtro por
texto (os botões abrem só as linhas visíveis); "reviewed" por linha fica no localStorage do navegador.

    python3 lista_migradas_mai_en.py        # -> dados/mapas/global2_migradas_mai-en.html
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import golive_mai_en as g  # noqa: E402

SAIDA = Path(__file__).resolve().parents[2] / "dados" / "mapas" / "global2_migradas_mai-en.html"


def dados():
    L = json.load(open(g.LEVANTAMENTO))
    P = json.load(open(g.PLANO))
    g2t = {v["g_rel"]: t for t, v in L["linhas"].items()}          # rel normalizado -> grafia do GWI/copia-teste
    trocadas = {t["rel"] for t in P["trocar"]}
    pags = []
    for rel in [r for r in g.paginas(g.STG) if r]:
        st, jc = g.ler(f"{g.G}/{rel}/jcr:content")
        jc = jc or {}
        pags.append({"rel": rel, "title": (jc.get("pageTitle") or jc.get("jcr:title") or rel).strip(), "http": st,
                     "state": "shell" if rel in trocadas else "new", "redirect": jc.get("cq:redirectTarget", ""),
                     "perm": jc.get("cq:redirectPermanent") == "true", "gwi": g2t.get(rel, rel)})
    extras = []
    for rel, gwi, nota in (("contact-us", "contact/form", "302 to /contact/form"),
                           ("about-us/Careers", "about-us/Careers", "old shell: 301 to recruitee, hidden from menu")):
        _, jc = g.ler(f"{g.G}/{rel}/jcr:content")
        extras.append({"rel": rel, "title": (jc or {}).get("jcr:title", rel), "http": 200, "state": "set",
                       "redirect": (jc or {}).get("cq:redirectTarget", ""), "perm": (jc or {}).get("cq:redirectPermanent") == "true",
                       "gwi": gwi, "note": nota})
    return {"base": g.BASE, "G": g.G, "W": g.W, "xf": f"{g.XF_G}/event-meeting-request-form/master",
            "pages": pags, "extras": extras}


PAGINA = r"""<meta charset="utf-8">
<title>mai/en Go-Live Review</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
:root{
  --ground:#F4F5F7; --surface:#FFFFFF; --ink:#1B2130; --muted:#5A6376; --line:#DCE0E7; --line-soft:#E9ECF1;
  --accent:#1D5FA8; --accent-ink:#FFFFFF; --accent-soft:#E6EEF8; --focus:#1D5FA8;
  --new-fg:#1E6B45; --new-bg:#E2F2E9; --shell-fg:#8A5300; --shell-bg:#FBEFD8;
  --redir-fg:#5E4596; --redir-bg:#EEE9F8; --set-fg:#4A5568; --set-bg:#EAEDF2;
  --done:#1E6B45; --warn-fg:#8A2C0B; --warn-bg:#FCE7DE;
  --sans:"IBM Plex Sans", "Segoe UI", system-ui, -apple-system, sans-serif;
  --mono:"IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --ground:#12151A; --surface:#1A1E25; --ink:#E3E6EC; --muted:#99A2B3; --line:#2D333D; --line-soft:#232830;
    --accent:#7FB0EE; --accent-ink:#0F1622; --accent-soft:#1E2B3D; --focus:#7FB0EE;
    --new-fg:#7FD3A6; --new-bg:#17311F; --shell-fg:#F2BE6B; --shell-bg:#34270F;
    --redir-fg:#C3B0F0; --redir-bg:#2A2340; --set-fg:#B5BECD; --set-bg:#262B34;
    --done:#7FD3A6; --warn-fg:#F7B79C; --warn-bg:#3A1F16;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --ground:#12151A; --surface:#1A1E25; --ink:#E3E6EC; --muted:#99A2B3; --line:#2D333D; --line-soft:#232830;
  --accent:#7FB0EE; --accent-ink:#0F1622; --accent-soft:#1E2B3D; --focus:#7FB0EE;
  --new-fg:#7FD3A6; --new-bg:#17311F; --shell-fg:#F2BE6B; --shell-bg:#34270F;
  --redir-fg:#C3B0F0; --redir-bg:#2A2340; --set-fg:#B5BECD; --set-bg:#262B34;
  --done:#7FD3A6; --warn-fg:#F7B79C; --warn-bg:#3A1F16;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:14px/1.45 var(--sans);padding-inline:16px;padding-block:0 48px}
.wrap{max-width:1180px;margin:0 auto}
header.top{padding-block:28px 12px;display:grid;gap:6px}
h1{font-size:22px;font-weight:600;margin:0;text-wrap:balance;letter-spacing:-.01em}
.sub{color:var(--muted);margin:0;max-width:78ch}
.stats{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:6px;font-variant-numeric:tabular-nums;color:var(--muted)}
.stats b{color:var(--ink);font-weight:600}
.bar{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--ground);border-bottom:1px solid var(--line);
  padding-block:10px;display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:6px;overflow:hidden;background:var(--surface)}
.seg input{position:absolute;opacity:0;pointer-events:none}
.seg label{padding:6px 11px;cursor:pointer;color:var(--muted);border-right:1px solid var(--line);user-select:none}
.seg label:last-of-type{border-right:0}
.seg input:checked + label{background:var(--accent);color:var(--accent-ink)}
.seg input:focus-visible + label{outline:2px solid var(--focus);outline-offset:-2px}
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin-right:6px}
.grp{display:flex;align-items:center}
input[type=search]{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:6px 10px;width:min(280px,100%)}
input[type=search]:focus-visible{outline:2px solid var(--focus);outline-offset:1px}
.toast{margin-left:auto;font-size:13px;padding:5px 10px;border-radius:6px;background:var(--accent-soft);color:var(--ink)}
.toast.warn{background:var(--warn-bg);color:var(--warn-fg)}
section{margin-top:26px}
.sh{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px;padding-bottom:8px;border-bottom:1px solid var(--line)}
h2{font-size:16px;font-weight:600;margin:0}
.count{color:var(--muted);font-variant-numeric:tabular-nums;font-size:13px}
.desc{color:var(--muted);font-size:13px;flex-basis:100%;margin:0;max-width:90ch}
.chunks{display:flex;flex-wrap:wrap;gap:6px;margin-left:auto}
button{font:inherit;font-size:13px;cursor:pointer;border-radius:6px;padding:5px 10px;border:1px solid var(--accent);background:var(--surface);color:var(--accent)}
button:hover{background:var(--accent-soft)}
button:focus-visible{outline:2px solid var(--focus);outline-offset:1px}
button.opened{border-color:var(--line);color:var(--muted)}
button.opened::after{content:" ✓"}
ol.rows{list-style:none;margin:0;padding:0}
.row{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:4px 12px;align-items:start;padding:8px 2px;border-bottom:1px solid var(--line-soft)}
.row input[type=checkbox]{margin:3px 0 0;width:15px;height:15px;accent-color:var(--done)}
.row.rev .t{color:var(--muted)}
.t{font-weight:500;overflow-wrap:anywhere}
.p{font-family:var(--mono);font-size:12px;color:var(--muted);overflow-wrap:anywhere}
.meta{display:flex;flex-wrap:wrap;gap:6px 8px;align-items:center;margin-top:3px}
.chip{font-size:11px;letter-spacing:.03em;padding:1px 7px;border-radius:999px;white-space:nowrap}
.chip.new{color:var(--new-fg);background:var(--new-bg)} .chip.shell{color:var(--shell-fg);background:var(--shell-bg)}
.chip.redir{color:var(--redir-fg);background:var(--redir-bg)} .chip.set{color:var(--set-fg);background:var(--set-bg)}
.links{display:flex;gap:10px;white-space:nowrap;font-size:13px}
.links a{color:var(--accent);text-decoration:none}
.links a:hover{text-decoration:underline}
.links a:visited{color:var(--muted)}
.links a:focus-visible{outline:2px solid var(--focus);outline-offset:2px;border-radius:2px}
.foot{margin-top:32px;color:var(--muted);font-size:12px}
@media (max-width:640px){.row{grid-template-columns:22px minmax(0,1fr)}.links{grid-column:2}.toast{margin-left:0}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div class="wrap">
  <header class="top">
    <h1>mai/en go-live — pages to review</h1>
    <p class="sub">Everything the 23 Sep 2026 migration put into <span class="p">macnicaglobal2/americas/mai/en</span>: new pages, filled shells and redirects, events included. Pick what the buttons open, then open a section in sets.</p>
    <div class="stats" id="stats"></div>
  </header>
  <div class="bar" role="toolbar" aria-label="Open options">
    <div class="grp"><span class="lbl" id="l-mode">Open</span>
      <div class="seg" role="radiogroup" aria-labelledby="l-mode">
        <input type="radio" name="mode" id="m-page" value="page" checked><label for="m-page">global2 page</label>
        <input type="radio" name="mode" id="m-edit" value="edit"><label for="m-edit">global2 editor</label>
        <input type="radio" name="mode" id="m-gwi" value="gwi"><label for="m-gwi">GWI original</label>
      </div></div>
    <div class="grp"><span class="lbl" id="l-size">Per set</span>
      <div class="seg" role="radiogroup" aria-labelledby="l-size">
        <input type="radio" name="size" id="s-5" value="5"><label for="s-5">5</label>
        <input type="radio" name="size" id="s-10" value="10" checked><label for="s-10">10</label>
        <input type="radio" name="size" id="s-20" value="20"><label for="s-20">20</label>
        <input type="radio" name="size" id="s-all" value="0"><label for="s-all">All</label>
      </div></div>
    <div class="grp"><label class="lbl" for="q">Filter</label><input type="search" id="q" placeholder="title or path"></div>
    <div class="toast" id="toast" hidden></div>
  </div>
  <main id="main"></main>
  <p class="foot" id="foot"></p>
</div>

<script>
const D = __DADOS__;
const GROUPS = [
  {id:"contact", name:"Contact", desc:"New branch at /contact (as in the GWI). /contact-us now redirects to /contact/form.",
   test:r=>r==="contact"||r.startsWith("contact/"), extra:"contact-us"},
  {id:"top", name:"Top-level pages", desc:"request-a-quote and error were empty shells; the raffle terms page is new.",
   test:r=>["request-a-quote","error","terms-conditions-mep100-ecosystem-partners-tour-challenge-raffle"].includes(r)},
  {id:"about", name:"About Us", desc:"Landing and sections. careers is a redirect to recruitee; the old Careers shell redirects too and is hidden from the menu.",
   test:r=>r==="about-us"||(r.startsWith("about-us/")&&!/^about-us\/(partner-with-macnica|newsletter($|\/)|news-events\/)/.test(r)), extra:"about-us/Careers"},
  {id:"partner", name:"Partner with Macnica", desc:"Landing plus the 7 associations — each association page redirects (301) to its own site, as in the GWI.",
   test:r=>r.startsWith("about-us/partner-with-macnica")},
  {id:"news", name:"News archive", desc:"Landing plus every press release.",
   test:r=>r.startsWith("about-us/news-events/news-archive")},
  {id:"newsletter", name:"Newsletter", desc:"Landing plus every issue.",
   test:r=>r==="about-us/newsletter"||r.startsWith("about-us/newsletter/")},
  {id:"events", name:"Events archive", desc:"Landing (was a shell redirecting to the old public site) plus every event. ibc-2024 and nab-2025 redirect, as in the GWI.",
   test:r=>r.startsWith("about-us/news-events/events-archive")},
];
const key = k => "mai-en-review:" + k;
const store = {get(k,d){try{const v=localStorage.getItem(key(k));return v===null?d:v}catch(e){return d}},
               set(k,v){try{localStorage.setItem(key(k),v)}catch(e){}}};
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const url = (p, m) => m==="edit" ? `${D.base}/editor.html${p}.html` : `${D.base}${p}.html?wcmmode=disabled`;
function linksOf(it){
  return {page:url(`${D.G}/${it.rel}`,"page"), edit:url(`${D.G}/${it.rel}`,"edit"), gwi:url(`${D.W}/${it.gwi}`,"page")};
}
function landingFirst(a,b){return a.rel.split("/").length-b.rel.split("/").length || a.rel.localeCompare(b.rel)}

// grupos
const rest = D.pages.slice();
for (const g of GROUPS){
  g.items = rest.filter(p=>g.test(p.rel)).sort(landingFirst);
  if (g.extra){ const e = D.extras.find(x=>x.rel===g.extra); if (e) g.items.push(e); }
}
const xfGroup = {id:"xf", name:"Experience fragment", desc:"The shared event form (Meeting Request + page title). Embedded in 12 event pages.",
  items:[{rel:"XF", title:"Event Meeting Request Form", state:"xf", xf:true}]};
GROUPS.push(xfGroup);

function chip(it){
  if (it.xf) return `<span class="chip new">new XF</span>`;
  const out = [];
  if (it.state==="new") out.push(`<span class="chip new">new page</span>`);
  if (it.state==="shell") out.push(`<span class="chip shell">shell filled</span>`);
  if (it.state==="set") out.push(`<span class="chip set">redirect set · ${esc(it.note)}</span>`);
  else if (it.redirect){
    let host = it.redirect; try{ host = it.redirect.startsWith("/") ? it.redirect.split("/").pop() : new URL(it.redirect).host }catch(e){}
    out.push(`<span class="chip redir" title="${esc(it.redirect)}">redirect ${it.perm?"301":"302"} → ${esc(host)}</span>`);
  }
  return out.join("");
}
function rowHTML(it, gid){
  const k = it.xf ? "XF" : it.rel;
  const done = store.get("rev:"+k,"") === "1";
  let l;
  if (it.xf){ l = {page:url(D.xf,"page"), edit:url(D.xf,"edit"), gwi:""}; }
  else l = linksOf(it);
  const path = it.xf ? D.xf.replace("/content/experience-fragments/macnicaglobal2/americas/mai/en/","xf …/") : it.rel;
  return `<li class="row${done?" rev":""}" data-k="${esc(k)}" data-page="${esc(l.page)}" data-edit="${esc(l.edit)}" data-gwi="${esc(l.gwi)}" data-s="${esc((it.title+" "+path).toLowerCase())}">
    <input type="checkbox" id="c-${gid}-${esc(k).replace(/[^a-z0-9]/gi,"_")}" aria-label="Reviewed: ${esc(it.title)}" ${done?"checked":""}>
    <div><div class="t">${esc(it.title)}</div>
      <div class="meta"><span class="p">${esc(path)}</span>${chip(it)}</div></div>
    <div class="links"><a href="${esc(l.page)}" target="_blank" rel="noopener">page</a><a href="${esc(l.edit)}" target="_blank" rel="noopener">edit</a>${l.gwi?`<a href="${esc(l.gwi)}" target="_blank" rel="noopener">GWI</a>`:""}</div>
  </li>`;
}
const main = document.getElementById("main");
main.innerHTML = GROUPS.map(g => `<section id="${g.id}" aria-labelledby="h-${g.id}">
  <div class="sh"><h2 id="h-${g.id}">${esc(g.name)}</h2><span class="count" data-count></span><div class="chunks" data-chunks></div><p class="desc">${esc(g.desc)}</p></div>
  <ol class="rows">${g.items.map(it=>rowHTML(it,g.id)).join("")}</ol></section>`).join("");

const total = D.pages.length, nNew = D.pages.filter(p=>p.state==="new").length, nShell = total-nNew,
      nRedir = D.pages.filter(p=>p.redirect).length + D.extras.length;
document.getElementById("stats").innerHTML =
  `<span><b>${total}</b> pages</span><span><b>${nNew}</b> new</span><span><b>${nShell}</b> shells filled</span>` +
  `<span><b>${nRedir}</b> redirects</span><span><b>1</b> XF</span><span id="revcount"></span>`;
document.getElementById("foot").textContent = `Author: ${D.base.replace("https://","")} · pages open outside the editor with ?wcmmode=disabled (redirect pages then go straight to their target) · nothing here is published.`;

const mode = () => document.querySelector("input[name=mode]:checked").value;
const size = () => +document.querySelector("input[name=size]:checked").value;
for (const n of ["mode","size"]){
  const v = store.get(n,null); const el = v && document.querySelector(`input[name=${n}][value="${v}"]`); if (el) el.checked = true;
  document.querySelectorAll(`input[name=${n}]`).forEach(i=>i.addEventListener("change",()=>{store.set(n,i.value); render()}));
}
const toast = document.getElementById("toast");
function say(msg, warn){ toast.textContent = msg; toast.hidden = false; toast.classList.toggle("warn", !!warn); }
function openSet(rows, btn){
  const m = mode(); let blocked = 0, n = 0;
  for (const r of rows){
    const u = r.dataset[m]; if (!u) continue; n++;
    const w = window.open(u, "_blank");
    if (!w) blocked++; else { try{ w.opener = null }catch(e){} }
  }
  if (blocked) say(`${blocked} of ${n} tabs were blocked — allow pop-ups for this page and click the set again (or use the row links).`, true);
  else { say(`Opened ${n} tab${n===1?"":"s"} (${m==="page"?"global2 page":m==="edit"?"editor":"GWI original"}).`); btn.classList.add("opened"); }
}
function render(){
  const q = document.getElementById("q").value.trim().toLowerCase();
  let rev = 0, all = 0;
  for (const sec of main.querySelectorAll("section")){
    const rows = [...sec.querySelectorAll(".row")];
    rows.forEach(r => r.hidden = !!q && !r.dataset.s.includes(q));
    const vis = rows.filter(r=>!r.hidden);
    sec.hidden = vis.length === 0;
    const done = rows.filter(r=>r.classList.contains("rev")).length; rev += done; all += rows.length;
    sec.querySelector("[data-count]").textContent = `${vis.length}${q?` of ${rows.length}`:""} · ${done} reviewed`;
    const box = sec.querySelector("[data-chunks]"); box.innerHTML = "";
    const s = size() || vis.length;
    for (let i = 0; i < vis.length; i += s){
      const part = vis.slice(i, i+s), b = document.createElement("button");
      b.textContent = (s >= vis.length) ? `Open all ${vis.length}` : `Open ${i+1}–${i+part.length}`;
      b.addEventListener("click", () => openSet(part, b));
      box.appendChild(b);
    }
  }
  document.getElementById("revcount").innerHTML = `<b>${rev}</b>/${all} reviewed`;
}
main.addEventListener("change", e => {
  if (e.target.type !== "checkbox") return;
  const row = e.target.closest(".row"); row.classList.toggle("rev", e.target.checked);
  store.set("rev:"+row.dataset.k, e.target.checked ? "1" : ""); render();
});
document.getElementById("q").addEventListener("input", render);
render();
</script>
"""


def main():
    d = dados()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(PAGINA.replace("__DADOS__", json.dumps(d, ensure_ascii=False).replace("</", "<\\/")))
    print(f"{len(d['pages'])} páginas + {len(d['extras'])} redirects extras + 1 XF -> {SAIDA}")


if __name__ == "__main__":
    main()
