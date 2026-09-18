() => {
  const out = [];
  const sel = '.cmp-title, .cmp-text, .cmp-image, .link-button, .cmp-embed, .cmp-tabs, .cmp-table';
  document.querySelectorAll(sel).forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.height === 0) return;
    const cs = getComputedStyle(el);
    const t = (el.innerText || '').trim().slice(0, 38).split('\n').join(' ');
    // nearest ancestor that is a grid column, to know the column geometry
    let col = el.closest('.aem-GridColumn');
    const cr = col ? col.getBoundingClientRect() : r;
    out.push({
      cls: (typeof el.className === 'string' ? el.className : '').slice(0, 40),
      x: Math.round(r.x), y: Math.round(r.y + window.scrollY),
      w: Math.round(r.width), h: Math.round(r.height),
      colx: Math.round(cr.x), colw: Math.round(cr.width),
      colcls: col ? (typeof col.className === 'string' ? col.className : '').slice(0, 70) : '',
      mt: cs.marginTop, mb: cs.marginBottom, pt: cs.paddingTop, pb: cs.paddingBottom,
      txt: t
    });
  });
  out.sort((a, b) => a.y - b.y || a.x - b.x);
  return out;
}
