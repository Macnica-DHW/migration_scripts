"""
direto.py — migração DIRETO no macnicaglobal2 (sem staging), usada por `aem_remigrar.py --alvo-global2`.
Não é para rodar.

Autorizado pelo Hazael em 21/09/2026 para `/technology` e `/services` ("it's how Anion has been doing
it"). As travas, todas conferidas AO VIVO imediatamente antes de cada escrita:

  REGRA MESTRA  nunca gravar no GWI. Nenhum POST sai daqui para URL que contenha `macnicagwi` —
                nem o `:operation=copy` do Sling, que é um POST na URL da ORIGEM. Asset vem por
                `@CopyFrom`: o POST vai para a pasta de DESTINO e o GWI só é lido.
  lista branca  só os caminhos EXATOS de página passados em `Alvo(paginas=…)` e as pastas do DAM
                `<DAM_MAI>/<seção>`; nada mais do global2.
  página        404 -> cria. Existe e é NOSSA (manifesto) -> regrava. Existe, de outra pessoa, com
                ZERO componente de conteúdo (as cascas do ohashi) -> grava, com backup. Qualquer
                outra coisa -> ABORTA: é trabalho de alguém.
  nome          sempre o normalizado (regra do projeto). Casca com o nome do GWI em MAIÚSCULA ao
                lado NÃO é tocada; só se aceita gêmeo que esteja em `gemeos_conhecidos`.
  backup        `jcr:content.infinity.json` inteiro de toda página que já existe, antes de gravar.
  manifesto     dados/golive/manifesto_direto.jsonl — tudo o que foi criado, para desfazer.
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
from aem_lib import CONFIG, normalize_name  # noqa: E402

DADOS = Path(__file__).resolve().parents[2] / "dados" / "golive"
MANIFESTO = DADOS / "manifesto_direto.jsonl"
BACKUPS = DADOS / "backup_direto"

GWI_MAI = "/content/macnicagwi/americas/mai/en"
MAI = "/content/macnicaglobal2/americas/mai/en"
DAM_GWI = "/content/dam/macnicagwi"
DAM_MAI = "/content/dam/macnicaglobal2/americas/mai/en"
XF_GWI = "/content/experience-fragments/macnicagwi/americas/mai/en/site"
XF_G2 = "/content/experience-fragments/macnicaglobal2/americas/mai/en/site"
NOSSO_USUARIO = "valter.toffolo@macnicadhw.com.br"
# o que trocar o prefixo não resolve (o global2 tem outra árvore) — mesma tabela do go-live
FIXOS = [(f"{MAI}/contact/form", f"{MAI}/contact-us"),
         ("/content/macnicaglobal2/europe/atd-europe", "/content/macnicaglobal2/eu/atd-europe")]
ESTRUTURA = ("container", "responsivegrid", "breadcrumb", "experiencefragment")

BASE = CONFIG["base_url"].rstrip("/")
assert re.match(r"^https://author-[a-z0-9-]+\.adobeaemcloud\.com$", BASE), BASE   # cookie só vai para o author


class Abortar(SystemExit):
    pass


def aborta(msg):
    print(f"\n[ABORTADO] {msg}", file=sys.stderr)
    raise Abortar(1)


def _url(path, sufixo=""):
    return BASE + quote(unquote(path), safe="/:") + sufixo


def _norm(nome):
    return re.sub(r"[^a-z0-9]+", "-", unquote(nome).lower()).strip("-")


def nome_asset(n):
    base, _, ext = unquote(n).rpartition(".")
    return re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-") + "." + ext.lower()


def subpasta(a):
    ext = a.rsplit(".", 1)[-1].lower()
    if "/logos/" in a:
        return "logos"
    if ext == "pdf":
        return "pdfs"
    if ext in ("zip", "rar", "gz"):
        return "downloads"
    return "images"


def componentes_de_conteudo(jc):
    """Quantos componentes de CONTEÚDO há sob jcr:content/root (a casca do template não conta)."""
    n = 0

    def anda(no):
        nonlocal n
        rt = str(no.get("sling:resourceType", "")).rsplit("/", 1)[-1]
        if rt and rt not in ESTRUTURA:
            n += 1
        for v in no.values():
            if isinstance(v, dict):
                anda(v)
    raiz = jc.get("root")
    if isinstance(raiz, dict):
        anda(raiz)
    return n


class Alvo:
    def __init__(self, sessao, secao, paginas, gemeos_conhecidos=()):
        self.s = sessao
        self.secao = secao.strip("/")
        self.paginas = set(paginas)                       # caminhos EXATOS no global2
        self.gemeos = set(gemeos_conhecidos)              # cascas de nome errado que ficam ao lado
        self.dam = f"{DAM_MAI}/{self.secao}"
        self.pastas_feitas = set()
        self.assets = {}                                  # ref do GWI -> destino no global2
        for p in self.paginas:
            if not p.startswith(f"{MAI}/{self.secao}") or "macnicagwi" in p:
                aborta(f"página fora de {MAI}/{self.secao}: {p}")
            if p != MAI + "/" + "/".join(normalize_name(x) for x in p[len(MAI):].strip("/").split("/")):
                aborta(f"nome de nó não normalizado na lista branca: {p}")

    # ---------- leitura
    def ler(self, path, sufixo=".json"):
        r = self.s.get(_url(path, sufixo), timeout=90, allow_redirects=False)
        try:
            return r.status_code, (r.json() if r.status_code == 200 else None)
        except ValueError:
            return r.status_code, None

    def ler_conteudo(self, pagina):
        st, jc = self.ler(pagina + "/jcr:content", ".infinity.json")
        if not isinstance(jc, dict):                      # HTTP 300: lista de profundidades
            st, jc = self.ler(pagina + "/jcr:content", ".50.json")
        return st, jc

    # ---------- escrita: tudo passa por aqui
    def _post(self, path, dados, arquivos=None, timeout=300):
        if "macnicagwi" in path:
            aborta(f"REGRA MESTRA: tentativa de escrita no GWI: {path}")
        if not (path in self.paginas or any(path.startswith(p + "/") for p in self.paginas)
                or path == self.dam or path.startswith(self.dam + "/")):
            aborta(f"escrita fora da lista branca: {path}")
        return self.s.post(_url(path), data={**dados, "_charset_": "utf-8"}, files=arquivos, timeout=timeout)

    def _registra(self, op, origem, destino, status, extra=None):
        DADOS.mkdir(parents=True, exist_ok=True)
        with open(MANIFESTO, "a") as f:
            f.write(json.dumps({"quando": datetime.datetime.now().isoformat(timespec="seconds"), "op": op,
                                "origem": origem, "destino": destino, "status": status, **(extra or {})},
                               ensure_ascii=False) + "\n")

    def _nosso(self, path):
        if not MANIFESTO.exists():
            return False
        for l in MANIFESTO.read_text().splitlines():
            m = json.loads(l)
            if m["destino"] == path and m["status"] in (200, 201) and m["op"] in ("pagina-nova", "pagina-preenchida", "asset", "pasta"):
                return True
        return False

    # ---------- página
    def situacao(self, pagina, executar=False):
        """'nova' | 'nossa' | 'casca'. Aborta em qualquer outro caso. Lido AO VIVO."""
        if pagina not in self.paginas:
            aborta(f"página fora da lista branca: {pagina}")
        st, j = self.ler(pagina, ".1.json")
        if st == 404:
            pai, nome = pagina.rsplit("/", 1)
            stp, jp = self.ler(pai, ".1.json")
            if stp == 404 and pai in self.paginas and not executar:
                return "nova"                              # dry-run: o pai nasce neste mesmo lote
            if stp != 200:
                # gravando, o pai TEM de existir: o Sling criaria o intermediário sem tipo
                aborta(f"o pai não existe (HTTP {stp}): {pai}")
            gemeos = [k for k, v in jp.items() if isinstance(v, dict) and k != nome and _norm(k) == _norm(nome)]
            estranhos = [g for g in gemeos if f"{pai}/{g}" not in self.gemeos]
            if estranhos:
                aborta(f"irmão com o mesmo nome em outra grafia, fora da lista de conhecidos: {pai}/{estranhos}")
            return "nova"
        if st != 200:
            aborta(f"HTTP {st} ao conferir {pagina} (cookie vencido?) — sem certeza, não gravo")
        if self._nosso(pagina):
            return "nossa"
        stc, jc = self.ler_conteudo(pagina)
        if not isinstance(jc, dict):
            aborta(f"não consegui ler o jcr:content de {pagina} (HTTP {stc})")
        if jc.get("deleted") or jc.get("deletedBy"):
            aborta(f"página com soft-delete — decisão do Hazael: {pagina}")
        n = componentes_de_conteudo(jc)
        if n:
            aborta(f"a página JÁ TEM {n} componentes de conteúdo de outra pessoa "
                   f"({jc.get('cq:lastModifiedBy')}, {jc.get('cq:lastModified')}): {pagina}\n"
                   f"           Nada foi gravado — não sobrescrever trabalho alheio.")
        return "casca"

    def backup(self, pagina):
        st, jc = self.ler_conteudo(pagina)
        if st != 200 or not isinstance(jc, dict) or "root" not in jc:
            aborta(f"backup impossível (HTTP {st}, sem root): {pagina}")
        BACKUPS.mkdir(parents=True, exist_ok=True)
        carimbo = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        arq = BACKUPS / f"{pagina[len(MAI):].strip('/').replace('/', '__')}__{carimbo}.json"
        arq.write_text(json.dumps({"caminho": pagina, "lido_em": carimbo, "jcr:content": jc},
                                  indent=1, ensure_ascii=False))
        return arq

    def gravar_pagina(self, pagina, payload_pagina, payload_conteudo):
        """Devolve (situacao, status). Backup e delete do root quando a página já existe."""
        sit = self.situacao(pagina, executar=True)
        if sit in ("casca", "nossa"):
            arq = self.backup(pagina)
            r = self._post(pagina + "/jcr:content/root", {":operation": "delete"})
            if r.status_code not in (200, 204, 404):
                aborta(f"não consegui limpar o root de {pagina}: HTTP {r.status_code}")
            self._registra("backup+limpa-root", None, pagina, r.status_code, {"backup": str(arq.name), "era": sit})
        r1 = self._post(pagina, payload_pagina)
        if r1.status_code not in (200, 201):
            self._registra("pagina-falhou", None, pagina, r1.status_code)
            return sit, f"falha página {r1.status_code} {r1.text[:120]}"
        r2 = self._post(pagina, payload_conteudo)
        self._registra("pagina-nova" if sit == "nova" else "pagina-preenchida", None, pagina, r2.status_code,
                       {"era": sit})
        return sit, ("ok" if r2.status_code in (200, 201) else f"falha conteúdo {r2.status_code} {r2.text[:120]}")

    # ---------- assets
    def destino_asset(self, ref, familia):
        return f"{self.dam}/{familia}/{subpasta(ref)}/{nome_asset(ref.rsplit('/', 1)[-1])}"

    def _pasta(self, path, executar):
        atual = DAM_MAI
        for seg in path[len(DAM_MAI):].strip("/").split("/"):
            atual += "/" + seg
            if atual in self.pastas_feitas:
                continue
            st, _j = self.ler(atual, ".0.json")
            if st == 404 and executar:
                r = self._post(atual, {"jcr:primaryType": "sling:Folder",
                                       "jcr:content/jcr:primaryType": "nt:unstructured",
                                       "jcr:content/jcr:title": seg})
                self._registra("pasta", None, atual, r.status_code)
                if r.status_code not in (200, 201):
                    aborta(f"não criei a pasta {atual}: HTTP {r.status_code}")
            elif st == 200 and atual == self.dam and not self._nosso(atual):
                aborta(f"a pasta {atual} já existe e não é nossa — conferir antes de gravar nela")
            elif st not in (200, 404):
                aborta(f"HTTP {st} ao conferir a pasta {atual}")
            self.pastas_feitas.add(atual)

    def sha1(self, asset):
        st, md = self.ler(asset + "/jcr:content/metadata", ".json")
        return (md or {}).get("dam:sha1")

    def copiar_asset(self, ref, familia, executar):
        """ref do DAM do GWI -> caminho no DAM do global2 (criando se preciso). None se falhar."""
        ref = unquote(ref)
        if ref in self.assets:
            return self.assets[ref]
        if not ref.startswith(DAM_GWI + "/"):
            return None
        destino = self.destino_asset(ref, familia)
        origem_sha = self.sha1(ref)
        st, _j = self.ler(destino, ".0.json")
        if st == 200:
            if self.sha1(destino) == origem_sha and origem_sha:
                self.assets[ref] = destino                 # o mesmo arquivo já está lá
                return destino
            base, ext = destino.rsplit(".", 1)
            destino = f"{base}-2.{ext}"
            st, _j = self.ler(destino, ".0.json")
            if st == 200:
                if self.sha1(destino) == origem_sha:
                    self.assets[ref] = destino
                    return destino
                return None
        if st != 404:
            aborta(f"HTTP {st} ao conferir {destino}")
        if not executar:
            print(f"    [simulado] asset {ref.rsplit('/', 1)[-1]} -> {destino[len(DAM_MAI):]}")
            self.assets[ref] = destino
            return destino
        pasta, nome = destino.rsplit("/", 1)
        self._pasta(pasta, executar)
        # `@CopyFrom`: o POST vai para a PASTA de destino; o GWI só é lido pelo servidor.
        r = self._post(pasta, {f"{nome}@CopyFrom": ref})
        self._registra("asset", ref, destino, r.status_code)
        if r.status_code not in (200, 201):
            print(f"    [falha] asset HTTP {r.status_code}: {ref}")
            return None
        st, j = self.ler(destino, ".1.json")
        if st != 200 or (j or {}).get("jcr:primaryType") != "dam:Asset" or self.sha1(destino) != origem_sha:
            print(f"    [falha] asset copiado não confere (HTTP {st}): {destino}")
            return None
        self.assets[ref] = destino
        return destino


    # ---------- logo de card: todos do MESMO tamanho
    # O card de fornecedor do GWI encaixa (`object-fit:contain`) qualquer logo numa caixa de 147x120
    # centrada numa área de 229x120 — medido nos 22 cards da `imaging-and-vision`. O `image` do global2
    # não tem opção de tamanho e o CSS do site não tem "contain" para imagem solta (cardlist/teaser
    # CORTAM com `cover`). Então a uniformidade vai no ARQUIVO: cada logo é redesenhado, centrado e
    # inteiro, numa tela transparente de tamanho único (2x, para tela de alta densidade). Arquivos de
    # dimensões idênticas renderizam idênticos. Exigência do Hazael em 21/09/2026 ("MUST be the same size").
    TELA = (458, 240)
    CAIXA = (294, 204)          # 18px de folga em cima e embaixo: a legenda fica colada na imagem

    def _desenhar_logo(self, ref):
        """PNG (bytes) do logo de `ref` encaixado na tela única. Só LÊ o GWI."""
        import io
        from PIL import Image
        r = self.s.get(_url(ref + "/jcr:content/renditions/original"), timeout=120)
        if r.status_code != 200 or not r.content:
            return None
        if ref.lower().endswith(".svg"):
            from playwright.sync_api import sync_playwright
            import base64
            with sync_playwright() as pw:
                nav = pw.chromium.launch(executable_path="/usr/bin/google-chrome",
                                         args=["--no-sandbox", "--disable-dev-shm-usage"])
                pg = nav.new_page(viewport={"width": self.CAIXA[0] * 2, "height": self.CAIXA[1] * 2})
                uri = "data:image/svg+xml;base64," + base64.b64encode(r.content).decode()
                pg.set_content(f'<html><body style="margin:0;background:transparent"><img id="l" src="{uri}" '
                               f'style="width:{self.CAIXA[0] * 2}px;height:auto;display:block"></body></html>')
                pg.wait_for_timeout(400)
                bruto = pg.locator("#l").screenshot(omit_background=True)
                nav.close()
            logo = Image.open(io.BytesIO(bruto)).convert("RGBA")
        else:
            logo = Image.open(io.BytesIO(r.content)).convert("RGBA")
        caixa = logo.getbbox()                              # tira a margem transparente do arquivo
        if caixa:
            logo = logo.crop(caixa)
        f = min(self.CAIXA[0] / logo.width, self.CAIXA[1] / logo.height)
        logo = logo.resize((max(1, round(logo.width * f)), max(1, round(logo.height * f))), Image.LANCZOS)
        tela = Image.new("RGBA", self.TELA, (255, 255, 255, 0))
        tela.paste(logo, ((self.TELA[0] - logo.width) // 2, (self.TELA[1] - logo.height) // 2), logo)
        out = io.BytesIO()
        tela.save(out, "PNG", optimize=True)
        return out.getvalue()

    def logo_uniforme(self, ref, familia, executar):
        """ref do logo no GWI -> asset `card-<nome>.png` no DAM do global2 (criando se preciso)."""
        ref = unquote(ref)
        chave = "card:" + ref
        if chave in self.assets:
            return self.assets[chave]
        base = nome_asset(ref.rsplit("/", 1)[-1]).rsplit(".", 1)[0]
        destino = f"{self.dam}/{familia}/logos/card-{base}.png"
        st, _j = self.ler(destino, ".0.json")
        if st == 200:
            if not self._nosso(destino):
                aborta(f"já existe e não é nosso: {destino}")
            self.assets[chave] = destino
            return destino
        if st != 404:
            aborta(f"HTTP {st} ao conferir {destino}")
        if not executar:
            print(f"    [simulado] logo uniforme {ref.rsplit('/', 1)[-1]} -> {destino[len(DAM_MAI):]}")
            self.assets[chave] = destino
            return destino
        png = self._desenhar_logo(ref)
        if not png:
            return None
        pasta, nome = destino.rsplit("/", 1)
        self._pasta(pasta, executar)
        if "macnicagwi" in pasta or not pasta.startswith(self.dam + "/"):
            aborta(f"upload fora do DAM da seção: {pasta}")
        r = self.s.post(_url(pasta + ".createasset.html"), files={"file": (nome, png, "image/png")}, timeout=180)
        self._registra("asset", f"logo uniforme de {ref}", destino, r.status_code)
        if r.status_code not in (200, 201):
            print(f"    [falha] upload do logo HTTP {r.status_code}: {destino}")
            return None
        # `createasset` NÃO garante o processamento: em 21/09/2026, 8 de 17 logos subiram e ficaram
        # só com a `original` (imagem quebrada na página). Conferir e reprocessar NA HORA.
        if self.reprocessar([destino], espera=180):
            print(f"    [falha] o DAM não processou {destino}")
            return None
        self.assets[chave] = destino
        return destino


    def saudavel(self, asset):
        """Processado de verdade? `dc:format` + mais que a `original` (o `.coreimg` de asset não
        processado devolve 1 byte e a imagem sai quebrada — lição da cv75)."""
        st, j = self.ler(asset + "/jcr:content", ".2.json")
        md = (j or {}).get("metadata") or {}
        rend = [k for k, v in ((j or {}).get("renditions") or {}).items() if isinstance(v, dict)]
        return bool(md.get("dc:format")) and len(rend) > 1

    def reprocessar(self, assets, espera=240):
        """"Reprocess Assets" (POST em /bin/asynccommand) só para asset NOSSO, no DAM da seção."""
        import time
        pend = [a for a in assets if not self.saudavel(a)]
        for a in pend:
            if "macnicagwi" in a or not a.startswith(self.dam + "/") or not self._nosso(a):
                aborta(f"só reprocesso asset que esta ferramenta criou: {a}")
            r = self.s.post(BASE + "/bin/asynccommand", timeout=120, data={
                "_charset_": "utf-8", "operation": "PROCESS", "description": "direto.py",
                "profile-select": "full-process", "runPostProcess": "false", "asset": a})
            self._registra("reprocess", None, a, r.status_code)
        fim = time.time() + espera
        while pend and time.time() < fim:
            time.sleep(8)
            pend = [a for a in pend if not self.saudavel(a)]
        return pend                                        # o que continuou sem processar


def familia_de(pagina_destino, secao):
    """Pasta do DAM: a página de 1º nível da seção; a landing da seção usa `common`."""
    rel = pagina_destino[len(f"{MAI}/{secao.strip('/')}"):].strip("/")
    return rel.split("/")[0] if rel else "common"


_ATRIBUTO = re.compile(r'(\b(?:href|src)\s*=\s*)(["\'])(.*?)\2', re.I | re.S)


def _uma_url(u, secoes):
    for de, para in FIXOS:
        if u == de or (u.startswith(de) and u[len(de)] in "/.#?"):
            u = para + u[len(de):]
    for sec in secoes:                                     # nome NORMALIZADO dentro do que estamos migrando
        raiz = f"{MAI}/{sec.strip('/')}"
        if u.startswith(raiz + "/"):
            m = re.match(r"((?:/[^/.#?]+)+)(.*)$", u[len(raiz):], re.S)
            if m:
                u = raiz + "/".join(normalize_name(x) if x else x for x in m.group(1).split("/")) + m.group(2)
    return u


def acertar_links(payload, secoes):
    """FIXOS do go-live + nome normalizado para link que aponta para página das seções migradas."""
    for k, v in list(payload.items()):
        if isinstance(v, str) and MAI in v:
            if v.startswith("/content/") and "<" not in v:
                payload[k] = _uma_url(v, secoes)
            else:
                payload[k] = _ATRIBUTO.sub(lambda m: f"{m.group(1)}{m.group(2)}{_uma_url(m.group(3), secoes)}{m.group(2)}", v)
        elif isinstance(v, list):
            payload[k] = [_uma_url(x, secoes) if isinstance(x, str) and x.startswith(MAI) else x for x in v]


_ASSET_NO_HTML = re.compile(r'(\b(?:href|src|data-src|poster)\s*=\s*)(["\'])(/content/dam/macnicagwi/[^"\']+)\2', re.I)


def assets_do_html(payload, alvo, familia, executar):
    """`<img src>` e `<a href>` de rich text/tabela que apontam para o DAM do GWI (HTML cru do autor:
    logos de fornecedor e PDFs na `japan-innovation`). Copia o asset e troca o caminho. Devolve as
    refs que não deu para copiar."""
    falhas = []

    def troca(m):
        ref = unquote(m.group(3).split("?")[0].split("#")[0])
        novo = alvo.copiar_asset(ref, familia, executar)
        if not novo:
            falhas.append(ref)
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}{novo}{m.group(2)}"

    for k, v in list(payload.items()):
        if isinstance(v, str) and DAM_GWI in v and "<" in v:
            payload[k] = _ASSET_NO_HTML.sub(troca, v)
    return falhas


_PAGINA = re.compile(r"^(" + re.escape(MAI) + r"/[^.#?\s]*?)(/?)((?:\.html)?(?:[#?].*)?)$")
# o global2 tem outra árvore neste ponto (a Anion aninhou a família): mesma observação do go-live
ANINHADOS = [(f"{MAI}/products/semiconductors/sony-image-sensors", f"{MAI}/products/semiconductors/sony/sony-image-sensors")]


def resolver_alvos(payload, alvo, a_nascer=()):
    """Link interno para página que NÃO existe no global2 com aquele nome: tenta, AO VIVO, o nome
    normalizado, o aninhamento conhecido e um irmão de nome único que comece igual (o blog do
    global2 completou nomes que o GWI truncava). Devolve ([(antes, depois)], [sem solução])."""
    cache, trocas, mortos = {}, [], []

    def existe(p):
        if p in a_nascer:
            return True                                    # nasce neste mesmo lote
        if p not in cache:
            cache[p] = alvo.ler(p, ".0.json")[0] == 200
        return cache[p]

    def resolve(u):
        m = _PAGINA.match(u)
        if not m or "/content/dam/" in u:
            return u
        p, _barra, resto = m.group(1).rstrip("/"), m.group(2), m.group(3)
        if existe(p):
            return p + resto                               # só tira a barra final que o autor digitou
        cands = [MAI + "/" + "/".join(normalize_name(x) for x in p[len(MAI):].strip("/").split("/"))]
        for de, para in ANINHADOS:
            if p == de or p.startswith(de + "/"):
                cands.append(para + p[len(de):])
        pai, nome = p.rsplit("/", 1)
        st, jp = alvo.ler(pai, ".1.json")
        if st == 200:
            irm = [k for k, v in jp.items() if isinstance(v, dict) and v.get("jcr:primaryType") == "cq:Page"
                   and (_norm(k).startswith(_norm(nome)) or _norm(nome).startswith(_norm(k)))]
            if len(irm) == 1:
                cands.append(f"{pai}/{irm[0]}")
        for c in cands:
            if c != p and existe(c):
                trocas.append((p, c))
                return c + resto
        mortos.append(p)
        return u

    for k, v in list(payload.items()):
        if isinstance(v, str) and MAI in v:
            if v.startswith("/content/") and "<" not in v:
                payload[k] = resolve(v)
            else:
                payload[k] = _ATRIBUTO.sub(lambda m: f"{m.group(1)}{m.group(2)}{resolve(m.group(3))}{m.group(2)}", v)
        elif isinstance(v, list):
            payload[k] = [resolve(x) if isinstance(x, str) and x.startswith(MAI) else x for x in v]
    return sorted(set(trocas)), sorted(set(mortos))


def diferenca_com_o_servidor(alvo, pagina, payload):
    """(+, -, ~) entre o payload novo e o jcr:content/root gravado — o dry-run de verdade."""
    IGN = ("jcr:created", "jcr:lastModified", "cq:lastModified", "jcr:mixinTypes", "cq:lastReplicat", "cq:isDelivered")

    def normv(v):
        if isinstance(v, list):
            return tuple(str(x) for x in v)
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)
    st, raiz = alvo.ler(pagina + "/jcr:content/root", ".infinity.json")
    atual = {}

    def achata(n, base):
        for k, v in n.items():
            if isinstance(v, dict):
                achata(v, f"{base}/{k}")
            elif not k.startswith(IGN):
                atual[f"{base}/{k}"] = normv(v)
    if isinstance(raiz, dict):
        achata(raiz, "jcr:content/root")
    novo = {k: normv(v) for k, v in payload.items() if "@" not in k and k.startswith("jcr:content/root")}
    return (len(set(novo) - set(atual)), len(set(atual) - set(novo)),
            sum(1 for k in set(novo) & set(atual) if novo[k] != atual[k]))


PROIBIDO = re.compile(r"/content/(?:dam/)?copia-teste|/content/(?:dam/)?macnicagwi|experience-fragments/(?:copia-teste|macnicagwi)")


def sobras_proibidas(payload):
    """Referência que NÃO pode ir para o global2 (GWI, copia-teste). [(chave, trecho)]"""
    out = []
    for k, v in payload.items():
        for x in (v if isinstance(v, list) else [v]):
            if isinstance(x, str):
                for m in PROIBIDO.finditer(x):
                    out.append((k, x[max(0, m.start() - 10):m.end() + 70]))
    return out
