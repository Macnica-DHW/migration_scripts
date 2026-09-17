#!/usr/bin/env python3
"""
Recria os blocos de topo (imagem+intro e Features) que faltam no GLOBAL2.

A DIFERENÇA PARA O aem_corrigir_divergencia.py
Aquele CORRIGE campo que existe com conteúdo errado. Este CRIA o
componente que não existe. Foi essa a falha: em tqmt1022 não há
textwithimage nem bloco de Features, então o script de divergência
passou batido — não havia campo para comparar.

POR QUE ESTAS PÁGINAS FICARAM ASSIM
A maioria das páginas do GWI embrulha texto+imagem num 'imagetext'.
Algumas usam 'resizablecontainer' aninhado:

    resizablecontainer
      resizablecontainer -> text            (a lista de Features)
      resizablecontainer -> resizableimage  (a foto do produto)

A migração não tratou esse formato e perdeu o topo inteiro da página:
H1, parágrafo de introdução, Features E a imagem. Specifications e
Ordering, que ficam no nível plano, passaram normalmente.

COMO ACHA O CONTEÚDO
Achata o jcr:content do GWI em ordem de documento e lê:
  H1       = primeiro heading
  intro    = primeiro text com conteúdo
  features = text logo depois do heading que começa com "Features"
  imagem   = primeiro nó com fileReference
Assim funciona com 'imagetext' e com 'resizablecontainer' aninhado.

A IMAGEM
O fileReference do GWI aponta para /content/dam/macnicagwi/...; o
destino usa /content/dam/macnicaglobal2/.... O asset equivalente JÁ
existe (as páginas irmãs usam), então a busca é pelo NOME do arquivo no
DAM do global2, tolerando maiúsculas e troca de extensão
(TQMT10xx.jpg -> tqmt10xx.jpeg). Se não achar, a página é reportada e
NÃO recebe imagem — melhor sem foto do que com a foto de outro produto.

O QUE CRIA (copiando a convenção das páginas irmãs corretas)
  container_imagem   [cq:styleIds 1717498053499, 1717498056876]
     textwithimage   text = <h1>H1</h1> + intro, fileReference, alt
  container_features [backgroundColor #f0f0f0, styleIds 1717498053499]
     text            <h3>Features</h3> + lista

Posiciona logo depois do container do título, com ':order'. Não mexe em
Specifications, Ordering, botões nem em nada que já exista.

IDEMPOTENTE: só cria o que falta.

COMO RODAR
  python3 aem_reconstruir_blocos.py --destino /content/macnicaglobal2/.../tq-systems \
                                    --origem  /content/macnicagwi/.../tq-systems
  python3 aem_reconstruir_blocos.py --destino ... --origem ... --executar \
      --permitir-escrita-global2 /content/macnicaglobal2/.../tq-systems
"""

import argparse
import html as _h
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from urllib.parse import urljoin, quote
from aem_lib import (CONFIG, HEADING_TYPES, TITLE_TYPES, build_session, crawl_tree,
                     fetch_with_depth_fallback, get_json, list_child_nodes,
                     normalize_name, post_node, print_header, rewrite_links_in_html,
                     session_expired, write_csv)

TAG_RE = re.compile(r"<[^>]+>")
CONTAINER_RT = "macnicaglobal2/components/content/container"
TWI_RT = "macnicaglobal2/components/content/textwithimage"
TEXT_RT = "macnicaglobal2/components/content/text"
ESTILO_IMAGEM = ["1717498053499", "1717498056876"]
ESTILO_FEATURES = ["1717498053499"]
ESTILO_TWI = ["1718154328384", "1783061491236"]


def plano(v):
    return re.sub(r"\s+", " ", _h.unescape(TAG_RE.sub(" ", v or ""))).strip() \
        if isinstance(v, str) else ""


def achatar(jcr):
    """jcr:content em ordem de documento: [(resourceType, nó)]."""
    out = []

    def walk(node):
        for _, ch in list_child_nodes(node):
            out.append((ch.get("sling:resourceType", ""), ch))
            walk(ch)

    walk(jcr)
    return out


def ler_gwi(jcr):
    """(h1, intro_html, features_html, fileReference)."""
    seq = achatar(jcr)
    h1 = intro = feats = img = None
    idx_features = None
    for i, (rt, n) in enumerate(seq):
        texto = plano(n.get("text") or n.get("jcr:title") or "")
        if h1 is None and (rt in HEADING_TYPES or rt in TITLE_TYPES) and texto:
            h1 = texto
            continue
        if idx_features is None and (rt in HEADING_TYPES or rt in TITLE_TYPES) \
                and texto.lower().startswith("features"):
            idx_features = i
            continue
        if rt.endswith("/text") and plano(n.get("text")):
            if idx_features is not None and feats is None:
                feats = n.get("text")
            elif idx_features is None and intro is None:
                intro = n.get("text")
        if img is None and n.get("fileReference"):
            img = n.get("fileReference")
    return h1, intro, feats, img


