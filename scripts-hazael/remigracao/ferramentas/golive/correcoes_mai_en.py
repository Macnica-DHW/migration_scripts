#!/usr/bin/env python3
"""
correcoes_mai_en.py --lote <familias|downloads|raffle|signup> [--paginas REL…] [--executar] — correções no global2
depois do go-live de mai/en, achadas pelo Hazael na conferência de 23/09/2026 e decididas por ele (AskUserQuestion):

  familias   `showInLists=true` nas 32 famílias de produto que a grade do partner-with-macnica lista (o cardlist só
             mostra página com essa propriedade; nenhuma família do global2 tinha): 12 nossas, 16 do Bruno, 4 da Anion
             (canon, deepx, design-gateway, sony). Só acrescenta a propriedade.
  downloads  as 6 `download` das páginas migradas (company-profile ×2, 4 notícias de 2015–2016) viram BOTÃO para o
             mesmo PDF, com o rótulo que o GWI mostra: o `download` do global2 é o Core sem estilo nenhum no tema
             (desenha Filename/Size/Format cru). O botão entra no mesmo wrap e o download sai. As 16 do ip-software
             (Bruno) não entram — decisão do Hazael.
  raffle     terms-conditions-mep100-…-raffle: apaga `heading_1` (título em dobro; fica o title_wrap padrão) e põe
             os 9 títulos de seção em h2, como no GWI.
  signup     news-archive: o botão "Sign up for our newsletter" ocupa 3/12 com offset 9 e desenha 550px (estoura a
             borda direita) — coluna 12/12 sem offset (default e tablet), estilo Center que ele já tem.

Dry-run por padrão. Antes de gravar: JSON inteiro do jcr:content de cada página tocada em
dados/golive/backup_mai-en/correcoes_<data>/; carimbo relido e comparado com o do dry-run (`--carimbos` gerado
pelo dry-run); lista branca = os nós exatos de cada lote. REGRA MESTRA: nada com `macnicagwi` é gravado.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import golive_mai_en as g  # noqa: E402

G = g.G
P = f"{G}/products"
FAMILIAS = ([f"{P}/semiconductors/{x}" for x in (
    "altera", "ambarella", "analog-devices", "canon", "deepx", "genesys-logic", "i-chips", "infineon", "microchip",
    "namuga-advanced-camera-and-3d-sensing-solutions-for-intelligent-systems", "on-semiconductor", "renesas", "sitime",
    "toppan-3d-tof-sensing-solutions", "design-gateway", "sony")]
    + [f"{P}/boards-modules/{x}" for x in (
        "tq-systems", "connect-tech", "hitek-systems", "ibase", "iei", "ienso", "mpression", "reflex-ces", "silex",
        "terasic", "transcend")]
    + [f"{P}/displays/{x}" for x in ("high-brightness", "innolux", "lg-oled-display-signage", "lilliput-monitors", "macnica-displays")])
NA = f"{G}/about-us/news-events/news-archive"
DOWNLOADS = [  # (página, nó do download, rótulo do GWI)
    (f"{G}/about-us/company-profile", "download_1_wrap/download_1", "ISO9001 Certificate"),
    (f"{G}/about-us/company-profile", "download_2_wrap/download_2", "Macnica Americas (USA & Canada) Standard Terms and Conditions of Sale"),
    (f"{NA}/2015-09-11-macnica-americas-demonstrates-sonys-ip-live-production", "download_1_wrap/download_1", "IBC 2015 Sony IP Live demo press release"),
    (f"{NA}/2016-02-09-macnica-americas-expands-distribution-agreement-with-ambarella", "download_1_wrap/download_1", "Macnica Americas Adds Ambarella Across the Americas"),
    (f"{NA}/2016-02-16-macnica-demonstrates-video-transport-over-ip-interoperability-at", "download_1_wrap/download_1", "PR - VidTrans 2016 (final)"),
    (f"{NA}/2016-04-14-macnica-demonstrates-interoperability-with-sonys-ip-live-production", "download_1_wrap/download_1", "Macnica NAB Press Release - Sony IP Live Interop Demo"),
]
BOTAO_ESTILOS = ["", "1722936853890", "1717669229626"]      # FixedMin + Center: os outros botões destas páginas
RAFFLE = f"{G}/terms-conditions-mep100-ecosystem-partners-tour-challenge-raffle"
SIGNUP = (f"{G}/about-us/news-events/news-archive", "container_migrado_2/button")
# newsletters em que o `image` residual do imagetext do GWI (escondido lá; só o resizableimage aparece — R57) virou
# imagem visível: em cada par de blocos de imagem vizinhos que casa com (image, resizableimage) de um imagetext do GWI,
# o 1º é o resíduo. Achado pelo Hazael e pela varredura de 23/09 (só estas 2 de 114 páginas).
RESIDUOS = ["about-us/newsletter/macnica-technology-update-june-2026", "about-us/newsletter/macnica-technology-update-july-2026"]


def _arq(u):
    n = str(u or "").rsplit("/", 1)[-1].lower()
    return n.rsplit(".", 1)[0] + "." + {"jpg": "jpeg"}.get(n.rsplit(".", 1)[-1], n.rsplit(".", 1)[-1]) if "." in n else n


def residuos(rel):
    """Wraps do global2 que são o `image` residual do GWI: [(chave do wrap, arquivo)]."""
    _, w = g.ler(f"{g.W}/{rel}/jcr:content", ".infinity.json")
    pares = []

    def anda(n):
        for k, v in n.items():
            if isinstance(v, dict):
                if str(v.get("sling:resourceType", "")).endswith("/imagetext"):
                    im, ri = v.get("image") or {}, v.get("resizableimage") or {}
                    if im.get("fileReference") and ri.get("fileReference"):
                        pares.append((_arq(im["fileReference"]), _arq(ri["fileReference"])))
                anda(v)
    anda(w or {})
    cont = jc_de(f"{G}/{rel}").get("root", {}).get("container", {})
    blocos = []
    for k, v in cont.items():
        if isinstance(v, dict):
            filhos = [x for x in v.values() if isinstance(x, dict)]
            img = filhos[0] if len(filhos) == 1 and str(filhos[0].get("sling:resourceType", "")).endswith("/image") else None
            blocos.append((k, _arq(img.get("fileReference")) if img else None))
    marcados, i = [], 0
    for r, s_ in pares:
        j = next((j for j in range(i, len(blocos) - 1) if blocos[j][1] == r and blocos[j + 1][1] == s_), None)
        if j is not None:
            marcados.append(blocos[j])
            i = j + 2
    return marcados


def jc_de(pagina):
    st, jc = g.ler(f"{pagina}/jcr:content", ".infinity.json")
    if st != 200 or not isinstance(jc, dict):
        g.aborta(f"HTTP {st} lendo {pagina}/jcr:content")
    return jc


def no(jc, rel):
    x = jc.get("root", {}).get("container", {})
    for k in rel.split("/"):
        x = x.get(k) if isinstance(x, dict) else None
    return x


def plano(lote, so):
    """[(página, [(nó absoluto, operação, payload)])] — só leitura."""
    out = []
    if lote == "familias":
        for p in FAMILIAS:
            jc = jc_de(p)
            if jc.get("showInLists") == "true":
                continue
            out.append((p, [(f"{p}/jcr:content", "props", {"showInLists": "true"})]))
    elif lote == "downloads":
        for p, rel, rotulo in DOWNLOADS:
            if so and not any(p.endswith(x) for x in so):
                continue
            jc = jc_de(p)
            d = no(jc, rel)
            if not isinstance(d, dict) or not str(d.get("sling:resourceType", "")).endswith("/download"):
                continue                                         # já trocado
            wrap = f"{p}/jcr:content/root/container/{rel.rsplit('/', 1)[0]}"
            out.append((p, [(f"{wrap}/button_download", "props", {
                "jcr:primaryType": "nt:unstructured", "sling:resourceType": "macnicaglobal2/components/content/button",
                "jcr:title": rotulo, "linkURL": d["fileReference"], "linkTarget": "_blank",
                "cq:styleIds": BOTAO_ESTILOS, "cq:styleIds@TypeHint": "String[]"}),
                (f"{p}/jcr:content/root/container/{rel}", "delete", None)]))
    elif lote == "raffle":
        jc = jc_de(RAFFLE)
        ops = []
        if isinstance(no(jc, "heading_1_wrap/heading_1"), dict):
            ops.append((f"{RAFFLE}/jcr:content/root/container/heading_1_wrap/heading_1", "delete", None))
        for i in range(2, 11):
            h = no(jc, f"heading_{i}_wrap/heading_{i}")
            if isinstance(h, dict) and h.get("type") != "h2":
                ops.append((f"{RAFFLE}/jcr:content/root/container/heading_{i}_wrap/heading_{i}", "props", {"type": "h2"}))
        if ops:
            out.append((RAFFLE, ops))
    elif lote == "signup":
        p, rel = SIGNUP
        b = no(jc_de(p), rel)
        r = (b or {}).get("cq:responsive", {})
        if (r.get("default") or {}).get("width") != "12":
            base = f"{p}/jcr:content/root/container/{rel}/cq:responsive"
            out.append((p, [(f"{base}/default", "props", {"width": "12", "offset": "0"}),
                            (f"{base}/tablet", "props", {"width": "12", "offset": "0"})]))
    elif lote == "residuos":
        for rel in RESIDUOS:
            ops = [(f"{G}/{rel}/jcr:content/root/container/{k}", "delete", None) for k, _ in residuos(rel)]
            if ops:
                out.append((f"{G}/{rel}", ops))
    else:
        g.aborta("lote: familias | downloads | raffle | signup | residuos")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lote", required=True)
    ap.add_argument("--paginas", nargs="*", default=None, help="só estas páginas (sufixo do caminho)")
    ap.add_argument("--executar", action="store_true")
    a = ap.parse_args()
    CARIMBOS = g.DADOS / f"correcoes_mai_en_carimbos_{a.lote}.json"      # um por lote: o dry-run de um não apaga o do outro
    pl = plano(a.lote, a.paginas)
    print(f"{'EXECUTANDO' if a.executar else 'dry-run'} lote={a.lote}: {len(pl)} página(s)")
    carimbos = {p: jc_de(p).get("cq:lastModified") for p, _ in pl}
    if not a.executar:
        json.dump(carimbos, open(CARIMBOS, "w"), indent=1)
    else:
        antes = json.load(open(CARIMBOS)) if CARIMBOS.exists() else {}
        mudou = [p for p in carimbos if antes.get(p) != carimbos[p]]
        if mudou:
            g.aborta(f"carimbo mudou desde o dry-run (ou não houve dry-run) em: {[m[len(G):] for m in mudou]} — rode o dry-run de novo")
        pasta = g.DADOS / "backup_mai-en" / f"correcoes_{datetime.datetime.now():%Y-%m-%d_%H%M%S}_{a.lote}"
        pasta.mkdir(parents=True, exist_ok=True)
        for p, _ in pl:
            (pasta / (p[len(G) + 1:].replace("/", "__") + ".json")).write_text(json.dumps(jc_de(p), ensure_ascii=False, indent=1))
        print(f"backup: {pasta}")
    lista = {op[0] for _, ops in pl for op in ops}
    for p, ops in pl:
        print(f"  {p[len(G):]}")
        for caminho, tipo, payload in ops:
            if tipo == "delete":
                st = g.apagar(caminho, a.executar, lista)
            else:
                st = g.post(caminho, payload, a.executar, lista)
            print(f"      {st}  {tipo:6} {caminho[len(p):]}  {json.dumps(payload, ensure_ascii=False)[:150] if payload else ''}")
            if a.executar:
                g.registra(f"correcao-{a.lote}-{tipo}", caminho, {"payload": payload})


if __name__ == "__main__":
    main()
