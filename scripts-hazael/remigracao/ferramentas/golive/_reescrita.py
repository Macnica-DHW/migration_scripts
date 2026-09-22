"""
_reescrita.py — a tabela de reescrita de referências do go-live, num lugar só. Não é para rodar.

  asset  (DAM copia-teste / DAM do GWI)      -> dados/golive/mapa_assets.csv   (desenho e nome da Anion)
  XF     experience-fragments/copia-teste    -> experience-fragments/macnicaglobal2   (mesmo caminho relativo)
  página T/...                               -> G/...                          (os `pages` de list, R5)
  página /content/macnicagwi/americas/mai/en -> /content/macnicaglobal2/americas/mai/en   (só os botões dos XFs)
  e o que trocar prefixo NÃO resolve (o global2 tem outra árvore):
         <mai/en>/contact/form                     -> <mai/en>/contact-us       (é o que a Anion usa; /contact dá 404)
         /content/macnicaglobal2/europe/atd-europe -> /content/macnicaglobal2/eu/atd-europe
         <mai/en>/technology                       -> <mai/en>/solutions       (move do Hazael, 21/09/2026)

Fica de fora, de propósito: `<mai/en>/products/ip-software/{v-by-oner-hs-ip,munvme-ip-core}` — o caminho
está CERTO, a página é que ainda não existe no global2 (6 links). Externos, âncoras e tags não mudam.
"""
import csv
import html
import re
from urllib.parse import unquote

from _comum import DADOS, G, MAI, T, XF_G2, XF_T

GWI_MAI = "/content/macnicagwi/americas/mai/en"
FIXOS = [(f"{MAI}/contact/form", f"{MAI}/contact-us"),
         ("/content/macnicaglobal2/europe/atd-europe", "/content/macnicaglobal2/eu/atd-europe"),
         (f"{MAI}/technology", f"{MAI}/solutions")]          # /technology virou /solutions em 21/09/2026 (move no console)
PROIBIDO = re.compile(r"/content/(?:dam/)?copia-teste|/content/(?:dam/)?macnicagwi|experience-fragments/copia-teste")
ATRIBUTO = re.compile(r'(\b(?:href|src|data-src|poster)\s*=\s*)(["\'])(.*?)\2', re.I | re.S)
IGNORAR = {"jcr:primaryType", "jcr:mixinTypes", "sling:resourceType", "sling:resourceSuperType", "cq:template",
           "jcr:createdBy", "cq:lastModifiedBy", "jcr:lastModifiedBy", "jcr:uuid", "cq:tags"}


def mapa_assets():
    return {unquote(l["origem"]): l["destino"] for l in csv.DictReader(open(DADOS / "mapa_assets.csv"))}


def _troca_prefixo(u, de, para):
    """Troca `de` por `para` só quando `de` é o caminho inteiro ou vem seguido de / . # ?"""
    if u == de or (u.startswith(de) and u[len(de)] in "/.#?"):
        return para + u[len(de):]
    return u


def uma_url(u, assets):
    dec = unquote(u.strip())
    if dec in assets:
        return assets[dec]
    n = u.strip()
    n = _troca_prefixo(n, XF_T, XF_G2)
    n = _troca_prefixo(n, T, G)
    n = _troca_prefixo(n, GWI_MAI, MAI)
    for de, para in FIXOS:
        n = _troca_prefixo(n, de, para)
    return n if n != u.strip() else u


def valor(v, assets):
    """Reescreve UM valor string (caminho inteiro, ou HTML com href/src)."""
    if not isinstance(v, str) or "/content/" not in v:
        return v
    if v.lstrip().startswith("/content/") and "<" not in v:
        return uma_url(v, assets)

    def attr(m):
        antigo = html.unescape(m.group(3))
        novo = uma_url(antigo, assets)
        return m.group(0) if novo == antigo else f"{m.group(1)}{m.group(2)}{html.escape(novo, quote=True)}{m.group(2)}"
    return ATRIBUTO.sub(attr, v)


def mudancas(no, caminho, assets, saida, erros):
    """Percorre um jcr:content; acumula (caminho-do-nó, prop, antes, depois) e o que sobrou de proibido."""
    for k, v in no.items():
        if isinstance(v, dict):
            mudancas(v, f"{caminho}/{k}", assets, saida, erros)
        elif k not in IGNORAR and isinstance(v, (str, list)):
            novo = [valor(x, assets) for x in v] if isinstance(v, list) else valor(v, assets)
            if novo != v:
                saida.append((caminho, k, v, novo))
            for x in (novo if isinstance(novo, list) else [novo]):
                if isinstance(x, str) and PROIBIDO.search(x):
                    erros.append((caminho, k, PROIBIDO.search(x).group(0), x[:160]))


def payload(prop, novo):
    if isinstance(novo, list):
        return {prop: novo, f"{prop}@TypeHint": "String[]"}
    return {prop: novo}
