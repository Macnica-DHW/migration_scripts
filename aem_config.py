#!/usr/bin/env python3
"""
Configuração compartilhada dos scripts de migração AEM (GWI -> GLOBAL2).

Lê o arquivo .env (sem depender de python-dotenv) e expõe:
  - as constantes de caminho/comportamento já com os defaults do projeto
  - build_session(), que monta a requests.Session autenticada

ORDEM DE PRECEDÊNCIA de cada valor:
  1. variável de ambiente já exportada no shell
  2. o que estiver no .env
  3. o default embutido aqui

AUTENTICAÇÃO: se AEM_COOKIES estiver preenchida no .env, é usada direto.
Se estiver vazia, cai no prompt getpass de sempre — então o script
continua funcionando mesmo sem .env configurado.

USO NOS SCRIPTS:
    from aem_config import CONFIG, build_session, add_common_args

    parser = argparse.ArgumentParser(...)
    add_common_args(parser)          # --base-url, --dry-run, --timeout...
    args = parser.parse_args()

    session, auth_tracker = build_session()
    base_url = args.base_url
"""

import getpass
import os
import sys
from pathlib import Path

import requests

ENV_PATH = Path(__file__).resolve().parent / ".env"


# ============================================================
# Leitura do .env
# ============================================================

def load_env(path=ENV_PATH):
    """Lê um .env simples (KEY=VALUE, # comenta a linha inteira).

    Não sobrescreve variáveis já exportadas no shell — ambiente ganha
    do arquivo, que é o comportamento esperado para rodar em CI ou com
    um cookie temporário via `AEM_COOKIES=... python3 script.py`.
    """
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # tira aspas se alguém colar o valor entre aspas
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


load_env()


def _get(key, default=""):
    return os.environ.get(key, default)


def _get_float(key, default):
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def _get_int(key, default):
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return int(default)


def _get_list(key, default=""):
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(";") if item.strip()]


# ============================================================
# Configuração
# ============================================================

CONFIG = {
    "base_url": _get("AEM_BASE_URL", "https://author-p53812-e590634.adobeaemcloud.com").rstrip("/"),

    # Origem — SOMENTE LEITURA
    "source_root": _get("AEM_SOURCE_ROOT", "/content/macnicagwi/americas/mai/en/products"),
    "gwi_prefix": _get("AEM_GWI_PREFIX", "/content/macnicagwi"),
    "global2_prefix": _get("AEM_GLOBAL2_PREFIX", "/content/macnicaglobal2"),

    # Destino — ÚNICO lugar onde se escreve
    "target_root": _get("AEM_TARGET_ROOT", "/content/copia-teste/americas/mai/en/products"),
    "target_prefix": _get("AEM_TARGET_PREFIX", "/content/copia-teste"),

    # Templates
    "templates_root": _get("AEM_TEMPLATES_ROOT", "/conf/macnicaglobal2/settings/wcm/templates"),
    "template_title": _get("AEM_TEMPLATE_TITLE", "Macnica Americas Product Page"),

    # DAM
    "dam_source_prefix": _get("AEM_DAM_SOURCE_PREFIX", "/content/dam/macnicagwi"),
    "dam_target_prefix": _get("AEM_DAM_TARGET_PREFIX", "/content/dam/copia-teste"),

    # Experience Fragments
    "ef_root": _get("AEM_EF_ROOT", "/content/experience-fragments/copia-teste/americas/mai/en/site"),
    "xf_template": _get("AEM_XF_TEMPLATE", "/conf/macnicaglobal2/settings/wcm/templates/xf-web-variation"),

    # Comportamento
    "source_depth": _get_int("AEM_SOURCE_DEPTH", 50),
    "request_delay": _get_float("AEM_REQUEST_DELAY", 0.05),
    "write_delay": _get_float("AEM_WRITE_DELAY", 0.1),
    "timeout": _get_int("AEM_TIMEOUT", 30),
    "max_pages": _get_int("AEM_MAX_PAGES", 3000),
    "auth_fail_threshold": _get_int("AEM_AUTH_FAIL_THRESHOLD", 5),
    "skip_path_contains": _get_list("AEM_SKIP_PATH_CONTAINS", "sony-image-sensors/sony-image-sensors"),
}

# Constantes de resourceType do GLOBAL2 (confirmadas na biblioteca real
# em /apps/macnicaglobal2/components/content)
PAGE_RESOURCE_TYPE = "macnicaglobal2/components/page"
CONTAINER_RESOURCE_TYPE = "macnicaglobal2/components/content/container"
RESPONSIVE_GRID_RESOURCE_TYPE = "wcm/foundation/components/responsivegrid"


