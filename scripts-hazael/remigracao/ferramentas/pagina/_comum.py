"""
_comum.py — o que as ferramentas de pagina/ compartilham: caminho da página, nome dos arquivos, pasta de saída.
Não é para rodar.

Caminho: relativo a /content/macnicaglobal2/americas/mai/en (ex.: /products/boards-modules/iei) ou absoluto
(/content/...), com ou sem .html, ou a URL inteira do author/editor.

Nome dos arquivos: o caminho sem /content/<site>/ e sem americas/mai/en/, com "/" -> "__" — igual para as duas
pontas (global2 e GWI), para o render de cada lado cair ao lado do outro:
    /content/macnicaglobal2/americas/mai/en/products/boards-modules/iei  ->  products__boards-modules__iei
    /content/macnicagwi/americas/mai/en/products/boards-modules/iei      ->  products__boards-modules__iei
Página renomeada (GWI /technology/... = global2 /solutions/...): passar --nome para os dois lados casarem.

Saídas em remigracao/dados/paginas/<nome>/ (fora do git: dados/ é saída de ferramenta).
"""
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[4]                    # migration_scripts/
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG  # noqa: E402  (importar o aem_lib carrega o .env no os.environ)

MAI = "/content/macnicaglobal2/americas/mai/en"
G2 = "/content/macnicaglobal2/"
GWI = "/content/macnicagwi/"
DADOS = Path(__file__).resolve().parents[2] / "dados" / "paginas"
AQUI = Path(__file__).resolve().parent
SCREENSHOT = _RAIZ / "scripts-hazael" / "aem_screenshot.py"

BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE     # cookie só vai para o author
HOST = BASE.split("//", 1)[1]


def absoluto(caminho):
    """Caminho JCR absoluto da página (sem .html, sem query, sem barra final)."""
    p = caminho.strip()
    if p.startswith("http"):
        p = "/content/" + p.split("/content/", 1)[1]
    p = re.sub(r"\.html$", "", p.split("?")[0].split("#")[0]).rstrip("/")
    return p if p.startswith("/content/") else MAI + (p if p.startswith("/") else "/" + p)


def caminho_gwi(caminho):
    """A contraparte no GWI: troca /content/macnicaglobal2/ por /content/macnicagwi/. Caminho do GWI passa direto
    (é assim que se trata página renomeada: /solutions no global2 era /technology no GWI; europe -> eu)."""
    p = absoluto(caminho)
    if p.startswith(GWI):
        return p
    if p.startswith(G2):
        return GWI + p[len(G2):]
    raise SystemExit(f"{p}: não é do global2 nem do GWI — passar o caminho absoluto do GWI")


def caminho_lado(caminho, lado):
    p = absoluto(caminho)
    if lado == "gwi":
        return caminho_gwi(p)
    if p.startswith(GWI):
        raise SystemExit(f"{p} é do GWI e o lado pedido é g2 — usar --lado gwi")
    return p


def nome(caminho):
    """products__boards-modules__iei — igual para global2 e GWI."""
    p = re.sub(r"^/content/[^/]+/", "", absoluto(caminho))
    p = p[len("americas/mai/en/"):] if p.startswith("americas/mai/en/") else p
    return p.replace("/", "__") or "_raiz"


def pasta(nome_, saida=None):
    """remigracao/dados/paginas/<nome>/, ou a --saida dada. Não cria: quem grava faz o mkdir."""
    return Path(saida) if saida else DADOS / nome_


def arquivo(nome_, lado, etiqueta, ext, saida=None):
    """<pasta>/<nome>__<lado>__<etiqueta>.<ext> — ex.: products__boards-modules__iei__g2__antes.json"""
    return pasta(nome_, saida) / f"{nome_}__{lado}__{etiqueta}.{ext}"
