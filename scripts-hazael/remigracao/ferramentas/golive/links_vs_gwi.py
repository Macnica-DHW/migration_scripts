#!/usr/bin/env python3
"""
links_vs_gwi.py — SOMENTE LEITURA. Todo link das páginas do macnicaglobal2 comparado com o link correspondente da
mesma página no GWI. Sai um relatório HTML em inglês, para mandar: as páginas com link que não bate, o texto do
link, para onde aponta hoje no global2, para onde deveria apontar e o link original do GWI.

Pedido do Hazael (24/09/2026), com o exemplo da notícia connect-tech: "deliver integrated AI and high-performance
computing platforms" aponta para `/blog` no global2 e para `/blog/Removing-the-Barriers-to-Edge-and-Gen-AI-in-
Embedded-Vision.html` no GWI — o link foi cortado no pai.

Só GET, só no author: querybuilder dos dois sites (lista de páginas e redirects), `jcr:content.infinity.json` de
cada par e de cada XF embutido. Nenhum link é aberto: "existe" = está na lista de páginas do querybuilder.

Link = <a href> em qualquer propriedade HTML (text, table…); propriedade *link/*url/*href de componente (linkURL do
button, da imagem…) com o rótulo do próprio nó (jcr:title, alt…); e o cq:redirectTarget da página. Fora: listas
geradas da árvore (pages/parentPage), fileReference/src de imagem, fragmentPath, action/redirect de form, canonical.

Casamento, página a página (links dos XFs embutidos entram nos dois lados, marcados com o XF):
  1. mesmo texto e mesmo alvo                  -> OK
  2. mesmo texto, alvo diferente               -> DIVERGE (o relatório)
  3. mesmo alvo, texto diferente               -> OK (texto editado)
  4. texto parecido (≥0,85), alvo diferente    -> DIVERGE, marcado "text differs"
  sobra do GWI = link que não veio; sobra do global2 = link novo (contados; listados à parte).
Mesmo alvo: página -> o par no global2 da página do GWI (nome normalizado + ALIAS), seguindo cq:redirectTarget dos
dois lados; DAM -> mesmo nome de arquivo ou mapa_assets.csv; externo -> mesma URL (http=https, www e barra final
ignorados); âncora comparada à parte (#tabs-… ignorada: o id da aba muda no global2).

ESCOPO = as páginas do mapa de links final (dados/mapas/global2_link_map_complete_*.html, o mais novo), não a árvore
inteira — "you only need to check the links in our final link map" (Hazael, 24/09). A listagem das duas árvores
(querybuilder, ~15 GETs) serve só para achar o par de cada ALVO de link; só as páginas do mapa são lidas.

    python3 links_vs_gwi.py                    # coleta ao vivo (cache em dados/links) + relatório
    python3 links_vs_gwi.py --do-cache         # refaz o relatório do cache, sem rede
    python3 links_vs_gwi.py --mapa dados/mapas/global2_link_map_complete_2026-09-23.html
"""
import argparse
import collections
import csv
import datetime
import difflib
import html
import json
import pickle
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, unquote

_RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, build_session, normalize_name  # noqa: E402

REMIG = Path(__file__).resolve().parents[2]
CACHE = REMIG / "dados" / "links" / "jcr_cache_links_vs_gwi.pkl"          # .gitignore: jcr_cache*.pkl
MAPAS = REMIG / "dados" / "mapas"
MAPA_ASSETS = REMIG / "dados" / "golive" / "mapa_assets.csv"

G2, GW = "/content/macnicaglobal2", "/content/macnicagwi"
# onde a árvore do global2 é outra: prefixo relativo no global2 -> no GWI (já normalizado)
ALIAS = [("americas/mai/en/solutions", "americas/mai/en/technology"),           # move do Hazael, 21/09
         ("eu/atd-europe", "europe/atd-europe"),
         ("americas/mai/en/products/semiconductors/sony/sony-image-sensors",   # a Anion aninhou a sony
          "americas/mai/en/products/semiconductors/sony-image-sensors")]

BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE     # cookie só vai para o author
_sessao = None


def get(path, sufixo="", **kw):
    """SÓ GET, só no author (o GWI nunca recebe outra coisa)."""
    global _sessao
    if _sessao is None:
        _sessao, _ = build_session(prompt_if_missing=False, verbose=False)
    return _sessao.get(BASE + quote(unquote(path), safe="/:") + sufixo, timeout=300, allow_redirects=False, **kw)


# ---------------------------------------------------------------- coleta (rede)
PROPS = ("jcr:path jcr:content/jcr:title jcr:content/pageTitle jcr:content/deleted jcr:content/cq:redirectTarget "
         "jcr:content/cq:lastModifiedBy")


def paginas(raiz):
    out, off = [], 0
    while True:
        r = get("/bin/querybuilder.json", params={
            "path": raiz, "type": "cq:Page", "p.limit": "1000", "p.offset": str(off),
            "p.hits": "selective", "p.properties": PROPS, "orderby": "path"})
        assert r.status_code == 200, (r.status_code, raiz)
        hits = r.json()["hits"]
        out += hits
        off += len(hits)
        print(f"  {raiz}: {off} páginas", file=sys.stderr)
        if len(hits) < 1000:
            return out


def fundo(path):
    """JSON completo de `path`, contornando o HTTP 300 (profundidade recusada) como o censo_links."""
    r = get(path, ".infinity.json")
    if r.status_code == 200:
        return r.json(), 200
    if r.status_code != 300:
        return None, r.status_code
    d = max(int(m.group(1)) for o in r.json() if (m := re.search(r"\.(\d+)\.json$", str(o))))
    r = get(path, f".{d}.json")
    if r.status_code != 200:
        return None, r.status_code
    j = r.json()

    def desce(no, p, nivel):
        for k, v in list(no.items()):
            if isinstance(v, dict):
                if nivel + 1 >= d:
                    sub, _ = fundo(f"{p}/{k}")
                    if sub is not None:
                        no[k] = sub
                else:
                    desce(v, f"{p}/{k}", nivel + 1)
    desce(j, path, 0)
    return j, 200


XF_PROPS = ("fragmentVariationPath", "fragmentPath")


