#!/usr/bin/env python3
"""
Renderiza uma página do AEM e salva screenshot. SOMENTE LEITURA.

PARA QUE SERVE
Todo o resto deste diretório lê o JCR — propriedades, resourceTypes, HTML
guardado. Nada disso mostra como a página FICA. Em 17/09/2026 vários
problemas só apareceram quando um humano olhou a tela: a primeira coluna
do Ordering espremida quebrando o part number no meio, a tabela de
Specifications centralizada, a imagem do Text with Image na posição
errada. Nenhum passou pelos diagnósticos automáticos.

Com isto dá para fechar o ciclo sozinho:
    1. renderiza a página do GWI
    2. renderiza a equivalente no destino
    3. compara
    4. corrige
    5. renderiza de novo para conferir

COMO FUNCIONA
A página do AEM abre com um GET autenticado normal em `<caminho>.html` —
sai o conteúdo renderizado, sem o chrome do editor (nada de 'cq-Editable').
Então basta abrir o Chrome pelo Playwright com os cookies do `.env`.

Playwright e /usr/bin/google-chrome já estavam instalados nesta máquina em
17/09/2026. Se faltar o browser: `python3 -m playwright install chromium`.

CUSTO
Cada screenshot ocupa bastante contexto de conversa — na prática dá para
umas 30-50 páginas por sessão de trabalho. Para famílias grandes, vá em
lotes e registre onde parou.

COMO RODAR
  python3 aem_screenshot.py /content/macnicaglobal2/.../uma-pagina
  python3 aem_screenshot.py /content/macnicagwi/.../uma-pagina -o gwi.png --full
  python3 aem_screenshot.py /content/.../pagina --largura 1400 --altura 1200
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import CONFIG, parse_cookie_string


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("caminho", help="Caminho JCR da página, sem o .html")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--full", action="store_true",
                    help="Página inteira em vez de só a primeira dobra.")
    ap.add_argument("--largura", type=int, default=1400)
    ap.add_argument("--altura", type=int, default=1000)
    ap.add_argument("--chrome", default="/usr/bin/google-chrome")
    ap.add_argument("--timeout", type=int, default=60000)
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[erro] playwright não instalado: pip install playwright", file=sys.stderr)
        sys.exit(1)

    raw = os.environ.get("AEM_COOKIES", "").strip()
    if not raw:
        print("[erro] AEM_COOKIES vazio — o .env da raiz precisa do login-token.",
              file=sys.stderr)
        sys.exit(1)
    cookies = parse_cookie_string(raw)

    caminho = args.caminho.rstrip("/")
    saida = args.output or (caminho.rsplit("/", 1)[-1] + ".png")
    host = args.base_url.split("//", 1)[1].rstrip("/")
    url = f"{args.base_url.rstrip('/')}{caminho}.html"

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=args.chrome,
            args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = navegador.new_context(
            viewport={"width": args.largura, "height": args.altura})
        ctx.add_cookies([{"name": k, "value": v, "domain": host, "path": "/"}
                         for k, v in cookies.items()])
        pagina = ctx.new_page()
        try:
            pagina.goto(url, wait_until="networkidle", timeout=args.timeout)
        except Exception as e:
            print(f"[erro] não renderizou: {e}", file=sys.stderr)
            navegador.close()
            sys.exit(1)
        titulo = pagina.title()
        pagina.screenshot(path=saida, full_page=args.full)
        navegador.close()

    print(f"  url        : {url}")
    print(f"  título     : {titulo[:70]}")
    print(f"  screenshot : {saida}")


if __name__ == "__main__":
    main()
