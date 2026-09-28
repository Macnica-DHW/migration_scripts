"""
_comum.py — o que TODA ferramenta de go-live usa para gravar. Não é para rodar.

Regra do Hazael (21/09/2026): não sobrescrever NADA da Anion. `canon`, `design-gateway` e a landing
ficam fora; só entram as famílias que não existem no global2. Por isso toda escrita passa por
`gravar()`/`copiar()`, que:

  1. só aceita destino dentro da LISTA BRANCA abaixo (nunca a árvore revisada T, nunca outro ponto
     do global2);
  2. relê o destino AO VIVO imediatamente antes: tem que dar 404 — comparando também sem
     maiúsculas com os irmãos de lá —, ou ser algo que ESTA ferramenta criou (está no manifesto);
  3. aborta se o que existe foi criado/modificado por outra pessoa;
  4. nunca manda `:replace` — o próprio Sling recusa (412) sobrescrever.

Tudo que é criado vai para dados/golive/manifesto.jsonl: é a lista do que desfazer.

A Session é a travada do aem_lib: AEM_BLOQUEAR_EDITADAS_MIN=N na linha de comando recusa gravar em página
editada nos últimos N minutos (alguém trabalhando nela).
"""
import datetime
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote

_RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_RAIZ / "scripts-hazael"))
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, build_session, contas_nossas, eh_nossa  # noqa: E402,F401

DADOS = Path(__file__).resolve().parents[2] / "dados" / "golive"
MANIFESTO = DADOS / "manifesto.jsonl"

MAI = "/content/macnicaglobal2/americas/mai/en"
T = "/content/copia-teste/americas/mai/en/products/semiconductors-remigration"      # revisada: NUNCA gravar
STG = "/content/copia-teste/americas/mai/en/products/semiconductors-golive"          # staging
G = f"{MAI}/products/semiconductors"
DAM_G2 = "/content/dam/macnicaglobal2/americas/mai/en/products/semiconductors"
XF_T = "/content/experience-fragments/copia-teste/americas/mai/en/site"
XF_G2 = "/content/experience-fragments/macnicaglobal2/americas/mai/en/site"

# Contas "nossas" (aem_lib.CONTAS_NOSSAS: valter.toffolo e bruno.jaques). Padrão: as duas; quem roda escolhe na
# linha de comando com AEM_CONTAS_NOSSAS=valter|bruno|ambas, e quem importa pode chamar contas_nossas(...).
NOSSAS = contas_nossas()
SEGURAR = {"canon", "design-gateway"}                 # da Anion — não entram
TESTE = {"/ambarella/test-277-gwi-base-page", "/ambarella/test-277-product-detail-page",
         "/ambarella/test-autogenerate-list-ambarella-n1-soc-html", "/ambarella/test-fixed-list-ambarella-n1-soc"}
# pasta do DAM por família (a Anion usa nome curto de marca: canon, sony, deepx, designgateway)
PASTA_DAM = {"namuga-advanced-camera-and-3d-sensing-solutions-for-intelligent-systems": "namuga",
             "toppan-3d-tof-sensing-solutions": "toppan"}

BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE     # cookie só vai para o author
sessao, _auth = build_session()


class Abortar(SystemExit):
    pass


def aborta(msg):
    print(f"\n[ABORTADO] {msg}", file=sys.stderr)
    raise Abortar(1)


def url(path, sufixo=""):
    return BASE + quote(unquote(path), safe="/:") + sufixo


def ler(path, sufixo=".json"):
    """(status, json|None). Só GET."""
    r = sessao.get(url(path, sufixo), timeout=90, allow_redirects=False)
    try:
        return r.status_code, (r.json() if r.status_code == 200 else None)
    except ValueError:
        return r.status_code, None


def filhos(path, tipo=None):
    st, j = ler(path, ".1.json")
    return [k for k, v in (j or {}).items()
            if isinstance(v, dict) and (tipo is None or v.get("jcr:primaryType") == tipo)]


def familias():
    """As famílias que entram: filhas de T, menos as seguradas. Lido ao vivo."""
    return sorted(f for f in filhos(T, "cq:Page") if f not in SEGURAR)


def lista_branca():
    fams = familias()
    dam = {PASTA_DAM.get(f, f) for f in fams} | {"common"}
    return ([STG] + [f"{G}/{f}" for f in fams] + [f"{DAM_G2}/{d}" for d in sorted(dam)] + [XF_G2])


def _na_lista(path):
    return any(path == p or path.startswith(p + "/") for p in lista_branca())


def manifesto():
    if not MANIFESTO.exists():
        return []
    return [json.loads(l) for l in MANIFESTO.read_text().splitlines() if l.strip()]


def _criado_por_nos(path):
    return any(m["destino"] == path and m["status"] in (200, 201) for m in manifesto())


def _registra(op, origem, destino, status):
    DADOS.mkdir(parents=True, exist_ok=True)
    with open(MANIFESTO, "a") as f:
        f.write(json.dumps({"quando": datetime.datetime.now().isoformat(timespec="seconds"), "op": op,
                            "origem": origem, "destino": destino, "status": status}) + "\n")


