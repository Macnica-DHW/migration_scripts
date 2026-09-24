#!/usr/bin/env python3
"""
Biblioteca compartilhada dos scripts de migração AEM (GWI -> GLOBAL2).

Este arquivo NÃO é executável como script de migração — é o que os três
scripts principais importam:

    aem_tree.py     -> explorar (somente leitura)
    aem_migrate.py  -> criar páginas + migrar conteúdo + clonar
    aem_verify.py   -> conferir origem vs destino

Concentra tudo que antes estava duplicado em 14 arquivos: autenticação,
HTTP com fallback de profundidade, travessia da árvore, normalização de
nomes, extração de conteúdo do GWI e montagem do payload do GLOBAL2.

REGRA DE SEGURANÇA: toda escrita passa por assert_target_is_safe(), que
aborta se o caminho não estiver dentro da área de teste. macnicagwi e
macnicaglobal2 são SOMENTE LEITURA.
"""

import csv
import getpass
import html
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit

import requests

# ============================================================
# Configuração (.env)
# ============================================================

# O .env vive na pasta do projeto, um nível acima desta.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env(path=ENV_PATH):
    """Lê um .env simples (KEY=VALUE, # comenta a linha inteira).

    Não sobrescreve variáveis já exportadas no shell — ambiente ganha do
    arquivo, o que permite rodar com cookie temporário sem editar nada:
        AEM_COOKIES='...' python3 aem_tree.py /content/macnicagwi
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


load_env()


def _env(key, default=""):
    return os.environ.get(key, default)


def _env_int(key, default):
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return int(default)


def _env_float(key, default):
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _env_list(key, default=""):
    return [x.strip() for x in os.environ.get(key, default).split(";") if x.strip()]


CONFIG = {
    "base_url": _env("AEM_BASE_URL", "https://author-p53812-e590634.adobeaemcloud.com").rstrip("/"),
    "source_root": _env("AEM_SOURCE_ROOT", "/content/macnicagwi/americas/mai/en/products"),
    "gwi_prefix": _env("AEM_GWI_PREFIX", "/content/macnicagwi"),
    "global2_prefix": _env("AEM_GLOBAL2_PREFIX", "/content/macnicaglobal2"),
    "target_root": _env("AEM_TARGET_ROOT", "/content/copia-teste/americas/mai/en/products"),
    "target_prefix": _env("AEM_TARGET_PREFIX", "/content/copia-teste"),
    "templates_root": _env("AEM_TEMPLATES_ROOT", "/conf/macnicaglobal2/settings/wcm/templates"),
    "template_title": _env("AEM_TEMPLATE_TITLE", "Macnica Americas Product Page"),
    "dam_source_prefix": _env("AEM_DAM_SOURCE_PREFIX", "/content/dam/macnicagwi"),
    "dam_target_prefix": _env("AEM_DAM_TARGET_PREFIX", "/content/dam/copia-teste"),
    "ef_root": _env("AEM_EF_ROOT", "/content/experience-fragments/copia-teste/americas/mai/en/site"),
    "xf_template": _env("AEM_XF_TEMPLATE", "/conf/macnicaglobal2/settings/wcm/templates/xf-web-variation"),
    "source_depth": _env_int("AEM_SOURCE_DEPTH", 50),
    "request_delay": _env_float("AEM_REQUEST_DELAY", 0.05),
    "write_delay": _env_float("AEM_WRITE_DELAY", 0.1),
    "timeout": _env_int("AEM_TIMEOUT", 30),
    "max_pages": _env_int("AEM_MAX_PAGES", 3000),
    "auth_fail_threshold": _env_int("AEM_AUTH_FAIL_THRESHOLD", 5),
    "skip_path_contains": _env_list("AEM_SKIP_PATH_CONTAINS", "sony-image-sensors/sony-image-sensors"),
    "tags_root": _env("AEM_TAGS_ROOT", "/content/cq:tags"),
}


# ============================================================
# Vocabulário de componentes
# ============================================================

PAGE_RESOURCE_TYPE = "macnicaglobal2/components/page"
CONTAINER_RT = "macnicaglobal2/components/content/container"
RESPONSIVE_GRID_RT = "wcm/foundation/components/responsivegrid"

# --- Origem (GWI) ---
TEXT_TYPES = {"macnicagwi/components/content/text"}
IMAGE_TYPES = {
    "macnicagwi/components/content/resizableimage",
    "macnicagwi/components/content/image",
    "core/wcm/components/image/v3/image",
    # bannerimage: mesmas fileReference/alt do resizableimage, achado no
    # dry-run de macnica-products (macnica-cv75) com fileReference real.
    # Trata como imagem comum — perde só as props de banner (popup, etc.),
    # que não têm componente equivalente confirmado no GLOBAL2.
    "macnicagwi/components/content/bannerimage",
}
# heading E title do GWI viram o mesmo 'title' do GLOBAL2. O 'title' do
# GWI foi confirmado pelo Bruno em 13/09/2026 ("title é title"): nas
# páginas de blog ele TEM jcr:title preenchido (ex: 'Blog'), diferente
# do caso vazio visto em macnica-products. Eram 70 ocorrências perdidas
# em silêncio (16 em products, 54 no blog).
# Diferença de propriedade: heading guarda o texto em 'text', title em
# 'jcr:title' — tratado no extract_content.
HEADING_TYPES = {"macnicagwi/components/content/heading"}
TITLE_TYPES = {"macnicagwi/components/content/title"}
BUTTON_TYPES = {"macnicagwi/components/content/button"}
DOWNLOAD_TYPES = {"macnicagwi/components/content/download"}
TABLE_TYPES = {"macnicagwi/components/content/table"}
VIDEO_TYPES = {"macnicagwi/components/content/video"}

# tabs -> tabs (confirmado pelo Bruno em 13/09/2026). Estrutura idêntica
# nos dois lados: o nó 'tabs' não tem propriedade própria, e cada item é
# um container com 'cq:panelTitle' (o rótulo da aba) + o conteúdo dentro.
# Diferença: no GWI o cq:panelTitle vem como array duplicado
# (['NVIDIA Jetson', 'NVIDIA Jetson']); no GLOBAL2 é string simples.
TABS_TYPES = {"macnicagwi/components/content/tabs"}

# productlisting -> list (confirmado pelo Bruno em 13/09/2026). O 'list'
# do GLOBAL2 usa as MESMAS propriedades do productlisting do GWI
# (listFrom, parentPage, sortOrder, tagsMatch, linkItems, childDepth),
# confirmado com exemplo autoral real em tq-embedded-arm-modules.
PRODUCTLISTING_TYPES = {"macnicagwi/components/content/productlisting"}

# Mapeamentos confirmados pelo Bruno em 13/09/2026:
#   carousel     -> carousel     (mesmo nome; itens são imagens com
#                                 fileReference + alt + cq:panelTitle)
#   supplierlist -> list         (mesmas props de listagem do productlisting;
#                                 cardlist fica reservado para as páginas de
#                                 template technical article)
#   downloadlist -> downloadlist (mesmo nome; aponta para uma pasta do DAM)
CAROUSEL_TYPES = {"macnicagwi/components/content/carousel"}
SUPPLIERLIST_TYPES = {"macnicagwi/components/content/supplierlist"}
DOWNLOADLIST_TYPES = {"macnicagwi/components/content/downloadlist"}

# imagepack -> flexcontainer (confirmado pelo Bruno em 13/09/2026). No GWI
# é um invólucro que agrupa imagens + texto; no GLOBAL2 o equivalente é o
# flexcontainer, cujos filhos ficam cada um num flexcontaineritem.
IMAGEPACK_TYPES = {"macnicagwi/components/content/imagepack"}

MANUAL_REVIEW_TYPES = {
    "macnicagwi/components/content/experiencefragment",
    "macnicagwi/components/content/relatedsuggestions",
}

# Invólucros puros: não têm conteúdo próprio, só agrupam. Abrir sem sinalizar.
KNOWN_CONTAINER_TYPES = {
    "macnicagwi/components/content/container",
    "macnicagwi/components/content/resizablecontainer",
    "macnicagwi/components/content/imagetext",
}

# Configuração de página, não conteúdo. Confirmado com dado real: só tem
# flags "false" de quais campos exibir. Ignorar sem virar pendência.
IGNORE_NO_CONTENT_TYPES = {
    "macnicagwi/components/content/pageproperties",
}

# Propriedades que não fazem sentido herdar numa clonagem (devem ser
# geradas novas para o nó novo).
SKIP_EXACT_KEYS = {
    "jcr:uuid", "jcr:versionHistory", "jcr:baseVersion", "jcr:predecessors",
    "jcr:isCheckedOut", "jcr:created", "jcr:createdBy", "jcr:mixinTypes",
}
SKIP_PREFIXES = ("cq:lastReplicat", "cq:lastModif", "cq:isDelivered", "cq:redirect")

IGNORE_KEY_PREFIXES = ("jcr:", "cq:", "sling:", "rep:")


# ============================================================
# Autenticação
# ============================================================

def parse_cookie_string(raw):
    """Quebra a string do 'Copy as cURL' num dicionário.

    Não decodifica nada: o login-token vem como login%3a<JWT>%3acrx.default
    e precisa ir inteiro, exatamente como está.
    """
    cookies = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip()
        value = value.strip().strip('"')
        if key:
            cookies[key] = value
    return cookies


def build_session(prompt_if_missing=True, verbose=True):
    """Monta a Session autenticada e o auth_tracker.

    Usa AEM_COOKIES do .env/ambiente; se estiver vazia, cai no getpass.
    Retorna (session, auth_tracker).
    """
    raw = os.environ.get("AEM_COOKIES", "").strip()
    origem = "o .env"
    if not raw:
        if not prompt_if_missing:
            print("[erro] AEM_COOKIES vazia e --no-prompt ativo.", file=sys.stderr)
            sys.exit(1)
        raw = getpass.getpass(
            "Cole a string COMPLETA de cookies (Copy as cURL, conteúdo depois de -b '...'): "
        ).strip()
        origem = "o prompt"

    if not raw:
        print("[erro] nenhuma string de cookies fornecida.", file=sys.stderr)
        sys.exit(1)

    cookies = parse_cookie_string(raw)
    tem_token = "login-token" in cookies

    if verbose:
        print(f"{len(cookies)} cookies carregados de {origem} "
              f"(login-token presente: {'sim' if tem_token else 'NÃO'})")
        if not tem_token:
            print("  [aviso] sem login-token: a requisição copiada provavelmente não era "
                  "do domínio do AEM, ou a string foi cortada.", file=sys.stderr)
        print()

    session = requests.Session()
    for key, value in cookies.items():
        session.cookies.set(key, value)
    session.headers.update({"Accept": "application/json"})
    travar_session(session)

    return session, {"fails": 0, "threshold": CONFIG["auth_fail_threshold"]}


# ============================================================
# Páginas protegidas (revisadas e aprovadas à mão) e o GWI
# ============================================================
# A trava fica na PRÓPRIA Session: vale para todo script que usa build_session(), inclusive os que chamam
# session.post() direto (a maioria das ferramentas de scripts-hazael). Só leitura passa (GET/HEAD/OPTIONS).
#   - GWI: nada que não seja leitura em URL com `macnicagwi` (REGRA MESTRA do Hazael, 21/09/2026).
#   - paginas_protegidas.txt (pasta do projeto, ao lado do .env): a página e o jcr:content dela não recebem
#     escrita; a página e os ancestrais não podem ser apagados/movidos; nada é copiado/movido para dentro nem
#     para fora dela. Páginas-filhas de uma protegida NÃO estão protegidas (têm de estar na lista).
PROTEGIDAS_PATH = Path(__file__).resolve().parent.parent / "paginas_protegidas.txt"
LEITURA = {"GET", "HEAD", "OPTIONS"}


class EscritaProibida(RuntimeError):
    """Escrita barrada pela trava da Session (página protegida ou GWI)."""


def carregar_protegidas(path=PROTEGIDAS_PATH):
    if not Path(path).exists():
        return ()
    out = []
    for linha in Path(path).read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip().rstrip("/")
        if linha:
            out.append(re.sub(r"\.html$", "", linha))
    return tuple(out)


def _no_conteudo(caminho, pagina):
    """`caminho` é a própria página ou algo dentro do jcr:content dela (filha NÃO conta)."""
    return caminho == pagina or caminho.startswith(pagina + "/jcr:content")


def _ancestral_ou_ela(caminho, pagina):
    return caminho == pagina or pagina.startswith(caminho.rstrip("/") + "/")


def _pares(data):
    if isinstance(data, dict):
        return [(str(k), v) for k, v in data.items()]
    if isinstance(data, (list, tuple)):
        return [(str(k), v) for k, v in data]
    if isinstance(data, (str, bytes)):
        try:
            return parse_qsl(data.decode() if isinstance(data, bytes) else data, keep_blank_values=True)
        except Exception:                                      # noqa: BLE001
            return []
    return []


def _valores(pares, chave):
    out = []
    for k, v in pares:
        if k == chave:
            out += [str(x) for x in (v if isinstance(v, (list, tuple)) else [v])]
    return out


def motivo_bloqueio(metodo, url, data=None, protegidas=None):
    """None se a requisição pode sair; senão, o motivo. Não faz rede — testável offline."""
    if metodo.upper() in LEITURA:
        return None
    if "macnicagwi" in unquote(url):
        return f"{metodo} em URL do GWI (REGRA MESTRA: nunca gravar no GWI): {url}"
    protegidas = carregar_protegidas() if protegidas is None else protegidas
    if not protegidas:
        return None
    caminho = unquote(urlsplit(url).path).rstrip("/")
    sem_ext = re.sub(r"(/[^/.]+)\.[A-Za-z0-9.]+$", r"\1", caminho)     # /x/pagina.html -> /x/pagina
    alvos = {caminho, sem_ext}
    pares = _pares(data)
    ops = {v.lower() for v in _valores(pares, ":operation")}
    for p in protegidas:
        for c in alvos:
            if _no_conteudo(c, p):
                return f"{metodo} em página protegida: {c}"
            if ops & {"delete", "move"} and _ancestral_ou_ela(c, p):
                return f":operation={'/'.join(sorted(ops))} em {c} apagaria/moveria a página protegida {p}"
        for x in _valores(pares, ":applyTo"):
            if ops & {"delete", "move"} and _ancestral_ou_ela(x.rstrip("/"), p):
                return f":applyTo={x} apagaria/moveria a página protegida {p}"
        for d in _valores(pares, ":dest"):
            destino = d if d.startswith("/") else caminho.rsplit("/", 1)[0] + "/" + d
            if destino.endswith("/"):
                destino += caminho.rsplit("/", 1)[-1]
            if _no_conteudo(destino.rstrip("/"), p):
                return f":dest={d} grava dentro da página protegida {p}"
        for k, v in pares:
            if k.endswith("@MoveFrom") and any(_no_conteudo(str(x).rstrip("/"), p) or _ancestral_ou_ela(str(x), p)
                                               for x in (v if isinstance(v, (list, tuple)) else [v])):
                return f"{k}={v} tira conteúdo da página protegida {p}"
            if "/" in k.split("@", 1)[0]:                      # propriedade relativa: jcr:content/x/prop
                pai = (caminho + "/" + k.split("@", 1)[0].lstrip("./")).rsplit("/", 1)[0]
                if _no_conteudo(pai, p):
                    return f"propriedade {k} grava dentro da página protegida {p}"
        if caminho.startswith("/bin/"):                        # wcmcommand, replicate…
            for chave in ("path", "srcPath", "destPath"):
                for x in _valores(pares, chave):
                    if _no_conteudo(x.rstrip("/"), p) or _ancestral_ou_ela(x.rstrip("/"), p):
                        return f"{caminho} com {chave}={x} mexe na página protegida {p}"
    return None


def travar_session(session):
    """Põe a trava em `session.request` (post/put/delete/patch passam por ele)."""
    original = session.request

    def request(method, url, *args, **kwargs):
        motivo = motivo_bloqueio(method, url, kwargs.get("data", args[1] if len(args) > 1 else None))
        if motivo:
            print(f"\n[ABORTADO] {motivo}", file=sys.stderr)
            raise EscritaProibida(motivo)
        return original(method, url, *args, **kwargs)

    session.request = request
    return session


# ============================================================
# Trava de segurança
# ============================================================

def assert_target_is_safe(path, allow_extra=()):
    """Aborta qualquer escrita fora da área de teste.

    Regra inegociável, confirmada pelo Bruno: macnicagwi e macnicaglobal2
    são SOMENTE LEITURA. Chamar antes de todo POST.
    """
    safe = (CONFIG["target_prefix"], CONFIG["dam_target_prefix"],
            "/content/experience-fragments/copia-teste") + tuple(allow_extra)
    if not path.startswith(safe):
        print(f"\n[ABORTADO] tentativa de escrita fora da área de teste:\n"
              f"  {path}\n"
              f"  Permitido apenas em: {', '.join(safe)}\n"
              f"  macnicagwi e macnicaglobal2 são SOMENTE LEITURA.", file=sys.stderr)
        sys.exit(1)


def session_expired(auth_tracker):
    return auth_tracker["fails"] >= auth_tracker["threshold"]


# ============================================================
# HTTP
# ============================================================

def get_json(session, url, auth_tracker=None, timeout=None):
    """GET que devolve (json, status). Alimenta o auth_tracker."""
    timeout = timeout or CONFIG["timeout"]
    try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 200:
            if auth_tracker is not None:
                auth_tracker["fails"] = 0
            try:
                return resp.json(), 200
            except ValueError:
                return None, 200
        if resp.status_code == 404:
            if auth_tracker is not None:
                auth_tracker["fails"] = 0
            return None, 404
        if resp.status_code in (401, 403) and auth_tracker is not None:
            auth_tracker["fails"] += 1
        return None, resp.status_code
    except requests.RequestException as e:
        print(f"  [erro de rede] {e}", file=sys.stderr)
        return None, None


def fetch_with_depth_fallback(session, base_url, path, depth, auth_tracker,
                              timeout=None, _quiet=True):
    """Busca <path>.<depth>.json, tratando o HTTP 300.

    Algumas páginas (geralmente pastas de categoria) recusam profundidades
    altas com 300 e devolvem, no corpo, a lista de profundidades válidas.
    Nesse caso extrai a maior aceita e tenta de novo sozinho.
    """
    timeout = timeout or CONFIG["timeout"]
    url = urljoin(base_url, f"{path}.{depth}.json")
    try:
        resp = session.get(url, timeout=timeout)
    except requests.RequestException as e:
        print(f"  [erro de rede] {e}", file=sys.stderr)
        return None, None

    if resp.status_code == 200:
        if auth_tracker is not None:
            auth_tracker["fails"] = 0
        try:
            return resp.json(), 200
        except ValueError:
            return None, 200

    if resp.status_code == 300:
        try:
            depths = [int(m.group(1)) for opt in resp.json()
                      if (m := re.search(r"\.(\d+)\.json$", str(opt)))]
            if depths:
                maior = max(depths)
                if not _quiet:
                    print(f"    [aviso] profundidade {depth} recusada em {path}, "
                          f"usando {maior}")
                return fetch_with_depth_fallback(session, base_url, path, maior,
                                                 auth_tracker, timeout, _quiet)
        except (ValueError, TypeError):
            pass
        return None, 300

    if resp.status_code == 404:
        if auth_tracker is not None:
            auth_tracker["fails"] = 0
        return None, 404
    if resp.status_code in (401, 403) and auth_tracker is not None:
        auth_tracker["fails"] += 1
    return None, resp.status_code


def post_node(session, base_url, path, payload, auth_tracker, timeout=None,
              allow_extra=()):
    """POST de payload achatado. Retorna (status, trecho_da_resposta).

    Passa pela trava de segurança antes de escrever. allow_extra: só
    para exceções pontuais e explícitas (ex: criar tq-systems-embedded
    dentro de macnicaglobal2, aprovado pelo Bruno em 16/09/2026) — cada
    caminho extra tem que ser passado deliberadamente por quem chama,
    nunca um default permissivo aqui.
    """
    assert_target_is_safe(path, allow_extra=allow_extra)
    timeout = timeout or CONFIG["timeout"]
    url = urljoin(base_url, path)
    try:
        resp = session.post(url, data=payload, timeout=timeout)
        if resp.status_code in (200, 201):
            if auth_tracker is not None:
                auth_tracker["fails"] = 0
        elif resp.status_code in (401, 403) and auth_tracker is not None:
            auth_tracker["fails"] += 1
        return resp.status_code, resp.text[:300]
    except requests.RequestException as e:
        return None, str(e)


def delete_node(session, base_url, path, auth_tracker, timeout=None, allow_extra=()):
    """Apaga um nó via POST com :operation=delete (convenção Sling).

    Mesma trava de segurança do post_node: só aceita apagar dentro da
    área de teste. Operação destrutiva — quem chama deve confirmar
    antes. allow_extra: mesma regra do post_node, exceção pontual e
    explícita, nunca default permissivo.
    """
    assert_target_is_safe(path, allow_extra=allow_extra)
    timeout = timeout or CONFIG["timeout"]
    url = urljoin(base_url, path)
    try:
        resp = session.post(url, data={":operation": "delete"}, timeout=timeout)
        if resp.status_code in (200, 204):
            if auth_tracker is not None:
                auth_tracker["fails"] = 0
        elif resp.status_code in (401, 403) and auth_tracker is not None:
            auth_tracker["fails"] += 1
        return resp.status_code, resp.text[:300]
    except requests.RequestException as e:
        return None, str(e)


# ============================================================
# Cópia de assets do DAM
# ============================================================
# Portado em 17/09/2026 do scripts-luiza/aem_create_and_migrate_semiconductors.py,
# que era a única implementação disto no projeto. Três mudanças no caminho:
#
#   1. TRAVA DE SEGURANÇA. O original escrevia com session.post() direto, sem
#      passar pelo assert_target_is_safe() — dava para subir asset em qualquer
#      lugar, inclusive no DAM do GWI. Aqui toda escrita passa pela trava.
#   2. sling:Folder nas pastas aninhadas. O original criava tudo como
#      sling:OrderedFolder; conferido no DAM real em 17/09/2026: a RAIZ é
#      OrderedFolder, mas as pastas de dentro são sling:Folder.
#   3. dry_run, para conferir antes de subir nada.
#
# O endpoint '.createasset.html' vinha marcado como "experimental" no original.
# Confirmado funcionando nesta instância — ver o teste no final deste arquivo.


def map_asset_path(source_path, source_prefix, target_prefix):
    """Caminho equivalente do asset no DAM de destino (troca só o prefixo)."""
    if not source_path or not source_path.startswith(source_prefix):
        return None
    return target_prefix + source_path[len(source_prefix):]


def ensure_dam_folder(session, base_url, folder_path, auth_tracker,
                      cache=None, timeout=None, allow_extra=(), dry_run=False):
    """Cria a pasta do DAM nível a nível, o que faltar. Devolve True/False.

    A raiz do DAM é sling:OrderedFolder e as pastas de dentro são
    sling:Folder — conferido nas pastas reais, não é convenção inventada.
    """
    cache = cache if cache is not None else set()
    if folder_path in cache:
        return True
    timeout = timeout or CONFIG["timeout"]
    atual = ""
    for seg in [s for s in folder_path.strip("/").split("/") if s]:
        atual += "/" + seg
        if atual in cache:
            continue
        data, _ = get_json(session, urljoin(base_url, f"{atual}.json"), auth_tracker)
        if data is None:
            if dry_run:
                print(f"    [simulado] criaria pasta {atual}")
                cache.add(atual)
                continue
            assert_target_is_safe(atual, allow_extra=allow_extra)
            try:
                resp = session.post(urljoin(base_url, atual),
                                    data={"jcr:primaryType": "sling:Folder"},
                                    timeout=timeout)
            except requests.RequestException as e:
                print(f"    [erro de rede criando {atual}] {e}", file=sys.stderr)
                return False
            if resp.status_code not in (200, 201):
                print(f"    [erro] não criou a pasta {atual} (HTTP {resp.status_code})",
                      file=sys.stderr)
                return False
        cache.add(atual)
    return True


def copy_asset(session, base_url, source_path, source_prefix, target_prefix,
               auth_tracker, cache=None, timeout=None, allow_extra=(),
               dry_run=False):
    """Copia um asset do DAM de origem para o de destino.

    Baixa o binário e sobe em '<pasta>.createasset.html', preservando a
    estrutura de pastas. Devolve o caminho novo, ou None se falhar — quem
    chama decide se mantém a referência antiga como fallback.

    É o que faltava no aem_lib: sem isto, página migrada cujo asset só
    existe no DAM do GWI fica sem imagem, ou obriga a caçar um arquivo de
    nome parecido no DAM de destino (e o nodename do QueryBuilder é
    sensível a maiúscula enquanto o DAM está todo em minúscula, então a
    busca falha em silêncio).
    """
    destino = map_asset_path(source_path, source_prefix, target_prefix)
    if destino is None:
        return None
    timeout = timeout or CONFIG["timeout"]

    ja, _ = get_json(session, urljoin(base_url, f"{destino}.json"), auth_tracker)
    if ja is not None:
        return destino                      # idempotente: já está lá

    try:
        resp = session.get(urljoin(base_url, source_path), timeout=max(timeout, 60))
    except requests.RequestException as e:
        print(f"    [erro de rede baixando {source_path}] {e}", file=sys.stderr)
        return None
    if resp.status_code != 200:
        print(f"    [erro] não baixou {source_path} (HTTP {resp.status_code})",
              file=sys.stderr)
        return None
    binario = resp.content
    tipo = resp.headers.get("Content-Type", "application/octet-stream")

    pasta, arquivo = destino.rsplit("/", 1)
    if not ensure_dam_folder(session, base_url, pasta, auth_tracker, cache,
                             timeout, allow_extra, dry_run):
        return None

    if dry_run:
        print(f"    [simulado] subiria {arquivo} ({len(binario)} bytes) em {pasta}")
        return destino

    assert_target_is_safe(destino, allow_extra=allow_extra)
    try:
        resp = session.post(urljoin(base_url, f"{pasta}.createasset.html"),
                            files={"file": (arquivo, binario, tipo)},
                            timeout=max(timeout, 60))
    except requests.RequestException as e:
        print(f"    [erro de rede subindo {arquivo}] {e}", file=sys.stderr)
        return None
    if resp.status_code in (200, 201):
        if auth_tracker is not None:
            auth_tracker["fails"] = 0
        return destino
    print(f"    [erro] upload de {arquivo} falhou (HTTP {resp.status_code}): "
          f"{resp.text[:160]}", file=sys.stderr)
    return None


# ============================================================
# Navegação de nós
# ============================================================

def list_child_nodes(node):
    """Filhos que são nós de verdade (descarta jcr:/cq:/sling:/rep:)."""
    return [
        (key, val) for key, val in node.items()
        if isinstance(val, dict) and not key.startswith(IGNORE_KEY_PREFIXES)
    ]


def is_page(node):
    """Um nó é página se for cq:Page ou tiver jcr:content com template."""
    if node.get("jcr:primaryType") == "cq:Page":
        return True
    content = node.get("jcr:content")
    return isinstance(content, dict) and bool(content.get("cq:template"))


def normalize_name(name):
    """Slug: minúsculo, hífen simples, sem hífen duplo nem nas pontas.

    Nunca confiar que a origem já está no padrão — o GWI tem vários nomes
    de nó com maiúscula por engano (ex: TQMa67xx).
    """
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def normalize_path(path, source_root, target_root):
    """Mapeia um caminho de origem para o destino, normalizando CADA
    segmento — o bug de maiúscula aparece em qualquer nível, não só no
    último."""
    rel = path[len(source_root):].lstrip("/") if path.startswith(source_root) else ""
    segments = [normalize_name(s) for s in rel.split("/") if s]
    return target_root + ("/" + "/".join(segments) if segments else "")


def is_meaningful_text(html):
    """Texto que sobra depois de tirar tags e &nbsp; — evita migrar
    parágrafos vazios."""
    if not html:
        return False
    stripped = re.sub(r"<[^>]+>", "", html).replace("&nbsp;", "").strip()
    return len(stripped) > 0


# Bloco "vazio" do editor do GWI: um parágrafo (ou heading) cujo conteúdo
# é só espaço/&nbsp;/<br>. O autor usava isso como "enter" para espaçar o
# texto — no GLOBAL2 o espaçamento vem do padding do container, então
# esses blocos viram espaço em branco duplicado.
EMPTY_BLOCK_RE = re.compile(
    r"<(p|h[1-6]|div)\b[^>]*>(?:\s|&nbsp;|<br\s*/?>)*</\1>\s*",
    re.IGNORECASE,
)


def strip_empty_blocks(html):
    """Remove os blocos de espaçamento vazios de um texto rico.

    Confirmado com dado real migrado (macnica-cv75): o GWI tem vários
    '<p>&nbsp;</p>' isolados, usados como "enter" para separar parágrafos.

    Remove só blocos SEM conteúdo de verdade — um <p> com texto, imagem,
    link ou qualquer outro elemento fica intacto. Também normaliza os
    \\r\\n que o editor do GWI deixa entre as tags.
    """
    if not html or not isinstance(html, str):
        return html
    limpo = EMPTY_BLOCK_RE.sub("", html)
    # Sobra do editor do GWI: quebras de linha soltas entre as tags.
    limpo = re.sub(r"(\r\n|\r|\n){2,}", "\n", limpo)
    return limpo.strip()


META_DESCRIPTION_MAX_LEN = 160


def extrair_meta_description(rich_text_html, max_len=META_DESCRIPTION_MAX_LEN):
    """Deriva uma meta description a partir do primeiro <p> com texto
    de verdade num rich text. Usado como fallback quando NEM a página
    de destino nem o GWI têm jcr:description preenchido (achado real
    em tq-embedded-x86-modules: 45/50 páginas sem o campo em nenhum
    dos dois lados) — o Bruno confirmou usar o primeiro parágrafo da
    própria página como origem.

    Ignora headings (h1-h6): pega só o conteúdo de <p>, senão o título
    do bloco entra colado no início da frase. Corta em max_len na
    última palavra inteira (não corta no meio de uma palavra), sem
    reticências — texto de meta description não precisa indicar corte.
    Devolve None se não achar nenhum <p> com texto.
    """
    if not rich_text_html or not isinstance(rich_text_html, str):
        return None
    m = re.search(r"<p\b[^>]*>(.*?)</p>", rich_text_html, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    texto = re.sub(r"<[^>]+>", " ", m.group(1))
    # html.unescape decodifica &nbsp;, &quot;, &amp; etc — achado real:
    # '&quot;Apollo Lake-I&quot;' aparecia literal sem isso. Precisa do
    # parâmetro NÃO se chamar 'html' — sombreava o módulo importado no
    # topo do arquivo e quebrava esta chamada (bug real, pego em teste).
    texto = html.unescape(texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    if not texto:
        return None
    if len(texto) <= max_len:
        return texto
    cortado = texto[:max_len].rsplit(" ", 1)[0]
    return cortado


def slug_to_label(path):
    """Rótulo legível a partir do último segmento de um caminho."""
    slug = path.rstrip("/").rsplit("/", 1)[-1]
    label = re.sub(r"[-_]+", " ", slug)
    label = re.sub(r"\s+", " ", label).strip()
    return label.title() if label else "Ver página"


# ============================================================
# Reescrita de links
# ============================================================

# Captura qualquer href, não só os que já começam com /content/ — o
# rewrite_link decide o que fazer com cada um.
HREF_RE = re.compile(r'(href=")([^"]+)(")')

# Lixo de URL de AUTOR que precisa sumir antes do caminho /content/...:
#   https://author-p53812-e590634.adobeaemcloud.com/sites.html/content/...
#   /editor.html/content/...
# Tudo isso some, sobrando só o /content/... em diante. Confirmado com o
# Bruno em 13/09/2026 ("vai ser retirado todo o início do link e vai ser
# deixado o resto igual"). Links de author quebram ao publicar — é uma
# das checagens do guidelines-to-follow.txt do cliente.
AUTHOR_PREFIX_RE = re.compile(
    r"^(?:https?://[^/]*adobeaemcloud\.com)?"      # domínio de author (opcional)
    r"(?:/(?:sites|editor|cf#|assets)\.html)?"      # console do AEM (opcional)
    r"(?=/content/)",                               # tem que sobrar /content/
    re.IGNORECASE,
)

# Site público: https://www.macnica.com/americas/... -> /content/<site>/americas/...
# Confirmado pelo Bruno em 13/09/2026 que esses também devem ser convertidos.
PUBLIC_SITE_RE = re.compile(
    r"^https?://(?:www\.)?macnica\.com(?=/)",
    re.IGNORECASE,
)

# Sufixo .html que aparece no fim de links de página publicada.
HTML_SUFFIX_RE = re.compile(r"\.html(?=$|[?#])", re.IGNORECASE)


def rewrite_link(url, from_prefix=None, to_prefix=None):
    """Normaliza um link interno para o caminho do site de destino.

    Faz, nesta ordem:
      1. Remove o prefixo de AUTOR, se houver — domínio adobeaemcloud.com
         e/ou console (/sites.html, /editor.html):
            https://author-p53812-....com/sites.html/content/macnicagwi/x
         -> /content/macnicagwi/x
      2. Converte URL do site público (www.macnica.com/americas/...) para
         caminho de conteúdo.
      3. Troca o prefixo do site: macnicagwi -> macnicaglobal2.
      4. Tira o sufixo .html (link interno do AEM não usa).

    O resultado sai sempre como caminho absoluto começando em /content/
    (confirmado com o Bruno) — é o formato que os 62 links internos reais
    do GWI já usam e o que o AEM espera.

    Links realmente externos (outro domínio), mailto: e âncoras (#) passam
    intactos.
    """
    from_prefix = from_prefix or CONFIG["gwi_prefix"]
    to_prefix = to_prefix or CONFIG["global2_prefix"]
    if not url or not isinstance(url, str):
        return url

    limpo = url.strip()
    if limpo.startswith(("mailto:", "tel:", "#")):
        return url

    # 1. Tira o prefixo de author/console, deixando só /content/...
    limpo = AUTHOR_PREFIX_RE.sub("", limpo)

    # 2. Site público -> caminho de conteúdo (mantém o site de origem,
    #    que o passo 3 troca para o de destino).
    if PUBLIC_SITE_RE.match(limpo):
        limpo = PUBLIC_SITE_RE.sub(from_prefix, limpo)

    # Se depois disso ainda não é um caminho de conteúdo, é link externo
    # de verdade: devolve o original sem tocar.
    if not limpo.startswith("/content/"):
        return url

    # 3. Troca o prefixo do site.
    if limpo.startswith(from_prefix):
        limpo = to_prefix + limpo[len(from_prefix):]

    # 4. Tira o .html final.
    limpo = HTML_SUFFIX_RE.sub("", limpo)

    return limpo


def rewrite_links_in_html(html, from_prefix=None, to_prefix=None):
    """Reescreve todo href de um bloco de texto rico.

    Passa TODO href pelo rewrite_link — que devolve o original intocado
    quando o link é externo de verdade.
    """
    if not html or not isinstance(html, str):
        return html
    return HREF_RE.sub(
        lambda m: m.group(1) + rewrite_link(m.group(2), from_prefix, to_prefix) + m.group(3),
        html,
    )


# ============================================================
# Templates
# ============================================================

def find_template_path(session, base_url, templates_root, title_query, auth_tracker):
    """Acha o caminho técnico de um template pelo TÍTULO.

    Profundidade 2 é obrigatória: com .1.json o jcr:content de cada
    template não vem, e é lá que mora o jcr:title.
    Retorna (caminho, lista_de_titulos_encontrados).
    """
    data, _ = get_json(session, urljoin(base_url, f"{templates_root}.2.json"),
                       auth_tracker=auth_tracker)
    if data is None:
        return None, []
    encontrados = []
    for name, child in list_child_nodes(data):
        title = (child.get("jcr:content", {}) or {}).get("jcr:title", "")
        encontrados.append((name, title))
        if title.strip().lower() == title_query.strip().lower():
            return f"{templates_root}/{name}", encontrados
    return None, encontrados


def resolve_template(session, base_url, args, auth_tracker):
    """Resolve o template a partir de --template-path ou --template-title.

    Sai com erro listando os títulos disponíveis se não achar — em vez de
    seguir com um caminho inventado.
    """
    if getattr(args, "template_path", None):
        return args.template_path
    titulo = getattr(args, "template_title", None) or CONFIG["template_title"]
    raiz = getattr(args, "templates_root", None) or CONFIG["templates_root"]
    print(f"== Buscando template '{titulo}' ==")
    caminho, encontrados = find_template_path(session, base_url, raiz, titulo, auth_tracker)
    if caminho is None:
        print(f"[erro] template '{titulo}' não encontrado em {raiz}. Disponíveis:",
              file=sys.stderr)
        for name, title in encontrados:
            print(f"    - {name}: {title!r}", file=sys.stderr)
        sys.exit(1)
    print(f"  {caminho}\n")
    return caminho


# ============================================================
# Travessia da árvore
# ============================================================

def crawl_tree(session, base_url, root_path, auth_tracker, max_pages=None,
               max_depth=None, delay=None, skip_contains=(), only_pages=False,
               progress_every=25, quiet=False):
    """Percorre a árvore a partir de root_path, em largura.

    Um GET .1.json por nó: barato e suficiente para saber quem são os
    filhos. Devolve um dicionário caminho -> metadados.

    max_depth conta a partir da raiz (0 = só a raiz).
    only_pages=True descarta nós que não são páginas, mas continua
    descendo neles (uma pasta pode conter páginas).
    """
    max_pages = max_pages or CONFIG["max_pages"]
    delay = CONFIG["request_delay"] if delay is None else delay

    inventory = {}
    root_depth = root_path.rstrip("/").count("/")
    fila = [root_path]
    visitados = set()

    while fila:
        if session_expired(auth_tracker):
            print(f"\n  [erro] sessão expirou — {len(inventory)} nós preservados.",
                  file=sys.stderr)
            break
        if len(inventory) >= max_pages:
            print(f"  [aviso] limite de {max_pages} nós atingido "
                  f"(aumente com --max-pages).", file=sys.stderr)
            break

        path = fila.pop(0)
        if path in visitados:
            continue
        visitados.add(path)

        if any(p in path for p in skip_contains):
            continue

        depth = path.rstrip("/").count("/") - root_depth
        if max_depth is not None and depth > max_depth:
            continue

        # Profundidade 3, não 1: com .1.json o jcr:content vem sem o nó
        # 'root'; com .2.json o 'root' vem mas vazio de filhos. Só a
        # partir de 3 dá para distinguir página vazia de página cheia.
        # Mesmo número de requisições, resposta maior.
        data, status = fetch_with_depth_fallback(session, base_url, path, 3,
                                                 auth_tracker)
        if delay:
            time.sleep(delay)
        if data is None:
            continue

        content = data.get("jcr:content", {}) or {}
        filhos = [name for name, _ in list_child_nodes(data)]
        eh_pagina = is_page(data)

        if eh_pagina or not only_pages:
            root = content.get("root")
            # Tem conteúdo se o 'root' existir E tiver algum filho de
            # verdade dentro (um root com só jcr:primaryType é uma página
            # criada mas nunca preenchida).
            tem_conteudo = bool(root) and bool(list_child_nodes(root)) \
                if isinstance(root, dict) else False
            inventory[path] = {
                "title": content.get("jcr:title") or path.rsplit("/", 1)[-1],
                "template": content.get("cq:template"),
                "resource_type": content.get("sling:resourceType"),
                "primary_type": data.get("jcr:primaryType"),
                "is_page": eh_pagina,
                "depth": depth,
                "children": filhos,
                "has_content": tem_conteudo,
            }

        for filho in filhos:
            fila.append(f"{path}/{filho}")

        if not quiet and len(inventory) % progress_every == 0 and inventory:
            print(f"  ... {len(inventory)} nós — último: {path}", flush=True)

    return inventory


# ============================================================
# Extração de conteúdo (GWI)
# ============================================================

def extract_content(jcr_content):
    """Extrai os blocos migráveis de um jcr:content do GWI.

    Devolve (components, skipped). Nada some em silêncio: tipo não
    reconhecido vira pendência E o walk continua descendo nele, para não
    perder texto/imagem aninhado.
    """
    components = []
    skipped = []

    def emitir(col_width, comp):
        """Guarda o bloco, anotando em que coluna ele nasceu."""
        if col_width:
            comp["colWidth"] = col_width
        components.append(comp)

    def largura_coluna(node):
        """Largura em doze avos, quando o invólucro é uma coluna.

        No GWI a coluna não tem propriedade própria: é o container que
        carrega `cq:responsive/default/width`. width=12 (ou ausente) é
        largura cheia, então não é coluna.
        """
        larg = ((node.get("cq:responsive") or {}).get("default") or {}).get("width")
        if larg and str(larg).isdigit() and 0 < int(larg) < 12:
            return str(larg)
        return None

    def walk(node, col_width=None):
        for name, child in list_child_nodes(node):
            rt = child.get("sling:resourceType", "")

            # Invólucro puro: o conteúdo real está dentro. Se ele for uma
            # coluna, a largura desce junto — quem produz o bloco lá no
            # fundo precisa saber que nasce dentro de uma.
            if not rt or rt in KNOWN_CONTAINER_TYPES:
                walk(child, largura_coluna(child) or col_width)
                continue

            if rt in IGNORE_NO_CONTENT_TYPES:
                continue

            if rt in TEXT_TYPES:
                html = child.get("text", "")
                if is_meaningful_text(html):
                    emitir(col_width, {"kind": "text", "html": html})
                continue

            if rt in IMAGE_TYPES:
                ref = child.get("fileReference")
                if ref:
                    emitir(col_width, {"kind": "image", "fileReference": ref,
                                       "alt": child.get("alt", "")})
                else:
                    skipped.append({"path": name, "resourceType": rt,
                                    "categoria": "imagem_quebrada",
                                    "motivo": "IMAGEM QUEBRADA: sem fileReference"})
                continue

            if rt in HEADING_TYPES:
                texto = child.get("text", "")
                if texto.strip():
                    emitir(col_width, {"kind": "heading", "text": texto,
                                       "type": child.get("type", "h2")})
                continue

            if rt in TITLE_TYPES:
                # 'title' do GWI guarda o texto em jcr:title (o heading usa
                # 'text'). Vira o mesmo componente title do GLOBAL2.
                texto = str(child.get("jcr:title", "") or "")
                if texto.strip():
                    emitir(col_width, {"kind": "heading", "text": texto,
                                       "type": child.get("type", "h2")})
                continue

            if rt in BUTTON_TYPES:
                titulo = child.get("jcr:title", "")
                if titulo.strip():
                    emitir(col_width, {"kind": "button", "title": titulo,
                                       "linkURL": child.get("linkURL", ""),
                                       "linkTarget": child.get("linkTarget", "_self")})
                continue

            if rt in DOWNLOAD_TYPES:
                ref = child.get("fileReference", "")
                if ref:
                    # download não tem título próprio: deriva do nome do arquivo
                    nome = ref.rsplit("/", 1)[-1]
                    label = re.sub(r"\.[a-zA-Z0-9]+$", "", nome)
                    label = re.sub(r"[-_]+", " ", label)
                    label = re.sub(r"\s+", " ", label).strip() or "Download"
                    emitir(col_width, {"kind": "download", "fileReference": ref,
                                       "label": label})
                else:
                    skipped.append({"path": name, "resourceType": rt,
                                    "categoria": "imagem_quebrada",
                                    "motivo": "DOWNLOAD QUEBRADO: sem fileReference"})
                continue

            if rt in TABLE_TYPES:
                html = child.get("text", "")
                if is_meaningful_text(html):
                    emitir(col_width, {"kind": "table", "html": html})
                continue

            if rt in TABS_TYPES:
                # Cada item é uma aba: um container com cq:panelTitle + o
                # conteúdo real dentro. O conteúdo de cada aba é extraído
                # recursivamente, então text/image/table dentro das abas
                # são migrados normalmente.
                abas = []
                for item_nome, item in list_child_nodes(child):
                    titulo_aba = item.get("cq:panelTitle", "")
                    # No GWI vem como array duplicado; no GLOBAL2 é string.
                    if isinstance(titulo_aba, list):
                        titulo_aba = titulo_aba[0] if titulo_aba else ""
                    conteudo_aba, skipped_aba = extract_content(item)
                    skipped.extend(skipped_aba)
                    # Aba SEM conteúdo mas COM rótulo é preservada: o
                    # rótulo é conteúdo que o autor escreveu (ex: em
                    # boards-modules/iei há tabs cujos itens só têm
                    # cq:panelTitle). Descartar perderia esse texto.
                    if conteudo_aba or str(titulo_aba).strip():
                        abas.append({"title": str(titulo_aba),
                                     "components": conteudo_aba})
                if abas:
                    emitir(col_width, {"kind": "tabs", "abas": abas})
                continue

            if rt in PRODUCTLISTING_TYPES or rt in SUPPLIERLIST_TYPES:
                # Ambos viram 'list' no GLOBAL2, que usa as MESMAS
                # propriedades de listagem. supplierlist confirmado pelo
                # Bruno em 13/09/2026 (cardlist fica reservado para as
                # páginas de template technical article).
                # Só copiamos os modos que sabemos que funcionam: static
                # (array pages) e children (parentPage/rootPath). Modo por
                # tag fica pendente, mesma decisão do relatedsuggestions.
                modo = child.get("listFrom", "")
                if modo in ("static", "children"):
                    # supplierlist usa 'rootPath' onde o productlisting usa
                    # 'parentPage' — normalizar para o nome que o list espera.
                    pai = child.get("parentPage") or child.get("rootPath", "")
                    emitir(col_width, {
                        "kind": "list",
                        "listFrom": modo,
                        "pages": child.get("pages", []) if modo == "static" else [],
                        "parentPage": pai,
                        "sortOrder": child.get("sortOrder", "asc"),
                        "orderBy": child.get("orderBy", ""),
                        "linkItems": child.get("linkItems", "true"),
                        "childDepth": child.get("childDepth", "1"),
                        "tagsMatch": child.get("tagsMatch", "any"),
                        "maxItems": child.get("maxItems", ""),
                    })
                else:
                    skipped.append({"path": name, "resourceType": rt,
                                    "categoria": "related_suggestions",
                                    "motivo": f"LISTAGEM (modo '{modo}' não "
                                              f"suportado — só static e children)",
                                    "ref": child.get("query", "")})
                continue

            if rt in DOWNLOADLIST_TYPES:
                # downloadlist -> downloadlist (mesmo nome, confirmado pelo
                # Bruno). Lista os assets de uma pasta do DAM. O 'directory'
                # aponta para o DAM do GWI e NÃO é reescrito — assets são
                # tarefa à parte, decisão já tomada para fileReference.
                diretorio = child.get("directory", "")
                if diretorio:
                    emitir(col_width, {
                        "kind": "downloadlist",
                        "directory": diretorio,
                        "orderBy": child.get("orderBy", ""),
                        "sortOrder": child.get("sortOrder", "asc"),
                        "maxItems": child.get("maxItems", ""),
                        "searchContentType": child.get("searchContentType", "asset"),
                    })
                else:
                    skipped.append({"path": name, "resourceType": rt,
                                    "categoria": "tipo_nao_reconhecido",
                                    "motivo": "DOWNLOAD LIST sem 'directory'"})
                continue

            if rt in CAROUSEL_TYPES:
                # carousel -> carousel (mesmo nome, confirmado pelo Bruno).
                # A maioria dos itens é IMAGEM (resizableimage) com
                # fileReference + alt + cq:panelTitle — é galeria, não
                # abas. MAS um carousel pode ter um slide de VÍDEO
                # (achado real: sony-imx277cqt-c tem um item
                # macnicagwi/components/content/video dentro do
                # carousel) — sem tratamento isso desaparecia em
                # silêncio, porque não tem fileReference. Slide que não
                # é imagem nem vídeo vira pendência, não some.
                slides = []
                for item_nome, item in list_child_nodes(child):
                    item_rt = item.get("sling:resourceType", "")
                    rotulo = item.get("cq:panelTitle", "")
                    if isinstance(rotulo, list):
                        rotulo = rotulo[0] if rotulo else ""
                    ref = item.get("fileReference")
                    if ref:
                        slides.append({"tipo": "image", "fileReference": ref,
                                       "alt": item.get("alt", ""),
                                       "title": str(rotulo)})
                    elif item_rt in VIDEO_TYPES and item.get("youtubeVideoId"):
                        slides.append({
                            "tipo": "embed", "title": str(rotulo),
                            "embeddableResourceType": item.get(
                                "embeddableResourceType",
                                "core/wcm/components/embed/v1/embed/embeddable/youtube"),
                            "youtubeVideoId": item["youtubeVideoId"],
                            "youtubeAutoPlay": item.get("youtubeAutoPlay", "false"),
                            "youtubeLoop": item.get("youtubeLoop", "false"),
                            "youtubeMute": item.get("youtubeMute", "false"),
                            "youtubeRel": item.get("youtubeRel", "false"),
                            "youtubePlaysInline": item.get("youtubePlaysInline", "false"),
                        })
                    else:
                        skipped.append({"path": item_nome, "resourceType": item_rt,
                                        "categoria": "tipo_nao_reconhecido",
                                        "motivo": f"SLIDE DE CAROUSEL não reconhecido: {item_rt}"})
                if slides:
                    emitir(col_width, {"kind": "carousel", "slides": slides})
                continue

            if rt in IMAGEPACK_TYPES:
                # imagepack -> flexcontainer (confirmado pelo Bruno). É um
                # invólucro: o conteúdo real (imagens + texto) fica dentro.
                conteudo, skipped_pack = extract_content(child)
                skipped.extend(skipped_pack)
                if conteudo:
                    emitir(col_width, {"kind": "flexcontainer",
                                       "components": conteudo})
                continue

            if rt in VIDEO_TYPES:
                vid = child.get("youtubeVideoId", "")
                if vid:
                    emitir(col_width, {
                        "kind": "embed",
                        "embeddableResourceType": child.get(
                            "embeddableResourceType",
                            "core/wcm/components/embed/v1/embed/embeddable/youtube"),
                        "youtubeVideoId": vid,
                        "youtubeAutoPlay": child.get("youtubeAutoPlay", "false"),
                        "youtubeLoop": child.get("youtubeLoop", "false"),
                        "youtubeMute": child.get("youtubeMute", "false"),
                        "youtubeRel": child.get("youtubeRel", "false"),
                        "youtubePlaysInline": child.get("youtubePlaysInline", "false"),
                    })
                continue

            if rt in MANUAL_REVIEW_TYPES:
                if "relatedsuggestions" in rt:
                    modo = child.get("listFrom")
                    if modo == "static":
                        pages = child.get("pages", [])
                        if isinstance(pages, list) and pages:
                            emitir(col_width, {"kind": "related_static_links",
                                               "pages": pages})
                        continue  # resolvido, não é pendência
                    if modo == "children":
                        # Mesmo destino do productlisting: o 'list' do
                        # GLOBAL2 usa as MESMAS propriedades (listFrom,
                        # parentPage, orderBy, sortOrder, maxItems,
                        # childDepth) — é o caminho que o README já apontava
                        # nas pendências 3 e 4.
                        #
                        # Sem isto o componente não gerava NADA no destino, e
                        # a página perdia a lista inteira: em
                        # `sitime-clock-buffers` sumiam as 3 irmãs (SiTime
                        # Oscillators, Clock Generators, Jitter Cleaners) com
                        # título e descrição. Virar pendência escondia perda
                        # de conteúdo, não só de semântica.
                        emitir(col_width, {
                            "kind": "list",
                            "listFrom": "children",
                            "pages": [],
                            "parentPage": child.get("parentPage", ""),
                            "sortOrder": child.get("sortOrder", "asc"),
                            "orderBy": child.get("orderBy", ""),
                            "linkItems": child.get("linkItems", "true"),
                            "childDepth": child.get("childDepth", "1"),
                            "tagsMatch": child.get("tagsMatch", "any"),
                            "maxItems": child.get("maxItems", ""),
                        })
                        continue
                    else:
                        detalhe = child.get("query") or "(sem query nem listFrom)"
                        motivo = f"RELATED SUGGESTIONS (modo tag): {detalhe}"
                    categoria = "related_suggestions"
                else:
                    detalhe = child.get("fragmentVariationPath") or ""
                    motivo = f"EXPERIENCE FRAGMENT: sem mapeamento automático ({detalhe})"
                    categoria = "experience_fragment"
                skipped.append({"path": name, "resourceType": rt, "categoria": categoria,
                                "motivo": motivo, "ref": detalhe})
                continue

            # Tipo desconhecido: sinaliza, mas ainda olha dentro.
            skipped.append({"path": name, "resourceType": rt,
                            "categoria": "tipo_nao_reconhecido",
                            "motivo": f"TIPO NÃO RECONHECIDO: {rt}"})
            walk(child, col_width)

    walk(jcr_content)
    return components, skipped


# ============================================================
# Auditoria: conferir 100% do conteúdo migrado
# ============================================================

def contar_conteudo_migravel(jcr_content):
    """Conta TODO conteúdo real de um jcr:content, independente de o
    script saber migrá-lo ou não.

    É o denominador da conferência: 'quanto conteúdo existe na origem'.
    Conta só o que é conteúdo de verdade — texto com palavras, imagem com
    arquivo, botão com título — ignorando invólucros (container) e nós de
    configuração (pageproperties).

    Devolve um Counter por tipo de conteúdo.
    """
    contagem = Counter()

    def walk(node):
        for _, child in list_child_nodes(node):
            rt = child.get("sling:resourceType", "")

            if not rt or rt in KNOWN_CONTAINER_TYPES:
                walk(child)
                continue
            if rt in IGNORE_NO_CONTENT_TYPES:
                continue

            if rt in TEXT_TYPES and is_meaningful_text(child.get("text", "")):
                contagem["text"] += 1
            elif rt in TABLE_TYPES and is_meaningful_text(child.get("text", "")):
                contagem["table"] += 1
            elif rt in IMAGE_TYPES and child.get("fileReference"):
                contagem["image"] += 1
            elif rt in HEADING_TYPES and str(child.get("text", "")).strip():
                contagem["heading"] += 1
            elif rt in TITLE_TYPES and str(child.get("jcr:title", "") or "").strip():
                # 'title' do GWI vira o mesmo componente que o heading.
                contagem["heading"] += 1
            elif rt in BUTTON_TYPES and str(child.get("jcr:title", "")).strip():
                contagem["button"] += 1
            elif rt in DOWNLOAD_TYPES and child.get("fileReference"):
                contagem["download"] += 1
            elif rt in VIDEO_TYPES and child.get("youtubeVideoId"):
                contagem["embed"] += 1
            elif rt in TABS_TYPES:
                # Só conta se alguma aba tiver rótulo ou conteúdo — mesmo
                # critério do extract_content. Um tabs cujos itens estão
                # todos sem cq:panelTitle e sem filhos é componente vazio
                # (existe em pastas de teste do GWI), não conteúdo perdido.
                tem_algo = any(
                    str(item.get("cq:panelTitle") or "").strip() or list_child_nodes(item)
                    for _, item in list_child_nodes(child)
                )
                if tem_algo:
                    contagem["tabs"] += 1
            elif rt in PRODUCTLISTING_TYPES or rt in SUPPLIERLIST_TYPES:
                # Idem: só conta se tem de onde listar.
                if (child.get("pages") or child.get("parentPage")
                        or child.get("rootPath")):
                    contagem["list"] += 1
            elif rt in DOWNLOADLIST_TYPES:
                if child.get("directory"):
                    contagem["downloadlist"] += 1
            elif rt in CAROUSEL_TYPES:
                # A maioria dos slides é imagem, mas achado real
                # (sony-imx277cqt-c) mostrou um slide de VÍDEO dentro do
                # carousel também. Conta o carousel aqui; os slides em si
                # (imagem OU vídeo) são contados pelo walk(child) no fim
                # da função, que desce em TODO nó, não só containers.
                if any(item.get("fileReference") or item.get("youtubeVideoId")
                       for _, item in list_child_nodes(child)):
                    contagem["carousel"] += 1
            elif rt in IMAGEPACK_TYPES:
                # Invólucro: o conteúdo dentro é contado ao descer (walk),
                # aqui só registra o próprio flexcontainer se tiver filhos.
                if list_child_nodes(child):
                    contagem["flexcontainer"] += 1
            elif rt in MANUAL_REVIEW_TYPES:
                contagem["nao_migravel"] += 1
            elif rt.startswith("macnicagwi/") or rt.startswith("core/"):
                # Componente de conteúdo que o script ainda não trata.
                contagem["nao_migravel"] += 1

            walk(child)

    walk(jcr_content)
    return contagem


def auditar_migracao(origem_jcr, contagens_migradas, title_block=True,
                     tem_descricao=False):
    """Compara o conteúdo da ORIGEM com o que foi efetivamente migrado.

    Responde a pergunta do Bruno: "quantos % do conteúdo foi migrado?"

    contagens_migradas é o dict devolvido por build_content_payload. Os
    blocos que o migrate CRIA (o título da página e o texto derivado da
    descrição) não existem como componente na origem, então são
    descontados antes de comparar — senão o total migrado fica
    artificialmente maior que o da origem.

    Devolve um dict com o comparativo por tipo e o percentual geral.
    """
    na_origem = contar_conteudo_migravel(origem_jcr)

    migrado = Counter(contagens_migradas)
    # Metadado de página, não bloco de conteúdo — fora da conta.
    for meta in ("tags", "seo"):
        migrado.pop(meta, None)
    # Descontar o que o migrate CRIA do nada e não veio da origem.
    if title_block:
        migrado["title"] = max(0, migrado.get("title", 0) - 1)
    if tem_descricao:
        migrado["text"] = max(0, migrado.get("text", 0) - 1)
    # 'heading' do GWI vira componente 'title' no GLOBAL2 — normalizar
    # para comparar maçã com maçã.
    migrado["heading"] = migrado.get("heading", 0) + migrado.pop("title", 0)

    tipos = sorted((set(na_origem) | set(migrado)) - {"nao_migravel"})
    detalhe = {}
    for t in tipos:
        detalhe[t] = {"origem": na_origem.get(t, 0), "migrado": migrado.get(t, 0)}

    total_origem = sum(v for k, v in na_origem.items() if k != "nao_migravel")
    # Só conta como "migrado" até o que existia na origem: um excesso num
    # tipo (ex: um bloco extra que o script cria) não pode mascarar falta
    # em outro. Sem esse teto, a cobertura passa de 100% e esconde perda.
    total_migrado = sum(min(v["migrado"], v["origem"]) for v in detalhe.values())
    nao_migravel = na_origem.get("nao_migravel", 0)

    return {
        "detalhe": detalhe,
        "total_origem": total_origem,
        "total_migrado": total_migrado,
        "nao_migravel": nao_migravel,
        "pct": round(100 * total_migrado / total_origem, 1) if total_origem else 100.0,
        "completo": total_migrado >= total_origem,
    }


# ============================================================
# Taxonomia de tags (mai: / macnica-atd-europe:)
# ============================================================
#
# Achados em TAGS-taxonomia-achados.md (11/09/2026), confirmados de novo
# lendo a árvore ao vivo e comparando um par origem/destino real
# (sony-imx174llj-c, GWI vs GLOBAL2 já migrado por outra pessoa do time)
# antes de implementar:
#   - o NOME da propriedade não muda entre GWI e GLOBAL2 (manufacturer,
#     businessCategories, resolution, shuttertype, pixelsize,
#     opticalformat, interface, productcategory, productFamily) —
#     é cópia de propriedade, não remapeamento.
#   - o formato do valor (string solta vs lista) também não muda —
#     copiar como veio.
#   - sensorcategory e sensortype foram OMITIDAS na página de referência
#     (confirma achados 3.2 e 3.3 do documento: tag inválida = omitir).
#
# Regra: nunca inventar tag — se o valor não bater com a taxonomia real
# depois da correção mecânica, omitir a propriedade inteira e reportar
# como pendência.

# Templates onde a taxonomia dedicada é ESPERADA (seção 2 do
# levantamento). Só informativo: NÃO é usado para filtrar — ver a
# docstring de build_tag_props. O teste real em macnica-products achou
# tags em 'productpage' e 'basepage' também, e filtrar por template
# fazia elas sumirem em silêncio.
PRODUCT_TAG_RESOURCE_TYPES = {
    "macnicagwi/components/page/maeproductpage",
    "macnicaglobal2/components/maeproductpage",
    "macnicagwi/components/page/technicalarticlepage",
    "macnicaglobal2/components/technicalarticlepage",
}

# Propriedade dedicada -> categoria da taxonomia que ela deve referenciar.
# Mesmo nome de propriedade no destino (confirmado no exemplo real acima).
# 'manufacturer' (singular, GWI) mapeia para a categoria 'manufacturers'
# (plural) — é a correção mecânica #1 do documento; o NOME da propriedade
# continua singular, só o segmento do valor é que precisa bater no plural.
TAG_PROPERTY_TO_CATEGORY = {
    "manufacturer": "manufacturers",
    "businessCategories": "business-categories",
    "interface": "interface",
    "resolution": "resolution",
    "pixelsize": "Pixel-size",
    "opticalformat": "optical-format",
    "shuttertype": "shutter-type",
    "sensortype": "sensor-type",
    "productcategory": "product-category",
    "productFamily": "product-families",
    "technology": "technology",
}

# sensorcategory (achado #2): SEMPRE descartada — a categoria
# 'sensor-category' só existe no namespace da OUTRA região, e a
# informação já está redundante em 'sensortype'. Confirmado como
# descarte correto no exemplo real migrado. Nunca copiar.
DROPPED_TAG_PROPERTIES = {"sensorcategory"}

# Propriedades "sujas" com sufixo numérico observadas na origem
# (ex: 'shuttertype1', 'interface1', 'sensortype1', 'opticalformat1',
# 'pixelsize1'), sempre apontando para o namespace da REGIÃO ERRADA ou
# para uma categoria com sufixo que não existe em lugar nenhum
# ('shutter-type-2', 'optical-format-1', 'sensor-type-1'). Achado nesta
# implementação, não estava no documento original. Nunca copiar — são
# resíduo, a propriedade sem sufixo já tem o valor correto.
IGNORED_DIRTY_TAG_SUFFIX_RE = re.compile(r"^(manufacturer|businessCategories|interface|"
                                         r"resolution|pixelsize|opticalformat|shuttertype|"
                                         r"sensortype|sensorcategory|productcategory|"
                                         r"productFamily|technology)\d+$")

REGION_NAMESPACE = {
    "americas": "mai",
    "europe": "macnica-atd-europe",
}


def detect_tag_region(source_path):
    """Deriva a região (namespace de tags) a partir do caminho de origem.

    Confirmado no documento: Americas usa 'mai:', Europa usa
    'macnica-atd-europe:'. Nunca misturar (bug #2 nasceu de mistura).
    """
    if "/eu/" in source_path or "atd-europe" in source_path:
        return "europe"
    return "americas"


def load_tag_taxonomy(session, base_url, auth_tracker, tags_root=None):
    """Lê a árvore real de tags (ambos namespaces) e devolve

        {"mai": {"business-categories": {"semiconductors", ...}, ...},
         "macnica-atd-europe": {...}}

    Uma leitura só, cacheável pelo chamador — usada para VALIDAR toda
    tag antes de gravar, nunca para adivinhar uma tag que não exista.
    """
    tags_root = tags_root or CONFIG["tags_root"]
    taxonomy = {}
    for namespace in REGION_NAMESPACE.values():
        data, status = get_json(session, urljoin(base_url, f"{tags_root}/{namespace}.5.json"),
                                auth_tracker=auth_tracker)
        categories = {}
        if data:
            for cat_name, cat_node in list_child_nodes(data):
                children = {child_name for child_name, _ in list_child_nodes(cat_node)}
                categories[cat_name] = children
        taxonomy[namespace] = categories
    return taxonomy


def _validar_segmento(namespace, categoria_esperada, segmento, categories, segment_index):
    """Valida um segmento contra a taxonomia real, com a correção mecânica
    #3 (segmento pendurado na categoria pai errada, mas existe em outra
    categoria da MESMA taxonomia). Devolve (categoria_final, motivo_erro).
    motivo_erro é None quando válido.
    """
    if segmento in categories.get(categoria_esperada, set()):
        return categoria_esperada, None
    donos = segment_index.get(segmento, set())
    if len(donos) == 1:
        return next(iter(donos)), None
    if len(donos) > 1:
        return None, f"segmento '{segmento}' ambíguo entre categorias {sorted(donos)}"
    return None, (f"segmento '{segmento}' não existe em nenhuma categoria de "
                  f"{namespace}: (esperada: {categoria_esperada})")


def build_product_tags(jcr_content, region, taxonomy):
    """Extrai e corrige as tags dedicadas de uma página de produto do GWI.

    Copia a PROPRIEDADE com o mesmo nome (confirmado no exemplo real:
    GWI e GLOBAL2 usam os mesmos nomes de propriedade), preservando o
    formato do valor (string ou lista) — só troca o segmento de
    categoria quando a correção mecânica exigir, e VALIDA todo segmento
    contra a árvore real antes de aceitar.

    Ignora por completo (nem tenta corrigir, nem gera pendência):
      - DROPPED_TAG_PROPERTIES (sensorcategory)
      - propriedades "sujas" com sufixo numérico (achado desta sessão)

    Devolve (props, pendencias). props é propriedade -> valor pronto
    para o payload (string "ns:categoria/segmento" ou lista deles).
    """
    namespace = REGION_NAMESPACE[region]
    categories = taxonomy.get(namespace, {})
    segment_index = {}
    for cat_name, children in categories.items():
        for seg in children:
            segment_index.setdefault(seg, set()).add(cat_name)

    props = {}
    pendencias = []

    def registrar_pendencia(prop, valor_bruto, motivo):
        pendencias.append({"path": prop, "resourceType": "(propriedade de tag)",
                           "categoria": "tag_invalida",
                           "motivo": f"TAG INVÁLIDA ({prop}={valor_bruto!r}): {motivo}"})

    def corrigir_um_valor(prop, categoria_esperada, raw_item):
        if not raw_item or not isinstance(raw_item, str):
            return None, "valor vazio ou não-string"
        valor = raw_item.split(":", 1)[-1] if ":" in raw_item else raw_item
        if "/" not in valor:
            return None, "formato inesperado, sem 'categoria/segmento'"
        _, segmento = valor.split("/", 1)
        categoria_final, erro = _validar_segmento(
            namespace, categoria_esperada, segmento, categories, segment_index)
        if erro:
            return None, erro
        return f"{namespace}:{categoria_final}/{segmento}", None

    for prop, raw_value in jcr_content.items():
        if prop in DROPPED_TAG_PROPERTIES:
            continue  # descarte confirmado, não é pendência (redundante com sensortype)
        if IGNORED_DIRTY_TAG_SUFFIX_RE.match(prop):
            continue  # resíduo com sufixo numérico, propriedade sem sufixo já é a fonte
        if prop not in TAG_PROPERTY_TO_CATEGORY:
            continue

        categoria_esperada = TAG_PROPERTY_TO_CATEGORY[prop]

        if isinstance(raw_value, list):
            corrigidos = []
            for item in raw_value:
                valor_final, erro = corrigir_um_valor(prop, categoria_esperada, item)
                if erro:
                    registrar_pendencia(prop, item, erro)
                else:
                    corrigidos.append(valor_final)
            if corrigidos:
                props[prop] = corrigidos
        elif isinstance(raw_value, str):
            valor_final, erro = corrigir_um_valor(prop, categoria_esperada, raw_value)
            if erro:
                registrar_pendencia(prop, raw_value, erro)
            else:
                props[prop] = valor_final

    return props, pendencias


# Propriedade dedicada -> campo "Product Details" (pd_*) derivado dela.
# Confirmado em 13/09/2026 comparando 3 pares reais Sony (imx277cqt-c,
# imx174llj-c, imx273llr-c): GLOBAL2 tem pd_description=jcr:description,
# pd_interface=interface, pd_pixelSize=pixelsize, pd_resolution=resolution
# — mesmo valor, só o nome da propriedade muda de minúsculo para
# camelCase com prefixo pd_.
PD_PROPERTY_SOURCE = {
    "pd_interface": "interface",
    "pd_resolution": "resolution",
    "pd_pixelSize": "pixelsize",
}


def build_pd_props(jcr_content, page_name, manufacturer_slug=None):
    """Deriva os campos 'Product Details' (pd_*) a partir do que já foi
    migrado, sem propriedade nova nenhuma do GWI — são todos calculados.

    pd_modelName: confirmado em 3 pares reais Sony que é o NOME DO NÓ da
    página SEM o prefixo do fabricante, maiúsculo
    ('sony-imx277cqt-c' -> 'IMX277CQT-C'). O prefixo removido é o slug do
    FABRICANTE de verdade (manufacturer_slug, ex: 'sony', vindo da tag
    'manufacturer' já migrada) — não "tudo antes do primeiro hífen": um
    nome como 'tqma67xx-embedded-cortex-a53-module' não segue o padrão
    '<fabricante>-<modelo>' e cortar no primeiro hífen erraria o modelo.
    Sem manufacturer_slug (ou se o nome não começar por ele), usa o nome
    inteiro maiúsculo — não confirmado fora do caso Sony, mas evita
    cortar errado.

    pd_isModelNameLinkToPage: sempre 'true' nos 3 exemplos confirmados.

    As demais (pd_interface, pd_resolution, pd_pixelSize) só entram se a
    propriedade de origem existir — mesma regra de "não inventar" das
    tags. pd_description é tratado à parte no migrate porque description
    já passa por reescrita de links.
    """
    props = {}
    for pd_prop, origem in PD_PROPERTY_SOURCE.items():
        valor = jcr_content.get(origem)
        if valor:
            props[pd_prop] = valor

    modelo = page_name.upper()
    if manufacturer_slug:
        prefixo = f"{manufacturer_slug.lower()}-"
        if page_name.lower().startswith(prefixo):
            modelo = page_name[len(prefixo):].upper()
    if modelo:
        props["pd_modelName"] = modelo
        props["pd_isModelNameLinkToPage"] = "true"

    return props


def build_tag_props(source_resource_type, jcr_content, region, taxonomy):
    """Ponto de entrada usado pelo migrate: extrai as tags da origem e
    devolve (props_para_payload, pendencias), pronto para o jcr:content
    da página nova.

    O CRITÉRIO É O DADO, NÃO O TEMPLATE. A seção 2 do levantamento
    dizia "só maeproductpage/technicalarticlepage têm taxonomia", e
    filtrar por resourceType parecia seguro — mas o teste real em
    macnica-products mostrou o contrário:
        streal  -> macnicagwi/components/page/productpage  (não 'mae')
                   tem manufacturer + businessCategories + cq:tags
        smpte…  -> macnicagwi/components/page/basepage
                   tem cq:tags
    Filtrar por template descartava essas tags EM SILÊNCIO, que é
    exatamente o que a regra "nada some em silêncio" proíbe. Então o
    porteiro é: a página tem propriedade de tag? migra. O resourceType
    fica só como informação.
    """

    props, pendencias = build_product_tags(jcr_content, region, taxonomy)
    # cq:tags também pode existir já correto no GWI (achado: 0% erro no
    # array em si) — copiar direto se presente, sem tentar corrigir.
    cq_tags = jcr_content.get("cq:tags")
    if isinstance(cq_tags, list) and cq_tags:
        props["cq:tags"] = [str(t) for t in cq_tags]
    return props, pendencias


# ============================================================
# SEO / propriedades de página
# ============================================================
#
# Diretriz do cliente (guidelines-to-follow.txt, item 2 "Page
# Properties"): "Update the SEO information, including the title and
# meta description."
#
# Confirmado com dado real nas 6 páginas de macnica-products (GWI):
# 6/6 têm pageTitle E navTitle CURADOS, diferentes do jcr:title, e 5/6
# têm keywords. Exemplo (macnica-cv75):
#     jcr:title : 'CV75 SoM | Edge AI Vision for UAV/UAS and Robotics'
#     pageTitle : 'iENSO CV75 - Embedded Vision & Edge AI Platform | ...'
#     navTitle  : 'iENSO CV75'
# Ou seja: copiar o título em cima dessas três destrói SEO curado em
# 100% dos casos. São copiadas da origem, com o título só como fallback.
SEO_PROPERTIES = ("pageTitle", "navTitle", "keywords")


def build_seo_props(jcr_content):
    """Propriedades de SEO/navegação a preservar da origem.

    Devolve só o que a origem realmente tem — quem chama decide o
    fallback (ver build_page_payload). jcr:description (meta
    description) não entra aqui: já é tratada à parte porque também
    vira bloco de conteúdo.
    """
    props = {}
    for prop in SEO_PROPERTIES:
        valor = jcr_content.get(prop)
        if isinstance(valor, str) and valor.strip():
            props[prop] = valor
    return props


# ============================================================
# Montagem do payload (GLOBAL2)
# ============================================================

def build_page_payload(title, template_path, description=None, hide_in_nav=False,
                       extra_props=None, seo_props=None):
    """Payload de uma página vazia: título, template, resourceType.

    pageTitle e navTitle vêm de seo_props quando a origem os tem
    curados (o caso normal — ver SEO_PROPERTIES); o título só é usado
    como fallback para os que faltarem.

    'navTitle' foi CONFIRMADO em 11/09/2026 com exemplo autoral real do
    GLOBAL2 (sony-imx174llj-c, migrada por outra pessoa do time, tem
    navTitle='IMX174LLJ-C'). Deixou de ser convenção inferida.
    """
    seo_props = seo_props or {}
    payload = {
        "jcr:primaryType": "cq:Page",
        "jcr:content/jcr:primaryType": "cq:PageContent",
        "jcr:content/jcr:title": title,
        "jcr:content/pageTitle": seo_props.get("pageTitle", title),
        "jcr:content/navTitle": seo_props.get("navTitle", title),
        "jcr:content/cq:template": template_path,
        "jcr:content/sling:resourceType": PAGE_RESOURCE_TYPE,
    }
    if seo_props.get("keywords"):
        payload["jcr:content/keywords"] = seo_props["keywords"]
    if description:
        payload["jcr:content/jcr:description"] = description
    if hide_in_nav:
        # Diretriz do cliente: "Enable/select hide in Navigation for all pages"
        payload["jcr:content/hideInNav"] = "true"
    if extra_props:
        payload.update(extra_props)
    return payload


# Cores da alternância de "Alternative background Color Grading"
# (guidelines-to-follow.txt do cliente). Confirmado com o Bruno em
# 11/09/2026: alterna #fff / #f7f7f7 a cada bloco de conteúdo, na ordem
# em que são criados — não por seção, bloco a bloco. O primeiro bloco
# (o título) recebe a primeira cor da lista.
ALTERNATING_BACKGROUND_COLORS = ["#fff", "#f7f7f7"]

# Styles de padding do componente container. Os IDs vêm da policy real
# (/conf/macnicaglobal2/settings/wcm/policies/macnicaglobal2/components/
# content/container/policy_1586276378410700), grupos "【Padding -
# Top/Bottom】" e "【Padding - Left/Right】", e foram confirmados em uso
# numa página autoral real (test-gigadevice: todo container de 1º nível
# tem o Large L/R, a maioria combinado com Small T/B).
#
# Aplicados via 'cq:styleIds' (array) no nó do container — não existe
# propriedade "padding" direta; no AEM isso é style de policy.
STYLE_PADDING_TOP_BOTTOM_SMALL = "1717498052331"
STYLE_PADDING_LEFT_RIGHT_LARGE = "1717498053499"


class BlockBuilder:
    """Monta a estrutura de containers exigida — DOIS níveis.

    Confirmado com o Bruno (e com o exemplo autoral real de tq-systems):
    conteúdo migrado NÃO pode ficar todo solto num container só — cada
    bloco ganha o seu próprio container, filho direto do slot do
    template:

        root (responsivegrid)
          container            <- slot do template (nome FIXO, ver aviso
                                   abaixo — não é arbitrário)
            title_wrap          <- um container por bloco, cada um com
                                     backgroundColor alternado (ver
                                     ALTERNATING_BACKGROUND_COLORS)
              title
            text_1_wrap
              text_1
            image_1_wrap
              image_1

    ATÉ 11/09/2026 havia um nível intermediário extra ('containerpy',
    container-pai envolvendo todo o conteúdo). O Bruno pediu para
    removê-lo: os blocos ficam direto dentro do slot. O script
    aem_fix_containers.py promove esse nível nas páginas já criadas com
    a estrutura antiga.

    O NOME DO NÍVEL 1 ('container') NÃO é arbitrário — é obrigatório. Os
    4 templates do GLOBAL2 (mai-mae-product-page, mai-page-content,
    mai-page-top, mai-technical-article-page) definem sua estrutura fixa
    em /conf/.../<template>/structure, com um nó 'root' que já vem com
    experiencefragment (header), container_1885913789 (breadcrumb) e
    experiencefragment_860154339 (footer) herdados — e o ÚNICO filho
    marcado editable:true nos 4 é o nó chamado exatamente 'container'.
    A policy (/conf/.../<template>/policies) que autoriza cada tipo de
    componente (text, image, title, button...) está vinculada a esse
    MESMO NOME de nó dentro de 'root'.

    Um nome diferente nesse nível (ex: 'containerpy' usado como slot, até
    11/09/2026) não bate com nenhuma policy: o POST retorna 200 e o
    conteúdo fica gravado no JCR, mas o editor de autoria do AEM não sabe
    o que pode renderizar ali e mostra a página em branco — sem erro, sem
    aviso. O nível do bloco, dentro do slot já autorizado pela policy,
    não tem essa restrição de nome.
    """

    def __init__(self, payload=None, slot="jcr:content/root/container"):
        self.payload = payload if payload is not None else {}
        self.slot = slot
        self.base = slot
        self.counters = {}
        self._bloco_n = 0
        # Largura de coluna do PRÓXIMO bloco, em doze avos. None = largura
        # cheia. Quem monta o payload seta isto antes de cada add(); ver
        # o comentário em add().
        self.col_width = None
        self._init_root()

    def _init_root(self):
        # O slot do template — nome fixo, ver aviso na classe.
        self.payload.setdefault(f"{self.slot.rsplit('/', 1)[0]}/jcr:primaryType",
                                "nt:unstructured")
        self.payload.setdefault(f"{self.slot.rsplit('/', 1)[0]}/sling:resourceType",
                                RESPONSIVE_GRID_RT)
        self.payload.setdefault(f"{self.slot}/jcr:primaryType", "nt:unstructured")
        self.payload.setdefault(f"{self.slot}/sling:resourceType", CONTAINER_RT)

    def next_name(self, kind):
        self.counters[kind] = self.counters.get(kind, 0) + 1
        return f"{kind}_{self.counters[kind]}"

    def add(self, block_name, resource_type, props):
        """Cria um container próprio e põe o componente dentro dele.

        O container do bloco recebe:
          - backgroundColor alternado (ALTERNATING_BACKGROUND_COLORS)
          - padding Left/Right Large em TODOS os containers
          - padding Top/Bottom Small só no PRIMEIRO (o do título)
        """
        primeiro = self._bloco_n == 0
        cor = ALTERNATING_BACKGROUND_COLORS[self._bloco_n % len(ALTERNATING_BACKGROUND_COLORS)]
        self._bloco_n += 1

        # Padding L/R Large em todos; T/B Small só no primeiro container.
        styles = [STYLE_PADDING_LEFT_RIGHT_LARGE]
        if primeiro:
            styles.append(STYLE_PADDING_TOP_BOTTOM_SMALL)

        wrap = f"{self.base}/{block_name}_wrap"
        self.payload[f"{wrap}/jcr:primaryType"] = "nt:unstructured"
        self.payload[f"{wrap}/sling:resourceType"] = CONTAINER_RT
        self.payload[f"{wrap}/backgroundColor"] = cor
        self.payload[f"{wrap}/cq:styleIds"] = styles
        # Sem o TypeHint, uma lista de 1 elemento é gravada como String
        # simples pelo Sling — e as páginas autorais reais têm cq:styleIds
        # sempre como String[]. Confirmado comparando com test-gigadevice.
        self.payload[f"{wrap}/cq:styleIds@TypeHint"] = "String[]"

        # Coluna. No GWI a largura não é propriedade do componente: fica em
        # `cq:responsive/default/width`, em doze avos, no container que
        # embrulha o bloco — três colunas são três `resizablecontainer`
        # irmãos com width=4. Sem copiar isso, o destino recebe os mesmos
        # textos empilhados em largura cheia, que foi o que aconteceu com o
        # "Portfolio At-a-Glance" da altera.
        #
        # `phone` fica em 12 de propósito, como no GWI: em tela estreita as
        # colunas voltam a empilhar.
        if self.col_width:
            resp = f"{wrap}/cq:responsive"
            self.payload[f"{resp}/jcr:primaryType"] = "nt:unstructured"
            self.payload[f"{resp}/default/jcr:primaryType"] = "nt:unstructured"
            self.payload[f"{resp}/default/width"] = str(self.col_width)
            self.payload[f"{resp}/default/offset"] = "0"
            self.payload[f"{resp}/phone/jcr:primaryType"] = "nt:unstructured"
            self.payload[f"{resp}/phone/width"] = "12"
            self.payload[f"{resp}/phone/offset"] = "0"

        comp = f"{wrap}/{block_name}"
        self.payload[f"{comp}/jcr:primaryType"] = "nt:unstructured"
        self.payload[f"{comp}/sling:resourceType"] = resource_type
        for k, v in props.items():
            self.payload[f"{comp}/{k}"] = v
        return comp


def build_content_payload(title, components, template_path, description=None,
                          hide_in_nav=False, rewrite_links=True,
                          from_prefix=None, to_prefix=None, title_block=True,
                          seo_props=None):
    """Payload completo: página + todos os blocos de conteúdo.

    Devolve (payload, contagens_por_tipo).

    rewrite_links=True troca o prefixo do site em todo link interno
    (linkURL de botões e href dentro de texto rico), preservando o resto
    do caminho.
    """
    def link(url):
        return rewrite_link(url, from_prefix, to_prefix) if rewrite_links else url

    def html(texto):
        # Limpa os blocos de espaçamento vazios ('<p>&nbsp;</p>' que o
        # autor do GWI usava como "enter") ANTES de reescrever os links —
        # a ordem não muda o resultado, mas assim o regex de href trabalha
        # sobre um HTML já menor.
        texto = strip_empty_blocks(texto)
        return rewrite_links_in_html(texto, from_prefix, to_prefix) if rewrite_links else texto

    # A descrição também é um campo de texto rico: reescrever aqui, uma vez,
    # para a propriedade da página e o bloco derivado dela ficarem iguais.
    description = html(description) if description else description

    payload = build_page_payload(title, template_path, description, hide_in_nav,
                                 seo_props=seo_props)
    b = BlockBuilder(payload)
    contagens = {}

    def conta(kind):
        contagens[kind] = contagens.get(kind, 0) + 1

    if title_block:
        b.add("title", "macnicaglobal2/components/content/title",
              {"jcr:title": title, "type": "h1"})
        conta("title")

    # A description NÃO vira bloco de texto. Ela é a META DESCRIPTION da
    # origem — o build_page_payload acima já a grava em jcr:description, que
    # é o lugar dela. Gravar também no corpo fazia a página abrir com um
    # parágrafo que não existe em lugar nenhum da página do GWI: em
    # `4-helio-view-hardware` era "Transform your approach to FPGA with our
    # Helio View hardware vWorkshop...". Em `semiconductors` (17/09/2026)
    # eram 155 páginas assim.
    #
    # Quando o GWI de fato MOSTRA esse texto no corpo — description bem
    # escrita costuma repetir a primeira frase da página —, ele chega aqui
    # pelo componente `text` da origem, via extract_content. Não se perde
    # nada tirando o bloco daqui; ver aem_restaurar_description.py, que
    # limpou as páginas já migradas com a mesma distinção.

    for comp in components:
        kind = comp["kind"]
        # Largura da coluna em que este bloco nasceu no GWI (extract_content
        # anota em colWidth). O BlockBuilder grava no _wrap do bloco.
        b.col_width = comp.get("colWidth")

        if kind == "text":
            b.add(b.next_name("text"), "macnicaglobal2/components/content/text",
                  {"text": html(comp["html"]), "textIsRich": "true"})
            conta("text")

        elif kind == "image":
            props = {"fileReference": comp["fileReference"]}
            if comp.get("alt"):
                props["alt"] = comp["alt"]
            b.add(b.next_name("image"), "macnicaglobal2/components/content/image", props)
            conta("image")

        elif kind == "heading":
            b.add(b.next_name("heading"), "macnicaglobal2/components/content/title",
                  {"jcr:title": comp["text"], "type": comp["type"]})
            conta("heading")

        elif kind == "button":
            b.add(b.next_name("button"), "macnicaglobal2/components/content/button",
                  {"jcr:title": comp["title"], "linkURL": link(comp["linkURL"]),
                   "linkTarget": comp["linkTarget"]})
            conta("button")

        elif kind == "download":
            # A propriedade fileReference é INFERIDA por padrão (os outros
            # componentes confirmados mantêm o nome de propriedade do GWI,
            # só muda o resourceType). Nunca confirmada com exemplo autoral
            # real de download — conferir visualmente antes de confiar.
            b.add(b.next_name("download"), "macnicaglobal2/components/content/download",
                  {"fileReference": comp["fileReference"], "jcr:title": comp["label"]})
            conta("download")

        elif kind == "table":
            b.add(b.next_name("table"), "macnicaglobal2/components/content/table",
                  {"text": html(comp["html"]), "textIsRich": "true"})
            conta("table")

        elif kind == "embed":
            b.add(b.next_name("embed"), "macnicaglobal2/components/content/embed",
                  {"embeddableResourceType": comp["embeddableResourceType"],
                   "youtubeVideoId": comp["youtubeVideoId"],
                   "type": "embeddable", "layout": "responsive",
                   "youtubeAutoPlay": comp["youtubeAutoPlay"],
                   "youtubeLoop": comp["youtubeLoop"],
                   "youtubeMute": comp["youtubeMute"],
                   "youtubeRel": comp["youtubeRel"],
                   "youtubePlaysInline": comp["youtubePlaysInline"]})
            conta("embed")

        elif kind == "related_static_links":
            # Cada página escolhida vira um botão. Não é o ideal — perde a
            # semântica de "lista de relacionados" — mas é o que temos
            # confirmado hoje. Investigar o componente 'list' do GLOBAL2.
            for page_path in comp["pages"]:
                b.add(b.next_name("button"), "macnicaglobal2/components/content/button",
                      {"jcr:title": slug_to_label(page_path),
                       "linkURL": link(page_path), "linkTarget": "_self"})
                conta("button")

        elif kind == "list":
            # 'list' do GLOBAL2 — mesmas propriedades do productlisting do
            # GWI, confirmado com exemplo autoral real.
            props = {
                "listFrom": comp["listFrom"],
                "sortOrder": comp["sortOrder"],
                "linkItems": comp["linkItems"],
                "childDepth": comp["childDepth"],
                "tagsMatch": comp["tagsMatch"],
            }
            if comp.get("orderBy"):
                props["orderBy"] = comp["orderBy"]
            if comp.get("maxItems"):
                props["maxItems"] = comp["maxItems"]
            if comp["listFrom"] == "static" and comp["pages"]:
                props["pages"] = [link(p) for p in comp["pages"]]
                props["pages@TypeHint"] = "String[]"
            elif comp["listFrom"] == "children" and comp["parentPage"]:
                props["parentPage"] = link(comp["parentPage"])
            b.add(b.next_name("list"), "macnicaglobal2/components/content/list", props)
            conta("list")

        elif kind == "downloadlist":
            # Confirmado com exemplo autoral real (sony-imx147lqt-c):
            # directory + orderBy + sortOrder + maxItems.
            # O 'directory' aponta para o DAM do GWI e NÃO é reescrito —
            # migração de assets é tarefa à parte.
            props = {"directory": comp["directory"],
                     "sortOrder": comp["sortOrder"]}
            if comp.get("orderBy"):
                props["orderBy"] = comp["orderBy"]
            if comp.get("maxItems"):
                props["maxItems"] = comp["maxItems"]
            b.add(b.next_name("downloadlist"),
                  "macnicaglobal2/components/content/downloadlist", props)
            conta("downloadlist")

        elif kind == "carousel":
            # Galeria de imagens (e ocasionalmente vídeo — achado real em
            # sony-imx277cqt-c): cada slide vira 'image' ou 'embed' dentro
            # do carousel, como item_N (mesma convenção do tabs).
            nome_car = b.next_name("carousel")
            comp_path = b.add(nome_car, "macnicaglobal2/components/content/carousel", {})
            conta("carousel")
            for idx, slide in enumerate(comp["slides"], 1):
                item = f"{comp_path}/item_{idx}"
                b.payload[f"{item}/jcr:primaryType"] = "nt:unstructured"
                if slide["tipo"] == "image":
                    b.payload[f"{item}/sling:resourceType"] = \
                        "macnicaglobal2/components/content/image"
                    b.payload[f"{item}/fileReference"] = slide["fileReference"]
                    if slide.get("alt"):
                        b.payload[f"{item}/alt"] = slide["alt"]
                    conta("image")
                else:  # embed (vídeo)
                    b.payload[f"{item}/sling:resourceType"] = \
                        "macnicaglobal2/components/content/embed"
                    b.payload[f"{item}/embeddableResourceType"] = slide["embeddableResourceType"]
                    b.payload[f"{item}/youtubeVideoId"] = slide["youtubeVideoId"]
                    b.payload[f"{item}/type"] = "embeddable"
                    b.payload[f"{item}/layout"] = "responsive"
                    for prop in ("youtubeAutoPlay", "youtubeLoop", "youtubeMute",
                                "youtubeRel", "youtubePlaysInline"):
                        b.payload[f"{item}/{prop}"] = slide[prop]
                    conta("embed")
                if slide.get("title"):
                    b.payload[f"{item}/cq:panelTitle"] = slide["title"]

        elif kind == "flexcontainer":
            # Confirmado com exemplo autoral real (test-gigadevice): o
            # flexcontainer tem flexcontaineritem como filhos, e o conteúdo
            # vai DENTRO de cada item — dois níveis, não um.
            nome_flex = b.next_name("flexcontainer")
            comp_path = b.add(nome_flex,
                              "macnicaglobal2/components/content/flexcontainer", {})
            conta("flexcontainer")
            for idx, sub in enumerate(comp["components"], 1):
                item = f"{comp_path}/flexcontaineritem_{idx}"
                b.payload[f"{item}/jcr:primaryType"] = "nt:unstructured"
                b.payload[f"{item}/sling:resourceType"] = \
                    "macnicaglobal2/components/content/flexcontaineritem"
                if add_simple_block(b.payload, item, sub, link, html):
                    conta(sub["kind"])

        elif kind == "tabs":
            # Estrutura confirmada com exemplo autoral real: o nó 'tabs'
            # não tem propriedade própria; cada aba é um container com
            # cq:panelTitle + o conteúdo dentro.
            nome_tabs = b.next_name("tabs")
            comp_path = b.add(nome_tabs, "macnicaglobal2/components/content/tabs", {})
            conta("tabs")
            for idx, aba in enumerate(comp["abas"], 1):
                item_path = f"{comp_path}/item_{idx}"
                b.payload[f"{item_path}/jcr:primaryType"] = "nt:unstructured"
                b.payload[f"{item_path}/sling:resourceType"] = CONTAINER_RT
                b.payload[f"{item_path}/layout"] = "responsiveGrid"
                if aba["title"]:
                    b.payload[f"{item_path}/cq:panelTitle"] = aba["title"]
                # O conteúdo de cada aba entra direto no container da aba,
                # sem os _wrap/cor/padding — esses são só do nível da página.
                for sub in aba["components"]:
                    add_simple_block(b.payload, item_path, sub, link, html)
                    conta(sub["kind"])

    return b.payload, contagens


def add_simple_block(payload, base, comp, link, html):
    """Grava um componente simples direto sob 'base', sem container-wrap.

    Usado para o conteúdo DENTRO das abas do tabs: ali o container da aba
    já é o invólucro, então cada bloco não precisa (nem deve) ganhar o seu
    próprio '_wrap' com cor e padding.
    """
    kind = comp["kind"]
    mapa = {
        "text": ("macnicaglobal2/components/content/text",
                 lambda c: {"text": html(c["html"]), "textIsRich": "true"}),
        "table": ("macnicaglobal2/components/content/table",
                  lambda c: {"text": html(c["html"]), "textIsRich": "true"}),
        "heading": ("macnicaglobal2/components/content/title",
                    lambda c: {"jcr:title": c["text"], "type": c["type"]}),
        "image": ("macnicaglobal2/components/content/image",
                  lambda c: {"fileReference": c["fileReference"],
                             **({"alt": c["alt"]} if c.get("alt") else {})}),
        "button": ("macnicaglobal2/components/content/button",
                   lambda c: {"jcr:title": c["title"], "linkURL": link(c["linkURL"]),
                              "linkTarget": c["linkTarget"]}),
    }
    if kind not in mapa:
        return False
    resource_type, props_fn = mapa[kind]
    nome = f"{kind}_{sum(1 for k in payload if k.startswith(f'{base}/{kind}_')) + 1}"
    node = f"{base}/{nome}"
    payload[f"{node}/jcr:primaryType"] = "nt:unstructured"
    payload[f"{node}/sling:resourceType"] = resource_type
    for k, v in props_fn(comp).items():
        payload[f"{node}/{k}"] = v

    # Coluna dentro de aba. Aqui não há '_wrap' — o container da aba é
    # `layout=responsiveGrid`, então a largura vai no próprio nó do
    # componente. É o caso do "Portfolio At-a-Glance" da altera, onde as
    # três colunas vivem dentro da primeira aba.
    if comp.get("colWidth"):
        resp = f"{node}/cq:responsive"
        payload[f"{resp}/jcr:primaryType"] = "nt:unstructured"
        payload[f"{resp}/default/jcr:primaryType"] = "nt:unstructured"
        payload[f"{resp}/default/width"] = str(comp["colWidth"])
        payload[f"{resp}/default/offset"] = "0"
        payload[f"{resp}/phone/jcr:primaryType"] = "nt:unstructured"
        payload[f"{resp}/phone/width"] = "12"
        payload[f"{resp}/phone/offset"] = "0"
    return True


# ============================================================
# Clonagem fiel
# ============================================================

def should_skip_key(key):
    return key in SKIP_EXACT_KEYS or any(key.startswith(p) for p in SKIP_PREFIXES)


def flatten_node(node, base_path, payload):
    """Achata uma árvore JCR em chaves 'a/b/c' para POST.

    Descarta metadado que não faz sentido herdar (uuid, versionamento,
    datas de replicação).
    """
    for key, val in node.items():
        if should_skip_key(key):
            continue
        full = f"{base_path}/{key}" if base_path else key
        if isinstance(val, dict):
            flatten_node(val, full, payload)
        elif isinstance(val, list):
            payload[full] = [("" if item is None else str(item)) for item in val]
        elif isinstance(val, bool):
            payload[full] = "true" if val else "false"
        elif val is None:
            continue
        else:
            payload[full] = str(val)


def build_clone_payload(source_data, template_path=None):
    """Clona uma página, preservando a estrutura de containers — mas só
    o CONTEÚDO da própria página, nunca de páginas-filhas.

    Bug real encontrado em 16/09/2026: fetch_with_depth_fallback com
    profundidade alta, numa página de categoria com muitos produtos
    dentro (ex: 70), traz as páginas-filhas inteiras junto no mesmo
    JSON (cada uma é um 'cq:Page' completo). Achatar source_data por
    inteiro incluía esse conteúdo no payload da categoria — o Sling
    POST servlet então tentava criar as páginas-filhas na MESMA
    requisição da página-pai, e retornava 422 'invalid payload' (o pai
    ainda nem existia, então filho nenhum tem onde entrar).

    O migrate.py já processa cada página-filha na sua PRÓPRIA linha do
    mapping — não precisa (e não pode) vir carona no payload da mãe.
    Por isso só entra aqui 'jcr:content' e as chaves de nível 0 que não
    são cq:Page (metadados como jcr:primaryType, jcr:createdBy).
    """
    payload = {}
    for key, val in source_data.items():
        if isinstance(val, dict) and val.get("jcr:primaryType") == "cq:Page":
            continue  # página-filha: fica de fora, tem sua própria linha
        if key == "jcr:content":
            flatten_node(val, "jcr:content", payload)
        elif not should_skip_key(key) and not isinstance(val, dict):
            payload[key] = val
    if template_path:
        payload["jcr:content/cq:template"] = template_path
    payload.setdefault("jcr:primaryType", "cq:Page")
    payload.setdefault("jcr:content/jcr:primaryType", "cq:PageContent")
    return payload


# ============================================================
# Saída
# ============================================================

def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return path


def add_common_args(parser):
    """Flags que todo script usa, com defaults vindos do .env."""
    parser.add_argument("--base-url", default=CONFIG["base_url"])
    parser.add_argument("--timeout", type=int, default=CONFIG["timeout"])
    parser.add_argument("--max-pages", type=int, default=CONFIG["max_pages"])
    parser.add_argument("--delay", type=float, default=CONFIG["request_delay"])
    parser.add_argument("--no-prompt", action="store_true",
                        help="Falha em vez de pedir o cookie via getpass.")
    return parser


def print_header(titulo):
    print("=" * 66)
    print(titulo)
    print("=" * 66)


if __name__ == "__main__":
    print_header("aem_lib — configuração ativa")
    print(f"\n.env: {ENV_PATH}  ({'existe' if ENV_PATH.exists() else 'NÃO EXISTE, usando defaults'})\n")
    for k, v in CONFIG.items():
        print(f"  {k:22} = {v}")
    raw = os.environ.get("AEM_COOKIES", "").strip()
    if raw:
        c = parse_cookie_string(raw)
        print(f"\n  {'AEM_COOKIES':22} = {len(c)} cookies, "
              f"login-token {'presente' if 'login-token' in c else 'AUSENTE'}")
    else:
        print(f"\n  {'AEM_COOKIES':22} = vazio (scripts pedem via getpass)")
