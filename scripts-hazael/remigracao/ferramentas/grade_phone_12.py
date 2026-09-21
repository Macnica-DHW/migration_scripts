#!/usr/bin/env python3
"""
grade_phone_12.py — dá a variante `phone` (largura 12, offset 0) ao container de CORPO que só tem o
breakpoint `default` com largura < 12. É o que o modo Layout do editor grava. Dry-run por padrão.

Por que existe: 28 páginas de `macnicaglobal2/.../boards-modules/tq-systems` (feitas à mão em 02/09/2026)
têm o corpo inteiro num container `default: width 8, offset 2` — no desktop, uma coluna centrada de 933px.
Sem variante `phone`, a grade 8/12 vale também no celular: a 375px TODO o conteúdo cabe em 250px, com
62px de margem morta de cada lado, e o bloco "Stay up to date… Sign up | Contact us" começa em x=103 —
mesmo empilhado (flex_sp_1coluna.py) o botão de 345px vai até x=448. O template define
`phone` = até 768px e `tablet` = até 1200px; só `phone` é gravado (a 1200 a coluna de 8 cabe).
O desktop não muda: `default` fica como está. Pedido do Hazael em 21/09/2026 ("find what works").

NÃO FOI APLICADO EM LOTE: as 28 páginas são TODAS soft-deleted (sobra do clone antigo; a gêmea minúscula,
viva, é `mai-mae-product-page` e não tem esse container). Testado em uma (funciona: corpo de 250 -> 345px,
botão de 103..448 para 40..385) e revertido. Fica para o caso de o padrão aparecer em página viva; o resto
dos 10px é o `min-width:345px` do CSS do site somado a 15+25px de padding — só o clientlib resolve.

Travas: só nas RAÍZES abaixo; só container filho DIRETO de `root/container`; relido ao vivo; só CRIA o nó
`cq:responsive/phone` (se já existir, não mexe). Backup = lista dos nós criados; `--restaurar` os apaga.

    python3 grade_phone_12.py <raiz>                              # dry-run
    python3 grade_phone_12.py <raiz> --paginas /a --executar
    python3 grade_phone_12.py <raiz> --restaurar dados/golive/grade_phone_12_backup_....json --executar
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "golive"))
from _comum import DADOS, aborta, ler, sessao, url  # noqa: E402
from staging import paginas  # noqa: E402

RAIZES = ("/content/macnicaglobal2/americas/mai/en/products/boards-modules/tq-systems",)
RT_CONTAINER = "macnicaglobal2/components/content/container"


def main():
    args = sys.argv[1:]
    executar = "--executar" in args
    raiz = args[0].rstrip("/")
    if raiz not in RAIZES:
        aborta(f"raiz não autorizada: {raiz}")

    if "--restaurar" in args:
        bk = json.load(open(args[args.index("--restaurar") + 1]))
        for no in bk["criados"]:
            if not (no.startswith(raiz + "/") and no.endswith("/cq:responsive/phone")):
                aborta(f"backup com nó inesperado: {no}")
            st = sessao.post(url(no), data={":operation": "delete"}, timeout=60).status_code if executar else "dry"
            print(f"  apaga {no[len(raiz):]}: {st}")
        return

    so = None
    if "--paginas" in args:
        i = args.index("--paginas"); so = {p for p in args[i + 1:] if not p.startswith("--")}

    plano, fica = [], []
    for rel in [""] + paginas(raiz):
        if so is not None and (rel or "/") not in so:
            continue
        st, j = ler(f"{raiz}{rel}/jcr:content/root/container", ".3.json")
        if st != 200:
            continue
        for k, v in j.items():
            if not isinstance(v, dict) or v.get("sling:resourceType") != RT_CONTAINER:
                continue
            resp = v.get("cq:responsive") or {}
            dft = resp.get("default") or {}
            if str(dft.get("width", "12")) == "12" and str(dft.get("offset", "0")) == "0":
                continue
            no = f"{raiz}{rel}/jcr:content/root/container/{k}"
            if "phone" in resp:
                fica.append((rel, k, "já tem variante phone", resp["phone"])); continue
            plano.append((no, dft.get("width"), dft.get("offset")))
    for no, w, o in plano:
        print(f"  {no[len(raiz):]}   default w={w} o={o}  ->  + phone w=12 o=0")
    for f in fica:
        print("  [fica]", *f)
    print(f"\n{len(plano)} containers em {len({n.split('/jcr:content')[0] for n, _, _ in plano})} páginas")
    if not executar:
        print("  [dry-run] nada gravado."); return

    bk = DADOS / f"grade_phone_12_backup_{datetime.datetime.now():%Y-%m-%d_%H%M%S}.json"
    json.dump({"quando": datetime.datetime.now().isoformat(timespec="seconds"), "raiz": raiz,
               "criados": [f"{n}/cq:responsive/phone" for n, _, _ in plano]}, open(bk, "w"), indent=1)
    print(f"  backup -> {bk}")
    falhas = 0
    for no, _, _ in plano:
        alvo = f"{no}/cq:responsive/phone"
        if ler(alvo)[0] != 404:
            aborta(f"{alvo} passou a existir — alguém mexeu; parei")
        r = sessao.post(url(alvo), timeout=60, data={"jcr:primaryType": "nt:unstructured", "width": "12", "offset": "0", "_charset_": "utf-8"})
        _, j = ler(alvo)
        certo = r.status_code in (200, 201) and j and j.get("width") == "12" and j.get("offset") == "0"
        falhas += not certo
        if not certo:
            print(f"  [FALHA] HTTP {r.status_code} {alvo}")
    print(f"  gravados: {len(plano) - falhas}; falhas: {falhas}")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