# ============================================================
# Autenticação
# ============================================================

def parse_cookie_string(raw):
    """Quebra a string de cookies do 'Copy as cURL' num dicionário.

    Não decodifica nada: o login-token vem no formato
    login%3a<JWT>%3acrx.default e precisa ir inteiro, como está.
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


def get_cookie_string(prompt_if_missing=True):
    """Pega a string de cookies do .env/ambiente, ou pergunta via getpass."""
    raw = os.environ.get("AEM_COOKIES", "").strip()
    if raw:
        return raw, "env"
    if not prompt_if_missing:
        return "", "vazio"
    raw = getpass.getpass(
        "Cole a string COMPLETA de cookies (Copy as cURL, conteúdo depois de -b '...'): "
    ).strip()
    return raw, "prompt"


def build_session(prompt_if_missing=True, verbose=True):
    """Monta a Session autenticada e o auth_tracker.

    Retorna (session, auth_tracker). O auth_tracker é o dicionário de
    sempre: conta 401/403 seguidos e, ao bater o threshold, o script
    para e marca o restante do CSV como "NÃO TENTADO (sessão expirou)".
    """
    raw, origem = get_cookie_string(prompt_if_missing)
    if not raw:
        print("[erro] nenhuma string de cookies disponível. Preencha AEM_COOKIES "
              "no .env ou rode sem --no-prompt.", file=sys.stderr)
        sys.exit(1)

    cookies = parse_cookie_string(raw)
    tem_token = "login-token" in cookies

    if verbose:
        fonte = ".env/ambiente" if origem == "env" else "prompt"
        print(f"{len(cookies)} cookies carregados de {fonte} "
              f"(login-token presente: {'sim' if tem_token else 'NÃO'})")
        if not tem_token:
            print("  [aviso] sem login-token: a requisição copiada provavelmente "
                  "não era do domínio do AEM, ou a string foi cortada.", file=sys.stderr)
        print()

    session = requests.Session()
    for key, value in cookies.items():
        session.cookies.set(key, value)
    session.headers.update({"Accept": "application/json"})

    auth_tracker = {"fails": 0, "threshold": CONFIG["auth_fail_threshold"]}
    return session, auth_tracker


# ============================================================
# Flags comuns
# ============================================================

def add_common_args(parser):
    """Adiciona as flags que todo script usa, já com os defaults do .env."""
    parser.add_argument("--base-url", default=CONFIG["base_url"])
    parser.add_argument("--timeout", type=int, default=CONFIG["timeout"])
    parser.add_argument("--source-depth", type=int, default=CONFIG["source_depth"])
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sem escrever nada. Rode SEMPRE antes da execução real.")
    parser.add_argument("--no-prompt", action="store_true",
                        help="Falha em vez de pedir o cookie via getpass "
                             "(para rodar sem interação).")
    return parser


def assert_target_is_safe(path):
    """Trava de segurança: aborta qualquer escrita fora de copia-teste.

    Regra inegociável do projeto, confirmada pelo Bruno: macnicagwi e
    macnicaglobal2 são SOMENTE LEITURA. Chame isto antes de todo POST.
    """
    safe_prefixes = (CONFIG["target_prefix"], CONFIG["dam_target_prefix"],
                     "/content/experience-fragments/copia-teste")
    if not path.startswith(safe_prefixes):
        print(f"\n[ABORTADO] tentativa de escrita fora da área de teste: {path}\n"
              f"  Permitido apenas em: {', '.join(safe_prefixes)}\n"
              f"  macnicagwi e macnicaglobal2 são SOMENTE LEITURA.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # `python3 aem_config.py` imprime a configuração ativa, sem tocar na rede.
    print(f"Config lida de: {ENV_PATH}")
    print(f"  (arquivo {'existe' if ENV_PATH.exists() else 'NÃO EXISTE — usando defaults'})\n")
    for key, value in CONFIG.items():
        print(f"  {key:24} = {value}")
    raw = os.environ.get("AEM_COOKIES", "").strip()
    if raw:
        cookies = parse_cookie_string(raw)
        print(f"\n  AEM_COOKIES              = {len(cookies)} cookies, "
              f"login-token {'presente' if 'login-token' in cookies else 'AUSENTE'}")
    else:
        print(f"\n  AEM_COOKIES              = (vazio — scripts vão pedir via getpass)")