def xfs_de(no, out):
    for k, v in no.items():
        if isinstance(v, dict):
            xfs_de(v, out)
        elif k in XF_PROPS and isinstance(v, str) and v.startswith("/content/experience-fragments/"):
            out.add(v.rstrip("/"))
    return out


def escopo_do_mapa(arq):
    """Caminhos (sem .html) dos links do author no HTML do mapa, na ordem do mapa."""
    s = Path(arq).read_text(encoding="utf-8")
    out = []
    for h in re.findall(r'href="(https://author-[^"]+)"', s):
        p = re.sub(r"\.html$", "", unquote(re.sub(r"^https://[^/]+", "", html.unescape(h)).split("?")[0]))
        if p not in out:
            out.append(p)
    return out


def coletar(escopo, mapa):
    print("listando páginas…", file=sys.stderr)
    g2 = paginas(G2)
    gw = paginas(GW)
    bruto = {"quando": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
             "mapa": Path(mapa).name, "escopo": escopo, "g2": g2, "gw": gw, "jcr": {}, "xf": {}}
    idx = Indice(bruto)
    pares = idx.pares(escopo)
    alvos = sorted({p for par in pares for p in par})
    print(f"{len(pares)} pares; lendo {len(alvos)} jcr:content…", file=sys.stderr)

    def um(p):
        return p, fundo(f"{p}/jcr:content")
    with ThreadPoolExecutor(4) as ex:
        for i, (p, (j, st)) in enumerate(ex.map(um, alvos), 1):
            bruto["jcr"][p] = j if j is not None else st
            if i % 100 == 0:
                print(f"  {i}/{len(alvos)}", file=sys.stderr)
    complementos(bruto)
    xfs = set()
    for j in bruto["jcr"].values():
        if isinstance(j, dict):
            xfs_de(j, xfs)
    print(f"lendo {len(xfs)} XFs…", file=sys.stderr)
    with ThreadPoolExecutor(4) as ex:
        for p, (j, st) in ex.map(um, sorted(xfs)):
            bruto["xf"][p] = j if j is not None else st
    CACHE.write_bytes(pickle.dumps(bruto))
    return bruto


DAM_G2 = "/content/dam/macnicaglobal2/americas/mai/en"


def complementos(bruto):
    """O que o cache precisa além das páginas (só GET): vanity do GWI, nomes do DAM do global2 (para dizer onde está
    o arquivo que o link do GWI abre) e o jcr:content de par que ainda não está no cache. Devolve True se mudou."""
    mudou = False
    if "vanity" not in bruto:
        r = get("/bin/querybuilder.json", params={"path": GW, "type": "cq:PageContent", "property": "sling:vanityPath",
                "property.operation": "exists", "p.limit": "-1", "p.hits": "selective",
                "p.properties": "jcr:path sling:vanityPath"})
        assert r.status_code == 200, r.status_code
        bruto["vanity"], mudou = r.json()["hits"], True
    if "dam_g2" not in bruto:
        out, off = [], 0
        while True:
            r = get("/bin/querybuilder.json", params={"path": DAM_G2, "type": "dam:Asset", "p.limit": "1000",
                    "p.offset": str(off), "p.hits": "selective", "p.properties": "jcr:path", "orderby": "path"})
            assert r.status_code == 200, r.status_code
            hits = r.json()["hits"]
            out += [h["jcr:path"] for h in hits]
            off += len(hits)
            if len(hits) < 1000:
                break
        bruto["dam_g2"], mudou = out, True
    for par in Indice(bruto).pares(bruto["escopo"]):
        for p in par:
            if p not in bruto["jcr"]:
                j, st = fundo(f"{p}/jcr:content")
                bruto["jcr"][p], mudou = (j if j is not None else st), True
    return mudou


# ---------------------------------------------------------------- índice das duas árvores
def nrel(rel):
    return "/".join(normalize_name(unquote(p)) for p in rel.strip("/").split("/") if p)


def _alias(n, de, para):
    for a in ALIAS:
        x, y = a[de], a[para]
        if n == x or n.startswith(x + "/"):
            return y + n[len(x):]
    return n


def para_gwi(n):
    return _alias(n, 0, 1)


def para_g2(n):
    return _alias(n, 1, 0)


class Indice:
    def __init__(self, bruto):
        self.g2 = {h["jcr:path"]: h for h in bruto["g2"]}
        self.gw = {h["jcr:path"]: h for h in bruto["gw"]}
        self.g2_n, self.gw_n = {}, {}
        for site, pags, por_n in ((G2, self.g2, self.g2_n), (GW, self.gw, self.gw_n)):
            for p, h in sorted(pags.items(), key=lambda kv: (bool(self._morta(kv[1])), kv[0])):
                por_n.setdefault(nrel(p[len(site) + 1:]), p)       # viva antes da soft-deleted
        self.rev = {}                                              # página do GWI -> par no global2
        for p in sorted(self.g2, key=lambda x: bool(self._morta(self.g2[x]))):
            w = self.par_gwi(p)
            if w and w not in self.rev:
                self.rev[w] = p
        self.vanity = {}                                           # /mep100 -> página do GWI (sling:vanityPath)
        for h in bruto.get("vanity", []):
            for v in (h["sling:vanityPath"] if isinstance(h["sling:vanityPath"], list) else [h["sling:vanityPath"]]):
                k = re.sub(r"^(?:https?:)?//(?:www\.)?macnica\.com", "", v.strip(), flags=re.I).strip("/").lower()
                self.vanity.setdefault(k, h["jcr:path"].rsplit("/jcr:content", 1)[0])
        self.dam = collections.defaultdict(list)                   # nome normalizado -> assets do DAM do global2
        for p in bruto.get("dam_g2", []):
            self.dam[nome_arquivo(p)].append(p)
        self.por_titulo = {}
        for p in bruto.get("escopo", []):                          # renomeada no global2: mesmo pai + mesmo título
            if p in self.g2 and not self.par_gwi(p):
                w = self._par_titulo(p)
                if w:
                    self.por_titulo[p] = w
                    self.rev[w] = p

    def _par_titulo(self, p):
        pai = self.gw_n.get(para_gwi(nrel(p[len(G2) + 1:].rsplit("/", 1)[0])))
        t = self.titulo(p, "g2").lower()
        achados = [w for w in self.gw if w.rsplit("/", 1)[0] == pai and w not in self.rev
                   and self.titulo(w, "gw").lower() == t]
        return achados[0] if len(achados) == 1 else None

    @staticmethod
    def _morta(h):
        return (h.get("jcr:content") or {}).get("deleted")

    def par_gwi(self, p):
        n = nrel(p[len(G2) + 1:])
        return self.gw_n.get(para_gwi(n)) or self.gw_n.get(n)

    def par(self, p):
        return self.par_gwi(p) or self.por_titulo.get(p)

    def pares(self, escopo):
        return [(p, self.par(p)) for p in escopo if p in self.g2 and self.par(p)]

    def sem_par(self, escopo):
        """Páginas do escopo fora da comparação: XF, página que não está (mais) no global2, sem par no GWI."""
        return [p for p in escopo if p not in self.g2 or not self.par(p)]

    def redir(self, p, lado):
        pags = self.g2 if lado == "g2" else self.gw
        return ((pags.get(p) or {}).get("jcr:content") or {}).get("cq:redirectTarget")

    def titulo(self, p, lado):
        jc = ((self.g2 if lado == "g2" else self.gw).get(p) or {}).get("jcr:content") or {}
        return re.sub(r"\s+", " ", jc.get("pageTitle") or jc.get("jcr:title") or p.rsplit("/", 1)[-1]).strip()


