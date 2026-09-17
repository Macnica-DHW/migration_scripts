#!/usr/bin/env python3
"""
Corrige marcação quebrada que virou TEXTO VISÍVEL nas páginas do GLOBAL2.

O QUE SÃO ESTES BUGS
Não são dano de migração: os dois casos conhecidos existem IDÊNTICOS no
GWI e foram copiados fielmente. São erros de autoria da origem que hoje
aparecem para o visitante. Decisão do time (17/09/2026): o GWI é somente
leitura e não se mexe nele, mas o GLOBAL2 tem que sair limpo — então a
correção é feita aqui, do lado do destino.

OS DOIS CASOS

1. RESÍDUO DE TAG (automático)
   Um </strong> perdeu o '<' e foi escapado, virando texto:
       <p><b>TQMa3359-AA/strong&gt;</b></p>
   O visitante lê "TQMa3359-AA/strong>". Corrigido tirando o resíduo
   '/strong&gt;'. A varredura acha qualquer '/tag&gt;' ou '&lt;tag&gt;'
   que tenha sobrado como texto, não só este.

2. PART NUMBER FUNDIDO (lista explícita)
   Em tqmlx2160a, a 1ª coluna traz:
       TQMTQMLX2080A-AALX2120A-AA
   que é 'TQMLX2120A-AA' com 'TQMLX2080A-AA' enfiado no meio. Não é
   dedução: a 2ª coluna da MESMA linha começa com "TQMLX2080A-AA, 8
   Cortex®-A72..." e a tabela segue a sequência 2160A (16 núcleos) ->
   2120A (12) -> 2080A (8). Correção explícita, uma por uma, porque
   reconstruir part number por heurística é jeito de inventar peça que
   não existe.

ATENÇÃO — ISTO CRIA DIVERGÊNCIA PROPOSITAL COM O GWI
Depois desta correção, estas células passam a diferir da origem. O
aem_corrigir_divergencia.py NÃO reverte (ele só mexe em textwithimage e
no bloco de Features, nunca em tabela), mas uma REMIGRAÇÃO ou um
aem_clone_subtree.py a partir do GWI traz o lixo de volta. Se isso
acontecer, é só rodar este script de novo — ele é idempotente.

COMO RODAR
  python3 aem_corrigir_lixo_markup.py --raiz /content/macnicaglobal2/.../tq-systems
  python3 aem_corrigir_lixo_markup.py --raiz ... --executar \
      --permitir-escrita-global2 /content/macnicaglobal2/.../tq-systems
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts-bruno"))

from aem_lib import (CONFIG, build_session, crawl_tree, fetch_with_depth_fallback,
                     list_child_nodes, post_node, print_header, session_expired,
                     write_csv)

# Resíduo de tag que sobrou como texto escapado.
RESIDUO_RE = re.compile(r"(?:&lt;\s*/?\s*[A-Za-z][A-Za-z0-9]*\s*/?\s*&gt;)"
                        r"|(?:/[A-Za-z][A-Za-z0-9]*&gt;)")

# Correções pontuais, cada uma conferida contra a 2ª coluna da própria
# linha. Chave = trecho exato a substituir; valor = texto correto.
CORRECOES_EXPLICITAS = {
    # tqmlx2160a-embedded-cortexr-a72: a descrição da linha diz
    # "TQMLX2080A-AA, 8 Cortex®-A72/2.2 GHz..."
    "TQMTQMLX2080A-AALX2120A-AA": "TQMLX2080A-AA",
}

PROPS = ("text", "jcr:title", "jcr:description", "cq:panelTitle")


def corrigir(valor):
    """Devolve (novo_valor, [descrições do que mudou])."""
    if not isinstance(valor, str):
        return valor, []
    novo, mudancas = valor, []
    for errado, certo in CORRECOES_EXPLICITAS.items():
        if errado in novo:
            novo = novo.replace(errado, certo)
            mudancas.append(f"{errado} -> {certo}")
    for m in RESIDUO_RE.finditer(novo):
        mudancas.append(f"removido {m.group(0)!r}")
    novo = RESIDUO_RE.sub("", novo)
    return novo, mudancas


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

    saida = args.output or f"lixo_markup_{raiz.rsplit('/', 1)[-1]}.csv"
    s, at = build_session(prompt_if_missing=not args.no_prompt)
    base = args.base_url.rstrip("/")

    print_header("CORRIGIR MARCAÇÃO QUEBRADA VISÍVEL")
    print(f"  raiz: {raiz}")
    print(f"  modo: {'ESCRITA' if args.executar else 'diagnóstico'}\n")

    inv = crawl_tree(s, base, raiz, at, quiet=True)
    paginas = sorted(p for p, m in inv.items() if m["is_page"])
    print(f"  {len(paginas)} páginas\n")

    linhas, tarefas = [], []
    for p in paginas:
        dd, _ = fetch_with_depth_fallback(s, base, p, 10, at)
        if dd is None:
            continue
        jcr = (dd or {}).get("jcr:content", {}) or {}
        if jcr.get("deleted"):
            continue

        def walk(node, caminho):
            for nome, ch in list_child_nodes(node):
                sub = f"{caminho}/{nome}"
                for prop in PROPS:
                    novo, mud = corrigir(ch.get(prop))
                    if mud:
                        tarefas.append((p, sub.lstrip("/"), prop, novo))
                        linhas.append({"pagina": p, "no": sub.lstrip("/"),
                                       "propriedade": prop,
                                       "mudancas": " | ".join(mud),
                                       "acao": "pendente"})
                walk(ch, sub)

        walk(jcr, "jcr:content")

    print(f"  ocorrências a corrigir: {len(tarefas)}\n")
    for l in linhas:
        print(f"   {l['pagina'].rsplit('/', 1)[-1][:44]:<46} {l['propriedade']}")
        print(f"      {l['mudancas']}")
        print(f"      em {l['no']}")

    if not args.executar:
        write_csv(saida, ["pagina", "no", "propriedade", "mudancas", "acao"], linhas)
        print(f"\n  Nada escrito. Use --executar.\n  CSV: {saida}")
        return

    ok = falhas = 0
    for i, (p, no, prop, novo) in enumerate(tarefas, 1):
        if session_expired(at):
            print(f"\n[erro] sessão expirou em {i-1}/{len(tarefas)}", file=sys.stderr)
            break
        payload = {prop: novo}
        if prop == "text":
            payload["textIsRich"] = "true"
        st, corpo = post_node(s, base, f"{p}/{no}", payload, at, allow_extra=allow)
        if st in (200, 201):
            ok += 1; linhas[i - 1]["acao"] = "corrigido"
        else:
            falhas += 1; linhas[i - 1]["acao"] = f"FALHA {st}"
            print(f"  [FALHA {st}] {p}/{no} :: {corpo[:80]}")

    write_csv(saida, ["pagina", "no", "propriedade", "mudancas", "acao"], linhas)
    print(f"\n  corrigidas: {ok}   falhas: {falhas}\n  CSV: {saida}")


if __name__ == "__main__":
    main()
