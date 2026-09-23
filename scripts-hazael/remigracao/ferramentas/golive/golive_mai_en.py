#!/usr/bin/env python3
"""
golive_mai_en.py <passo> [--executar] — go-live de copia-teste/americas/mai/en → macnicaglobal2/americas/mai/en
(PLANO-go-live-mai-en.md; autorizado pelo Hazael em 22/09/2026 noite: "perform the migration using your
recommendations", com events-archive incluída depois que a Luiza terminou a revisão). Dry-run por padrão.

Passos (cada um só depois do anterior conferido):
  ensaio       troca de jcr:content (apagar + :operation=copy com :dest terminando em jcr:content) numa página
               de rascunho da copia-teste — prova a mecânica antes de usar no global2
  staging      cópia servidor-a-servidor de T para STG; tira o que não migra; renomeia para o nome normalizado
  reescrever   no STG: links (tabela abaixo), assets (mapa do levantamento), canonical = próprio caminho no
               global2, hideInNav do GWI (menos as folhas de news-archive/newsletter/events-archive, que o
               header do global2 desenharia — ele renderiza 3–4 níveis), redirects do GWI, destinatários de form
               vazios ← GWI. 2ª passada tem de dar 0
  conferir     censo do STG: 0 refs a copia-teste/gwi; todo alvo interno existe no global2 ou nasce com a cópia
  plano        o que vai ao global2, calculado AO VIVO: criar (nó mais alto novo de cada ramo), trocar
               jcr:content (só as cascas listadas em CASCAS, com o dono e o nº de componentes do levantamento),
               extras (redirect de /contact-us e da casca Careers), assets novos. Grava dados/golive/plano_mai_en.json
  gravar       executa o plano.json (nada fora dele); relê o destino antes de CADA gravação; backup antes de
               trocar; manifesto em dados/golive/manifesto_mai_en.jsonl
  faltantes    depois do go-live: copia de STG para G as páginas de FALTANTES (publicadas no GWI e deixadas de
               fora pelo critério errado de D3) — só se o destino for 404 e o staging já estiver reescrito.
               Ordem: `staging` (traz de T) -> `reescrever --so <rel>…` -> `conferir --so` -> `faltantes` ->
               `conferir-g --so <rel>… --tela`

REGRA MESTRA: nenhuma requisição que não seja GET contra caminho com `macnicagwi` (checado em toda escrita).
"""
import datetime
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

_RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, build_session, normalize_name  # noqa: E402

BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE     # cookie só vai para o author
sessao, _ = build_session(verbose=False)

T = "/content/copia-teste/americas/mai/en"
STG = "/content/copia-teste/americas/mai/en-golive"
ANTES = "/content/copia-teste/americas/mai/en-antes-2309"
ENSAIO = "/content/copia-teste/americas/mai/en-golive-ensaio"
G = "/content/macnicaglobal2/americas/mai/en"
W = "/content/macnicagwi/americas/mai/en"
DAM_G = "/content/dam/macnicaglobal2/americas/mai/en"
DADOS = Path(__file__).resolve().parents[2] / "dados" / "golive"
LEVANTAMENTO = DADOS / "levantamento_mai-en-escopo-v2.json"
PLANO = DADOS / "plano_mai_en.json"
MANIFESTO = DADOS / "manifesto_mai_en.jsonl"

RAIZES = ["about-us", "contact", "error", "request-a-quote",
          "terms-conditions-mep100-ecosystem-partners-tour-challenge-raffle"]
FORA = {"about-us/news-events/events-archive/Altera-Sales-Conference-2026":
            "D3 — dada como 'nunca publicada', mas está publicada no GWI (só _publish); decisão pendente",
        "about-us/news-events/events-archive/automate-2026": "G tem a da Anion (mahendra, 68 componentes) — não sobrescrever"}
# Publicadas no GWI (só cq:lastReplicationAction_publish) e deixadas de fora do go-live pelo critério errado (D3):
# os cards "Fill Out Our Online Contact Information Form" do /contact. Trazidas depois, decisão do Hazael (23/09):
# `staging` copia de T, `reescrever --so`, `faltantes` copia para G. O TEST-request-evaluatoin-kit fica de fora.
FALTANTES = ("contact/download", "contact/watch")
# cascas que podem ter o jcr:content trocado: rel -> (criador, último editor, máx. componentes) do levantamento
CASCAS = {"about-us": ("admin", "ohashi", 0), "about-us/company-profile": ("admin", "ohashi", 0),
          "about-us/locations": ("admin", "ohashi", 0), "about-us/news-events": ("admin", "ohashi", 0),
          "about-us/newsletter": ("admin", "ohashi", 0), "about-us/partner-with-macnica": ("admin", "ohashi", 0),
          "about-us/privacy-policy": ("admin", "ohashi", 0), "about-us/terms-and-conditions": ("admin", "ohashi", 0),
          "request-a-quote": ("admin", "ohashi", 0), "error": ("admin", "ohashi", 1),
          "about-us/news-events/events-archive": ("saichand", "saichand", 0)}
