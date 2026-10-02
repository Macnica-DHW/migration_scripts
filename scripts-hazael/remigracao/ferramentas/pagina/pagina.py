"""
pagina.py — ajudante de EDIÇÃO PONTUAL de uma página do global2 (classe Pagina). BIBLIOTECA, não é para rodar.
A lista de edições é escrita à mão, página a página (look and feel se julga por página, não por script cego).

REGRAS (25/09/2026: "regras, não sugestões") — várias travadas no código pela Session do aem_lib:
  1. Nunca gravar no GWI: nenhum não-GET em URL com `macnicagwi`. Pagina recusa caminho do GWI no construtor e a
     trava da Session barra de novo em cada requisição.
  2. Nunca gravar em página da blacklist do site-migration-tracker (a única fonte): Pagina recusa
     no construtor ("PROTEGIDA — parar"), mesmo em dry-run; a trava barra de novo em cada POST.
  3. Blacklist FRESCA: cada Pagina() abre uma Session nova (build_session faz o GET do tracker na hora; a Session
     baixa de novo se a cópia passar de 300 s). Sem resposta do tracker, Pagina não abre e nada grava.
  4. Estrutura compartilhada (XF em /content/experience-fragments, template/policy em /conf, componente em /apps)
     chega às páginas protegidas: só com "You can edit <caminho exato>" do usuário, passado NA LINHA DE COMANDO,
     uma rodada por vez:  AEM_COMPARTILHADO_AUTORIZADO=<caminho exato> python3 meu_lote.py
     ("go ahead", "all of them", aprovar o plano NÃO valem; no .env a trava recusa).
  5. Backup SEMPRE antes: no 1º não-GET em cada página, a Session salva o jcr:content inteiro em
     remigracao/dados/backups_aem/auto/<data>_<pid>/ (delete/move da própria página: a subárvore). Sem backup,
     não grava. `conferir()` mostra o arquivo.
  6. (opcional) Não sobrescrever trabalho em andamento: Pagina(..., bloquear_editadas_min=N) — ou
     AEM_BLOQUEAR_EDITADAS_MIN=N na linha de comando — recusa gravar se algum nó da página foi editado nos últimos
     N minutos (por qualquer conta). No dry-run a Pagina só avisa; com executar=True a trava da Session barra.
  E: conteúdo = GWI (layout pode mudar); mudar SÓ o que foi pedido; EscritaProibida = parar e perguntar.

FLUXO: plano -> backup -> mudança pontual -> conferência -> relato.
  1. plano: render.py antes (g2 e gwi), comparar_gwi.py, e a lista FECHADA de edições desta página;
  2. dry-run (executar=False, o PADRÃO): cada post() só IMPRIME a requisição planejada — nada é enviado (a Session
     do dry-run recusa qualquer não-GET) — e a aplica numa cópia local do JCR, para criar()/apagar_vazio() e
     conferir() funcionarem sem gravar. O JCR lido fica em <pasta>/<nome>__jcr__dryrun.json;
  3. executar=True com snapshot=<o __jcr__dryrun.json>: se a página mudou desde a leitura, aborta ("mudou desde a
     leitura" — reler e replanejar em cima do estado vivo, mantendo a edição manual); o backup sai sozinho;
  4. conferir(): sequência de componentes com as propriedades de conteúdo idêntica e na mesma ordem antes x depois;
     print --full --publicado (../../../aem_screenshot.py); pixels (faixas, respiro, vãos, fundo dos botões) antes x
     depois; PNG lado a lado. O print "antes" é o do render.py (<nome>__g2__antes.png);
  5. relato: <pasta>/<nome>__plano__<dryrun|executado>.json (cada requisição, com o HTTP) + o que conferir() imprime.
     Depois: render.py --etiqueta depois + antes_depois.py (texto/links/imagens/vídeos/abas/headings).

    import sys; sys.path.insert(0, "remigracao/ferramentas/pagina")         # de scripts-hazael/
    from pagina import Pagina, TB0, TBS
    p = Pagina("/products/boards-modules/iei")                                # dry-run: só imprime
    p.cinza("/container_1452989800")                                          # caminhos relativos a root/container
    p.criar("/container_novo", TB0, "after container_1814557326")
    p.mover("/container_1814557326/title", "/container_novo/title")
    p.apagar_vazio("/container_1814557326")
    p.conferir()
    # revisado o plano, a MESMA lista com:
    p = Pagina("/products/boards-modules/iei", executar=True,
               snapshot="remigracao/dados/paginas/products__boards-modules__iei/products__boards-modules__iei__jcr__dryrun.json")

Caminho da página: relativo a /content/macnicaglobal2/americas/mai/en ou absoluto. Nó: relativo a
jcr:content/root/container ("/container_3/text_1") ou absoluto, sempre DENTRO do jcr:content desta página.
"""
import copy
import datetime
import difflib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import BASE, GWI, MAI, SCREENSHOT, absoluto, arquivo, nome, pasta  # noqa: E402
import aem_lib as L  # noqa: E402

