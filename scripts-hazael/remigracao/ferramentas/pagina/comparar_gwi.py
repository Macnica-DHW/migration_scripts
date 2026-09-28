#!/usr/bin/env python3
"""
comparar_gwi.py <caminho>... [--etiqueta antes] [--etiqueta-gwi antes] [--saida DIR] [--nome NOME]
— conteúdo RENDERIZADO global2 x GWI da mesma página (regra: conteúdo = GWI). SOMENTE LEITURA (só GET no author).

Lê os dois renders do render.py (<nome>__g2__<etiqueta>.json e <nome>__gwi__<etiqueta-gwi>.json) e aponta:
  TEXTO        blocos visíveis na ordem (todas as abas abertas), diferença palavra a palavra com contexto;
  LINK-TEXTO   link pareado com texto diferente;
  LINK-FALTA / LINK-SOBRA   link que o GWI tem e o global2 não / o contrário (pareados por texto e ordem);
  LINK-ALVO    alvo interno conferido no author: página != 200 (como o visitante clica: link de TEXTO sem .html dá
               403), arquivo do DAM inexistente no global2 ou com dam:sha1 diferente do GWI, caminho ou âncora
               diferente do GWI, alvo externo diferente, alvo no GWI (macnicagwi);
  LINK-JANELA  target=_blank de um lado só;
  IMAGENS      contagem (imagens de largura > 1px; a do celular fica escondida a 1400);
  IMAGEM-LOGO  logo/featured que o GWI mostra por PROPRIEDADE DA PÁGINA (manufacturerlogo, productlinelogo,
               cq:featuredimage): o template do global2 não os renderiza — esperado, não é defeito;
  VÍDEOS       iframes (sem o reCAPTCHA), pela URL sem query;
  ABAS / ABA   rótulos das abas diferentes; por painel: nº de links/imagens diferente ou altura fora de 0,6–1,67x
               (painel vazio de um lado = conteúdo faltando, mesmo com o texto casado);
  REF-GWI      propriedade do jcr:content do global2 que aponta para o GWI (fileReference, linkURL, href no texto):
               só funciona enquanto o GWI existir.

O GWI se julga pelo que a página MOSTRA (o render), não pelo JCR — flags escondem conteúdo.
Diferenças esperadas, inofensivas: parágrafo espaçador vazio do GWI, o "opens in a new tab" escondido do global2.
Numa passada de layout as diferenças de conteúdo são RELATADAS, não corrigidas.

    cd scripts-hazael
    python3 remigracao/ferramentas/pagina/comparar_gwi.py /products/boards-modules/iei
    python3 remigracao/ferramentas/pagina/comparar_gwi.py /products/boards-modules/iei --etiqueta depois

Grava <pasta>/<nome>__comparacao__<etiqueta>.json. Só GET, e só no author (a trava da Session barra o resto).
"""
import argparse
import difflib
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import BASE, absoluto, arquivo, caminho_gwi, nome, pasta  # noqa: E402
import aem_lib as L  # noqa: E402

LOGOS = ("manufacturerlogo", "productlinelogo", "cq:featuredimage")
_s = _auth = None
_meta, _status = {}, {}


def sessao():
    global _s, _auth
    if _s is None:
        _s, _auth = L.build_session(prompt_if_missing=False, verbose=False)
    return _s, _auth


def meta(p):
    """(HTTP, dam:sha1) do arquivo do DAM."""
    p = urllib.parse.unquote(p.split("?")[0].split("#")[0])
    if p not in _meta:
        s, auth = sessao()
        d, st = L.get_json(s, f"{BASE}{p}/jcr:content/metadata.json", auth)
        _meta[p] = (st, d.get("dam:sha1") if isinstance(d, dict) else None)
    return _meta[p]


def pagina_ok(p):
    """HTTP da página como o visitante a abre (fora do editor, sem seguir redirect)."""
    p = p.split("#")[0]
    if p not in _status:
        s, _ = sessao()
        r = s.get(BASE + p + ("&" if "?" in p else "?") + "wcmmode=disabled", allow_redirects=False, timeout=30)
        _status[p] = r.status_code
    return _status[p]


def norm(t):
    t = re.sub(r"\s*opens in a new tab$", "", t)
    return re.sub(r"\s+", " ", t.replace("\xa0", " ")).strip()


def refs_gwi(no, caminho="", out=None):
    """(nó, propriedade, trecho) de todo valor do jcr:content que contém macnicagwi."""
    out = [] if out is None else out
    for k, v in no.items():
        if isinstance(v, dict):
            refs_gwi(v, f"{caminho}/{k}", out)
            continue
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, str) and "macnicagwi" in x:
                i = x.index("macnicagwi")
                out.append((caminho or "/", k, x[max(0, i - 40):i + 90]))
    return out


