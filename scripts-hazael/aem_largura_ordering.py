#!/usr/bin/env python3
"""
Ajusta a largura da 1ª coluna das tabelas de Ordering Information.

O PROBLEMA
A tabela nasce sem largura nenhuma na primeira coluna. Como a segunda
coluna tem descrições longas, o browser dá quase todo o espaço a ela e
espreme a primeira — o resultado é o part number quebrando NO MEIO,
inclusive no hífen: "TQMa8MSN / L-AA", às vezes em três linhas.

Largura fixa única não resolve: 100px serve para uns e corta outros,
porque os part numbers têm comprimentos diferentes por página.

A REGRA (definida com o time em 17/09/2026)
A largura tem que caber o maior TOKEN (pedaço separado por ESPAÇO) da
coluna — não a maior célula:

  "TQMa8MSNL-AA"             -> 1 token. O hífen faz parte do nome,
                                então precisa caber inteiro numa linha.
  "Starterkit STKa8MxNL set" -> 3 tokens. Pode (e deve) quebrar nos
                                espaços; o maior token é "STKa8MxNL".

Assim a coluna fica justa: cabe o part number mais longo sem quebrar, e
nome com várias palavras não infla a coluna só para caber numa linha.

COMO A LARGURA É CALCULADA
Por largura de caractere da fonte (tabela Helvetica-Bold, em milésimos
de em), não por contagem de caracteres — 'W' ocupa 3,4x o que ocupa 'I',
e part number é cheio de maiúscula. Some-se o padding da célula e
aplica-se um teto (--max-largura) para nenhum caso patológico estourar.

  largura = soma_das_larguras(maior_token) x --fonte + --padding

--fonte e --padding são estimativas do render. VALOR CALIBRADO EM
17/09/2026, conferido no navegador: --fonte 18 (com --padding 20). A
estimativa inicial de 15 deixava o part number quebrando; 17.4 ainda
ficou apertado; 18 ficou bom. É o default agora — mudar só se o tema
do site mudar de tamanho de fonte.

ONDE ESCREVE
Só no atributo style das <td> da primeira coluna, dentro do campo 'text'
do componente table que vem logo depois do título 'Ordering Information'.
Não toca no conteúdo das células, na segunda coluna, nem em outras
tabelas (Specifications fica de fora).

IDEMPOTENTE: recalcula e só grava se a largura mudar.

COMO RODAR
  python3 aem_largura_ordering.py --raiz /content/macnicaglobal2/.../tq-systems
  python3 aem_largura_ordering.py --raiz ... --executar \
      --permitir-escrita-global2 /content/macnicaglobal2/.../tq-systems
"""

import argparse
import html as _html
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from urllib.parse import urljoin
from aem_lib import (CONFIG, build_session, crawl_tree, fetch_with_depth_fallback,
                     list_child_nodes, post_node, print_header, session_expired,
                     write_csv)

TAG_RE = re.compile(r"<[^>]+>")
ROW_RE = re.compile(r"<tr[^>]*>.*?</tr>", re.S | re.I)
TD_RE = re.compile(r"<td([^>]*)>(.*?)</td>", re.S | re.I)
STYLE_RE = re.compile(r'\sstyle\s*=\s*"([^"]*)"', re.I)
WIDTH_DECL_RE = re.compile(r"\s*width\s*:\s*[^;]+;?", re.I)

# Larguras de avanço da Helvetica-Bold, em milésimos de em.
# Part number é quase todo maiúscula e dígito, onde a diferença entre
# 'I' (278) e 'W' (944) é grande demais para uma média simples servir.
W = {
    "A":722,"B":722,"C":722,"D":722,"E":667,"F":611,"G":778,"H":722,"I":278,
    "J":556,"K":722,"L":611,"M":833,"N":722,"O":778,"P":667,"Q":778,"R":722,
    "S":667,"T":611,"U":722,"V":667,"W":944,"X":667,"Y":667,"Z":611,
    "a":556,"b":611,"c":556,"d":611,"e":556,"f":333,"g":611,"h":611,"i":278,
    "j":278,"k":556,"l":278,"m":889,"n":611,"o":611,"p":611,"q":611,"r":389,
    "s":556,"t":333,"u":611,"v":556,"w":778,"x":556,"y":556,"z":500,
    "-":333,".":278,",":278,"/":278,"(":333,")":333,"+":584,"®":737,"°":400,
    ":":333,";":333,"_":556," ":278,
    "\u2013":556, "\u2014":1000, "\u2019":278, "\u00ae":737,
}
W_DIGITO = 556
W_PADRAO = 600