# folhas que ficam fora do menu mesmo o GWI mostrando: o header do global2 desenha 3–4 níveis (medido 23/09)
FOLHAS_OCULTAS = ("about-us/news-events/news-archive/", "about-us/newsletter/", "about-us/news-events/events-archive/")
FIXOS = [(f"{G}/technology/Broadcast-ProAV-Solutions", f"{G}/solutions/broadcast-proav-solutions"),
         (f"{G}/technology/broadcast-proav-solutions", f"{G}/solutions/broadcast-proav-solutions"),
         (f"{G}/technology", f"{G}/solutions"),
         (f"{G}/products/semiconductors/sony-image-sensors", f"{G}/products/semiconductors/sony/sony-image-sensors"),
         ("/content/macnicaglobal2/europe/atd-europe", "/content/macnicaglobal2/eu/atd-europe")]
PROIBIDO = re.compile(r"/content/(?:dam/|usergenerated/)?copia-teste|/content/(?:dam/)?macnicagwi|experience-fragments/copia-teste")
ATRIBUTO = re.compile(r'(\b(?:href|src|data-src|poster)\s*=\s*)(["\'])(.*?)\2', re.I | re.S)
IGNORAR = {"jcr:primaryType", "jcr:mixinTypes", "sling:resourceType", "sling:resourceSuperType", "cq:template",
           "jcr:createdBy", "cq:lastModifiedBy", "jcr:lastModifiedBy", "jcr:uuid", "cq:tags", "jcr:created",
           "jcr:lastModified", "cq:lastModified", "cq:redirectTarget"}
ICONES = "/content/dam/macnicaglobal2/americas/mai/en/images/icons"
XF_T = "/content/experience-fragments/copia-teste/americas/mai/en/site"
XF_G = "/content/experience-fragments/macnicaglobal2/americas/mai/en/site"
XFS = ["event-meeting-request-form"]              # criado em 22/09 (xf_form_evento.py); a Luiza embutiu em 12 eventos


# ---------------------------------------------------------------- HTTP
def url(p, suf=""):
    return BASE + quote(unquote(p), safe="/:") + suf


def ler(p, suf=".json"):
    r = sessao.get(url(p, suf), timeout=120, allow_redirects=False)
    if r.status_code == 300 and suf == ".infinity.json":         # profundidade recusada: desce por partes
        return 200, fundo(p)
    try:
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except ValueError:
        return r.status_code, None


def fundo(p):
    r = sessao.get(url(p, ".infinity.json"), timeout=120)
    if r.status_code == 200:
        return r.json()
    d = max(int(m.group(1)) for o in r.json() if (m := re.search(r"\.(\d+)\.json$", str(o))))
    j = sessao.get(url(p, f".{d}.json"), timeout=120).json()

    def desce(no, cam, nivel):
        for k, v in list(no.items()):
            if isinstance(v, dict):
                if nivel + 1 >= d:
                    no[k] = fundo(f"{cam}/{k}")
                else:
                    desce(v, f"{cam}/{k}", nivel + 1)
    desce(j, p, 0)
    return j


def aborta(msg):
    sys.exit(f"\n[ABORTADO] {msg}")


def _pode_gravar(caminho, lista_g=()):
    """copia-teste: só STG/ANTES/ENSAIO. global2: só caminho EXATO da lista do plano. GWI: nunca."""
    if "macnicagwi" in caminho:
        aborta(f"escrita em caminho do GWI — o GWI é SOMENTE LEITURA: {caminho}")
    if any(caminho == r or caminho.startswith(r + "/") for r in (STG, ANTES, ENSAIO)):
        return
    if caminho in lista_g:
        return
    aborta(f"escrita fora da lista branca: {caminho}")


def post(caminho, dados, executar, lista_g=()):
    _pode_gravar(caminho, lista_g)
    if not executar:
        return "dry"
    r = sessao.post(url(caminho), data={**dados, "_charset_": "utf-8"}, timeout=900)
    if r.status_code not in (200, 201):
        aborta(f"HTTP {r.status_code} gravando {caminho}: {r.text[:300]}")
    return r.status_code


def copiar(origem, destino, executar, lista_g=()):
    """:operation=copy servidor-a-servidor. A ORIGEM recebe o POST: nunca GWI; destino na lista branca."""
    if "macnicagwi" in origem:
        aborta(f"origem no GWI numa operação de escrita: {origem}")
    _pode_gravar(destino, lista_g)
    if not (origem.startswith(T + "/") or origem.startswith(STG + "/") or origem.startswith(G + "/")
            or any(origem == f"{XF_T}/{x}" for x in XFS)):
        aborta(f"origem inesperada para copy: {origem}")
    if not executar:
        return "dry"
    r = sessao.post(url(origem), data={":operation": "copy", ":dest": destino, "_charset_": "utf-8"}, timeout=900)
    if r.status_code not in (200, 201):
        aborta(f"copy falhou HTTP {r.status_code}: {origem} -> {destino}\n{r.text[:300]}")
    return r.status_code


def apagar(caminho, executar, lista_g=()):
    _pode_gravar(caminho, lista_g)
    if not executar:
        return "dry"
    r = sessao.post(url(caminho), data={":operation": "delete"}, timeout=300)
    if r.status_code not in (200, 204):
        aborta(f"delete falhou HTTP {r.status_code}: {caminho}\n{r.text[:300]}")
    return r.status_code


def registra(op, destino, extra=None):
    with open(MANIFESTO, "a") as f:
        f.write(json.dumps({"quando": datetime.datetime.now().isoformat(timespec="seconds"), "op": op,
                            "destino": destino, **(extra or {})}, ensure_ascii=False) + "\n")