def comparar(caminho, etiqueta="antes", etiqueta_gwi="antes", saida=None, nome_=None):
    n = nome_ or nome(absoluto(caminho))
    g = json.loads(arquivo(n, "gwi", etiqueta_gwi, "json", saida).read_text(encoding="utf-8"))
    d = json.loads(arquivo(n, "g2", etiqueta, "json", saida).read_text(encoding="utf-8"))
    s, auth = sessao()
    achados = []
    # texto: só blocos visíveis (com as abas abertas pelo render.py, os painéis todos contam)
    a = [norm(x[1]) for x in g["out"] if x[2]]
    b = [norm(x[1]) for x in d["out"] if x[2]]
    a = [x for x in a if x]; b = [x for x in b if x]
    ja, jb = " ".join(a), " ".join(b)
    if ja != jb:
        wa, wb = ja.split(" "), jb.split(" ")
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wb, autojunk=False).get_opcodes():
            if op == "equal":
                continue
            ctx = " ".join(wa[max(0, i1 - 6):i1])
            achados.append(("TEXTO", op, f"…{ctx} [GWI: {' '.join(wa[i1:i2])[:160]!r}] -> [global2: {' '.join(wb[j1:j2])[:160]!r}]"))
    # links
    la = [(norm(x[0]), x[1], x[2]) for x in g["links"] if x[3]]
    lb = [(norm(x[0]), x[1], x[2]) for x in d["links"] if x[3]]
    sm = difflib.SequenceMatcher(None, [x[0] for x in la], [x[0] for x in lb], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal" or op == "replace" and i2 - i1 == j2 - j1:
            pares = list(zip(la[i1:i2], lb[j1:j2]))
            if op == "replace":
                for x, y in pares:
                    achados.append(("LINK-TEXTO", "", f"{x[0][:50]!r} -> {y[0][:50]!r}"))
        else:
            pares = []
            for x in la[i1:i2]:
                achados.append(("LINK-FALTA", "", f"{x[0][:60]!r} {x[1][:120]}"))
            for y in lb[j1:j2]:
                achados.append(("LINK-SOBRA", "", f"{y[0][:60]!r} {y[1][:120]}"))
        for x, y in pares:
            hg, hd = x[1] or "", y[1] or ""
            if "macnicagwi" in hd:
                achados.append(("LINK-ALVO", "", f"{y[0][:40]!r}: global2 aponta para o GWI {hd[:120]}"))
            if hd.startswith("/content/dam/"):
                st2, sha2 = meta(hd)
                st1, sha1 = meta(hg) if hg.startswith("/content/dam/") else (None, None)
                if st2 != 200:
                    achados.append(("LINK-ALVO", "", f"{y[0][:40]!r}: arquivo não existe no global2 ({st2}) {hd}"))
                elif sha1 and sha1 != sha2:
                    achados.append(("LINK-ALVO", "", f"{y[0][:40]!r}: arquivo DIFERENTE do GWI {hd} x {hg}"))
                elif not sha1:
                    achados.append(("LINK-ALVO", "", f"{y[0][:40]!r}: GWI aponta para {hg[:100]} (não é DAM) e global2 para {hd}"))
            elif hd.startswith("/content/"):
                st = pagina_ok(hd)
                if st != 200:
                    achados.append(("LINK-ALVO", "", f"{y[0][:40]!r}: página {st} {hd}"))
                gg = hg.replace("/content/macnicagwi/", "/content/macnicaglobal2/").split("#")[0].lower()
                if hg.startswith("/content/macnicagwi/") and gg.rstrip("/") != hd.split("#")[0].lower().rstrip("/"):
                    achados.append(("LINK-ALVO", "", f"{y[0][:40]!r}: GWI {hg} -> global2 {hd} (caminho diferente)"))
                if "#" in hg and hg.split("#", 1)[1] != (hd.split("#", 1)[1] if "#" in hd else None):
                    achados.append(("LINK-ALVO", "", f"{y[0][:40]!r}: âncora GWI #{hg.split('#', 1)[1]} -> global2 {hd}"))
            elif hd.startswith("#") or hg.startswith("#"):
                if hd != hg:
                    achados.append(("LINK-ALVO", "", f"{y[0][:40]!r}: âncora {hg} -> {hd}"))
            elif hd != hg:
                achados.append(("LINK-ALVO", "", f"{y[0][:40]!r}: {hg[:110]} -> {hd[:110]}"))
            if (x[2] == "_blank") != (y[2] == "_blank"):
                achados.append(("LINK-JANELA", "", f"{y[0][:40]!r}: GWI target={x[2] or '-'} global2 target={y[2] or '-'}"))
    # imagens: o logo de propriedade da página do GWI (o template do global2 não o desenha) sai da conta
    ia = [i for i in g["imgs"] if i[2] > 1]; ib = [i for i in d["imgs"] if i[2] > 1]
    cam_gwi = g.get("caminho") or caminho_gwi(caminho)             # o render guarda o caminho real (renomeada)
    jg, st = L.fetch_with_depth_fallback(s, BASE, cam_gwi + "/jcr:content", 1, auth)
    if st != 200:
        achados.append(("IMAGEM-LOGO", "", f"jcr:content do GWI ilegível (HTTP {st}): logo de página não descontado"))
    jg = jg or {}
    logos = {str(jg[k].get("fileReference", "")).rsplit("/", 1)[-1] for k in LOGOS if isinstance(jg.get(k), dict)}
    so_logo = [i for i in ia if i[0] in logos]
    if so_logo:
        achados.append(("IMAGEM-LOGO", "", f"GWI mostra {[i[0] for i in so_logo]} (propriedade da página: logo/featured); o template do global2 não renderiza"))
    ia2 = [i for i in ia if i[0] not in logos]
    if len(ia2) != len(ib):
        achados.append(("IMAGENS", "", f"GWI {len(ia2)} {[i[0][:30] for i in ia2]} x global2 {len(ib)} {[i[0][:30] for i in ib]}"))
    # vídeos
    va = [re.sub(r"[?&].*", "", v[0]) for v in g["iframes"] if v[0] and "recaptcha" not in v[0]]
    vb = [re.sub(r"[?&].*", "", v[0]) for v in d["iframes"] if v[0] and "recaptcha" not in v[0]]
    if va != vb:
        achados.append(("VÍDEOS", "", f"GWI {va} x global2 {vb}"))
    # abas: rótulos e, painel a painel, links/imagens/altura
    ra = [x["rotulo"] for x in g.get("abas", [])]; rb = [x["rotulo"] for x in d.get("abas", [])]
    if ra != rb:
        achados.append(("ABAS", "", f"GWI {ra} x global2 {rb}"))
    else:
        for xa, xb in zip(g.get("abas", []), d.get("abas", [])):
            k = xa["aba"]
            nla = sum(1 for x in g["links"] if x[3] and x[4] == k); nlb = sum(1 for x in d["links"] if x[3] and x[4] == k)
            nia = sum(1 for i in ia2 if i[4] == k); nib = sum(1 for i in ib if i[4] == k)
            ha, hb = xa.get("h") or 0, xb.get("h") or 0
            if nla != nlb or nia != nib or (ha and not 0.6 <= hb / ha <= 1.67):
                achados.append(("ABA", "", f"{k} {xa['rotulo']!r}: GWI {nla} links, {nia} imagens, {ha}px x "
                                           f"global2 {nlb} links, {nib} imagens, {hb}px"))
    # referências ao GWI no JCR do global2 (o render não mostra o fileReference da imagem)
    j2, st2 = L.fetch_with_depth_fallback(s, BASE, d.get("caminho", absoluto(caminho)) + "/jcr:content", "infinity", auth)
    if st2 != 200:
        achados.append(("REF-GWI", "", f"jcr:content do global2 ilegível (HTTP {st2}): referências ao GWI não conferidas"))
    for no, prop, trecho in refs_gwi(j2 or {}):
        achados.append(("REF-GWI", "", f"{no} {prop}: …{trecho}…"))
    return achados, dict(blocos=len(a), links=len(la), imagens=len(ia), videos=len(va), abas=len(ra))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("caminhos", nargs="+")
    ap.add_argument("--etiqueta", default="antes", help="render do global2 (padrão: antes)")
    ap.add_argument("--etiqueta-gwi", default="antes", help="render do GWI (padrão: antes)")
    ap.add_argument("--saida", help="pasta dos renders (padrão: remigracao/dados/paginas/<nome>/)")
    ap.add_argument("--nome", help="nome dos arquivos, se o render usou --nome (página renomeada)")
    a = ap.parse_args()
    if a.nome and len(a.caminhos) > 1:
        ap.error("--nome vale para um caminho só")
    for c in a.caminhos:
        n = a.nome or nome(absoluto(c))
        try:
            ach, cont = comparar(c, a.etiqueta, a.etiqueta_gwi, a.saida, a.nome)
        except FileNotFoundError as e:
            print(f"### {c}: sem render ({Path(e.filename).name}) — rodar render.py antes"); continue
        print(f"### {c}  ({cont['blocos']} blocos, {cont['links']} links, {cont['imagens']} imagens, {cont['videos']} vídeos, "
              f"{cont['abas']} painéis de aba no GWI) — {len(ach) or 'sem'} diferença(s)")
        for k, op, t in ach:
            print(f"   {k:11} {t}")
        out = pasta(n, a.saida) / f"{n}__comparacao__{a.etiqueta}.json"
        out.write_text(json.dumps({"caminho": absoluto(c), "etiqueta_g2": a.etiqueta, "etiqueta_gwi": a.etiqueta_gwi,
                                   "contagens_gwi": cont, "achados": ach}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