# Resíduo de marcação que virou TEXTO na célula. Caso real achado em
# tqma335x-embedded-module: a célula contém "TQMa3359-AA/strong&gt;",
# ou seja um </strong> quebrado que foi escapado e hoje aparece
# literalmente para o visitante. É bug de CONTEÚDO da página (relatado
# à parte), mas não pode ditar a largura da coluna — sem limpar, esse
# lixo pedia 182px em vez dos ~131px que o part number real precisa.
RESIDUO_RE = re.compile(r"/?[A-Za-z][A-Za-z0-9]*>")


def largura_em(txt):
    """Largura do texto em 'em' (1 em = tamanho da fonte)."""
    total = 0
    for ch in txt:
        if ch.isdigit():
            total += W_DIGITO
        else:
            total += W.get(ch, W_PADRAO)
    return total / 1000.0


def texto_puro(html_frag):
    txt = _html.unescape(TAG_RE.sub(" ", html_frag))
    limpo = RESIDUO_RE.sub("", txt)
    return re.sub(r"\s+", " ", limpo).strip(), txt != limpo


def tem_residuo(celulas):
    return any(texto_puro(c)[1] for c in celulas)


def maior_token(celulas):
    """Maior token separado por ESPAÇO — hífen NÃO separa."""
    melhor, larg = "", 0.0
    for c in celulas:
        for tok in texto_puro(c)[0].split():
            l = largura_em(tok)
            if l > larg:
                melhor, larg = tok, l
    return melhor, larg


def primeira_coluna(html_tab):
    """Fragmentos internos das <td> da primeira coluna de cada linha."""
    out = []
    for linha in ROW_RE.findall(html_tab):
        tds = TD_RE.findall(linha)
        if tds:
            out.append(tds[0][1])
    return out


def aplicar_largura(html_tab, px):
    """Escreve style="width:Npx" nas <td> da primeira coluna."""
    def trata_linha(m):
        linha = m.group(0)
        tds = list(TD_RE.finditer(linha))
        if not tds:
            return linha
        td = tds[0]
        attrs = td.group(1)
        st = STYLE_RE.search(attrs)
        if st:
            corpo = WIDTH_DECL_RE.sub("", st.group(1)).strip()
            corpo = (corpo + ";" if corpo and not corpo.endswith(";") else corpo)
            novo_style = f'{corpo}width:{px}px;'
            attrs_novos = STYLE_RE.sub(f' style="{novo_style}"', attrs, count=1)
        else:
            attrs_novos = f'{attrs} style="width:{px}px;"'
        novo_td = f"<td{attrs_novos}>{td.group(2)}</td>"
        return linha[:td.start()] + novo_td + linha[td.end():]

    return ROW_RE.sub(trata_linha, html_tab)


def largura_atual(html_tab):
    for linha in ROW_RE.findall(html_tab):
        tds = TD_RE.findall(linha)
        if tds:
            st = STYLE_RE.search(tds[0][0])
            if st:
                m = re.search(r"width\s*:\s*(\d+)\s*px", st.group(1), re.I)
                if m:
                    return int(m.group(1))
    return None


