() => {
  const out = [];
  // destino (global2) E origem (GWI): os dois lados usam core components, com nomes próprios para o par imagem+texto
  const sel = '.cmp-title, .cmp-text, .cmp-image, .link-button, .cmp-embed, .cmp-tabs, .cmp-table, '
            + '.cmp-textwithimage, .cmp-image-text, .cmp-list, .cmp-carousel, .cmp-download, .cmp-form, '
            + '.cmp-heading, .anchor-link__list, .cmp-pagesectionlisting, hr';
  // nenhum dos dois sites tem <main>: o corpo é o body menos cabeçalho, rodapé e o botão "voltar ao topo"
  const FORA = 'header, footer, .cmp-experiencefragment--header, .cmp-experiencefragment--footer, .page-top';
  const main = document.querySelector('main') || document.body;
  main.querySelectorAll(sel).forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.height === 0 && el.tagName !== 'HR') return;
    if (el.closest(FORA)) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    let t = (el.innerText || '').trim().slice(0, 38).split('\n').join(' ');
    if (!t && el.tagName !== 'HR' && el.querySelector('hr')) t = '<hr>';
    // profundidade = quantos ancestrais também estão na lista (aba > text, textwithimage > text, text > hr)
    let depth = 0;
    for (let a = el.parentElement; a && a !== main; a = a.parentElement) if (a.matches(sel)) depth++;
    // o que o print mostra e a classe não diz: tamanho da imagem, nº de itens
    let extra = '';
    const tag = el.tagName === 'HR' ? 'hr' : (typeof el.className === 'string' ? el.className : '');
    if (el.matches('.cmp-textwithimage, .cmp-image-text, .cmp-image, .cmp-carousel')) {
      const i = el.querySelector('img');
      if (i) { const ri = i.getBoundingClientRect(); extra = `img=${Math.round(ri.width)}x${Math.round(ri.height)}@x${Math.round(ri.x)}`; }
    }
    if (el.matches('.cmp-list, .anchor-link__list, .cmp-pagesectionlisting')) extra = `itens=${el.querySelectorAll('li, .anchor-link__list__item').length}`;
    if (el.matches('.cmp-carousel')) extra += ` slides=${el.querySelectorAll('.cmp-carousel__item').length}`;
    if (el.matches('.cmp-tabs')) extra = `abas=${el.querySelectorAll('[role=tab]').length}`;
    // nearest ancestor that is a grid column, to know the column geometry
    let col = el.closest('.aem-GridColumn');
    const cr = col ? col.getBoundingClientRect() : r;
    out.push({
      cls: tag.slice(0, 40), depth, extra,
      x: Math.round(r.x), y: Math.round(r.y + window.scrollY),
      w: Math.round(r.width), h: Math.round(r.height),
      colx: Math.round(cr.x), colw: Math.round(cr.width),
      colcls: col ? (typeof col.className === 'string' ? col.className : '').slice(0, 70) : '',
      mt: cs.marginTop, mb: cs.marginBottom, pt: cs.paddingTop, pb: cs.paddingBottom,
      txt: t
    });
  });
  out.sort((a, b) => a.y - b.y || a.depth - b.depth || a.x - b.x);
  // estouro horizontal do CORPO (cabeçalho e rodapé do site passam 12px da janela em TODA página: não é nosso)
  const W = document.documentElement.clientWidth, estouro = [];
  main.querySelectorAll('*').forEach(el => {
    if (el.closest(FORA) || el.closest('.grecaptcha-badge')) return;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && r.right > W + 1) {
      // dentro de um wrapper que rola (tabela com scroll-hint) não é estouro da página
      for (let a = el.parentElement; a && a !== main; a = a.parentElement) {
        const o = getComputedStyle(a).overflowX;
        if (o === 'auto' || o === 'scroll' || o === 'hidden') return;
      }
      estouro.push(`${el.tagName.toLowerCase()}.${(typeof el.className === 'string' ? el.className : '').slice(0, 40)} direita=${Math.round(r.right)} y=${Math.round(r.y + scrollY)}`);
    }
  });
  return {rows: out, estouro: estouro.slice(0, 8)};
}
