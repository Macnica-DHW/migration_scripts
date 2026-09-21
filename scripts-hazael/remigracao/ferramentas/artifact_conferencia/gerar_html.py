import os as _os
PASTA_TRABALHO = _os.environ.get("CONF_SP") or _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_trabalho")
_os.makedirs(PASTA_TRABALHO, exist_ok=True)

import json
SP = PASTA_TRABALHO + ""
HOST = "https://author-p53812-e590634.adobeaemcloud.com"
rows = json.load(open(SP + "/paginas.json"))
# id de documento: grafia permitida no db (letras, dígitos, _ - . ~ : @ +)
import re
for r in rows:
    r["id"] = re.sub(r"[^A-Za-z0-9_.~:@+-]", "-", (r["rel"].strip("/") or "raiz").replace("/", "__"))
dados = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

TPL = r'''<title>Conferência da remigração</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --ground:#fbfafc; --surface:#f7f7f7; --surface2:#ebebeb; --line:#ddd6e1;
  --ink:#1e1826; --muted:#6c6473; --accent:#7f1080; --accent-ink:#ffffff;
  --ok:#1f7a3f; --ok-bg:#e3f3e8; --warn:#9a5206; --warn-bg:#fbeedb; --bad:#b3261e; --bad-bg:#fbe4e2;
  --sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --ground:#15111a; --surface:#1e1925; --surface2:#2a2433; --line:#3a3344;
  --ink:#ece7f0; --muted:#a59db0; --accent:#c77fca; --accent-ink:#1a0f1c;
  --ok:#5fc784; --ok-bg:#1c3324; --warn:#e6a24a; --warn-bg:#3a2a12; --bad:#ef7a73; --bad-bg:#3d1c1a;
}}
:root[data-theme="dark"]{
  --ground:#15111a; --surface:#1e1925; --surface2:#2a2433; --line:#3a3344;
  --ink:#ece7f0; --muted:#a59db0; --accent:#c77fca; --accent-ink:#1a0f1c;
  --ok:#5fc784; --ok-bg:#1c3324; --warn:#e6a24a; --warn-bg:#3a2a12; --bad:#ef7a73; --bad-bg:#3d1c1a;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font:14px/1.45 var(--sans);padding-inline:16px;padding-block:0 48px}
a{color:var(--accent)}
h1{font-size:20px;font-weight:600;margin:0;letter-spacing:-.01em;text-wrap:balance}
.topo{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--ground);padding-block:14px 10px;border-bottom:1px solid var(--line);margin-inline:-16px;padding-inline:16px}
.linha1{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 18px}
.sub{color:var(--muted);font-size:13px}
.resumo{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:8px;font-variant-numeric:tabular-nums;font-size:13px}
.resumo b{font-weight:600}
.resumo .sep{color:var(--line)}
.filtros{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.filtros input,.filtros select{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:6px 9px;min-height:34px}
.filtros input{flex:1 1 220px;min-width:0}
.filtros select{flex:0 1 auto}
.filtros button{font:inherit;font-size:13px;color:var(--muted);background:none;border:1px solid transparent;border-radius:6px;padding:6px 8px;cursor:pointer}
.filtros button:hover{color:var(--ink);border-color:var(--line)}
.filtros button.acao{color:var(--accent);border-color:var(--accent);margin-left:auto}
.filtros button.acao:hover{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.filtros button.acao.dois{margin-left:0}
.filtros button.acao.armado{background:var(--warn-bg);color:var(--warn);border-color:var(--warn)}
.aviso{font-size:12.5px;color:var(--muted);margin-top:8px}
.aviso.on{color:var(--warn)}
.tabela{margin-top:4px}
.cab,.row{display:grid;grid-template-columns:minmax(260px,1.6fr) 90px 58px 52px 150px 44px 200px 118px minmax(180px,1fr);gap:0 12px;align-items:center;padding:9px 6px;border-bottom:1px solid var(--line)}
.cab{position:sticky;top:0;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);background:var(--ground);border-bottom:1px solid var(--line);z-index:1}
.row:hover{background:var(--surface)}
.row.s-ok{box-shadow:inset 3px 0 0 var(--ok)}
.row.s-corrigir{box-shadow:inset 3px 0 0 var(--bad)}
.row.s-duvida{box-shadow:inset 3px 0 0 var(--warn)}
.path{font:13px/1.3 var(--mono);word-break:break-all}
.tit{font-size:12px;color:var(--muted);margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.num{font-variant-numeric:tabular-nums;text-align:right;padding-right:10px}
.chip{display:inline-block;font-size:11.5px;line-height:1;padding:5px 7px;border-radius:4px;background:var(--surface2);color:var(--ink);white-space:nowrap}
.chip.spec-ok{background:var(--ok-bg);color:var(--ok)}
.chip.spec-corte{background:var(--warn-bg);color:var(--warn)}
.chip.spec-na{background:transparent;color:var(--muted);border:1px solid var(--line)}
.faixa{display:inline-block;width:14px;height:14px;border-radius:3px;border:1px solid var(--line);background:#fff;vertical-align:middle}
.faixa.on{background:#f7f7f7;border-color:#b9b2be;box-shadow:inset 0 0 0 3px #ebebeb}
.vista{color:var(--ok);font-weight:600;text-align:center}
.vista.nao{color:var(--muted);font-weight:400}
.links{display:flex;flex-wrap:wrap;gap:4px 6px;font-size:12px}
.links span{color:var(--muted);margin-right:2px}
.links a{text-decoration:none;border:1px solid var(--line);border-radius:4px;padding:3px 6px;color:var(--accent);white-space:nowrap}
.links a:hover{border-color:var(--accent)}
.row select,.row input{font:inherit;font-size:13px;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:5px 7px;width:100%;min-height:32px}
.row input::placeholder{color:var(--muted)}
:is(a,button,input,select):focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.vazio{padding:32px 6px;color:var(--muted)}
.rotulo{display:none}
@media (max-width:900px){
  .cab{display:none}
  .row{grid-template-columns:1fr 1fr;gap:8px 12px;padding:12px 6px}
  .row>*{min-width:0}
  .c-path{grid-column:1/-1}
  .c-links{grid-column:1/-1}
  .c-status,.c-nota{grid-column:1/-1}
  .rotulo{display:inline;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-right:6px}
  .num{text-align:left;padding-right:0}
  .vista{text-align:left}
}
@media (prefers-reduced-motion: no-preference){ .row{transition:background .12s} }
</style>

<header class="topo">
  <div class="linha1">
    <h1>Conferência da remigração</h1>
    <span class="sub">semiconductors-remigration × macnicagwi · author · 1400px · <code>?wcmmode=disabled</code></span>
  </div>
  <div class="resumo" id="resumo"></div>
  <div class="filtros">
    <input id="q" type="search" placeholder="filtrar por caminho ou título" aria-label="filtrar por caminho ou título">
    <select id="f-arq" aria-label="arquétipo">
      <option value="">todos os arquétipos</option>
      <option value="E">E · folha de produto</option>
      <option value="B">B · editorial longo</option>
      <option value="C">C · landing de fabricante</option>
      <option value="D">D · landing de linha</option>
      <option value="G">G · teste/fantasma</option>
    </select>
    <select id="f-spec" aria-label="spec">
      <option value="">spec: todas</option>
      <option value="pintável já">spec com nó próprio</option>
      <option value="corte">spec divide o nó (precisa corte)</option>
      <option value="sem spec">sem spec</option>
    </select>
    <select id="f-st" aria-label="status">
      <option value="">status: todos</option>
      <option value="nenhum">não vista</option>
      <option value="ok">ok</option>
      <option value="corrigir">corrigir</option>
      <option value="duvida">dúvida</option>
    </select>
    <button type="button" id="limpar">limpar filtros</button>
    <button type="button" id="abrir-ed" class="acao">abrir páginas</button>
    <button type="button" id="abrir-fundo" class="acao dois">abrir as com fundo novo</button>
  </div>
  <div class="aviso" id="aviso">conectando ao registro compartilhado…</div>
</header>

<main class="tabela" id="tabela">
  <div class="cab">
    <div>página</div><div>arquétipo</div><div class="num">seções</div><div>faixa</div>
    <div>spec</div><div>vista</div><div>links</div><div>status</div><div>nota</div>
  </div>
  <div id="linhas"></div>
</main>

<script type="application/json" id="dados">__DADOS__</script>
<script>
(function(){
  'use strict';
  var HOST = "__HOST__";
  var dados = JSON.parse(document.getElementById('dados').textContent);
  var estado = {};            // id -> {status, nota, quando}
  var db = null, dbOk = false;
  var linhasEl = document.getElementById('linhas');
  var resumoEl = document.getElementById('resumo');
  var avisoEl  = document.getElementById('aviso');
  var q = document.getElementById('q'), fArq = document.getElementById('f-arq'),
      fSpec = document.getElementById('f-spec'), fSt = document.getElementById('f-st');
  var abrirBtn = document.getElementById('abrir-ed'), armadoAte = 0, visiveis = 0;

  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function specClasse(v){ return v === 'pintável já' ? 'spec-ok' : v === 'sem spec' ? 'spec-na' : 'spec-corte'; }
  function specRotulo(v){ return v === 'pintável já' ? 'nó próprio' : v; }
  function ver(p){ return HOST + p + '.html?wcmmode=disabled'; }
  function editor(p){ return HOST + '/editor.html' + p + '.html'; }

  // ---- render (uma vez; depois só atualiza status/nota por linha) ----
  var html = dados.map(function(r){
    return '<div class="row" data-id="' + esc(r.id) + '" data-arq="' + esc(r.arq) + '" data-spec="' + esc(r.spec) + '">' +
      '<div class="c-path"><div class="path">' + esc(r.rel) + '</div><div class="tit" title="' + esc(r.titulo) + '">' + esc(r.titulo) + '</div></div>' +
      '<div><span class="rotulo">arquétipo</span><span class="chip" title="' + esc(r.arqNome) + '">' + esc(r.arq || '—') + '</span></div>' +
      '<div class="num"><span class="rotulo">seções</span>' + r.secoes + '</div>' +
      '<div><span class="rotulo">faixa</span><span class="faixa' + (r.bandas ? ' on' : '') + '" title="' + (r.bandas ? r.bandas + ' seção(ões) com fundo' : 'sem fundo') + '"></span></div>' +
      '<div><span class="rotulo">spec</span><span class="chip ' + specClasse(r.spec) + '">' + esc(specRotulo(r.spec)) + '</span></div>' +
      '<div class="vista' + (r.conferida ? '' : ' nao') + '"><span class="rotulo">vista</span>' + (r.conferida ? '✓' : '·') + '</div>' +
      '<div class="links c-links">' +
        '<span>remig</span><a href="' + esc(ver(r.dest)) + '" target="_blank" rel="noopener">página</a><a href="' + esc(editor(r.dest)) + '" target="_blank" rel="noopener">editor</a>' +
        '<span>gwi</span><a href="' + esc(ver(r.orig)) + '" target="_blank" rel="noopener">página</a><a href="' + esc(editor(r.orig)) + '" target="_blank" rel="noopener">editor</a>' +
      '</div>' +
      '<div class="c-status"><label class="rotulo" for="st-' + esc(r.id) + '">status</label>' +
        '<select id="st-' + esc(r.id) + '" data-k="status"><option value="">não vista</option><option value="ok">ok</option><option value="corrigir">corrigir</option><option value="duvida">dúvida</option></select></div>' +
      '<div class="c-nota"><label class="rotulo" for="nt-' + esc(r.id) + '">nota</label>' +
        '<input id="nt-' + esc(r.id) + '" data-k="nota" type="text" placeholder="o que fazer" autocomplete="off"></div>' +
    '</div>';
  }).join('');
  linhasEl.innerHTML = html;

  var rows = {};
  Array.prototype.forEach.call(linhasEl.children, function(el){ rows[el.dataset.id] = el; });

  function aplicarEstado(id){
    var el = rows[id]; if (!el) return;
    var s = estado[id] || {};
    var sel = el.querySelector('select'), inp = el.querySelector('input');
    if (document.activeElement !== sel) sel.value = s.status || '';
    if (document.activeElement !== inp) inp.value = s.nota || '';
    el.className = 'row' + (s.status ? ' s-' + s.status : '');
  }

  function resumo(){
    var c = {ok:0, corrigir:0, duvida:0}, vistas = 0;
    dados.forEach(function(r){ var s = (estado[r.id]||{}).status; if (s) { c[s] = (c[s]||0)+1; vistas++; } });
    var spec = {}; dados.forEach(function(r){ spec[r.spec] = (spec[r.spec]||0)+1; });
    resumoEl.innerHTML =
      '<span><b>' + dados.length + '</b> páginas</span><span class="sep">·</span>' +
      '<span><b>' + vistas + '</b> com status</span>' +
      '<span style="color:var(--ok)"><b>' + c.ok + '</b> ok</span>' +
      '<span style="color:var(--bad)"><b>' + c.corrigir + '</b> corrigir</span>' +
      '<span style="color:var(--warn)"><b>' + c.duvida + '</b> dúvida</span><span class="sep">·</span>' +
      '<span>spec: <b>' + (spec['pintável já']||0) + '</b> nó próprio, <b>' +
        ((spec['divide com herói+CTA']||0)+(spec['divide com CTA']||0)+(spec['divide com herói']||0)) + '</b> precisa corte, <b>' + (spec['sem spec']||0) + '</b> sem spec</span>';
  }

  function filtrar(){
    var t = q.value.trim().toLowerCase(), a = fArq.value, sp = fSpec.value, st = fSt.value, n = 0;
    dados.forEach(function(r){
      var el = rows[r.id], s = (estado[r.id]||{}).status || '';
      var ok = (!t || r.rel.toLowerCase().indexOf(t) >= 0 || (r.titulo||'').toLowerCase().indexOf(t) >= 0)
        && (!a || r.arq === a)
        && (!sp || (sp === 'corte' ? r.spec.indexOf('divide') === 0 : r.spec === sp))
        && (!st || (st === 'nenhum' ? !s : s === st));
      el.hidden = !ok; if (ok) n++;
    });
    visiveis = n; armadoAte = 0; abrirBtn.className = 'acao';
    abrirBtn.textContent = 'abrir ' + n + ' páginas (remig)'; abrirBtn.disabled = !n;
    var v = document.getElementById('vazio');
    if (!n && !v) { v = document.createElement('div'); v.id = 'vazio'; v.className = 'vazio'; v.textContent = 'nenhuma página com esses filtros'; linhasEl.appendChild(v); }
    else if (n && v) v.remove();
    try { localStorage.setItem('conf-filtros', JSON.stringify({q:q.value, a:a, sp:sp, st:st})); } catch(e){}
  }
  [q, fArq, fSpec, fSt].forEach(function(el){ el.addEventListener('input', filtrar); el.addEventListener('change', filtrar); });
  document.getElementById('limpar').addEventListener('click', function(){ q.value=''; fArq.value=''; fSpec.value=''; fSt.value=''; filtrar(); });
  // Abre a PÁGINA da remigração (?wcmmode=disabled) de todas as linhas à mostra. Acima de 20 pede um
  // segundo clique (confirm() não funciona dentro do iframe do artifact).
  abrirBtn.addEventListener('click', function(){
    var vis = dados.filter(function(r){ return !rows[r.id].hidden; });
    if (!vis.length) return;
    if (vis.length > 20 && Date.now() > armadoAte) {
      armadoAte = Date.now() + 5000; abrirBtn.className = 'acao armado';
      abrirBtn.textContent = 'clique de novo para abrir ' + vis.length + ' abas';
      setTimeout(function(){ if (Date.now() >= armadoAte) { abrirBtn.className = 'acao'; abrirBtn.textContent = 'abrir ' + visiveis + ' páginas (remig)'; } }, 5100);
      return;
    }
    armadoAte = 0; abrirBtn.className = 'acao';
    var ok = 0;
    vis.forEach(function(r){ var w = window.open(ver(r.dest), '_blank'); if (w) { try { w.opener = null; } catch(e){} ok++; } });
    abrirBtn.textContent = 'abrir ' + visiveis + ' páginas (remig)';
    if (ok < vis.length) {
      avisoEl.textContent = 'o navegador abriu ' + ok + ' de ' + vis.length + ' abas — permita pop-ups para esta página e clique de novo, ou filtre um grupo menor';
      avisoEl.className = 'aviso on';
    }
  });
  try { var f = JSON.parse(localStorage.getItem('conf-filtros') || 'null'); if (f) { q.value=f.q||''; fArq.value=f.a||''; fSpec.value=f.sp||''; fSt.value=f.st||''; } } catch(e){}

  // ---- persistência: db compartilhado; sem db, localStorage (só neste navegador) ----
  // As páginas do lote 13 (fundo cinza no corpo, lista do Hazael) — abre todas,
  // com ou sem filtro na tela.
  var fundoBtn = document.getElementById('abrir-fundo');
  var comFundo = dados.filter(function(r){ return r.fundo; });
  var rotuloFundo = 'abrir as ' + comFundo.length + ' com fundo novo';
  fundoBtn.textContent = rotuloFundo; fundoBtn.disabled = !comFundo.length;
  fundoBtn.addEventListener('click', function(){
    if (comFundo.length > 20 && Date.now() > (fundoBtn._armado || 0)) {
      fundoBtn._armado = Date.now() + 5000; fundoBtn.classList.add('armado');
      fundoBtn.textContent = 'clique de novo para abrir ' + comFundo.length + ' abas';
      setTimeout(function(){ if (Date.now() >= fundoBtn._armado) { fundoBtn.classList.remove('armado'); fundoBtn.textContent = rotuloFundo; } }, 5100);
      return;
    }
    fundoBtn._armado = 0; fundoBtn.classList.remove('armado'); fundoBtn.textContent = rotuloFundo;
    var ok = 0;
    comFundo.forEach(function(r){ var w = window.open(ver(r.dest), '_blank'); if (w) { try { w.opener = null; } catch(e){} ok++; } });
    if (ok < comFundo.length) {
      avisoEl.textContent = 'o navegador abriu ' + ok + ' de ' + comFundo.length + ' abas — permita pop-ups para esta página e clique de novo';
      avisoEl.className = 'aviso on';
    }
  });
  var fila = {};   // id -> {emVoo:Promise, sujo:bool}
  var pend = {};   // id -> {status, nota}: edição local que o servidor ainda não devolveu igual
  function gravar(id){
    var s = estado[id];
    if (!dbOk) { try { localStorage.setItem('conf-est', JSON.stringify(estado)); } catch(e){} return; }
    var f = fila[id] || (fila[id] = {emVoo:null, sujo:false});
    if (f.emVoo) { f.sujo = true; return; }
    var corpo = {status: s.status || '', nota: s.nota || '', quando: new Date().toISOString()};
    f.emVoo = db.doc('verificacao/' + id).set(corpo).catch(function(e){
      avisoEl.textContent = 'não gravou (' + (e && e.code || 'erro') + '); tente de novo';
      avisoEl.className = 'aviso on';
    }).then(function(){ f.emVoo = null; if (f.sujo) { f.sujo = false; gravar(id); } });
  }
  function aoMudar(ev){
    var el = ev.target, row = el.closest('.row'); if (!row) return;
    var id = row.dataset.id, k = el.dataset.k; if (!k) return;
    var atual = estado[id] || {};
    if ((atual[k] || '') === el.value) return;
    // CÓPIA: o objeto que vem do snapshot é congelado — escrever nele falhava
    // calado, o valor ANTIGO ia para o banco e o select voltava atrás assim
    // que perdia o foco e chegava o snapshot seguinte.
    estado[id] = {status: atual.status || '', nota: atual.nota || ''};
    estado[id][k] = el.value;
    pend[id] = {status: estado[id].status, nota: estado[id].nota};
    row.className = 'row' + (estado[id].status ? ' s-' + estado[id].status : '');
    resumo();
    if (k === 'nota') { clearTimeout(el._t); el._t = setTimeout(function(){ gravar(id); }, 700); }
    else gravar(id);
  }
  linhasEl.addEventListener('change', aoMudar);
  linhasEl.addEventListener('input', function(ev){ if (ev.target.dataset.k === 'nota') aoMudar(ev); });

  // primeiro paint sem db
  try { var e0 = JSON.parse(localStorage.getItem('conf-est') || 'null'); if (e0) estado = e0; } catch(e){}
  dados.forEach(function(r){ aplicarEstado(r.id); });
  resumo(); filtrar();

  var uso = (window.claude && typeof window.claude.use === 'function') ? window.claude.use('db') : Promise.resolve(null);
  uso.then(function(ns){
    if (!ns) { avisoEl.textContent = 'sem registro compartilhado nesta visualização — status e notas ficam só neste navegador'; avisoEl.className = 'aviso on'; return; }
    db = ns;
    db.collection('verificacao').onSnapshot(function(snap){
      dbOk = true;
      snap.docs.forEach(function(d){
        if (!d.exists) return;
        var v = d.data() || {}, p = pend[d.id];
        if (p) {   // edição local manda até o servidor devolver o MESMO valor
          if ((v.status || '') === p.status && (v.nota || '') === p.nota) delete pend[d.id];
          else return;
        }
        estado[d.id] = {status: v.status || '', nota: v.nota || '', quando: v.quando};
      });
      dados.forEach(function(r){ aplicarEstado(r.id); });
      resumo(); filtrar();
      avisoEl.textContent = 'registro compartilhado ligado — status e notas ficam gravados por página' + (snap.metadata.hasPendingWrites ? ' (gravando…)' : '');
      avisoEl.className = 'aviso';
    }, function(e){
      dbOk = false;
      avisoEl.textContent = 'registro compartilhado indisponível (' + (e && e.code || 'erro') + ') — status e notas ficam só neste navegador';
      avisoEl.className = 'aviso on';
    });
  });
})();
</script>
'''
out = TPL.replace("__DADOS__", dados).replace("__HOST__", HOST)
open(SP + "/conferencia.html", "w").write(out)
print("bytes:", len(out), " linhas:", len(rows), " ids únicos:", len({r['id'] for r in rows}))
print("maior id:", max(len(r['id']) for r in rows), "bytes")