def achar_tabelas_ordering(jcr):
    """[(caminho_rel, html)] das tabelas logo após o título Ordering."""
    achados = []
    cont = ((jcr.get("root") or {}).get("container") or {})
    for nome, wrap in list_child_nodes(cont):
        filhos = list(list_child_nodes(wrap))
        for i, (n2, comp) in enumerate(filhos):
            titulo = texto_puro(str(comp.get("jcr:title") or ""))[0].lower()
            if not titulo.startswith("ordering"):
                continue
            for n3, seg in filhos[i + 1:]:
                if (seg.get("sling:resourceType") or "").endswith("/table"):
                    achados.append((f"jcr:content/root/container/{nome}/{n3}",
                                    seg.get("text") or ""))
                    break
                if str(seg.get("jcr:title") or "").strip():
                    break
    return achados


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", required=True)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    ap.add_argument("--fonte", type=float, default=18.0,
                    help="Tamanho da fonte em px usado na estimativa. Padrão 18, "
                         "calibrado no navegador em 17/09/2026.")
    ap.add_argument("--padding", type=int, default=20,
                    help="Folga somada à largura do texto, em px (padrão 20).")
    ap.add_argument("--min-largura", type=int, default=60)
    ap.add_argument("--max-largura", type=int, default=260,
                    help="Teto de segurança: nenhuma coluna passa disto.")
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    raiz = args.raiz.rstrip("/")
    allow = ()
    if args.permitir_escrita_global2:
        lib = args.permitir_escrita_global2.rstrip("/")
        if lib != raiz:
            print("[erro] --permitir-escrita-global2 precisa ser igual a --raiz.",
                  file=sys.stderr)
            sys.exit(1)
        allow = (lib,)

    saida = args.output or f"ordering_largura_{raiz.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("LARGURA DA 1ª COLUNA — ORDERING INFORMATION")
    print(f"  raiz    : {raiz}")
    print(f"  fonte   : {args.fonte}px   padding: {args.padding}px   "
          f"teto: {args.max_largura}px")
    print(f"  modo    : {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv = crawl_tree(s, base, raiz, at, quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")

    linhas, tarefas = [], []
    for p in paginas:
        dd, _ = fetch_with_depth_fallback(s, base, p, 8, at)
        if dd is None:
            continue
        jcr = (dd or {}).get("jcr:content", {}) or {}
        if jcr.get("deleted"):
            continue
        for rel, html_tab in achar_tabelas_ordering(jcr):
            celulas = primeira_coluna(html_tab)
            if not celulas:
                continue
            tok, em = maior_token(celulas)
            residuo = tem_residuo(celulas)
            px = int(math.ceil(em * args.fonte)) + args.padding
            px = max(args.min_largura, min(args.max_largura, px))
            atual = largura_atual(html_tab)
            if atual == px:
                continue
            novo = aplicar_largura(html_tab, px)
            tarefas.append((p, rel, novo))
            linhas.append({"pagina": p, "tabela": rel.rsplit("/", 1)[-1],
                           "linhas_tabela": len(celulas), "maior_token": tok,
                           "largura_atual": atual if atual else "(nenhuma)",
                           "largura_nova": px,
                           "conteudo_corrompido": "SIM" if residuo else "",
                           "acao": "pendente"})

    print(f"  tabelas de Ordering a ajustar: {len(tarefas)}\n")
    print(f"  {'página':<44}{'maior token':<26}{'de':>10}{'para':>8}")
    print("  " + "-" * 88)
    for l in linhas[:40]:
        print(f"  {l['pagina'].rsplit('/', 1)[-1][:42]:<44}{l['maior_token'][:24]:<26}"
              f"{str(l['largura_atual']):>10}{l['largura_nova']:>8}")
    if len(linhas) > 40:
        print(f"  ... e mais {len(linhas) - 40}")

    if not args.executar:
        corrompidas = [l for l in linhas if l["conteudo_corrompido"]]
        if corrompidas:
            print(f"\n  [aviso] {len(corrompidas)} tabela(s) com resíduo de marcação "
                  f"no TEXTO da célula (bug de conteúdo, corrigir à parte):")
            for l in corrompidas:
                print(f"     {l['pagina'].rsplit('/', 1)[-1]}")
        write_csv(saida, ["pagina", "tabela", "linhas_tabela", "maior_token",
                          "largura_atual", "largura_nova", "conteudo_corrompido",
                          "acao"], linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    ok = falhas = 0
    for i, (p, rel, novo) in enumerate(tarefas, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(tarefas)}", file=sys.stderr)
            break
        st, corpo = post_node(s, base, f"{p}/{rel}",
                              {"text": novo, "textIsRich": "true"},
                              at, allow_extra=allow)
        if st in (200, 201):
            ok += 1; linhas[i - 1]["acao"] = "ajustado"
        else:
            falhas += 1; linhas[i - 1]["acao"] = f"FALHA {st}"
            print(f"  [FALHA {st}] {p} :: {corpo[:80]}")
        if i % 25 == 0:
            print(f"  [{i}/{len(tarefas)}] ok={ok} falhas={falhas}", flush=True)

    write_csv(saida, ["pagina", "tabela", "linhas_tabela", "maior_token",
                      "largura_atual", "largura_nova", "conteudo_corrompido",
                      "acao"], linhas)
    print(f"\n  ajustadas: {ok}   falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