# ---------------------------------------------------------------- extração dos links
A_RE = re.compile(r"<a\b([^>]*)>(.*?)</a\s*>", re.I | re.S)
HREF_RE = re.compile(r"""\bhref\s*=\s*(["'])(.*?)\1""", re.I | re.S)
ALT_RE = re.compile(r"""<img\b[^>]*?\balt\s*=\s*(["'])(.*?)\1""", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")
PROP_LINK = re.compile(r"(link|url|href)$", re.I)
VIDEO = re.compile(r"embed|video|youtube|vimeo", re.I)
URLISH = re.compile(r"^(/|#|https?://|//|www\.|mailto:|tel:)", re.I)
FORA = {"cq:canonicalUrl", "sling:vanityPath", "fileReference", "fragmentVariationPath", "fragmentPath", "pages",
        "parentPage", "searchIn", "rootPath", "tagsSearchRoot", "directory", "action", "redirect",
        "errorFragmentPath", "successFragmentPath", "cq:template", "sling:resourceType", "sling:resourceSuperType"}
ROTULO = ("jcr:title", "title", "buttonText", "linkText", "label", "ctaText", "ctaLabel", "alt", "heading", "text")


def texto(s):
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", s or "")).replace(" ", " ")).strip()


def _rotulo(no, prop):
    for k in ROTULO:
        v = no.get(k)
        if isinstance(v, str) and texto(v):
            return texto(v)[:160]
    return f"({prop})"


def links_de(no, caminho, out, censo, xf_links=None, via=""):
    """Links do nó em ordem de documento. `xf_links(path)` devolve os links de um XF embutido (já extraídos)."""
    rt = str(no.get("sling:resourceType", "")).rsplit("/", 1)[-1]
    for k, v in no.items():
        if isinstance(v, dict):
            if k != "cq:responsive":
                links_de(v, f"{caminho}/{k}", out, censo, xf_links, via)
            continue
        if k in XF_PROPS and xf_links and isinstance(v, str) and v.startswith("/content/experience-fragments/"):
            for ln in xf_links(v.rstrip("/")):
                out.append(dict(ln, via=v.rstrip("/")))
            continue
        for s in (v if isinstance(v, list) else [v]):
            if not isinstance(s, str) or not s.strip():
                continue
            if "<a" in s.lower() and "href" in s.lower():
                for m in A_RE.finditer(s):
                    h = HREF_RE.search(m.group(1))
                    if not h:
                        continue
                    inner = m.group(2)
                    t = texto(inner)
                    if not t:
                        alt = ALT_RE.search(inner)
                        t = (f"(image) {texto(alt.group(2))}".strip() if alt else
                             "(image)" if "<img" in inner.lower() else "(invisible link — no text)")
                    out.append({"txt": t[:200], "href": h.group(2), "no": caminho, "prop": k, "comp": rt, "via": via})
                    censo[(rt, k, "<a>")] += 1
            elif k == "cq:redirectTarget" and caminho == "jcr:content":
                out.append({"txt": "(page redirect)", "href": s, "no": caminho, "prop": k, "comp": rt, "via": via})
                censo[(rt, k, "redirect")] += 1
            elif (k not in FORA and PROP_LINK.search(k) and URLISH.match(s.strip()) and "\n" not in s
                  and len(s) < 1000 and not VIDEO.search(rt)):             # url do embed = o vídeo, não um link
                t = f"(page property {k})" if caminho == "jcr:content" else _rotulo(no, k)
                out.append({"txt": t, "href": s, "no": caminho, "prop": k, "comp": rt, "via": via})
                censo[(rt, k, "prop")] += 1
    return out


# ---------------------------------------------------------------- alvo de um href
AUTHOR = re.compile(r"^(?:https?://[^/]*adobeaemcloud\.com)?(?:/(?:sites|editor|cf#|assets)\.html)?(?=/content/)", re.I)
PUBLICO = re.compile(r"^(?:https?:)?//(?:www\.)?macnica\.com(/[^?#]*)?(\?[^#]*)?(#.*)?$", re.I)
PARTES = re.compile(r"^([^?#]*)(\?[^#]*)?(#.*)?$")


def alvo(href):
    """{kind, site, rel|arq|url, frag, raw}. kind: pagina, dam, xf, externo, ancora, mail, tel, js, vazio, outro."""
    s = html.unescape(href or "").strip()
    a = {"raw": s, "kind": "outro", "site": "", "rel": "", "frag": "", "chave": s}
    low = s.lower()
    if not s or s == "#":
        return dict(a, kind="vazio", chave="")
    if low.startswith("#"):
        return dict(a, kind="ancora", frag=s[1:], chave=s[1:])
    for pre, k in (("mailto:", "mail"), ("tel:", "tel"), ("javascript:", "js")):
        if low.startswith(pre):
            return dict(a, kind=k, chave=re.sub(r"\s+", "", unquote(low)))
    s2 = AUTHOR.sub("", s)
    m = PUBLICO.match(s2)
    if m:
        caminho, frag, site = m.group(1) or "/", (m.group(3) or "")[1:], "publico"
    elif s2.startswith("/"):
        m = PARTES.match(s2)
        caminho, frag, site = m.group(1), (m.group(3) or "")[1:], ""
    elif re.match(r"^(https?:)?//", s2, re.I) or low.startswith("www."):
        u = ("https://" + s2) if low.startswith("www.") else ("https:" + s2 if s2.startswith("//") else s2)
        m = re.match(r"^(https?)://([^/?#]+)([^?#]*)(\?[^#]*)?(#.*)?$", u, re.I)
        if not m:
            return dict(a, kind="externo", chave=u)
        host = m.group(2).lower()
        host = host[4:] if host.startswith("www.") else host
        chave = f"{host}{unquote(m.group(3)).rstrip('/')}{unquote(m.group(4) or '')}{m.group(5) or ''}"
        return dict(a, kind="externo", chave=chave)
    else:
        return a
    caminho = unquote(caminho)
    if caminho.startswith("/content/dam/"):
        dono = caminho.split("/")[3] if caminho.count("/") > 3 else ""
        return dict(a, kind="dam", site=dono, rel=caminho, chave=nome_arquivo(caminho))
    if caminho.startswith("/content/experience-fragments/"):
        return dict(a, kind="xf", rel=caminho, chave=caminho)
    caminho = re.sub(r"\.html?(/.*)?$", "", caminho, flags=re.I).rstrip("/")
    if caminho.startswith("/content/"):
        _, _, site, *resto = caminho.split("/") + [""]
        caminho = "/" + "/".join(resto)
    return dict(a, kind="pagina", site=site or "relativo", rel=caminho.strip("/"), frag=frag)


def nome_arquivo(caminho):
    """sakura-main-panel-24x36-v02.pdf == Sakura Main Panel_24x36_v02.pdf: o DAM do global2 normaliza os nomes."""
    nome = unquote(caminho.rsplit("/", 1)[-1])
    base, ponto, ext = nome.rpartition(".")
    return f"{normalize_name(base)}.{ext.lower()}" if ponto else normalize_name(nome)


def _frag(f):
    return "" if not f or f.startswith("tabs-") else f


# ---------------------------------------------------------------- comparação
class Comparador:
    def __init__(self, idx):
        self.idx = idx
        self.assets = {}
        if MAPA_ASSETS.exists():
            self.assets = {unquote(r["origem"]): r["destino"] for r in csv.DictReader(open(MAPA_ASSETS))}
        self._esp, self._atu = {}, {}

    def _cadeia(self, n, lado):
        """Páginas (caminho) a partir do rel normalizado `n`, seguindo cq:redirectTarget (até 4 saltos)."""
        por_n = self.idx.g2_n if lado == "g2" else self.idx.gw_n
        out, p = [], por_n.get(n)
        while p and p not in out and len(out) < 4:
            out.append(p)
            r = self.idx.redir(p, lado)
            a = alvo(r) if r else None
            p = por_n.get(nrel(a["rel"])) if a and a["kind"] == "pagina" else None
        return out

    def esperado(self, w):
        """Link do GWI -> (rels normalizados do global2 que valem como mesmo alvo, caminho para exibir, nota)."""
        k = (w["site"], w["rel"])
        if k not in self._esp:
            n = nrel(w["rel"])
            cad = [] if w["site"] == "macnicaglobal2" else self._cadeia(n, "gw")
            v = self.idx.vanity.get(w["rel"].strip("/").lower()) if not cad else None
            if v:
                cad = self._cadeia(nrel(v[len(GW) + 1:]), "gw")
            cands, mostra, nota = [], None, ""
            for i, p in enumerate(cad):
                g = self.idx.rev.get(p)
                if g:
                    cands.append(nrel(g[len(G2) + 1:]))
                    if mostra is None:
                        mostra, nota = g, ("the GWI target redirects there" if i else "")
            cands.append(para_g2(n))
            if mostra is None:
                mostra = self.idx.g2_n.get(para_g2(n))
            if mostra is None and not cad and w["site"] == "publico":   # www.macnica.com/, /mep100: fora do AEM
                mostra, nota = w["raw"], "public URL, keep it as on the GWI"
            if mostra is None:
                mostra = f"{G2}/{_alias_cru(cad[0][len(GW) + 1:] if cad else w['rel'])}"
                nota = "not in global2 yet" if cad else "no such page in the GWI either"
            self._esp[k] = (cands, mostra, nota)
        return self._esp[k]

    def atual(self, d):
        k = d["rel"]
        if k not in self._atu:
            n = nrel(k)
            self._atu[k] = [n] + [nrel(p[len(G2) + 1:]) for p in self._cadeia(n, "g2")]
        return self._atu[k]

    def mesmo(self, d, w):
        """(mesmo alvo?, mesma âncora?)"""
        if d["kind"] != w["kind"]:
            return False, True
        if d["kind"] == "pagina":
            if d["site"] in ("macnicagwi", "copia-teste"):
                return False, True
            cands, mostra, _ = self.esperado(w)
            ok = bool(set(self.atual(d)) & set(cands)) or (d["raw"] == mostra and d["site"] == "publico")
            return ok, _frag(d["frag"]) == _frag(w["frag"])
        if d["kind"] == "dam":
            if d["site"] in ("macnicagwi", "copia-teste"):
                return False, True
            mapeado = self.assets.get(w["rel"])
            return d["chave"] == w["chave"] or bool(mapeado and unquote(mapeado) == d["rel"]), True
        if d["kind"] == "ancora":
            return _frag(d["frag"]) == _frag(w["frag"]), True
        return d["chave"] == w["chave"], True

    def deveria(self, w):
        """(href para exibir, nota) do que o link do global2 deveria ser."""
        if w["raw"].startswith("#"):
            return w["raw"], "anchor on the same page"
        if w["kind"] == "pagina":
            _, mostra, nota = self.esperado(w)
            f = _frag(w["frag"])
            return mostra + (f"#{f}" if f else ""), nota
        if w["kind"] == "dam":
            m = self.assets.get(w["rel"])
            if m:
                return m, ""
            achados = self.idx.dam.get(w["chave"], [])
            if achados:
                return achados[0], (f"{len(achados)} copies in the global2 DAM" if len(achados) > 1 else "")
            return w["rel"], "not in the global2 DAM yet; this is the GWI file"
        return w["raw"], ""

    def padrao(self, d, w, mesmo_alvo):
        if d["kind"] == "vazio":
            return "empty"
        if d["site"] == "macnicagwi":
            return "gwi"
        if d["site"] == "copia-teste":
            return "copia"
        if mesmo_alvo:
            return "anchor"
        if d["kind"] != w["kind"]:
            return "kind"
        if d["kind"] == "pagina":
            _, mostra, _ = self.esperado(w)
            e = nrel(mostra[len(G2) + 1:]) if mostra.startswith(G2 + "/") else ""
            if (any(e.startswith(x + "/") for x in self.atual(d))                    # no global2
                    or nrel(w["rel"]).startswith(para_gwi(nrel(d["rel"])) + "/")):     # ou no caminho do GWI
                return "cut"
            return "page"
        return {"dam": "file", "externo": "external", "ancora": "anchor", "mail": "mail", "tel": "mail"}.get(d["kind"], "other")


def chave_txt(t):
    t = t.lower().replace(" ", " ")
    t = re.sub(r"\s+", " ", t)
    return re.sub(r"^[\s>›»→·•:–—-]+|[\s>›»→·•:–—.,;!-]+$", "", t)


def parecido(a, b):
    if not a or not b or a.startswith("(") or b.startswith("("):
        return False
    curto, longo = sorted((a, b), key=len)
    return (len(curto) >= 12 and curto in longo) or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def casar(cmp, ds, ws):
    """(divergentes, ok, novos, faltando) de uma página. ds/ws = links do global2/GWI com 'a' = alvo()."""
    for x in ds + ws:
        x["t"] = chave_txt(x["txt"])
    livre_d, livre_w = set(range(len(ds))), set(range(len(ws)))
    ok, div = [], []

    def tira(i, j):
        livre_d.discard(i)
        livre_w.discard(j)

    # 1. mesmo texto, mesmo alvo e mesma âncora
    for i in sorted(livre_d):
        for j in sorted(livre_w):
            if ds[i]["t"] == ws[j]["t"] and cmp.mesmo(ds[i]["a"], ws[j]["a"]) == (True, True):
                ok.append((i, j)); tira(i, j); break
    # 2. mesmo texto, alvo (ou âncora) diferente — entre vários, o GWI de alvo mais parecido
    for i in sorted(livre_d):
        cands = [j for j in sorted(livre_w) if ds[i]["t"] == ws[j]["t"]]
        if cands:
            j = max(cands, key=lambda j: difflib.SequenceMatcher(None, ds[i]["a"]["raw"], ws[j]["a"]["raw"]).ratio())
            div.append((i, j, False)); tira(i, j)
    # 3. mesmo alvo, texto diferente
    for i in sorted(livre_d):
        for j in sorted(livre_w):
            if cmp.mesmo(ds[i]["a"], ws[j]["a"]) == (True, True):
                ok.append((i, j)); tira(i, j); break
    # 4. texto parecido
    for i in sorted(livre_d):
        cands = [j for j in sorted(livre_w) if parecido(ds[i]["t"], ws[j]["t"])]
        if cands:
            j = max(cands, key=lambda j: difflib.SequenceMatcher(None, ds[i]["t"], ws[j]["t"]).ratio())
            if cmp.mesmo(ds[i]["a"], ws[j]["a"]) == (True, True):
                ok.append((i, j))
            else:
                div.append((i, j, True))
            tira(i, j)
    return div, ok, sorted(livre_d), sorted(livre_w)


def _alias_cru(rel):
    """rel do GWI com o caso original -> rel no global2 (aplica ALIAS comparando normalizado)."""
    partes = rel.strip("/").split("/")
    n = nrel(rel)
    for g, w in ALIAS:
        if n == w or n.startswith(w + "/"):
            return g + "/" + "/".join(partes[w.count("/") + 1:]) if n != w else g
    return rel.strip("/")


def comparar(bruto):
    idx = Indice(bruto)
    cmp = Comparador(idx)
    censo = {"g2": collections.Counter(), "gw": collections.Counter()}
    xf_cache = {}

    def xf_links(lado):
        def f(p):
            if (lado, p) not in xf_cache:
                j = bruto["xf"].get(p)
                xf_cache[(lado, p)] = links_de(j, "jcr:content", [], censo[lado]) if isinstance(j, dict) else []
            return xf_cache[(lado, p)]
        return f

    res, erros = [], []
    for p, w in idx.pares(bruto["escopo"]):
        jd, jw = bruto["jcr"].get(p), bruto["jcr"].get(w)
        if not isinstance(jd, dict) or not isinstance(jw, dict):
            erros.append({"g2": p, "gw": w, "st": [jd if not isinstance(jd, dict) else 200,
                                                   jw if not isinstance(jw, dict) else 200]})
            continue
        ds = links_de(jd, "jcr:content", [], censo["g2"], xf_links("g2"))
        ws = links_de(jw, "jcr:content", [], censo["gw"], xf_links("gw"))
        for lado, pag, site, xs in (("g2", p, G2, ds), ("gw", w, GW, ws)):
            for x in xs:
                x["a"] = alvo(x["href"])
                if x["a"]["kind"] == "ancora":                  # #kit == /…/easymvc#kit na própria página
                    x["a"] = dict(x["a"], kind="pagina", site=site.rsplit("/", 1)[-1], rel=pag[len(site) + 1:])
        div, ok, novos, falt = casar(cmp, ds, ws)
        # sobra só conta se o DESTINO não está do outro lado: o XF signup-and-contact do GWI tem o bloco duas vezes
        # (variantes de layout: Sign up/Get in touch e Sign up/Contact us) e a página do global2, uma
        falt = [j for j in falt if not any(cmp.mesmo(d["a"], ws[j]["a"])[0] for d in ds)]
        novos = [i for i in novos if not any(cmp.mesmo(ds[i]["a"], g["a"])[0] for g in ws)]
        itens = []
        for i, j, txt_dif in div:
            d, g = ds[i], ws[j]
            mesmo_alvo, _ = cmp.mesmo(d["a"], g["a"])
            dev, nota = cmp.deveria(g["a"])
            itens.append({"txt": d["txt"], "txt_gwi": g["txt"] if txt_dif else "", "agora": d["a"]["raw"],
                          "deveria": dev, "nota": nota, "gwi": g["a"]["raw"], "padrao": cmp.padrao(d["a"], g["a"], mesmo_alvo),
                          "via": d["via"], "via_gwi": g["via"], "comp": d["comp"], "no": d["no"]})
        res.append({"g2": p, "gw": w, "titulo": idx.titulo(p, "g2"), "n_g2": len(ds), "n_gw": len(ws), "ok": len(ok),
                    "div": itens,
                    "novos": [{"txt": ds[i]["txt"], "href": ds[i]["a"]["raw"], "via": ds[i]["via"]} for i in novos],
                    "faltando": [dict(zip(("deveria", "nota"), cmp.deveria(ws[j]["a"])), txt=ws[j]["txt"],
                                      href=ws[j]["a"]["raw"], via=ws[j]["via"]) for j in falt],
                    "editor": ((idx.g2[p].get("jcr:content") or {}).get("cq:lastModifiedBy") or "")})
    return res, erros, idx.sem_par(bruto["escopo"]), censo


# ---------------------------------------------------------------- HTML
PADROES = {  # chave: (rótulo, explicação) — em ordem de gravidade para o relatório
    "cut": ("Cut off at a parent page", "Points to an ancestor of the right page (e.g. /blog instead of the blog post)."),
    "page": ("Points to another page", "Points to a different page than the GWI link's counterpart."),
    "gwi": ("Still points to the GWI", "The global2 link goes to /content/macnicagwi."),
    "copia": ("Points to the test copy", "The global2 link goes to /content/copia-teste."),
    "empty": ("Link without a target", "The global2 link has an empty href or just #."),
    "kind": ("Different kind of target", "E.g. the GWI links to a file and global2 to a page."),
    "file": ("Different file", "Points to a different DAM file (compared by file name)."),
    "external": ("Different external URL", "The external URL differs (http/https, www and a trailing slash are ignored)."),
    "anchor": ("Right page, different anchor", "Same target page, but the #anchor differs or was dropped."),
    "mail": ("Different e-mail or phone", "The mailto:/tel: address differs."),
    "other": ("Other", ""),
    "missing": ("Missing on global2", "The GWI page has this link; the global2 page has no link with this text or to this destination."),
}


def _u(path):
    """href do author para um alvo mostrado no relatório (página ganha .html; DAM e externo ficam como estão)."""
    if path.startswith(("http://", "https://", "mailto:", "tel:", "//")):
        return path
    base, _, frag = path.partition("#")
    base, _, qs = base.partition("?")
    if not base.startswith("/content/"):
        return None
    sufixo = "" if base.startswith("/content/dam/") or re.search(r"\.html?$", base) else ".html"
    return BASE + quote(unquote(base), safe="/:") + sufixo + (f"?{qs}" if qs else "") + (f"#{frag}" if frag else "")


def _alink(path, rotulo=None):
    u = _u(path)
    if not u:                                               # âncora, relativo, javascript: só o texto
        return html.escape(rotulo or path)
    return f'<a href="{html.escape(u, quote=True)}" target="_blank" rel="noopener">{html.escape(rotulo or path)}</a>'


def _secao(rel):
    p = rel.split("/")
    base = 3 if len(p) > 3 else len(p)                     # americas/mai/en, eu/atd-europe/en
    fim = base + (2 if len(p) > base + 1 and p[base] == "products" else 1)
    return "/".join(p[:fim])


CSS = """
:root{--bg:#fbfaf7;--fg:#1d1f23;--mut:#6a6f78;--lin:#e4e1d8;--acc:#0b5cad;--vis:#6b3fa0;--card:#fff;
--bad:#b3261e;--badbg:#fdecea;--ok:#1e6b35;--okbg:#e7f4ea;--warn:#8a5a00;--warnbg:#fff3d6;--tag:#eef0f4}
@media (prefers-color-scheme:dark){:root{--bg:#15171b;--fg:#e8e6e1;--mut:#9aa0aa;--lin:#2b2f36;--acc:#7db7f5;
--vis:#c3a2ee;--card:#1c1f24;--bad:#ffb4ab;--badbg:#3a1d1b;--ok:#9ad3a8;--okbg:#17301f;--warn:#f3c969;--warnbg:#3a2e12;--tag:#262a31}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:32px 16px 80px}
h1{font-size:26px;margin:0 0 4px}
.sub{color:var(--mut);margin:0 0 18px}
a{color:var(--acc);text-decoration:none;overflow-wrap:anywhere}a:hover{text-decoration:underline}
.resumo{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;margin:0 0 22px}
.resumo div{background:var(--card);border:1px solid var(--lin);border-radius:8px;padding:10px 12px}
.resumo b{display:block;font-size:22px}
.resumo span{color:var(--mut);font-size:13px}
.barra{position:sticky;top:0;background:var(--bg);padding:10px 0;border-bottom:1px solid var(--lin);z-index:2;
display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.barra input[type=search]{flex:1 1 260px;padding:8px 10px;border:1px solid var(--lin);border-radius:6px;background:var(--card);color:var(--fg);font:inherit}
.barra label{font-size:13px;color:var(--mut);white-space:nowrap}
.barra nav{flex-basis:100%;font-size:14px;line-height:1.7}.barra nav a{margin-right:12px;white-space:nowrap}
h2{font-size:22px;margin:44px 0 4px;scroll-margin-top:160px;overflow-wrap:anywhere;border-bottom:2px solid var(--lin);padding-bottom:6px}
h3{font-size:17px;margin:26px 0 6px;scroll-margin-top:160px;overflow-wrap:anywhere}
.intro{color:var(--mut);margin:0 0 8px}
h2 .n,h3 .n,summary .n{color:var(--mut);font-weight:400;font-size:14px;margin-left:6px}
details{background:var(--card);border:1px solid var(--lin);border-radius:8px;margin:10px 0;padding:0 14px}
summary{cursor:pointer;padding:11px 0;font-weight:600}
details[open]>summary{border-bottom:1px solid var(--lin)}
.abre{font-size:13px;margin:8px 0 2px;color:var(--mut)}.abre a{margin-right:14px}
.p{color:var(--mut);font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;overflow-wrap:anywhere}
.lk{border-top:1px solid var(--lin);padding:10px 0}.lk:first-of-type{border-top:0}
.lk .t{font-weight:600;margin-bottom:4px;overflow-wrap:anywhere}
.lk dl{display:grid;grid-template-columns:120px 1fr;gap:2px 10px;margin:0;font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.lk dt{color:var(--mut);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.lk dd{margin:0;overflow-wrap:anywhere}
.agora a{color:var(--bad)}.dev a{color:var(--ok)}
.nota{display:inline-block;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--warn);background:var(--warnbg);border-radius:4px;padding:0 6px;margin-left:6px;font-size:12px}
.tag{display:inline-block;font-size:12px;font-weight:500;background:var(--tag);border-radius:10px;padding:1px 8px;margin-left:8px;vertical-align:1px}
.tag.cut,.tag.gwi,.tag.copia,.tag.empty{background:var(--badbg);color:var(--bad)}
.via{font-size:12px;color:var(--mut);font-weight:400}
table{border-collapse:collapse;width:100%;font-size:14px;margin:6px 0 10px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--lin);vertical-align:top}
th{color:var(--mut);font-weight:500}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.oculto{display:none}
footer{margin-top:48px;color:var(--mut);font-size:13px;border-top:1px solid var(--lin);padding-top:12px}
@media (max-width:600px){.lk dl{grid-template-columns:1fr}.lk dt{margin-top:4px}.barra{position:static}}
"""

JS = """
const q=document.getElementById('q'), box=[...document.querySelectorAll('.barra input[type=checkbox]')];
function filtra(){
  const t=q.value.trim().toLowerCase(), on=new Set(box.filter(b=>b.checked).map(b=>b.value));
  document.querySelectorAll('.lk').forEach(l=>{
    const ok=on.has(l.dataset.p)&&(!t||l.dataset.s.includes(t));
    l.classList.toggle('oculto',!ok);
  });
  document.querySelectorAll('details.pg').forEach(d=>{
    const vis=d.querySelector('.lk:not(.oculto)');
    d.classList.toggle('oculto',!vis);
  });
  document.querySelectorAll('section.sec').forEach(s=>s.classList.toggle('oculto',!s.querySelector('details.pg:not(.oculto)')));
}
q.addEventListener('input',filtra);box.forEach(b=>b.addEventListener('change',filtra));
"""


def _item(it):
    tag = PADROES[it["padrao"]][0]
    via = (f' <span class="via">from {"GWI " if it["padrao"] == "missing" else ""}experience fragment '
           f'{html.escape(it["via"].split("/site/")[-1])}</span>') if it["via"] else ""
    txt_gwi = (f"<dt>GWI link text</dt><dd>{html.escape(it['txt_gwi'])}</dd>") if it.get("txt_gwi") else ""
    nota = f'<span class="nota">{html.escape(it["nota"])}</span>' if it["nota"] else ""
    agora = (_alink(it["agora"]) if it["agora"] else "(empty)") if it["padrao"] != "missing" else "(no such link)"
    busca = html.escape(f"{it['txt']} {it['agora']} {it['deveria']} {it['gwi']}".lower(), quote=True)
    return (f'<div class="lk" data-p="{it["padrao"]}" data-s="{busca}"><div class="t">“{html.escape(it["txt"])}”'
            f'<span class="tag {it["padrao"]}">{html.escape(tag)}</span>{via}</div><dl>{txt_gwi}'
            f'<dt>Points to now</dt><dd class="agora">{agora}</dd>'
            f'<dt>Should point to</dt><dd class="dev">{_alink(it["deveria"])}{nota}</dd>'
            f'<dt>GWI link</dt><dd>{_alink(it["gwi"])}</dd></dl></div>')


def _nome_fora(p):
    if p.startswith("/content/experience-fragments/"):
        return "the " + p.split("/site/")[-1].rsplit("/master", 1)[0] + " experience fragment"
    return p.rsplit("/", 1)[-1]


def _parte(paginas, chave, prefixo, nav):
    """Seções (por área do site) com um <details> por página; `chave` = lista de itens da página."""
    secoes = collections.defaultdict(list)
    for r in paginas:
        secoes[_secao(r["g2"][len(G2) + 1:])].append(r)
    corpo = []
    for sec in sorted(secoes):
        rs = sorted(secoes[sec], key=lambda r: r["g2"])
        idr = prefixo + re.sub(r"[^a-z0-9]+", "-", sec.lower())
        n = sum(len(r[chave]) for r in rs)
        nav.append(f'<a href="#{idr}">{html.escape(sec.split("/", 3)[-1])} ({n})</a>')
        corpo.append(f'<section class="sec"><h3 id="{idr}">{html.escape(sec)}<span class="n">{len(rs)} page'
                     f'{"s" if len(rs) != 1 else ""}, {n} link{"s" if n != 1 else ""}</span></h3>')
        for r in rs:
            ordem = sorted(r[chave], key=lambda it: list(PADROES).index(it["padrao"]))
            corpo.append(f'<details class="pg" open><summary>{html.escape(r["titulo"])}<span class="n">{len(ordem)} '
                         f'link{"s" if len(ordem) != 1 else ""}</span></summary>'
                         f'<div class="abre">{_alink(r["g2"] + ".html?wcmmode=disabled", "global2 page")}'
                         f'{_alink(r["gw"] + ".html?wcmmode=disabled", "GWI page")}'
                         f'<span class="p">{html.escape(r["g2"])}</span></div>'
                         + "".join(_item(it) for it in ordem) + "</details>")
        corpo.append("</section>")
    return corpo


def montar_html(res, erros, sem_par, quando, n_escopo):
    for r in res:                                               # faltando no mesmo formato dos divergentes
        r["falt"] = [{"txt": x["txt"], "agora": "", "deveria": x["deveria"], "nota": x["nota"], "gwi": x["href"],
                      "padrao": "missing", "via": x["via"]} for x in r["faltando"]]
    errados = [r for r in res if r["div"]]
    faltam = [r for r in res if r["falt"]]
    todos = [it for r in res for it in r["div"] + r["falt"]]
    por_padrao = collections.Counter(it["padrao"] for it in todos)
    pags_padrao = collections.Counter(p for r in res for p in {it["padrao"] for it in r["div"] + r["falt"]})
    n_div, n_falt = len([it for r in errados for it in r["div"]]), len([it for r in faltam for it in r["falt"]])

    resumo = [f'<div><b>{len(res)}</b><span>pages compared with the same page in the GWI</span></div>',
              f'<div><b>{sum(r["n_g2"] for r in res)}</b><span>links on those global2 pages</span></div>',
              f'<div><b>{n_div}</b><span>links that point to the wrong place, on {len(errados)} pages</span></div>',
              f'<div><b>{n_falt}</b><span>GWI links missing on global2, on {len(faltam)} pages</span></div>']
    linhas = "".join(f'<tr><td><span class="tag {k}">{html.escape(PADROES[k][0])}</span></td><td>{html.escape(PADROES[k][1])}</td>'
                     f'<td class="num">{por_padrao[k]}</td><td class="num">{pags_padrao[k]}</td></tr>'
                     for k in PADROES if por_padrao[k])
    caixas = " ".join(f'<label><input type="checkbox" value="{k}" checked> {html.escape(PADROES[k][0])} ({por_padrao[k]})</label>'
                     for k in PADROES if por_padrao[k])
    nav1, nav2 = [], []
    corpo1 = _parte(errados, "div", "w-", nav1)
    corpo2 = _parte(faltam, "falt", "m-", nav2)
    fora = ", ".join(_nome_fora(p) for p in sem_par)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>global2 links vs GWI</title><style>{CSS}</style></head><body><main>
<h1>global2 links that differ from the GWI</h1>
<p class="sub">Every link on the {len(res)} pages of the macnicaglobal2 link map (Americas / MAI / EN), compared with the
matching link on the same page in the GWI. The GWI is the source of truth: “Should point to” is the global2 page (or
file) that corresponds to where the GWI link goes. Links open in the AEM author in a new tab; you must be logged in.
Generated {quando}.</p>
<div class="resumo">{''.join(resumo)}</div>
<table><thead><tr><th>What is wrong</th><th>Meaning</th><th class="num">Links</th><th class="num">Pages</th></tr></thead>
<tbody>{linhas}</tbody></table>
<div class="barra"><input id="q" type="search" placeholder="Filter by link text or path…" autocomplete="off"> {caixas}
<nav><a href="#parte1"><b>Wrong place</b></a> {' '.join(nav1)}</nav>
<nav><a href="#parte2"><b>Missing</b></a> {' '.join(nav2)}</nav></div>
<h2 id="parte1">1. Links that point to the wrong place<span class="n">{n_div} links on {len(errados)} pages</span></h2>
<p class="intro">The global2 page has the link, but it goes somewhere other than the GWI link.</p>
{''.join(corpo1)}
<h2 id="parte2">2. GWI links missing on global2<span class="n">{n_falt} links on {len(faltam)} pages</span></h2>
<p class="intro">The GWI page has the link; the global2 page has no link with the same text or to the same destination
(for example, a heading, image or button that is no longer clickable).</p>
{''.join(corpo2)}
<footer><p><b>How links were matched.</b> Read from the authored content of each page and of the experience fragments it
embeds (not from the rendered page). A global2 link is paired with the GWI link that has the same text; when the text
was edited, with the GWI link that goes to the same place or has similar text. Two links go to the same place when the
global2 target is the global2 counterpart of the GWI target (same path, allowing for the known moves: technology →
solutions, europe → eu, sony-image-sensors → sony/sony-image-sensors), also through page redirects; files match by file
name (the global2 DAM renames “Sakura Main Panel_24x36.pdf” to “sakura-main-panel-24x36.pdf”); external URLs match
ignoring http/https, www and a trailing slash. Lists built automatically from the page tree, images, videos and form
settings are not included. Only GET requests were made; nothing was changed in either site.</p>
<p>The link map has {n_escopo} entries: {len(res)} pages were compared{f"; {len(sem_par)} ({html.escape(fora)}) has no GWI counterpart and was not compared" if sem_par else ""}{f"; {len(erros)} could not be read" if erros else ""}.</p></footer>
</main><script>{JS}</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mapas = sorted(MAPAS.glob("global2_link_map_complete_*.html"))
    ap.add_argument("--mapa", default=str(mapas[-1]) if mapas else None,
                    help="HTML do mapa de links final — o escopo (padrão: o mais novo, %(default)s)")
    ap.add_argument("--do-cache", action="store_true", help="não vai à rede: usa o cache da última coleta")
    ap.add_argument("--saida", default=f"global2_links_vs_gwi_{datetime.date.today().isoformat()}",
                    help="nome (sem extensão) em dados/mapas")
    a = ap.parse_args()
    if a.do_cache:
        bruto = pickle.loads(CACHE.read_bytes())
        if complementos(bruto):                                 # cache de versão anterior: só o que falta (GET)
            CACHE.write_bytes(pickle.dumps(bruto))
    else:
        bruto = coletar(escopo_do_mapa(a.mapa), a.mapa)
    res, erros, sem_par, censo = comparar(bruto)

    MAPAS.mkdir(parents=True, exist_ok=True)
    (MAPAS / f"{a.saida}.html").write_text(montar_html(res, erros, sem_par, bruto["quando"], len(bruto["escopo"])), encoding="utf-8")
    (MAPAS / f"{a.saida}.json").write_text(json.dumps(
        {"quando": bruto["quando"], "mapa": bruto["mapa"], "paginas": res, "erros": erros, "sem_par": sem_par},
        ensure_ascii=False, indent=1), encoding="utf-8")

    com = [r for r in res if r["div"]]
    print(f"{len(res)} pares comparados; {len(com)} com divergência; "
          f"{sum(len(r['div']) for r in res)} links divergentes; {len(sem_par)} sem par; {len(erros)} erros")
    for k, n in collections.Counter(it["padrao"] for r in res for it in r["div"]).most_common():
        print(f"  {n:5d}  {k}")
    print(f"faltando (GWI sem par): {sum(len(r['faltando']) for r in res)}; novos (global2 sem par): "
          f"{sum(len(r['novos']) for r in res)}")
    for lado in ("g2", "gw"):                                     # de onde vieram os links (conferir a extração)
        print(f"censo {lado}: " + "; ".join(f"{c}.{p}[{t}]={n}" for (c, p, t), n in censo[lado].most_common(25)))
    print(f"-> {MAPAS / (a.saida + '.html')}")


if __name__ == "__main__":
    main()