def paginas(raiz):
    """rels (relativos a raiz, sem barra inicial) de toda cq:Page debaixo de raiz, raiz incluída como ''.
    Percorre a árvore com .1.json — NÃO o querybuilder: o índice é assíncrono e, logo depois de um copy/move,
    ainda não vê o nó (o `careers` renomeado sumiu da contagem em 23/09)."""
    out = []

    def anda(cam, rel):
        st, j = ler(cam, ".1.json")
        if st != 200:
            return
        if j.get("jcr:primaryType") == "cq:Page":
            out.append(rel)
        for k, v in j.items():
            if isinstance(v, dict) and k != "jcr:content" and v.get("jcr:primaryType") in ("cq:Page", "sling:Folder", "sling:OrderedFolder"):
                anda(f"{cam}/{k}", f"{rel}/{k}".strip("/"))
    anda(raiz, "")
    return sorted(out)


def componentes(jc):
    n = 0

    def anda(no):
        nonlocal n
        for v in no.values():
            if isinstance(v, dict):
                rt = str(v.get("sling:resourceType", "")).rsplit("/", 1)[-1]
                if rt and rt not in ("container", "responsivegrid", "flexcontainer", "flexcontaineritem"):
                    n += 1
                anda(v)
    if isinstance(jc, dict) and isinstance(jc.get("root"), dict):
        anda(jc["root"])
    return n


def norm_rel(rel):
    return "/".join(normalize_name(x) for x in rel.split("/")) if rel else rel


# ---------------------------------------------------------------- ensaio
def ensaio(executar):
    """Página de rascunho com mix:versionable; troca o jcr:content pelo de uma página de T; relê."""
    fonte = f"{T}/about-us/company-profile/jcr:content"
    alvo = f"{ENSAIO}/pagina"
    print(f"ensaio: {alvo}  <- jcr:content de {fonte}")
    if ler(ENSAIO)[0] == 404:
        print("  pasta:", post(ENSAIO, {"jcr:primaryType": "sling:Folder"}, executar))
    if ler(alvo)[0] == 404:
        print("  página:", post(alvo, {"jcr:primaryType": "cq:Page", "jcr:content/jcr:primaryType": "cq:PageContent",
                                        "jcr:content/jcr:title": "ensaio (apagar)", "jcr:content/jcr:mixinTypes": "mix:versionable",
                                        "jcr:content/cq:template": "/conf/macnicaglobal2/settings/wcm/templates/mai-page-content",
                                        "jcr:content/sling:resourceType": "macnicaglobal2/components/page"}, executar))
    print("  apaga jcr:content:", apagar(f"{alvo}/jcr:content", executar))
    print("  copia:", copiar(fonte, f"{alvo}/jcr:content", executar))
    if executar:
        _, a = ler(fonte, ".infinity.json")
        _, b = ler(f"{alvo}/jcr:content", ".infinity.json")
        print(f"  componentes fonte={componentes(a)} ensaio={componentes(b)}  título={b.get('jcr:title')!r}  root={'root' in b}")
        r = sessao.get(url(alvo, ".html?wcmmode=disabled"), timeout=90)
        print(f"  render {r.status_code}, {len(r.text)} bytes")


# ---------------------------------------------------------------- staging
def staging(executar):
    print(f"staging {STG}")
    if ler(STG)[0] == 404:
        print("  raiz:", post(STG, {"jcr:primaryType": "sling:Folder", "jcr:title": "STAGING do go-live mai/en — NÃO EDITAR"}, executar))
    for r in RAIZES:
        st, _ = ler(f"{STG}/{r}")
        print(f"  {r}:", "já está" if st == 200 else copiar(f"{T}/{r}", f"{STG}/{r}", executar))
    for rel, motivo in FORA.items():
        st, _ = ler(f"{STG}/{rel}")
        if st == 200 or not executar:
            print(f"  tira {rel} ({motivo}):", apagar(f"{STG}/{rel}", executar) if st == 200 else "dry")
    for rel in FALTANTES:                               # o ramo já estava no staging: a página vem sozinha de T
        if ler(f"{STG}/{rel}")[0] == 404:
            print(f"  traz {rel} (faltante):", copiar(f"{T}/{rel}", f"{STG}/{rel}", executar))
    # nome normalizado: move no próprio staging, do mais fundo para o mais raso
    for rel in sorted(paginas(STG) if executar else [], key=lambda x: -x.count("/")):
        seg = rel.rsplit("/", 1)[-1]
        if rel and normalize_name(seg) != seg:
            pai = rel.rsplit("/", 1)[0] if "/" in rel else ""
            novo = f"{STG}/{pai}/{normalize_name(seg)}".replace("//", "/")
            print(f"  renomeia {rel} -> {normalize_name(seg)}")
            _pode_gravar(f"{STG}/{rel}"); _pode_gravar(novo)
            sessao.post(url(f"{STG}/{rel}"), data={":operation": "move", ":dest": novo, "_charset_": "utf-8"}, timeout=300)
    if executar:
        tem = paginas(STG)
        t = [norm_rel(p) for p in sum(([f"{r}/{x}".strip("/") for x in paginas(f"{T}/{r}")] for r in RAIZES), [])
             if not any(p == f or p.startswith(f + "/") for f in FORA)]
        print(f"  páginas: T no escopo {len(t)}, staging {len([x for x in tem if x])}; "
              f"faltando {sorted(set(t) - set(tem))[:5]}; sobrando {sorted(set(tem) - set(t) - {''})[:5]}")