def _norm(nome):
    return re.sub(r"[^a-z0-9]+", "-", unquote(nome).lower()).strip("-")


def destino_livre(path):
    """True se dá para CRIAR `path`. False se já é nosso (idempotente). Aborta em qualquer outro caso."""
    if not _na_lista(path):
        aborta(f"destino fora da lista branca: {path}")
    if path == T or path.startswith(T + "/"):
        aborta(f"a árvore revisada é somente leitura: {path}")
    st, j = ler(path)
    if st == 200:
        if _criado_por_nos(path):
            return False
        quem = (j or {}).get("jcr:createdBy") or ((j or {}).get("jcr:content") or {}).get("jcr:createdBy")
        aborta(f"o destino JÁ EXISTE e não foi criado por esta ferramenta (criado por {quem}): {path}\n"
               f"           Nada foi gravado. Pode ser trabalho da Anion — não sobrescrever.")
    if st != 404:
        aborta(f"HTTP {st} ao conferir {path} (cookie vencido?) — sem certeza de que está livre, não gravo")
    pai, nome = path.rsplit("/", 1)
    gemeos = [k for k in filhos(pai) if _norm(k) == _norm(nome) and k != nome]
    if gemeos:
        aborta(f"já existe irmão com o mesmo nome em outra grafia em {pai}: {gemeos} x {nome}")
    return True


def copiar(origem, destino, executar):
    """`:operation=copy` servidor-a-servidor, sem `:replace`. Devolve 'criado' | 'ja-nosso' | 'dry'."""
    # REGRA MESTRA (Hazael, 21/09/2026): nunca gravar no GWI. O copy do Sling é um POST na URL da
    # ORIGEM — não altera a origem, mas é requisição de escrita contra ela. Origem no GWI: recusar.
    if "macnicagwi" in origem or "macnicagwi" in destino:
        aborta(f"caminho do GWI numa operação de escrita — o GWI é SOMENTE LEITURA: {origem} -> {destino}")
    if not destino_livre(destino):
        return "ja-nosso"
    if not executar:
        return "dry"
    r = sessao.post(url(origem), data={":operation": "copy", ":dest": destino, "_charset_": "utf-8"}, timeout=900)
    _registra("copy", origem, destino, r.status_code)
    if r.status_code not in (200, 201):
        aborta(f"cópia falhou HTTP {r.status_code}: {origem} -> {destino}\n{r.text[:300]}")
    return "criado"


def criar(path, props, executar):
    """Cria um nó NOVO (pasta, raiz de XF, raiz do staging)."""
    if not destino_livre(path):
        return "ja-nosso"
    if not executar:
        return "dry"
    r = sessao.post(url(path), data={**props, "_charset_": "utf-8"}, timeout=120)
    _registra("create", None, path, r.status_code)
    if r.status_code not in (200, 201):
        aborta(f"criação falhou HTTP {r.status_code}: {path}\n{r.text[:300]}")
    return "criado"


def alterar(path, props, executar):
    """Altera propriedades de um nó que TEM de estar debaixo de algo que nós criamos (staging, XF novo)."""
    if not _na_lista(path):
        aborta(f"alteração fora da lista branca: {path}")
    raiz = next((m["destino"] for m in manifesto()
                 if m["status"] in (200, 201) and (path == m["destino"] or path.startswith(m["destino"] + "/"))), None)
    if raiz is None:
        aborta(f"só altero o que esta ferramenta criou; {path} não está debaixo de nada do manifesto")
    if not executar:
        return "dry"
    r = sessao.post(url(path), data={**props, "_charset_": "utf-8"}, timeout=120)
    if r.status_code not in (200, 201):
        aborta(f"alteração falhou HTTP {r.status_code}: {path}\n{r.text[:300]}")
    return "alterado"


def apagar_no_staging(path, executar):
    if not (path.startswith(STG + "/")):
        aborta(f"só apago dentro do staging: {path}")
    if not executar:
        return "dry"
    r = sessao.post(url(path), data={":operation": "delete"}, timeout=120)
    _registra("delete", None, path, r.status_code)
    return r.status_code


def retrato_global2():
    """{caminho: (criador, cq:lastModified, cq:lastModifiedBy)} de TODA página sob G — para o antes/depois."""
    r = sessao.get(BASE + "/bin/querybuilder.json", timeout=180, params={
        "path": G, "type": "cq:Page", "p.limit": "-1", "p.hits": "selective",
        "p.properties": "jcr:path jcr:createdBy jcr:content/cq:lastModified jcr:content/cq:lastModifiedBy"})
    return {h["jcr:path"]: (h.get("jcr:createdBy"), (h.get("jcr:content") or {}).get("cq:lastModified"),
                            (h.get("jcr:content") or {}).get("cq:lastModifiedBy")) for h in r.json()["hits"]}