CINZA = "rgb(247,247,247)"                                                     # faixa cinza (container de 1º nível)
LEFT = [("cq:styleIds", "1718154328384"), ("cq:styleIds", ""), ("cq:styleIds", ""), ("cq:styleIds@TypeHint", "String[]")]
TBS, TB0 = "1717498052331", "1717498056876"          # container: Top/Bottom padding Small (30px) / No Padding
CONTAINER = "macnicaglobal2/components/content/container"
ESTRUTURA = ("/container", "/flexcontainer", "/flexcontaineritem")
CONTEUDO = ("text", "jcr:title", "type", "fileReference", "pages", "linkURL", "link", "fragmentVariationPath", "alt",
            "imageRatio", "listFrom", "id", "youtubeVideoId")


def sequencia(no, out=None):
    """Componentes de conteúdo na ordem, com as propriedades de conteúdo (containers não contam)."""
    out = [] if out is None else out
    for v in no.values():
        if isinstance(v, dict):
            rt = v.get("sling:resourceType")
            if rt and not rt.endswith(ESTRUTURA):
                out.append((rt.rsplit("/", 1)[-1],) + tuple((c, json.dumps(v[c], ensure_ascii=False)) for c in CONTEUDO if c in v))
            sequencia(v, out)
    return out


def _pares(data):
    return list(data.items()) if isinstance(data, dict) else [tuple(x) for x in data]


def _curto(v, n=80):
    v = str(v).replace("\n", "\\n")
    return v if len(v) <= n else v[:n] + f"…({len(v)} car.)"