# ---------------------------------------------------------------- reescrita
class Reescrita:
    def __init__(self):
        L = json.load(open(LEVANTAMENTO))
        self.assets = {}
        for u, v in L["assets"].items():
            if v["igual"] in ("=", "≠", "JÁ-G2", "G2-404") and v["G"]:
                self.assets[u] = v["G"][0]
            elif v["igual"] == "VÁRIOS":
                boas = [p for p in v["G"] if not re.search(r"/(products|technology|solutions)/", p[len(DAM_G):])]
                self.assets[u] = boas[0] if len(boas) == 1 else None
            elif v["igual"] == "SEM-PAR" and "/images/icons/" in u:
                self.assets[u] = f"{ICONES}/{u.rsplit('/', 1)[-1]}"
            else:
                self.assets[u] = None
        self.escopo = {f"{G}/{p}".rstrip("/") for p in paginas(STG)}
        self.existe = {}
        self.pendentes = {}

    def _vivo(self, p):
        if p in self.escopo:
            return True
        if p not in self.existe:
            st, _ = ler(p)
            self.existe[p] = st == 200
        return self.existe[p]

    def pagina(self, u):
        m = re.match(r"^([^#?]*?)(\.html)?([#?].*)?$", u)
        caminho, ext, resto = m.group(1).rstrip("/"), m.group(2) or "", m.group(3) or ""
        original = caminho                               # link do global2 que já está certo não se mexe (nem a barra final)
        publico = False
        for de in ("https://www.macnica.com/americas/mai/en", "http://www.macnica.com/americas/mai/en"):
            if caminho == de or caminho.startswith(de + "/"):
                caminho, publico = G + caminho[len(de):], True
        for de in (T, W):
            if caminho == de or caminho.startswith(de + "/"):
                caminho = G + caminho[len(de):]
        if not caminho.startswith("/content/macnicaglobal2/"):
            return u
        cands = [caminho]
        if caminho.startswith(G):
            cands.append(G + "/" + norm_rel(caminho[len(G) + 1:]) if len(caminho) > len(G) else G)
        for c in list(cands):
            for de, para in FIXOS:
                if c == de or c.startswith(de + "/"):
                    cands.append(para + c[len(de):])
        cands = list(dict.fromkeys(cands))
        alvo = next((c for c in cands if c in self.escopo), None) or next((c for c in cands if self._vivo(c)), None)
        if alvo is None:
            alvo = cands[1] if len(cands) > 1 else cands[0]
            self.pendentes.setdefault(alvo, set()).add(u)
        if alvo == original and not resto.startswith("#tabs-"):
            return u
        if resto.startswith("#tabs-"):
            resto = ""
        return alvo + (".html" if (ext or publico) else "") + resto

    def uma(self, u):
        dec = unquote(u.strip())
        if dec.split("?")[0] in self.assets:
            novo = self.assets[dec.split("?")[0]]
            if novo is None:
                self.pendentes.setdefault("ASSET SEM DESTINO", set()).add(dec)
                return u
            return novo
        for x in XFS:
            if dec == f"{XF_T}/{x}" or dec.startswith(f"{XF_T}/{x}/"):
                return XF_G + dec[len(XF_T):]
        if dec.startswith("/content/usergenerated/copia-teste/"):
            return dec.replace("/content/usergenerated/copia-teste/", "/content/usergenerated/macnicaglobal2/")
        if dec.startswith(("/content/", "http://www.macnica.com/americas/mai/en", "https://www.macnica.com/americas/mai/en")):
            return self.pagina(dec)
        return u

    def valor(self, v):
        if not isinstance(v, str) or ("/content/" not in v and "macnica.com/americas/mai/en" not in v):
            return v
        if "<" not in v and v.strip().startswith(("/content/", "http://", "https://")):
            novo = self.uma(v)
            return novo if novo != v.strip() else v

        def attr(m):
            antigo = html.unescape(m.group(3))
            novo = self.uma(antigo)
            return m.group(0) if novo == antigo.strip() else f"{m.group(1)}{m.group(2)}{html.escape(novo, quote=True)}{m.group(2)}"
        return ATRIBUTO.sub(attr, v)

    def mudancas(self, no, caminho, saida, sobras):
        for k, v in no.items():
            if isinstance(v, dict):
                self.mudancas(v, f"{caminho}/{k}", saida, sobras)
            elif k not in IGNORAR and isinstance(v, (str, list)):
                novo = [self.valor(x) for x in v] if isinstance(v, list) else self.valor(v)
                if novo != v:
                    saida.append((caminho, k, v, novo))
                for x in (novo if isinstance(novo, list) else [novo]):
                    if isinstance(x, str) and PROIBIDO.search(x):
                        sobras.append((caminho, k, x[:160]))


def _forms(no, caminho, out):
    for k, v in no.items():
        if isinstance(v, dict):
            if re.search(r"/form/container$", str(v.get("sling:resourceType", ""))):
                out.append((f"{caminho}/{k}", v))
            _forms(v, f"{caminho}/{k}", out)
    return out


