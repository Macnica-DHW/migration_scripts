#!/usr/bin/env python3
"""
Conserta os três defeitos de layout que o BlockBuilder deixa na página.

De onde vêm. O `BlockBuilder` do aem_lib embrulha CADA bloco de página num
`container` próprio (`<nome>_wrap`) — decisão do cliente, confirmada com o
Bruno, e é ela que dá o respiro vertical da página: o CSS do global2 tem

    .container > .cmp-container { padding: 50px 25px }

ou seja, TODO container já rende 50px em cima e 50px embaixo por padrão. Os
styles de 【Padding - Top/Bottom】 só MUDAM esse valor (Small=30px, Large=50px,
No Padding=0). Onde não existe container, não existe respiro nenhum — e é
exatamente o que acontece nos três casos abaixo.

Medido na /altera em 18/09/2026, com `?wcmmode=disabled` (o modo de autoria
infla tudo com os placeholders de 29px e engana a medição):

    nível de página, entre blocos ..... 100px   (dois containers, 50+50)
    dentro das abas .................. 0px     (não há container nenhum)

--espaco-abas
    Os componentes dentro de `tabs/item_N` são filhos DIRETOS do container da
    aba — o migrador não cria `_wrap` ali. Resultado: "Portfolio At-a-Glance",
    "Where these devices fit" e "Why Macnica?" ficam colados no parágrafo de
    cima, sem 1px de separação. Embrulha cada filho num container, como no
    nível de página.

    Usa 【Padding - Left/Right】 = No Padding de propósito: o padrão do
    container é `padding: 50px 25px`, e os 25px empurrariam o texto da aba
    para dentro, desalinhando com o que já está lá. Só o eixo vertical muda.

--colunas-gwi
    No GWI a largura mora em `cq:responsive/default/width` do container que
    embrulha o bloco, e uma COLUNA é um `resizablecontainer` com width<12 que
    pode ter VÁRIOS componentes dentro. O migrador lê a largura da coluna e
    carimba em cada componente folha separadamente — a coluna de 6 com
    "texto + botão" vira dois blocos de 6 lado a lado, e o que vinha depois
    (o vídeo) é empurrado para a linha seguinte.

    Na /altera é literalmente o que se vê: intro à esquerda, "Request a Quote"
    à direita, vídeo embaixo. No GWI é intro+botão à esquerda e vídeo à
    direita.

    Relê o agrupamento na origem e refaz: um `_wrap` por COLUNA do GWI, com
    os componentes daquela coluna dentro. Casa origem e destino por texto
    normalizado; se algum membro do grupo não casar com segurança, PULA a
    página e reporta — remontar coluna por adivinhação troca conteúdo de
    lugar.

--logo
    O logo do fabricante no GWI não é conteúdo: é a propriedade de página
    `jcr:content/manufacturerlogo`, que o template do GWI rende no cabeçalho.
    O migrador não traduz propriedade de página, então tratou o logo como
    imagem e pendurou no FIM do corpo, em largura cheia — na /altera são
    405px de logo gigante fechando a página.

    As duas páginas autorais de referência do global2 (`deepx` e `sony`)
    concordam: `manufacturerlogo` preenchido, ZERO logo no corpo. Este flag
    faz o mesmo — grava a propriedade e tira a imagem do corpo.

    ATENÇÃO: o template `mai-mae-product-page` NÃO rende `manufacturerlogo`
    na página (conferido no HTML servido do `deepx`, que tem a propriedade:
    zero ocorrência). Depois deste flag o logo deixa de aparecer no corpo e
    NÃO reaparece no cabeçalho — fica igual às páginas de referência. Se o
    time quiser o logo visível, é decisão de layout e precisa de um bloco
    de conteúdo próprio, não desta propriedade.

CONVENÇÕES (as mesmas do resto do diretório)
  - Diagnóstico é o padrão; só escreve com --executar.
  - Trava de escrita: só `copia-teste`.
  - Backup obrigatório do jcr:content inteiro antes de qualquer escrita.
  - CSV com o estado anterior.
  - Idempotente: o que já está certo é pulado.

COMO RODAR
  python3 aem_corrigir_layout_blocos.py --raiz <caminho> --logo --espaco-abas
  python3 aem_corrigir_layout_blocos.py --raiz <caminho> --todos --executar
  python3 aem_corrigir_layout_blocos.py --raiz <raiz-da-familia> --todos \\
      --pular-contendo /canon/ /sony
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import (CONFIG, build_session, crawl_tree, delete_node, get_json,
                     post_node, print_header, session_expired, write_csv)

CONTAINER_RT = "macnicaglobal2/components/content/container"

# IDs da policy real do container (ver aem_lib.STYLE_*). Conferidos em
# /conf/macnicaglobal2/settings/wcm/policies/macnicaglobal2/components/content.
STYLE_PAD_TB_SMALL = "1717498052331"   # padding-top/bottom 30px (desktop)
STYLE_PAD_LR_NONE = "1717498055877"    # padding-left/right 0

# Tipos que o migrador emite como bloco de conteúdo no destino.
LEAF_HINTS = ("title", "text", "button", "embed", "image", "table",
              "teaser", "list", "download", "carousel")


def norm(s):
    """Texto comparável: sem markup, sem pontuação, espaço colapsado."""
    if not isinstance(s, str):
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace(" ", " ")
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip().lower()


def node_text(node):
    """O texto que identifica um componente, venha de onde vier."""
    for k in ("text", "jcr:title", "title"):
        v = node.get(k)
        if isinstance(v, str) and norm(v):
            return norm(v)
    fr = node.get("fileReference")
    if isinstance(fr, str) and fr:
        return "asset:" + fr.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower()
    yt = node.get("youtubeVideoId")
    if isinstance(yt, str) and yt:
        return "yt:" + yt
    return ""


def rt_tail(node):
    return str(node.get("sling:resourceType", "")).rsplit("/", 1)[-1]


def children(node):
    """Filhos de conteúdo, em ordem de documento."""
    return [(k, v) for k, v in node.items()
            if isinstance(v, dict) and not k.startswith("jcr:")
            and not k.startswith("cq:") and k != "cq:responsive"]


def resp_width(node, bp="default"):
    r = node.get("cq:responsive")
    if isinstance(r, dict):
        c = r.get(bp)
        if isinstance(c, dict) and "width" in c:
            try:
                return int(str(c["width"]))
            except ValueError:
                return None
    return None


# --------------------------------------------------------------------------
# --colunas-gwi : reler o agrupamento de colunas na origem
# --------------------------------------------------------------------------

def gwi_column_groups(jcr):
    """Grupos de folhas do GWI que pertencem à MESMA coluna.

    Devolve [(largura, [texto_normalizado, ...]), ...] só para os grupos com
    mais de uma folha — grupo de uma folha só já está correto no destino.

    Não entra em `tabs`: o conteúdo de aba é outro nível e tem o seu próprio
    agrupamento, tratado em --espaco-abas.
    """
    grupos = []

    def walk(node, col_id, col_w):
        for name, child in children(node):
            tail = rt_tail(child)
            if tail == "tabs":
                continue
            w = resp_width(child)
            if tail in ("resizablecontainer", "container", "imagetext"):
                # Container com largura < 12 abre uma coluna nova.
                if w is not None and 0 < w < 12:
                    walk(child, id(child), w)
                else:
                    walk(child, col_id, col_w)
                continue
            t = node_text(child)
            if not t:
                continue
            if col_id is not None:
                grupos.append((col_id, col_w, t))

    root = jcr.get("root", {})
    walk(root, None, None)

    # consecutivos com o mesmo col_id viram um grupo
    out = []
    for col_id, col_w, t in grupos:
        if out and out[-1][0] == col_id:
            out[-1][2].append(t)
        else:
            out.append([col_id, col_w, [t]])
    return [(w, ts) for _, w, ts in out if len(ts) > 1]


def plan_colunas(dest_jcr, gwi_jcr):
    """Casa os grupos do GWI com os `_wrap` do destino.

    Devolve (acoes, avisos). Cada ação junta N wraps num só.
    """
    cont = dest_jcr.get("root", {}).get("container", {})
    wraps = []
    for name, node in children(cont):
        if rt_tail(node) != "container":
            continue
        kids = children(node)
        wraps.append({"wrap": name, "comps": [k for k, _ in kids],
                      "txts": [node_text(v) for _, v in kids],
                      "w": resp_width(node)})

    def onde(t, ja):
        """(índice do wrap, índice do componente) para um texto da origem."""
        hits = [(i, j) for i, w in enumerate(wraps)
                for j, wt in enumerate(w["txts"])
                if wt and (wt == t or wt in t or t in wt) and (i, j) not in ja]
        return hits

    acoes, avisos = [], []
    for larg, textos in gwi_column_groups(gwi_jcr):
        pares, falhou = [], None
        for t in textos:
            hits = onde(t, pares)
            if len(hits) != 1:
                falhou = (t, len(hits))
                break
            pares.append(hits[0])
        if falhou:
            # Já agrupado por uma execução anterior? Então todo o grupo mora
            # num wrap só e não há nada a fazer — não é insegurança.
            alvos = {i for t in textos for i, _ in onde(t, [])}
            if len(alvos) == 1:
                continue
            avisos.append(f"grupo {textos[0][:34]!r}: "
                          f"{'nenhum' if not falhou[1] else str(falhou[1])} "
                          f"casamento para {falhou[0][:34]!r}")
            continue
        # todos no mesmo wrap => já está agrupado
        if len({i for i, _ in pares}) == 1:
            continue
        if any(len(wraps[i]["comps"]) != 1 for i, _ in pares):
            avisos.append(f"grupo {textos[0][:34]!r}: wrap com mais de um "
                          f"componente no meio do grupo")
            continue
        idxs = [i for i, _ in pares]
        if idxs != sorted(idxs) or idxs[-1] - idxs[0] != len(idxs) - 1:
            avisos.append(f"grupo {textos[0][:34]!r}: wraps não são consecutivos no destino")
            continue
        alvo = wraps[idxs[0]]
        acoes.append({"destino": alvo["wrap"], "largura": larg,
                      "mover": [(wraps[i]["wrap"], wraps[i]["comps"][0])
                                for i in idxs[1:]]})
    return acoes, avisos


# --------------------------------------------------------------------------
# --espaco-abas : embrulhar os filhos das abas em containers
# --------------------------------------------------------------------------

def plan_abas(dest_jcr):
    """Filhos de `tabs/item_N` que ainda não estão dentro de um container."""
    acoes = []

    def walk(node, path):
        for name, child in children(node):
            p = f"{path}/{name}"
            if rt_tail(child) == "tabs":
                for item_name, item in children(child):
                    ip = f"{p}/{item_name}"
                    filhos = children(item)
                    # já embrulhado? (todos os filhos são container)
                    if filhos and all(rt_tail(c) == "container" for _, c in filhos):
                        continue
                    for cname, cnode in filhos:
                        if rt_tail(cnode) == "container":
                            continue
                        acoes.append({"item": ip, "comp": cname,
                                      "w": resp_width(cnode),
                                      "wphone": resp_width(cnode, "phone"),
                                      "txt": node_text(cnode)[:40]})
                continue
            walk(child, p)

    walk(dest_jcr.get("root", {}), "jcr:content/root")
    return acoes


# --------------------------------------------------------------------------
# --logo : logo do fabricante vira propriedade de página
# --------------------------------------------------------------------------

def dam_no_destino(session, base_url, auth, fr):
    """Prefere o asset no DAM de copia-teste, se existir.

    A imagem no corpo costuma apontar para o DAM do GWI — o migrador copia a
    referência como está. Manter isso faz a página do destino depender de
    asset da origem. O gêmeo em `copia-teste` quase sempre existe (foi
    copiado junto); quando não existe, fica a referência original, que ao
    menos renderiza.
    """
    src, dst = CONFIG["dam_source_prefix"], CONFIG["dam_target_prefix"]
    if not fr.startswith(src):
        return fr
    alvo = dst + fr[len(src):]
    _j, st = get_json(session, f"{base_url}{alvo}.json", auth)
    return alvo if st == 200 else fr


def plan_logo(dest_jcr, session=None, base_url=None, auth=None):
    """Imagem de logo pendurada no corpo -> jcr:content/manufacturerlogo.

    Também corrige `manufacturerlogo` que já existe mas aponta para o DAM da
    origem, sem mexer no corpo (nesse caso não há corpo a mexer).
    """
    cont = dest_jcr.get("root", {}).get("container", {})
    achado = None
    for name, node in children(cont):
        kids = children(node)
        if rt_tail(node) != "container" or len(kids) != 1:
            continue
        ckey, cnode = kids[0]
        fr = str(cnode.get("fileReference", ""))
        if "/logos/" in fr.lower() and rt_tail(cnode) == "image":
            achado = {"wrap": name, "comp": ckey, "fileReference": fr,
                      "alt": cnode.get("alt") or fr.rsplit("/", 1)[-1].rsplit(".", 1)[0]}
            break

    atual = dest_jcr.get("manufacturerlogo")
    if isinstance(atual, dict):
        fr = str(atual.get("fileReference", ""))
        if not achado and fr.startswith(CONFIG["dam_source_prefix"]) and session:
            novo = dam_no_destino(session, base_url, auth, fr)
            if novo != fr:
                return {"wrap": None, "comp": None, "fileReference": novo,
                        "alt": atual.get("alt") or novo.rsplit("/", 1)[-1].rsplit(".", 1)[0]}
        return None

    if achado and session:
        achado["fileReference"] = dam_no_destino(session, base_url, auth,
                                                 achado["fileReference"])
    return achado


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raiz", required=True)
    ap.add_argument("--origem", default=None,
                    help="raiz equivalente no GWI (default: deduz do --raiz)")
    ap.add_argument("--logo", action="store_true")
    ap.add_argument("--espaco-abas", action="store_true")
    ap.add_argument("--colunas-gwi", action="store_true")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--pular-contendo", nargs="*", default=[],
                    help="trechos de caminho a blindar (ex: /canon/ /sony)")
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default="layout_blocos.csv")
    ap.add_argument("--backup", default=None)
    args = ap.parse_args()

    if args.todos:
        args.logo = args.espaco_abas = args.colunas_gwi = True
    if not (args.logo or args.espaco_abas or args.colunas_gwi):
        print("[erro] escolha ao menos um conserto (--logo/--espaco-abas/"
              "--colunas-gwi/--todos)", file=sys.stderr)
        sys.exit(1)

    backup_path = args.backup or (Path(args.output).stem + "_backup.json")
    origem_raiz = args.origem or args.raiz.replace(CONFIG["target_prefix"],
                                                   CONFIG["gwi_prefix"])

    print_header("corrigir layout dos blocos")
    print(f"  destino     : {args.raiz}")
    print(f"  origem(GWI) : {origem_raiz}")
    print(f"  consertos   : " + ", ".join(
        n for n, on in [("logo", args.logo), ("espaco-abas", args.espaco_abas),
                        ("colunas-gwi", args.colunas_gwi)] if on))
    print(f"  modo        : {'EXECUTAR (escreve)' if args.executar else 'diagnóstico'}")
    if args.pular_contendo:
        print(f"  blindado    : {', '.join(args.pular_contendo)}")

    session, auth = build_session(verbose=False)
    paginas = crawl_tree(session, args.base_url, args.raiz, auth,
                         only_pages=True, quiet=True)
    print(f"  páginas     : {len(paginas)}\n")

    linhas, backup, avisos_gerais = [], {}, []
    n_alt = 0

    for i, pag in enumerate(paginas):
        if any(s in pag for s in args.pular_contendo):
            continue
        if session_expired(auth):
            print("[erro] sessão expirada — pare e renove o cookie.", file=sys.stderr)
            sys.exit(1)

        dest, _st = get_json(session, f"{args.base_url}{pag}/jcr:content.50.json", auth)
        if not isinstance(dest, dict):
            linhas.append({"pagina": pag, "conserto": "-", "detalhe": "sem jcr:content"})
            continue

        acoes_logo = plan_logo(dest, session, args.base_url, auth) if args.logo else None
        acoes_abas = plan_abas(dest) if args.espaco_abas else []
        acoes_col, avisos = [], []
        if args.colunas_gwi:
            gwi_path = pag.replace(args.raiz, origem_raiz)
            gwi, _gst = get_json(session, f"{args.base_url}{gwi_path}/jcr:content.50.json", auth)
            if isinstance(gwi, dict):
                acoes_col, avisos = plan_colunas(dest, gwi)
            else:
                avisos = ["origem não encontrada no GWI"]
        for a in avisos:
            avisos_gerais.append(f"{pag}: {a}")
            linhas.append({"pagina": pag, "conserto": "colunas-gwi", "detalhe": f"PULADO — {a}"})

        if not (acoes_logo or acoes_abas or acoes_col):
            continue
        n_alt += 1

        # ---- backup antes de qualquer escrita nesta página
        if args.executar:
            backup[pag] = dest

        # ---- 1. colunas (antes das abas: mexe no nível de página)
        for a in acoes_col:
            alvo = f"jcr:content/root/container/{a['destino']}"
            movidos = ", ".join(w for w, _ in a["mover"])
            linhas.append({"pagina": pag, "conserto": "colunas-gwi",
                           "detalhe": f"{a['destino']} (w={a['largura']}) <- {movidos}"})
            if not args.executar:
                continue
            for wrap, comp in a["mover"]:
                src = f"{pag}/jcr:content/root/container/{wrap}/{comp}"
                dst = f"{pag}/{alvo}/{comp}"
                st, txt = post_node(session, args.base_url, src,
                                    {":operation": "move", ":dest": dst,
                                     ":order": "last"}, auth)
                if st not in (200, 201):
                    print(f"  [falha] move {src} -> {dst}: {st} {txt[:90]}")
                    continue
                delete_node(session, args.base_url,
                            f"{pag}/jcr:content/root/container/{wrap}", auth)
            payload = {
                f"{alvo}/cq:responsive/jcr:primaryType": "nt:unstructured",
                f"{alvo}/cq:responsive/default/jcr:primaryType": "nt:unstructured",
                f"{alvo}/cq:responsive/default/width": str(a["largura"]),
                f"{alvo}/cq:responsive/default/offset": "0",
                f"{alvo}/cq:responsive/phone/jcr:primaryType": "nt:unstructured",
                f"{alvo}/cq:responsive/phone/width": "12",
                f"{alvo}/cq:responsive/phone/offset": "0",
            }
            post_node(session, args.base_url, pag, payload, auth)

        # ---- 2. espaço nas abas
        #
        # Cria TODOS os wraps primeiro e só depois move: o Sling acrescenta o
        # nó novo no fim, então os wraps nascem na mesma ordem relativa dos
        # componentes; quando cada componente sai do pai para dentro do seu
        # wrap, sobra só a fila de wraps, na ordem original. Mover antes de
        # criar embaralharia a página.
        por_item = {}
        for a in acoes_abas:
            por_item.setdefault(a["item"], []).append(a)
        for item_path, lista in por_item.items():
            nomes = ", ".join(a["comp"] for a in lista)
            linhas.append({"pagina": pag, "conserto": "espaco-abas",
                           "detalhe": f"{item_path.split('/')[-2]}/{item_path.split('/')[-1]}: {nomes}"})
            if not args.executar:
                continue
            payload = {}
            for a in lista:
                wrap = f"{item_path}/{a['comp']}_wrap"
                payload[f"{wrap}/jcr:primaryType"] = "nt:unstructured"
                payload[f"{wrap}/sling:resourceType"] = CONTAINER_RT
                payload[f"{wrap}/cq:styleIds"] = [STYLE_PAD_LR_NONE, STYLE_PAD_TB_SMALL]
                payload[f"{wrap}/cq:styleIds@TypeHint"] = "String[]"
                if a["w"]:
                    payload[f"{wrap}/cq:responsive/jcr:primaryType"] = "nt:unstructured"
                    payload[f"{wrap}/cq:responsive/default/jcr:primaryType"] = "nt:unstructured"
                    payload[f"{wrap}/cq:responsive/default/width"] = str(a["w"])
                    payload[f"{wrap}/cq:responsive/default/offset"] = "0"
                    payload[f"{wrap}/cq:responsive/phone/jcr:primaryType"] = "nt:unstructured"
                    payload[f"{wrap}/cq:responsive/phone/width"] = str(a["wphone"] or 12)
                    payload[f"{wrap}/cq:responsive/phone/offset"] = "0"
            st, txt = post_node(session, args.base_url, pag, payload, auth)
            if st not in (200, 201):
                print(f"  [falha] criar wraps em {item_path}: {st} {txt[:90]}")
                continue
            for a in lista:
                src = f"{pag}/{item_path}/{a['comp']}"
                dst = f"{pag}/{item_path}/{a['comp']}_wrap/{a['comp']}"
                st, txt = post_node(session, args.base_url, src,
                                    {":operation": "move", ":dest": dst}, auth)
                if st not in (200, 201):
                    print(f"  [falha] move {src}: {st} {txt[:90]}")
                elif a["w"]:
                    # a largura passou para o wrap; no componente vira ruído
                    post_node(session, args.base_url, dst,
                              {"cq:responsive@Delete": ""}, auth)

        # ---- 3. logo
        if acoes_logo:
            linhas.append({"pagina": pag, "conserto": "logo",
                           "detalhe": f"{acoes_logo['wrap'] or 'manufacturerlogo'} -> manufacturerlogo "
                                      f"({acoes_logo['fileReference'].rsplit('/', 1)[-1]})"})
            if args.executar:
                payload = {
                    "jcr:content/manufacturerlogo/jcr:primaryType": "nt:unstructured",
                    "jcr:content/manufacturerlogo/sling:resourceType":
                        "core/wcm/components/image/v3/image",
                    "jcr:content/manufacturerlogo/fileReference":
                        acoes_logo["fileReference"],
                    "jcr:content/manufacturerlogo/alt": acoes_logo["alt"],
                }
                st, txt = post_node(session, args.base_url, pag, payload, auth)
                if st in (200, 201):
                    if acoes_logo["wrap"]:
                        delete_node(session, args.base_url,
                                    f"{pag}/jcr:content/root/container/{acoes_logo['wrap']}",
                                    auth)
                else:
                    print(f"  [falha] manufacturerlogo em {pag}: {st} {txt[:90]}")

        if args.executar:
            time.sleep(CONFIG["write_delay"])
        if i % 25 == 0:
            print(f"  ... {i}/{len(paginas)}", flush=True)

    if args.executar and backup:
        Path(backup_path).write_text(json.dumps(backup, indent=1, ensure_ascii=False))
        print(f"\n  backup      : {backup_path} ({len(backup)} páginas)")

    write_csv(args.output, ["pagina", "conserto", "detalhe"], linhas)
    print(f"\n  páginas com algo a consertar : {n_alt}")
    print(f"  ações                        : {len(linhas)}")
    if avisos_gerais:
        print(f"  pulados por insegurança      : {len(avisos_gerais)}")
        for a in avisos_gerais[:8]:
            print(f"      {a[:120]}")
    print(f"  CSV                          : {args.output}")
    if not args.executar:
        print("\n  (diagnóstico — nada foi escrito; use --executar)")


if __name__ == "__main__":
    main()