class Pagina:
    def __init__(self, caminho, snapshot=None, executar=False, saida=None, bloquear_editadas_min=None):
        self.P = absoluto(caminho)
        if self.P.startswith(GWI) or "macnicagwi" in self.P:
            raise SystemExit(f"{self.P} é do GWI — SOMENTE LEITURA (REGRA MESTRA: nunca gravar no GWI)")
        self.rel = self.P[len(MAI):] if self.P.startswith(MAI) else self.P
        self.nome, self.saida, self.executar = nome(self.P), saida, executar
        self.pasta = pasta(self.nome, saida)
        self.JC = self.P + "/jcr:content"
        self.C = self.JC + "/root/container"
        self.s, self.auth = L.build_session(prompt_if_missing=False, verbose=False,
                                            bloquear_editadas_min=bloquear_editadas_min)
        if not executar:                                  # dry-run: esta Session não manda nada além de GET
            original = self.s.request

            def so_leitura(method, url, *a, **k):
                if method.upper() not in L.LEITURA:
                    raise SystemExit(f"dry-run: {method} {url} barrado — nada é enviado sem executar=True")
                return original(method, url, *a, **k)
            self.s.request = so_leitura
        if self.s.blacklist.caminhos is None:
            raise SystemExit(f"blacklist indisponível ({self.s.blacklist.erro}) — parar")
        if self.P in set(self.s.blacklist.caminhos):
            raise SystemExit(f"{self.rel} PROTEGIDA — parar")
        self.antes = self.jcr()
        self._avisar_edicao_recente()
        if snapshot:
            lido = json.loads(Path(snapshot).read_text(encoding="utf-8"))
            if isinstance(lido, dict) and "jcr_content" in lido and "pagina" in lido:   # backup do aem_lib
                lido = lido["jcr_content"]
            if self.antes != lido:
                raise SystemExit(f"{self.rel} mudou desde a leitura ({self.antes.get('cq:lastModified')} por "
                                 f"{self.antes.get('cq:lastModifiedBy')}) — reler antes")
        elif executar:
            print("  [aviso] executar=True sem snapshot=: a página não é comparada com a leitura do plano")
        self.sim = copy.deepcopy(self.antes)             # o JCR como ficaria: cada post() se aplica aqui também
        self.plano = []
        self.pasta.mkdir(parents=True, exist_ok=True)                  # só depois de passar pelas travas
        arq = self.pasta / f"{self.nome}__jcr__{'antes' if executar else 'dryrun'}.json"
        arq.write_text(json.dumps(self.antes, ensure_ascii=False), encoding="utf-8")
        print(f"### {self.rel} — {'EXECUTAR: grava no AEM' if executar else 'DRY-RUN: nada é enviado'}  "
              f"(última edição {self.antes.get('cq:lastModified')} por {self.antes.get('cq:lastModifiedBy')}; JCR lido em {arq.name})")

    def _avisar_edicao_recente(self):
        """Com a trava de edição recente ligada: avisa já na leitura (no dry-run a Session nunca chega a conferir)."""
        n = self.s.bloquear_editadas_min
        u = L.ultima_edicao(self.antes) if n else None
        if not u:
            return
        idade = (datetime.datetime.now(datetime.timezone.utc) - u[0]).total_seconds() / 60
        if idade < n:
            msg = (f"{self.rel}: editada há {max(idade, 0):.0f} min ({u[0].astimezone():%d/%m %H:%M} por {u[1]}, em {u[2]})"
                   f" — trava de {n:g} min")
            if self.executar:
                raise SystemExit(f"[ABORTADO] {msg}: alguém pode estar trabalhando nela — conferir antes de gravar")
            print(f"  [aviso] {msg}: o dry-run segue, mas com executar=True a escrita será barrada")

    # ── leitura ───────────────────────────────────────────────────────────────────────────────────────────────
    def jcr(self):
        d, st = L.fetch_with_depth_fallback(self.s, BASE, self.JC, "infinity", self.auth, timeout=60)
        if st != 200 or not isinstance(d, dict):
            raise SystemExit(f"{self.rel}: jcr:content ilegível (HTTP {st})")
        return d

    def no(self, caminho, de=None):
        """O nó (dict) no JCR lido (ou em `de`), caminho relativo a root/container."""
        n = (de or self.antes)["root"]["container"]
        for k in caminho.strip("/").split("/"):
            n = n[k]
        return n

    def _abs(self, no):
        cam = no.rstrip("/") if no.startswith("/content/") else self.C + ("/" + no.strip("/") if no.strip("/") else "")
        if ".." in cam.split("/"):
            raise SystemExit(f"{no}: caminho com '..' — usar o caminho do nó por extenso")
        if not cam.startswith(self.JC + "/") and cam != self.JC:
            raise SystemExit(f"{cam} está fora do jcr:content de {self.rel} — Pagina só edita a própria página")
        return cam

    def _sim(self, cam, criar=False):
        n = self.sim
        for k in [x for x in cam[len(self.JC):].split("/") if x]:
            if not isinstance(n.get(k), dict):
                if not criar:
                    return None
                n[k] = {}
            n = n[k]
        return n

    def filhos(self, no):
        """Nós-filhos (inclui cq:responsive): executar = GET ao vivo; dry-run = a simulação."""
        cam = self._abs(no)
        if self.executar:
            d, st = L.get_json(self.s, BASE + cam + ".1.json", self.auth, timeout=30)
            if st != 200:
                raise SystemExit(f"{no}: HTTP {st}")
        else:
            d = self._sim(cam)
            if d is None:
                raise SystemExit(f"{no} não existe (na simulação)")
        return [k for k, v in d.items() if isinstance(v, dict)]

    def existe(self, no):
        cam = self._abs(no)
        if self.executar:
            return self.s.get(BASE + cam + ".json", timeout=30).status_code != 404
        return self._sim(cam) is not None

    # ── escrita ───────────────────────────────────────────────────────────────────────────────────────────────
    def post(self, no, data, rotulo):
        """UMA requisição Sling POST no nó. Dry-run: imprime e simula. Executar: envia pela Session travada."""
        cam = self._abs(no)
        pares = _pares(data)
        for k, v in pares:
            if k == ":dest":
                if not str(v).startswith("/content/"):
                    raise SystemExit(f":dest={v}: usar caminho absoluto (o relativo o Sling resolve pelo pai da origem)")
                self._abs(v)                                    # move só dentro desta página
        if not any(k == "_charset_" for k, _ in pares):
            pares.append(("_charset_", "utf-8"))
        bl = self.s.blacklist.atual()                           # GET fresco no tracker se a cópia passou de 300 s
        try:
            motivo = L.motivo_bloqueio("POST", BASE + cam, pares, autorizados=L.compartilhado_autorizado(),
                                       protegidas=tuple(bl or ()))
        except L.EscritaProibida as e:
            motivo = str(e)
        if not motivo and bl is None:
            motivo = f"sem blacklist fresca do tracker ({self.s.blacklist.erro}): nenhuma escrita sem ela"
        if motivo:
            raise SystemExit(f"[{'ABORTADO' if self.executar else 'BLOQUEARIA'}] {rotulo}: {motivo} — parar e perguntar")
        item = {"rotulo": rotulo, "no": cam, "dados": [(k, v) for k, v in pares if k != "_charset_"], "http": None}
        self.plano.append(item)
        if not self.executar:
            print(f"  plano  {rotulo}")
            print(f"         POST {cam[len(self.JC):] or cam}  " + "  ".join(f"{k}={_curto(v)}" for k, v in item["dados"]))
            self._simular(cam, pares)
            return
        try:
            r = self.s.post(BASE + cam, data=pares, timeout=60)
        except L.EscritaProibida as e:
            raise SystemExit(f"[ABORTADO pela trava] {rotulo}: {e} — parar e perguntar")
        item["http"] = r.status_code
        print(f"  {r.status_code}  {rotulo}")
        if r.status_code not in (200, 201):
            raise SystemExit(f"parou em {rotulo}: {r.text[:300]}")
        try:
            self._simular(cam, pares)                           # gravando, a simulação só acompanha: não aborta
        except SystemExit as e:
            print(f"  [aviso] simulação divergiu do AEM ({e}); conferir() relê o JCR ao vivo")

    def _simular(self, cam, pares):
        """Aplica a requisição à cópia local do JCR, com a semântica do Sling POST."""
        ops = [v for k, v in pares if k == ":operation"]
        ordem = next((v for k, v in pares if k == ":order"), None)
        pai_cam, nm = cam.rsplit("/", 1)
        if "delete" in ops:
            pai = self._sim(pai_cam)
            if pai is None or nm not in pai:
                raise SystemExit(f"simulação: {cam} não existe para apagar")
            del pai[nm]
            return
        if "move" in ops:
            dest = next(v for k, v in pares if k == ":dest")
            dest = dest + nm if dest.endswith("/") else dest
            pai, (dpai_cam, dnm) = self._sim(pai_cam), dest.rsplit("/", 1)
            dpai = self._sim(dpai_cam)
            if pai is None or nm not in pai:
                raise SystemExit(f"simulação: {cam} não existe para mover")
            if dpai is None:
                raise SystemExit(f"simulação: destino {dpai_cam} não existe")
            if dnm in dpai:
                raise SystemExit(f"simulação: {dest} já existe (o Sling recusa sem :replace)")
            dpai[dnm] = pai.pop(nm)                             # vai para o fim do novo pai
            if ordem:
                self._ordenar(dpai, dnm, ordem)
            return
        n = self._sim(cam, criar=True)                          # nó novo nasce no fim do pai
        vals, dicas = {}, {}
        for k, v in pares:
            if k.startswith(":") or k == "_charset_":
                continue
            base = k.split("@", 1)[0].removeprefix("./")
            if k.endswith("@Delete"):
                n.pop(base, None)
            elif k.endswith("@TypeHint"):
                dicas[base] = v
            else:
                vals.setdefault(base, []).append(v)
        for k, vs in vals.items():
            if dicas.get(k, "").endswith("[]") or len(vs) > 1:
                n[k] = vs
            elif vs[0] == "" and not dicas.get(k):
                n.pop(k, None)                                  # Sling: valor vazio apaga a propriedade
            else:
                n[k] = vs[0]
        if ordem:
            self._ordenar(self._sim(pai_cam), nm, ordem)

    @staticmethod
    def _ordenar(pai, nm, ordem):
        filhos = [k for k, v in pai.items() if isinstance(v, dict) and k != nm]
        if ordem == "first":
            i = 0
        elif ordem == "last":
            i = len(filhos)
        elif ordem.startswith(("before ", "after ")):
            ref = ordem.split(" ", 1)[1]
            if ref not in filhos:
                raise SystemExit(f"simulação: :order {ordem} — {ref} não existe")
            i = filhos.index(ref) + (1 if ordem.startswith("after ") else 0)
        elif ordem.isdigit():
            i = int(ordem)
        else:
            raise SystemExit(f"simulação: :order {ordem!r} desconhecido")
        filhos.insert(i, nm)
        props = {k: v for k, v in pai.items() if not isinstance(v, dict)}
        nos = {k: pai[k] for k in filhos}
        pai.clear(); pai.update(props); pai.update(nos)

    # ── atalhos das edições de look and feel ──────────────────────────────────────────────────────────────────
    def left(self, no):
        self.post(no, LEFT, f"{no} -> Image Position Left")

    def estilo(self, no, ids, rotulo=None):
        """cq:styleIds inteiro (o array é SUBSTITUÍDO: mandar todas as posições, "" nas vazias)."""
        self.post(no, [("cq:styleIds", x) for x in ids] + [("cq:styleIds@TypeHint", "String[]")],
                  rotulo or f"{no} -> cq:styleIds {list(ids)}")

    def cinza(self, no):
        self.post(no, {"backgroundColor": CINZA}, f"{no} -> faixa cinza")

    def branco(self, no):
        self.post(no, {"backgroundColor@Delete": ""}, f"{no} -> branco")

    def mover(self, de, para, antes_de=None):
        self.post(de, {":operation": "move", ":dest": self._abs(para)}, f"{de} -> {para}")
        if antes_de:
            self.post(para, {":order": f"before {antes_de}"}, f"{para} ordenado antes de {antes_de}")

    def criar(self, no, estilo, ordem):
        """Container novo (estilo na 2ª posição do cq:styleIds, como os da migração), na posição `ordem`
        ("after container_2", "before x", "first"...)."""
        if self.existe(no):
            raise SystemExit(f"{no} já existe")
        self.post(no, [("jcr:primaryType", "nt:unstructured"), ("sling:resourceType", CONTAINER),
                       ("cq:styleIds", ""), ("cq:styleIds", estilo), ("cq:styleIds@TypeHint", "String[]"), (":order", ordem)],
                  f"{no} criado (container, estilo {estilo}, {ordem})")

    def apagar_vazio(self, no):
        filhos = self.filhos(no)
        if filhos:
            raise SystemExit(f"{no} não está vazio: {filhos}")
        self.post(no, {":operation": "delete"}, f"{no} (vazio) apagado")

    # ── conferência ───────────────────────────────────────────────────────────────────────────────────────────
    def conferir(self, etiqueta="depois"):
        """Conteúdo idêntico antes x depois (dry-run: x a simulação); com executar=True também print, pixels e
        lado a lado. Devolve True se a sequência de conteúdo é idêntica."""
        a = sequencia(self.antes)                            # o jcr:content inteiro, como no original
        depois = self.sim if not self.executar else self.jcr()
        b = sequencia(depois)
        (self.pasta / f"{self.nome}__plano__{'executado' if self.executar else 'dryrun'}.json").write_text(
            json.dumps({"pagina": self.P, "executar": self.executar, "requisicoes": self.plano}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        modo = "" if self.executar else " (SIMULAÇÃO do dry-run)"
        print(f"  conteúdo{modo}: {len(a)} componentes antes, {len(b)} depois — idênticos e na mesma ordem: {a == b}")
        if a != b:
            ra, rb = [repr(x) for x in a], [repr(x) for x in b]
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ra, rb, autojunk=False).get_opcodes():
                if op == "equal":
                    continue
                if op == "replace" and i2 - i1 == j2 - j1:          # mesmo lugar: mostra só a propriedade que mudou
                    for x, y in zip(a[i1:i2], b[j1:j2]):
                        dx, dy = dict(x[1:]), dict(y[1:])
                        mud = {k: f"{_curto(dx.get(k), 50)} -> {_curto(dy.get(k), 50)}" for k in {**dx, **dy} if dx.get(k) != dy.get(k)}
                        print(f"     mudou: {x[0]}{'' if x[0] == y[0] else ' -> ' + y[0]} {mud}")
                else:
                    print(f"     {op}: {[_curto(r, 110) for r in ra[i1:i2][:3]]} -> {[_curto(r, 110) for r in rb[j1:j2][:3]]}")
        if not self.executar:
            print(f"  DRY-RUN: {len(self.plano)} requisição(ões) planejada(s), NADA enviado ao AEM. Para gravar: a mesma "
                  f"lista com executar=True, snapshot='{self.pasta / (self.nome + '__jcr__dryrun.json')}'")
            return a == b
        (self.pasta / f"{self.nome}__jcr__depois.json").write_text(json.dumps(depois, ensure_ascii=False), encoding="utf-8")
        print("  backup:", [str(v[0]) for v in self.s.backups.values()] or "nenhum (nada foi gravado)")
        png, png_antes = arquivo(self.nome, "g2", etiqueta, "png", self.saida), arquivo(self.nome, "g2", "antes", "png", self.saida)
        png.unlink(missing_ok=True)
        for _ in range(2):
            subprocess.run([sys.executable, str(SCREENSHOT), self.P, "-o", str(png), "--full", "--publicado"],
                           cwd=str(SCREENSHOT.parent), capture_output=True)
            if png.exists():
                break
        if not png.exists():
            print("  [aviso] print falhou duas vezes — JCR conferido, render NÃO conferido")
            return a == b
        from pixels import analisa, resumo
        for rot, f in (("antes ", png_antes), ("depois", png)):
            if f.exists():
                try:
                    print(f"  {rot}: {resumo(analisa(f))}")
                except ValueError as e:
                    print(f"  {rot}: {e}")
            else:
                print(f"  {rot}: sem print ({f.name}) — rodar render.py {self.rel} antes da gravação")
        if png_antes.exists():
            print(f"  lado a lado: {self.lado_a_lado(png_antes, png)}")
        return a == b

    def lado_a_lado(self, antes, depois, escala=0.32):
        from PIL import Image, ImageDraw
        a_, b_ = Image.open(antes).convert("RGB"), Image.open(depois).convert("RGB")
        a_ = a_.resize((int(a_.width * escala), int(a_.height * escala)))
        b_ = b_.resize((int(b_.width * escala), int(b_.height * escala)))
        H = max(a_.height, b_.height) + 22
        c = Image.new("RGB", (a_.width + b_.width + 10, H), (200, 0, 0))
        c.paste((255, 255, 255), (0, 0, a_.width, H)); c.paste((255, 255, 255), (a_.width + 10, 0, c.width, H))
        c.paste(a_, (0, 22)); c.paste(b_, (a_.width + 10, 22))
        dr = ImageDraw.Draw(c); dr.text((4, 4), "ANTES", fill=(0, 0, 0)); dr.text((a_.width + 14, 4), "DEPOIS", fill=(0, 0, 0))
        out = self.pasta / f"{self.nome}__lado__antes_depois.png"
        c.save(out)
        return out
