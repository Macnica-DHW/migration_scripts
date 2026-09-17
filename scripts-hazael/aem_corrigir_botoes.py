#!/usr/bin/env python3
"""
Padroniza os botões "Sign up" e "Contact us" das páginas de produto.

O QUE APLICA (definido pelo time em 17/09/2026)
    ambos      linkTarget = _blank      (abrir em nova aba)
    Sign up    linkURL    = https://visitor.r20.constantcontact.com/manage/optin?v=001dwtC1_...
    Contact us linkURL    = /content/macnicaglobal2/americas/mai/en/contact/form.html

ESTADO ANTES (conferido em tq-systems e na página de referência)
Os dois botões vinham com `linkTarget=_self` — inclusive na página de
referência da migração, então "igual à referência" NÃO descrevia o estado
real dela; o pedido é o alvo novo, não uma cópia do que já existe.

O link do "Sign up" já estava correto em tq-systems (328 caracteres,
idêntico). O do "Contact us" apontava para a URL pública absoluta
(`https://www.macnica.com/americas/mai/en/contact/form/`) e passa a apontar
para o caminho interno do global2 — o que sobrevive a troca de domínio e é
resolvido pelo próprio AEM.

"Abrir em nova aba" NÃO é style: a policy do button
(/conf/.../content/button/policy_1717669061681) só tem 【Background Color】,
【Width】 e 【Display Position】. O controle é a propriedade `linkTarget`.

Só mexe em `linkTarget` e `linkURL`, e só em botão cujo `jcr:title` seja
exatamente um dos dois. Não toca em estilo, posição, largura nem em
qualquer outro botão da página.

IDEMPOTENTE: botão já correto é pulado.

COMO RODAR
  python3 aem_corrigir_botoes.py --raiz /content/macnicaglobal2/.../tq-systems
  python3 aem_corrigir_botoes.py --raiz ... --executar \
      --permitir-escrita-global2 /content/macnicaglobal2/.../tq-systems
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import (CONFIG, build_session, crawl_tree, fetch_with_depth_fallback,
                     list_child_nodes, post_node, print_header, session_expired,
                     write_csv)

URL_SIGNUP = ("https://visitor.r20.constantcontact.com/manage/optin?v=001dwtC1_5l2X95pEGF-"
              "tfajTnjuco352BxLxaAjPBvxZ5ajvboL3j82hAC5eShsFYX4Y8c7eb7Psk1Wt0lNdmFTyykwvu3"
              "nROM6dYUzZFUXPCW1dI_Zl0xB0K2b9h3AzAVkJ9SdocYJEjotB7mFAE2Sbv_nGmDoHTm2i-E6X2"
              "JCP8ki47J_MKW8AXLzNumSzfSYiLtqpHza8sJthaI2rGXod-2XdCthogWDb8BRgH4ZI1or8ZkCR"
              "V81nlRPueUwIlPyqAHAf_SvzE%3D")
URL_CONTATO = "/content/macnicaglobal2/americas/mai/en/contact/form.html"
ALVO = "_blank"

BOTOES = {"sign up": URL_SIGNUP, "contact us": URL_CONTATO}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", required=True)
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--permitir-escrita-global2", default=None, metavar="CAMINHO")
    ap.add_argument("--base-url", default=CONFIG["base_url"])
    ap.add_argument("--output", default=None)
    ap.add_argument("--no-prompt", action="store_true")
    args = ap.parse_args()

    raiz = args.raiz.rstrip("/")
    allow = ()
    if args.permitir_escrita_global2:
        lib = args.permitir_escrita_global2.rstrip("/")
        if lib != raiz:
            print("[erro] --permitir-escrita-global2 precisa ser igual a --raiz.",
                  file=sys.stderr)
            sys.exit(1)
        allow = (lib,)

    saida = args.output or f"botoes_{raiz.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("BOTÕES Sign up / Contact us")
    print(f"  raiz: {raiz}")
    print(f"  alvo: linkTarget={ALVO}  |  Contact us -> {URL_CONTATO}")
    print(f"  modo: {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv = crawl_tree(s, base, raiz, at, quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")

    linhas, tarefas = [], []
    sem_botao = 0
    for p in paginas:
        dd, _ = fetch_with_depth_fallback(s, base, p, 10, at)
        if dd is None:
            continue
        jcr = (dd or {}).get("jcr:content", {}) or {}
        if jcr.get("deleted"):
            continue
        achou = False

        def walk(node, caminho):
            nonlocal achou
            for nome, ch in list_child_nodes(node):
                sub = f"{caminho}/{nome}"
                if (ch.get("sling:resourceType") or "").endswith("/button"):
                    titulo = str(ch.get("jcr:title") or "").strip().lower()
                    if titulo in BOTOES:
                        achou = True
                        url_ok = BOTOES[titulo]
                        muda = []
                        if str(ch.get("linkTarget") or "") != ALVO:
                            muda.append(f"linkTarget {ch.get('linkTarget') or '(ausente)'} -> {ALVO}")
                        if str(ch.get("linkURL") or "") != url_ok:
                            muda.append("linkURL atualizado")
                        if muda:
                            tarefas.append((p, sub.lstrip("/"), url_ok))
                            linhas.append({"pagina": p, "botao": ch.get("jcr:title"),
                                           "no": sub.lstrip("/"),
                                           "mudancas": " | ".join(muda),
                                           "url_antiga": str(ch.get("linkURL") or "")[:70],
                                           "acao": "pendente"})
                walk(ch, sub)

        walk(jcr, "jcr:content")
        if not achou:
            sem_botao += 1

    print(f"  páginas sem esses botões : {sem_botao}")
    print(f"  botões a corrigir        : {len(tarefas)}\n")
    from collections import Counter
    resumo = Counter((l["botao"], l["mudancas"]) for l in linhas)
    for (bt, mu), n in resumo.most_common():
        print(f"   {n:4d}x  {bt:<12} {mu}")
    if linhas:
        print(f"\n  exemplo de URL antiga do Contact us:")
        for l in linhas:
            if l["botao"].lower() == "contact us":
                print(f"     {l['url_antiga']}")
                break

    if not args.executar:
        write_csv(saida, ["pagina", "botao", "no", "mudancas", "url_antiga", "acao"], linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    ok = falhas = 0
    for i, (p, no, url) in enumerate(tarefas, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(tarefas)}", file=sys.stderr)
            break
        st, corpo = post_node(s, base, f"{p}/{no}",
                              {"linkTarget": ALVO, "linkURL": url},
                              at, allow_extra=allow)
        if st in (200, 201):
            ok += 1; linhas[i - 1]["acao"] = "corrigido"
        else:
            falhas += 1; linhas[i - 1]["acao"] = f"FALHA {st}"
            print(f"  [FALHA {st}] {p}/{no} :: {corpo[:70]}")
        if i % 50 == 0:
            print(f"  [{i}/{len(tarefas)}] ok={ok} falhas={falhas}", flush=True)

    write_csv(saida, ["pagina", "botao", "no", "mudancas", "url_antiga", "acao"], linhas)
    print(f"\n  corrigidos: {ok}   falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