def gwi_de(rel):
    """Página do GWI que corresponde ao rel normalizado: o GWI guarda MAIÚSCULAS (Careers, iENSO-…)."""
    cam = W
    for seg in rel.split("/"):
        if ler(f"{cam}/{seg}")[0] == 200:
            cam = f"{cam}/{seg}"
            continue
        irmaos = ler(cam, ".1.json")[1] or {}
        gw = next((k for k in irmaos if isinstance(irmaos[k], dict) and normalize_name(k) == seg), None)
        if gw is None:
            return None
        cam = f"{cam}/{gw}"
    return cam


POPUPS = "/content/experience-fragments/macnicaglobal2/americas/mai/en/site/popups"


def reescrever(executar, so=None):
    R = Reescrita()
    rels = [r for r in paginas(STG) if not so or r in so]
    print(f"{'EXECUTANDO' if executar else 'dry-run'} — {len(rels)} páginas no staging")
    log, sobras, n = [], [], 0
    for rel in rels:
        if not rel:
            continue
        jc_path = f"{STG}/{rel}/jcr:content"
        st, jc = ler(jc_path, ".infinity.json")
        if st != 200 or not isinstance(jc, dict):
            aborta(f"HTTP {st} lendo {jc_path}")
        muda = []
        R.mudancas(jc, jc_path, muda, sobras)
        props = {}
        # canonical = o próprio caminho no global2 (convenção do projeto)
        if jc.get("cq:canonicalUrl") != f"{G}/{rel}":
            props["cq:canonicalUrl"] = f"{G}/{rel}"
        # GWI: menu e redirect (a grafia de T ainda é a do GWI no levantamento; aqui o rel já é normalizado)
        w_pag = gwi_de(rel)
        w = (ler(f"{w_pag}/jcr:content")[1] or {}) if w_pag else {}
        oculta = w.get("hideInNav") == "true" or rel.startswith(FOLHAS_OCULTAS)
        if oculta and jc.get("hideInNav") != "true":
            props["hideInNav"] = "true"
        elif not oculta and jc.get("hideInNav"):
            props["hideInNav@Delete"] = ""
        if w.get("cq:redirectTarget") and not jc.get("cq:redirectTarget"):
            props["cq:redirectTarget"] = w["cq:redirectTarget"]
            if w.get("cq:redirectPermanent"):
                props["cq:redirectPermanent"] = w["cq:redirectPermanent"]
            if w.get("linkTarget"):
                props["linkTarget"] = w["linkTarget"]
        # destinatários de form vazios <- GWI (default_*); store -> macnicadefault como no GWI
        ft = _forms(jc, jc_path, [])
        fw = _forms(ler(f"{w_pag}/jcr:content", ".infinity.json")[1] or {}, "", []) if ft and w_pag else []
        if ft and len(ft) == len(fw):
            for (cam, f), (_, g) in zip(ft, fw):
                fp = {}
                if not f.get("macnicadefault_mailto") and g.get("default_mailto"):
                    fp.update({"macnicadefault_mailto": g["default_mailto"], "macnicadefault_mailto@TypeHint": "String[]"})
                    if not f.get("macnicadefault_subject") and g.get("default_subject"):
                        fp["macnicadefault_subject"] = g["default_subject"]
                    if g.get("default_mailcc") and not f.get("macnicadefault_mailcc"):
                        fp.update({"macnicadefault_mailcc": g["default_mailcc"], "macnicadefault_mailcc@TypeHint": "String[]"})
                    if f.get("actionType", "").endswith("/store"):
                        fp["actionType"] = "macnicaglobal2/components/form/actions/macnicadefault"
                    if not f.get("successFragmentPath"):
                        fp.update({"successFragmentPath": f"{POPUPS}/form-success/master", "errorFragmentPath": f"{POPUPS}/form-error/master"})
                if fp:
                    log.append([rel, cam[len(jc_path):] or "/", "FORM", "", json.dumps(fp, ensure_ascii=False)])
                    if executar:
                        post(cam, {k: (v if not isinstance(v, list) else v) for k, v in fp.items()}, True)
        elif ft:
            log.append([rel, "-", "FORM", f"{len(ft)} form(s) em T x {len(fw)} no GWI", "não casado — conferir à mão"])
        for caminho, prop, antes, depois in muda:
            log.append([rel, caminho[len(jc_path):] or "/", prop, antes, depois])
            if executar:
                post(caminho, {prop: depois, f"{prop}@TypeHint": "String[]"} if isinstance(depois, list) else {prop: depois}, True)
        for k, v in props.items():
            log.append([rel, "/", k, jc.get(k.split("@")[0], ""), v])
        if props and executar:
            post(jc_path, props, True)
        n += bool(muda or props)
    import collections
    import csv
    with open(DADOS / f"reescrita_mai_en_{'exec' if executar else 'dry'}{'_so' if so else ''}.csv", "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["pagina", "no", "prop", "antes", "depois"]); wr.writerows(log)
    print(f"{len(log)} mudanças em {n} páginas:", dict(collections.Counter(l[2] for l in log)))
    for alvo, us in R.pendentes.items():
        print(f"  [PENDENTE] {alvo[len(G):] if alvo.startswith(G) else alvo}  <- {sorted(us)[:2]}")
    for s in sobras[:20]:
        print("  [SOBROU]", s)
    print(f"sobras proibidas: {len(sobras)}; alvos pendentes: {len(R.pendentes)}")


# ---------------------------------------------------------------- conferir
def conferir(so=None):
    R = Reescrita()
    rels = [r for r in paginas(STG) if r and (not so or r in so)]
    refs, sobras = [], []
    for rel in rels:
        _, jc = ler(f"{STG}/{rel}/jcr:content", ".infinity.json")
        m = []
        R.mudancas(jc, rel, m, sobras)
        refs += m
    print(f"{len(rels)} páginas; mudanças que a reescrita ainda faria: {len(refs)}; refs proibidas: {len(sobras)}")
    for x in (refs + sobras)[:15]:
        print("  ", x)
    for alvo, us in R.pendentes.items():
        print(f"  [PENDENTE] {alvo}  <- {sorted(us)[:2]}")


# ---------------------------------------------------------------- plano / gravar
def plano():
    rels = [r for r in paginas(STG) if r]
    criar, trocar, bloqueado = [], [], []
    novos = set()
    for rel in sorted(rels, key=lambda x: (x.count("/"), x)):
        alvo = f"{G}/{rel}"
        st, j = ler(alvo)
        if st == 404:
            pai = alvo.rsplit("/", 1)[0]
            if any(alvo.startswith(n + "/") for n in novos):
                continue                                  # vai junto com o ancestral novo
            if ler(pai)[0] != 200:
                bloqueado.append((rel, f"pai {pai} não existe em G"))
                continue
            irmaos = ler(pai, ".1.json")[1] or {}
            gemeos = [k for k in irmaos if k != rel.rsplit("/", 1)[-1] and normalize_name(k) == rel.rsplit("/", 1)[-1]]
            novos.add(alvo)
            criar.append({"rel": rel, "destino": alvo, "gemeos": gemeos,
                          "descendentes": len([r for r in rels if r.startswith(rel + "/")])})
        elif st == 200 and rel in CASCAS:
            _, jc = ler(f"{alvo}/jcr:content", ".infinity.json")
            cri, por, maxc = CASCAS[rel]
            c = componentes(jc)
            ok = j.get("jcr:createdBy", "").startswith(cri) and str(jc.get("cq:lastModifiedBy", "")).startswith(por) and c <= maxc
            (trocar if ok else bloqueado).append({"rel": rel, "destino": alvo, "criador": j.get("jcr:createdBy"),
                                                   "por": jc.get("cq:lastModifiedBy"), "mod": jc.get("cq:lastModified"),
                                                   "componentes": c} if ok else (rel, f"casca mudou: {j.get('jcr:createdBy')} {jc.get('cq:lastModifiedBy')} {c}c"))
        else:
            bloqueado.append((rel, f"existe em G e não é casca permitida (HTTP {st})"))
    extras = []
    _, cu = ler(f"{G}/contact-us/jcr:content", ".infinity.json")
    extras.append({"destino": f"{G}/contact-us/jcr:content", "por": cu.get("cq:lastModifiedBy"), "mod": cu.get("cq:lastModified"),
                   "componentes": componentes(cu), "props": {"cq:redirectTarget": f"{G}/contact/form"}})
    _, ca = ler(f"{G}/about-us/Careers/jcr:content", ".infinity.json")
    _, cw = ler(f"{W}/about-us/Careers/jcr:content")
    extras.append({"destino": f"{G}/about-us/Careers/jcr:content", "por": ca.get("cq:lastModifiedBy"), "mod": ca.get("cq:lastModified"),
                   "componentes": componentes(ca), "props": {"cq:redirectTarget": cw["cq:redirectTarget"],
                                                            "cq:redirectPermanent": cw.get("cq:redirectPermanent", "true"),
                                                            "linkTarget": cw.get("linkTarget", "_blank"), "hideInNav": "true"}})
    assets = []
    for u, v in json.load(open(LEVANTAMENTO))["assets"].items():
        if v["igual"] == "SEM-PAR" and "/images/icons/" in u:
            dest = f"{ICONES}/{u.rsplit('/', 1)[-1]}"
            if ler(dest)[0] == 404:
                assets.append({"origem": u, "destino": dest})
    xfs = []
    for x in XFS:
        st, _ = ler(f"{XF_G}/{x}")
        if st == 404:
            xfs.append({"origem": f"{XF_T}/{x}", "destino": f"{XF_G}/{x}"})
        elif st != 200 or not str((ler(f"{XF_G}/{x}/master/jcr:content")[1] or {}).get("jcr:createdBy", "")).startswith("valter"):
            bloqueado.append((x, f"XF já existe em G e não é nosso (HTTP {st})"))
    p = {"quando": datetime.datetime.now().isoformat(timespec="seconds"), "criar": criar, "trocar": trocar, "xfs": xfs,
         "extras": extras, "assets": assets, "bloqueado": bloqueado}
    json.dump(p, open(PLANO, "w"), indent=1, ensure_ascii=False)
    print(f"criar {len(criar)} nós (+{sum(c['descendentes'] for c in criar)} descendentes), trocar {len(trocar)} jcr:content, "
          f"extras {len(extras)}, assets {len(assets)}, BLOQUEADO {len(bloqueado)}")
    for c in criar:
        print(f"  CRIAR  {c['rel']}" + (f"  (+{c['descendentes']})" if c["descendentes"] else "") + (f"  gêmeos={c['gemeos']}" if c["gemeos"] else ""))
    for t in trocar:
        print(f"  TROCAR {t['rel']}  ({t['criador']}/{t['por']}, {t['componentes']}c)")
    for e in extras:
        print(f"  EXTRA  {e['destino'][len(G):]}  ({e['por']}, {e['componentes']}c) {e['props']}")
    for a in assets:
        print(f"  ASSET  {a['destino'][len(DAM_G):]}")
    for x in xfs:
        print(f"  XF     {x['destino']}")
    for b in bloqueado:
        print(f"  BLOQUEADO {b}")
    print(f"JSON: {PLANO}")


def gravar(executar, lote):
    p = json.load(open(PLANO))
    if p["bloqueado"]:
        aborta(f"o plano tem {len(p['bloqueado'])} bloqueio(s) — resolver antes")
    lista = {x["destino"] for x in p["criar"]} | {f"{x['destino']}/jcr:content" for x in p["trocar"]} \
        | {x["destino"] for x in p["extras"]} | {x["destino"] for x in p["assets"]} | {ICONES} \
        | {x["destino"] for x in p.get("xfs", [])}
    print(f"{'EXECUTANDO' if executar else 'dry-run'} lote={lote}")
    if lote == "assets":
        if ler(ICONES)[0] == 404:
            print("  pasta icons:", post(ICONES, {"jcr:primaryType": "sling:Folder", "jcr:title": "icons"}, executar, lista))
        for a in p["assets"]:
            if ler(a["destino"])[0] != 404:
                print(f"  já existe {a['destino']}"); continue
            nome = a["destino"].rsplit("/", 1)[-1]
            print(f"  {nome}:", post(ICONES, {f"./{nome}@CopyFrom": a["origem"]}, executar, lista))
            if executar:
                registra("asset", a["destino"], {"origem": a["origem"]})
    elif lote == "xf":
        for x in p.get("xfs", []):
            if ler(x["destino"])[0] != 404:
                aborta(f"{x['destino']} passou a existir depois do plano — não sobrescrevo")
            print(f"  {x['destino']}:", copiar(x["origem"], x["destino"], executar, lista))
            if executar:
                registra("copy-xf", x["destino"], {"origem": x["origem"]})
    elif lote == "criar":
        for c in p["criar"]:
            if ler(c["destino"])[0] != 404:
                aborta(f"{c['destino']} passou a existir depois do plano — não sobrescrevo")
            print(f"  {c['rel']}:", copiar(f"{STG}/{c['rel']}", c["destino"], executar, lista))
            if executar:
                registra("copy", c["destino"], {"origem": f"{STG}/{c['rel']}"})
    elif lote == "cascas":
        pasta = ANTES
        if ler(pasta)[0] == 404:
            print("  backup:", post(pasta, {"jcr:primaryType": "sling:Folder"}, executar))
        for t in p["trocar"]:
            jc_path = f"{t['destino']}/jcr:content"
            _, jc = ler(jc_path, ".infinity.json")
            if jc.get("cq:lastModified") != t["mod"] or componentes(jc) != t["componentes"]:
                aborta(f"{jc_path} mudou depois do plano ({jc.get('cq:lastModifiedBy')} {jc.get('cq:lastModified')}) — re-planejar")
            bk = DADOS / "backup_mai-en"
            bk.mkdir(exist_ok=True)
            (bk / (t["rel"].replace("/", "__") + ".json")).write_text(json.dumps(jc, ensure_ascii=False, indent=1))
            plano_copia = f"{ANTES}/{t['rel'].replace('/', '__')}"
            if ler(plano_copia)[0] == 404:
                post(plano_copia, {"jcr:primaryType": "cq:Page"}, executar)
                copiar(jc_path, f"{plano_copia}/jcr:content", executar, lista | {jc_path})
            print(f"  {t['rel']}: backup ok; apaga", apagar(jc_path, executar, lista), "; copia",
                  copiar(f"{STG}/{t['rel']}/jcr:content", jc_path, executar, lista))
            if executar:
                _, novo = ler(jc_path, ".infinity.json")
                _, fonte = ler(f"{STG}/{t['rel']}/jcr:content", ".infinity.json")
                if componentes(novo) != componentes(fonte):
                    aborta(f"{jc_path}: {componentes(novo)} componentes x {componentes(fonte)} no staging")
                registra("troca-jcr:content", jc_path, {"backup": plano_copia})
    elif lote == "extras":
        for e in p["extras"]:
            _, jc = ler(e["destino"], ".infinity.json")
            if jc.get("cq:lastModified") != e["mod"] or componentes(jc) != e["componentes"]:
                aborta(f"{e['destino']} mudou depois do plano — re-planejar")
            bk = DADOS / "backup_mai-en"
            bk.mkdir(exist_ok=True)
            (bk / (e["destino"][len(G) + 1:].replace("/", "__") + ".json")).write_text(json.dumps(jc, ensure_ascii=False, indent=1))
            print(f"  {e['destino'][len(G):]}:", post(e["destino"], e["props"], executar, lista), e["props"])
            if executar:
                registra("props", e["destino"], {"props": e["props"], "antes": {k: jc.get(k) for k in e["props"]}})
    else:
        aborta("lote: assets | xf | criar | cascas | extras")


def faltantes(executar):
    """FALTANTES: STG -> G, sem plano.json (o `plano` de agora bloquearia as 125 que já estão em G). Destino tem
    de ser 404 com o pai existente; o staging tem de estar reescrito (canonical = caminho em G); lista branca =
    os caminhos exatos."""
    lista = {f"{G}/{rel}" for rel in FALTANTES}
    print(f"{'EXECUTANDO' if executar else 'dry-run'} — faltantes {list(FALTANTES)}")
    for rel in FALTANTES:
        destino = f"{G}/{rel}"
        st_t, jt = ler(f"{T}/{rel}/jcr:content")
        st_s, js = ler(f"{STG}/{rel}/jcr:content")
        print(f"  {rel}: T {st_t} ({(jt or {}).get('cq:lastModifiedBy')} {(jt or {}).get('cq:lastModified')}), STG {st_s}")
        if st_s != 200:
            aborta(f"{STG}/{rel} não existe — rode `staging --executar` antes")
        if js.get("cq:canonicalUrl") != destino:
            aborta(f"{STG}/{rel} não está reescrita (canonical {js.get('cq:canonicalUrl')!r}) — rode `reescrever --so {rel}`")
        if ler(destino)[0] != 404:
            aborta(f"{destino} já existe — não sobrescrevo")
        if ler(destino.rsplit("/", 1)[0])[0] != 200:
            aborta(f"pai de {destino} não existe em G")
        print(f"    -> {destino}:", copiar(f"{STG}/{rel}", destino, executar, lista))
        if executar:
            registra("copy", destino, {"origem": f"{STG}/{rel}", "motivo": "faltante (D3 errado), decisão do Hazael 23/09"})


def conferir_g(tela, so=None):
    """Depois da gravação: cada página do STG existe em G com os mesmos componentes, menu, canonical e
    redirect; com --tela, a geometria a 1400px (comparar_render.mede) STG x G."""
    rels = [r for r in paginas(STG) if r and (not so or r in so)]
    ruins = []
    for rel in rels:
        _, a = ler(f"{STG}/{rel}/jcr:content", ".infinity.json")
        st, b = ler(f"{G}/{rel}/jcr:content", ".infinity.json")
        if st != 200:
            ruins.append((rel, f"HTTP {st} em G")); continue
        dif = [k for k in ("hideInNav", "cq:canonicalUrl", "cq:redirectTarget", "cq:template", "jcr:title")
               if a.get(k) != b.get(k)]
        if componentes(a) != componentes(b) or dif:
            ruins.append((rel, f"componentes STG {componentes(a)} x G {componentes(b)}; props diferentes {dif}"))
    print(f"{len(rels)} páginas; {len(rels) - len(ruins)} iguais ao staging no JCR; diferentes: {len(ruins)}")
    for r in ruins:
        print("  ", r)
    if tela:
        from multiprocessing import Pool
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from comparar_render import mede
        from aem_lib import parse_cookie_string
        env = dict(l.strip().split("=", 1) for l in open(_RAIZ / ".env") if l.startswith("AEM_COOKIES="))
        cookies = parse_cookie_string(env["AEM_COOKIES"].strip().strip('"').strip("'"))
        sem_redirect = [r for r in rels if not (ler(f"{STG}/{r}/jcr:content")[1] or {}).get("cq:redirectTarget")]
        with Pool(6) as pool:
            res = pool.map(mede, [(BASE, cookies, BASE.split("//", 1)[1], (STG + "/", G + "/"), r) for r in sem_redirect], chunksize=1)
        json.dump(res, open(DADOS / "render_mai_en_STG_x_G.json", "w"))
        dif = []
        for r in res:
            A, B = r.get("A", {}), r.get("B", {})
            if A.get("http") != 200 or B.get("http") != 200:
                dif.append((r["rel"], f"http {A.get('http')} x {B.get('http')}"))
            elif A["rows"] != B["rows"] or B["quebradas"] or A["total"] != B["total"]:
                dif.append((r["rel"], f"altura {A['altura']} x {B['altura']}; imagens {A['total']} x {B['total']}; quebradas em G {B['quebradas'][:2]}"))
        print(f"tela: {len(res)} páginas (sem as de redirect); diferentes: {len(dif)}")
        for d in dif:
            print("  ", d)
        for r in [r for r in rels if r not in sem_redirect]:
            x = sessao.get(url(f"{G}/{r}", ".html?wcmmode=disabled"), allow_redirects=False, timeout=60)
            print(f"   redirect {r}: {x.status_code} -> {x.headers.get('Location')}")


if __name__ == "__main__":
    passo = sys.argv[1] if len(sys.argv) > 1 else ""
    ex = "--executar" in sys.argv
    # --so REL… : reescrever / conferir / conferir-g só nestas páginas do staging
    so = None
    if "--so" in sys.argv:
        i = sys.argv.index("--so") + 1
        so = []
        while i < len(sys.argv) and not sys.argv[i].startswith("--"):
            so.append(sys.argv[i].strip("/")); i += 1
    if passo == "ensaio":
        ensaio(ex)
    elif passo == "staging":
        staging(ex)
    elif passo == "reescrever":
        reescrever(ex, so)
    elif passo == "conferir":
        conferir(so)
    elif passo == "plano":
        plano()
    elif passo == "faltantes":
        faltantes(ex)
    elif passo == "conferir-g":
        conferir_g("--tela" in sys.argv, so)
    elif passo == "gravar":
        gravar(ex, sys.argv[sys.argv.index("--lote") + 1] if "--lote" in sys.argv else "")
    else:
        print(__doc__)
