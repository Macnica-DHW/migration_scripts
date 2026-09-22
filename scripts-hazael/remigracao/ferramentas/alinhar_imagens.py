#!/usr/bin/env python3
"""
alinhar_imagens.py — duas correções de `image` que andam juntas, página a página. Dry-run por padrão.

Por que existe (streal, 22/09/2026): numa linha de 3 `image` dentro de um `flexcontainer`, o componente
desenha cada arquivo no TAMANHO NATURAL (limitado pelo `max-width:100%` da coluna), então as legendas
saem em alturas diferentes — na `macnica-products/streal` eram 133px de desnível entre "SR300"/"SR500" e
"Evaluation Kit" (294x251, 282x241 e 455x392 de arquivo, colunas de 433px).

O `image` do global2 NÃO tem campo de tamanho no diálogo, mas a policy tem dois grupos de style
(`policy_589419553064100`), acessíveis pela aba Styles do próprio diálogo:
  【Size】             Expand to Fit Width = 1717565101174 -> classe `large`
                      `.large .cmp-image, .large .cmp-image .cmp-image__inner { width:100%; max-height:unset }`
  【Display Position】 Left 1726800547211 / Center 1726800548797 / Right 1726800549719
Com o style a imagem enche a coluna, que é o que o `resizableimage` do GWI já faz (medido na streal do
GWI: as 5 ocorrências saem com 239px de largura). Quando as imagens da linha têm a MESMA proporção,
largura igual dá altura igual e as legendas alinham — na streal, 133px de desnível viraram 4px.
Quando as proporções diferem (logos da imaging-and-vision), largura igual NÃO dá altura igual e a saída
é outra: normalizar o arquivo (R62, `golive/direto.py: logo_uniforme`).

ARMADILHA que trava o autor: a aba Metadata do diálogo exige `./alt`, e `altValueFromDAM` AUSENTE vale
`true` (default do core image v2) — o campo fica desabilitado, herdando do DAM. Se o asset não tem
`dc:title`/`dc:description`, não há o que herdar e **o diálogo inteiro não salva**, nem a aba Styles.
Foi o que travou o revisor da streal. Por isso `--destravar` grava `altValueFromDAM=false` e
`isDecorative=false` em todo nó que já tem `alt` — a flag também faz o `alt` autoral valer na tela.

O que grava, e só isso:  `altValueFromDAM`/`isDecorative` (--destravar) e `cq:styleIds` (--coluna).
Travas: nunca escreve em caminho com `macnicagwi`; só dentro da página passada; o nó é RELIDO ao vivo
antes e depois; backup do `jcr:content` inteiro da página antes de qualquer POST.

    python3 alinhar_imagens.py <página>                                  # auditoria (somente leitura)
    python3 alinhar_imagens.py <página> --destravar
    python3 alinhar_imagens.py <página> --coluna imgrow_1_wrap --executar
    python3 alinhar_imagens.py <página> --restaurar dados/alinhar_imagens_backup_....json --executar
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "golive"))
from _comum import BASE, DADOS, aborta, ler, sessao, url  # noqa: E402

S_EXPAND = "1717565101174"                     # 【Size】 Expand to Fit Width
RT_IMAGE = ("macnicaglobal2/components/content/image",)
PERMITIDO = ("/content/copia-teste/", "/content/macnicaglobal2/")


def guarda(caminho):
    """REGRA MESTRA: nada é escrito contra o GWI, e nada fora da página passada."""
    if "macnicagwi" in caminho:
        aborta(f"escrita contra o GWI recusada: {caminho}")
    if not caminho.startswith(PERMITIDO):
        aborta(f"fora das árvores permitidas: {caminho}")


def lista(v):
    return list(v) if isinstance(v, list) else ([v] if isinstance(v, str) and v else [])


def imagens(no, rel, saida):
    """(caminho relativo, nó) de todo `image` com fileReference, em ordem de documento."""
    for k, v in no.items():
        if not isinstance(v, dict) or k == "cq:responsive":
            continue
        filho = f"{rel}/{k}" if rel else k
        if v.get("sling:resourceType") in RT_IMAGE and v.get("fileReference"):
            saida.append((filho, v))
        imagens(v, filho, saida)
    return saida


def dimensoes(ref):
    """(largura, altura) do asset, do metadata do DAM. (None, None) se não der."""
    st, j = ler(ref + "/jcr:content/metadata", ".0.json")
    if st != 200 or not j:
        return None, None
    return j.get("tiff:ImageWidth"), j.get("tiff:ImageLength")


def backup(pagina, executar):
    st, j = ler(pagina + "/jcr:content", ".infinity.json")
    if st != 200 or not j:
        aborta(f"não consegui ler a página para o backup (HTTP {st}): {pagina}")
    if not executar:
        return None
    nome = (pagina.strip("/").replace("/", "__") + "_"
            + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".json")
    destino = Path(DADOS) / "backup_alinhar_imagens" / nome
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(j, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"backup: {destino}")
    return destino


def grava(no, props):
    guarda(no)
    r = sessao.post(url(no), timeout=60, data={**props, "_charset_": "utf-8"})
    return r.status_code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pagina", help="caminho absoluto da página (sem /jcr:content)")
    ap.add_argument("--destravar", action="store_true",
                    help="altValueFromDAM=false + isDecorative=false nos nós que já têm alt")
    ap.add_argument("--coluna", action="append", default=[], metavar="TRECHO",
                    help="liga 'Expand to Fit Width' nos image cujo caminho relativo contém TRECHO")
    ap.add_argument("--executar", action="store_true", help="grava (padrão é dry-run)")
    ap.add_argument("--restaurar", metavar="BACKUP",
                    help="devolve alt/flags/styleIds dos image ao que está no backup")
    args = ap.parse_args()

    pagina = args.pagina.rstrip("/")
    guarda(pagina)
    st, jc = ler(pagina + "/jcr:content", ".infinity.json")
    if st != 200 or not jc:
        aborta(f"página não lida (HTTP {st}): {pagina}")

    achados = imagens(jc, "", [])
    if not achados:
        print("nenhum `image` com fileReference nesta página.")
        return

    if args.restaurar:
        antigo = json.loads(Path(args.restaurar).read_text(encoding="utf-8"))
        anteriores = dict(imagens(antigo, "", []))
        plano = {}
        for rel, no in achados:
            velho = anteriores.get(rel)
            if velho is None:
                continue
            props = {}
            for p in ("altValueFromDAM", "isDecorative"):
                if no.get(p) != velho.get(p):
                    props[p] = velho.get(p) if velho.get(p) is not None else ""
                    if props[p] == "":
                        props[p + "@Delete"] = "true"
                        props.pop(p)
            if lista(no.get("cq:styleIds")) != lista(velho.get("cq:styleIds")):
                props["cq:styleIds"] = lista(velho.get("cq:styleIds"))
                props["cq:styleIds@TypeHint"] = "String[]"
                if not props["cq:styleIds"]:
                    props = {"cq:styleIds@Delete": "true"}
            if props:
                plano[f"{pagina}/jcr:content/{rel}"] = props
        for no, props in plano.items():
            print(("[dry-run] " if not args.executar else "") + f"restaura {no}: {props}")
            if args.executar:
                print("   HTTP", grava(no, props))
        print(f"\n{len(plano)} nó(s) {'restaurados' if args.executar else 'a restaurar'}")
        return

    # ---------- auditoria (sempre)
    largura_col = {}
    print(f"{len(achados)} `image` com fileReference em {pagina}\n")
    for rel, no in achados:
        w, h = dimensoes(no["fileReference"])
        razao = f"{w/h:.4f}" if w and h else "?"
        flags = []
        if no.get("altValueFromDAM") != "false":
            flags.append("DIÁLOGO TRAVA (altValueFromDAM ausente/true)")
        if S_EXPAND in lista(no.get("cq:styleIds")):
            flags.append("Expand to Fit Width")
        print(f"  {rel}")
        print(f"      {no['fileReference'].rsplit('/', 1)[-1]}  {w}x{h}  razão={razao}  "
              f"alt={no.get('alt')!r}  styles={lista(no.get('cq:styleIds')) or '-'}")
        if flags:
            print("      " + " | ".join(flags))
        largura_col.setdefault(rel.rsplit("/", 2)[0], []).append(razao)

    for pai, razoes in largura_col.items():
        if len(razoes) > 1:
            unicas = sorted(set(razoes))
            print(f"\n  linha {pai}: {len(razoes)} imagens, razões {', '.join(unicas)}"
                  + ("  -> largura igual dá altura igual (o style resolve)" if len(unicas) == 1
                     or (len(unicas) > 1 and max(float(x) for x in unicas) - min(float(x) for x in unicas) < 0.02)
                     else "  -> razões diferentes: o style NÃO alinha, normalizar o arquivo (R62)"))

    # ---------- plano de escrita
    plano = {}
    for rel, no in achados:
        caminho = f"{pagina}/jcr:content/{rel}"
        props = {}
        if args.destravar and no.get("altValueFromDAM") != "false":
            if not str(no.get("alt") or "").strip():
                print(f"\n  [pulado] {rel} não tem alt no nó — ver alt_faltando.py (R49)")
            else:
                props["altValueFromDAM"] = "false"
                props["isDecorative"] = "false"
        if any(t in rel for t in args.coluna):
            ids = lista(no.get("cq:styleIds"))
            if S_EXPAND not in ids:
                props["cq:styleIds"] = [x for x in ids if x] + [S_EXPAND]
                props["cq:styleIds@TypeHint"] = "String[]"
        if props:
            plano[caminho] = props

    if not plano:
        print("\nnada a gravar (já está como deveria, ou é só auditoria).")
        return

    print(f"\n{len(plano)} nó(s) a gravar:")
    for no, props in plano.items():
        print(f"  {no[len(pagina) + 13:]}  <-  {dict((k, v) for k, v in props.items() if '@' not in k)}")
    if not args.executar:
        print("\n[dry-run] nada gravado. Use --executar.")
        return

    backup(pagina, True)
    falhas = 0
    for no, props in plano.items():
        st = grava(no, props)
        rel = no[len(pagina) + 13:]
        conf, j = ler(no, ".0.json")
        ok = st in (200, 201) and j and all(
            (lista(j.get(k)) == lista(v) if k == "cq:styleIds" else j.get(k) == v)
            for k, v in props.items() if "@" not in k)
        print(f"  {'ok  ' if ok else 'FALHA'} HTTP {st}  {rel}")
        falhas += 0 if ok else 1
    print(f"\n{len(plano) - falhas} gravado(s), {falhas} falha(s)")


if __name__ == "__main__":
    main()