def mapear_dam(session, base_url, ref_gwi, auth, cache):
    """Acha no DAM do global2 o asset com o mesmo NOME de arquivo."""
    if not ref_gwi:
        return None
    nome = ref_gwi.rsplit("/", 1)[-1]
    raiz = nome.rsplit(".", 1)[0]
    if raiz in cache:
        return cache[raiz]

    # O predicado 'nodename' do QueryBuilder é SENSÍVEL A MAIÚSCULA e os
    # assets do DAM do global2 foram gravados em minúscula na migração
    # ('TQMT10xx.jpg' virou 'tqmt10xx.jpeg'). Procurar com o nome original
    # do GWI não acha NADA — foi assim que a primeira rodada deu
    # "NAO ENCONTRADA" em 7 de 7. Daí as variantes normalizadas.
    variantes = []
    for v in (raiz.lower(), raiz.lower().replace("_", "-"),
              raiz.lower().replace("_", ""), raiz.lower().replace(" ", "-")):
        if v and v not in variantes:
            variantes.append(v)

    escolha = None
    for v in variantes:
        q = ("/bin/querybuilder.json?path=/content/dam/macnicaglobal2"
             "&type=dam:Asset&nodename=" + quote(v + "*", safe="") +
             "&p.limit=20&p.hits=selective&p.properties=jcr%3apath")
        try:
            d = session.get(urljoin(base_url, q), timeout=60).json()
        except Exception:
            continue
        achados = [h.get("jcr:path") for h in d.get("hits", []) if h.get("jcr:path")]
        if not achados:
            continue
        # Preferir o nome exato: 'tqmt10xx.jpeg' antes de 'tqmt10xx (1).jpeg'.
        exato = [a for a in achados
                 if a.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower() == v]
        escolha = (exato or sorted(achados, key=len))[0]
        break
    cache[raiz] = escolha
    return escolha


def estado_destino(jcr):
    """(tem_twi, tem_features, nome_do_container_do_titulo)."""
    cont = ((jcr.get("root") or {}).get("container") or {})
    twi = feat = False
    titulo = None
    for nome, wrap in list_child_nodes(cont):
        for _, comp in list_child_nodes(wrap):
            rt = comp.get("sling:resourceType", "")
            if rt.endswith("/textwithimage"):
                twi = True
            if rt.endswith("/title") and titulo is None:
                titulo = nome
            if rt.endswith("/text") and plano(comp.get("text")).lower().startswith("features"):
                feat = True
    return twi, feat, titulo


def achar_origem(session, base_url, dst, dst_root, org_root, auth, cache):
    rel = dst[len(dst_root):].strip("/")
    atual = org_root
    for parte in rel.split("/") if rel else []:
        filhos = cache.get(atual)
        if filhos is None:
            d, _ = get_json(session, urljoin(base_url, f"{atual}.1.json"), auth)
            filhos = [n for n, _ in list_child_nodes(d or {})]
            cache[atual] = filhos
        exato = parte if parte in filhos else next(
            (n for n in filhos if normalize_name(n) == normalize_name(parte)), None)
        if exato is None:
            return None
        atual = f"{atual}/{exato}"
    return atual


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--destino", required=True)
    ap.add_argument("--origem", required=True)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    ap.add_argument("--link-de", default=CONFIG["gwi_prefix"])
    ap.add_argument("--link-para", default=CONFIG["global2_prefix"])
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    dst_root, org_root = args.destino.rstrip("/"), args.origem.rstrip("/")
    allow = ()
    if args.permitir_escrita_global2:
        lib = args.permitir_escrita_global2.rstrip("/")
        if lib != dst_root:
            print("[erro] --permitir-escrita-global2 precisa ser igual a --destino.",
                  file=sys.stderr)
            sys.exit(1)
        allow = (lib,)

    saida = args.output or f"reconstruir_{dst_root.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("RECRIAR BLOCOS DE TOPO (imagem+intro / Features)")
    print(f"  origem : {org_root}\n  destino: {dst_root}")
    print(f"  modo   : {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv = crawl_tree(s, base, dst_root, at, quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")

    cache_g, cache_dam = {}, {}
    linhas, tarefas = [], []
    for p in paginas:
        dd, _ = fetch_with_depth_fallback(s, base, p, 8, at)
        if dd is None:
            continue
        jcr_d = (dd or {}).get("jcr:content", {}) or {}
        if jcr_d.get("deleted"):
            continue
        tem_twi, tem_feat, cont_titulo = estado_destino(jcr_d)
        if tem_twi and tem_feat:
            continue
        gp = achar_origem(s, base, p, dst_root, org_root, at, cache_g)
        if gp is None:
            continue
        dg, _ = fetch_with_depth_fallback(s, base, gp, 16, at)
        if dg is None:
            continue
        h1, intro, feats, img_gwi = ler_gwi((dg or {}).get("jcr:content", {}) or {})
        if not (h1 or intro or feats):
            continue                       # página de categoria: nada a recriar
        img_dst = mapear_dam(s, base, img_gwi, at, cache_dam) if img_gwi else None

        criar = []
        if not tem_twi and (h1 or intro):
            criar.append("container_imagem")
        if not tem_feat and feats:
            criar.append("container_features")
        if not criar:
            continue
        tarefas.append((p, cont_titulo, criar, h1, intro, feats, img_dst))
        linhas.append({
            "pagina": p, "origem_gwi": gp, "criar": ", ".join(criar),
            "h1": (h1 or "")[:70], "tem_intro": "sim" if intro else "nao",
            "tem_features": "sim" if feats else "nao",
            "imagem_gwi": (img_gwi or "").rsplit("/", 1)[-1],
            "imagem_destino": img_dst or ("NAO ENCONTRADA" if img_gwi else ""),
            "acao": "pendente"})

    print(f"  páginas a reconstruir: {len(tarefas)}\n")
    for l in linhas:
        print(f"   {l['pagina'].rsplit('/', 1)[-1][:46]:<48} criar: {l['criar']}")
        print(f"      h1: {l['h1']}")
        print(f"      intro={l['tem_intro']}  features={l['tem_features']}  "
              f"imagem: {l['imagem_gwi']} -> {(l['imagem_destino'] or '-').rsplit('/', 1)[-1]}")

    if not args.executar:
        write_csv(saida, ["pagina", "origem_gwi", "criar", "h1", "tem_intro",
                          "tem_features", "imagem_gwi", "imagem_destino", "acao"], linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    ok = falhas = 0
    for i, (p, cont_titulo, criar, h1, intro, feats, img) in enumerate(tarefas, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(tarefas)}", file=sys.stderr)
            break
        erro = None
        ordem = f"after {cont_titulo}" if cont_titulo else "first"
        if "container_imagem" in criar:
            corpo = (f"<h1>{h1}</h1>\n" if h1 else "") + (intro or "")
            corpo = rewrite_links_in_html(corpo, args.link_de, args.link_para)
            payload = {
                "jcr:primaryType": "nt:unstructured",
                "sling:resourceType": CONTAINER_RT,
                "cq:styleIds": ESTILO_IMAGEM, "cq:styleIds@TypeHint": "String[]",
                ":order": ordem,
                "textwithimage/jcr:primaryType": "nt:unstructured",
                "textwithimage/sling:resourceType": TWI_RT,
                "textwithimage/text": corpo,
                "textwithimage/textIsRich": "true",
                "textwithimage/cq:styleIds": ESTILO_TWI,
                "textwithimage/cq:styleIds@TypeHint": "String[]",
            }
            if img:
                payload["textwithimage/fileReference"] = img
                payload["textwithimage/alt"] = h1 or ""
                payload["textwithimage/altValueFromDAM"] = "false"
                payload["textwithimage/isDecorative"] = "false"
            st, c = post_node(s, base, f"{p}/jcr:content/root/container/container_imagem",
                              payload, at, allow_extra=allow)
            if st not in (200, 201):
                erro = f"FALHA imagem {st}: {c[:60]}"
            ordem = "after container_imagem"
        if not erro and "container_features" in criar:
            corpo = rewrite_links_in_html("<h3>Features</h3>\n" + (feats or ""),
                                          args.link_de, args.link_para)
            payload = {
                "jcr:primaryType": "nt:unstructured",
                "sling:resourceType": CONTAINER_RT,
                "backgroundColor": "#f0f0f0",
                "cq:styleIds": ESTILO_FEATURES, "cq:styleIds@TypeHint": "String[]",
                ":order": ordem,
                "text/jcr:primaryType": "nt:unstructured",
                "text/sling:resourceType": TEXT_RT,
                "text/text": corpo, "text/textIsRich": "true",
            }
            st, c = post_node(s, base, f"{p}/jcr:content/root/container/container_features",
                              payload, at, allow_extra=allow)
            if st not in (200, 201):
                erro = f"FALHA features {st}: {c[:60]}"
        if erro:
            falhas += 1; linhas[i - 1]["acao"] = erro
            print(f"  [{erro}] {p}")
        else:
            ok += 1; linhas[i - 1]["acao"] = "reconstruído"

    write_csv(saida, ["pagina", "origem_gwi", "criar", "h1", "tem_intro",
                      "tem_features", "imagem_gwi", "imagem_destino", "acao"], linhas)
    print(f"\n  reconstruídas: {ok}   falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
