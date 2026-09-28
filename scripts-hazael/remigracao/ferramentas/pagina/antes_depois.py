#!/usr/bin/env python3
"""
antes_depois.py <caminho>... [--antes antes] [--depois depois] [--lado g2] [--saida DIR] [--nome NOME]
— a MESMA página antes x depois de uma gravação: prova de que o conteúdo não mudou. SOMENTE LEITURA (só lê os
renders do render.py; nenhuma requisição).

Compara <nome>__<lado>__<antes>.json com <nome>__<lado>__<depois>.json:
  texto    blocos visíveis, na MESMA ordem (todas as abas abertas);
  links    texto, href e target, na ordem;
  imagens  arquivo de cada imagem visível (largura > 1px), na ordem;
  vídeos   src dos iframes (sem o reCAPTCHA);
  abas     rótulos dos painéis;
  headings nível e começo do texto (mudança de nível aparece aqui);
e a altura da página. Tudo igual = OK; senão CONFERIR, com o que mudou. Uma fusão deliberada (3 componentes -> 1
Text with Image) muda a ordem/nível e sai como CONFERIR: listar como pretendida no relato.
Teste de estabilidade: dois renders SEM gravação no meio têm de dar OK — senão o comparador tem ruído.

    cd scripts-hazael
    python3 remigracao/ferramentas/pagina/render.py /products/boards-modules/iei --etiqueta depois
    python3 remigracao/ferramentas/pagina/antes_depois.py /products/boards-modules/iei

Sai com código 1 se alguma página der CONFERIR.
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import absoluto, arquivo, nome  # noqa: E402


def n(t):
    return re.sub(r"\s+", " ", t.replace("\xa0", " ")).strip()


def resumo(x):
    return dict(
        texto=" ".join(n(b[1]) for b in x["out"] if b[2]),
        headings=[(b[0], n(b[1])[:30]) for b in x["out"] if b[2] and b[0].startswith("H")],
        links=[(n(l[0]), l[1], l[2]) for l in x["links"]],
        imagens=[i[0] for i in x["imgs"] if i[2] > 1],
        videos=[v[0] if isinstance(v, list) else v for v in x["iframes"]],
        abas=[a["rotulo"] for a in x.get("abas", [])],
    )


def comparar(caminho, antes="antes", depois="depois", lado="g2", saida=None, nome_=None):
    nm = nome_ or nome(absoluto(caminho))
    a = json.loads(arquivo(nm, lado, antes, "json", saida).read_text(encoding="utf-8"))
    d = json.loads(arquivo(nm, lado, depois, "json", saida).read_text(encoding="utf-8"))
    ra, rd = resumo(a), resumo(d)
    ra["videos"] = [v for v in ra["videos"] if v and "recaptcha" not in v]
    rd["videos"] = [v for v in rd["videos"] if v and "recaptcha" not in v]
    iguais = {k: ra[k] == rd[k] for k in ("texto", "links", "imagens", "videos", "abas", "headings")}
    ok = all(iguais.values())
    print(f"### {caminho}: texto igual={iguais['texto']}  links iguais={iguais['links']} ({len(rd['links'])})  "
          f"imagens iguais={iguais['imagens']} ({len(rd['imagens'])})  vídeos iguais={iguais['videos']}  "
          f"abas iguais={iguais['abas']} ({len(rd['abas'])})  altura {a['h']} -> {d['h']}  => {'OK' if ok else 'CONFERIR'}")
    if not iguais["headings"]:
        print("   headings:", [x for x in ra["headings"] if x not in rd["headings"]], "->",
              [x for x in rd["headings"] if x not in ra["headings"]])
    if not iguais["texto"]:
        wa, wd = ra["texto"].split(), rd["texto"].split()
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wa, wd, autojunk=False).get_opcodes():
            if op != "equal":
                print("   texto", op, wa[i1:i2][:20], "->", wd[j1:j2][:20])
    for k in ("links", "imagens", "videos", "abas"):
        if not iguais[k]:
            print(f"   {k}: sumiu {[x for x in ra[k] if x not in rd[k]][:8]}  apareceu {[x for x in rd[k] if x not in ra[k]][:8]}"
                  + ("  (mesmos itens, outra ordem)" if sorted(map(str, ra[k])) == sorted(map(str, rd[k])) else ""))
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("caminhos", nargs="+")
    ap.add_argument("--antes", default="antes", help="etiqueta do render de antes (padrão: antes)")
    ap.add_argument("--depois", default="depois", help="etiqueta do render de depois (padrão: depois)")
    ap.add_argument("--lado", choices=["g2", "gwi"], default="g2")
    ap.add_argument("--saida", help="pasta dos renders (padrão: remigracao/dados/paginas/<nome>/)")
    ap.add_argument("--nome", help="nome dos arquivos, se o render usou --nome")
    a = ap.parse_args()
    if a.nome and len(a.caminhos) > 1:
        ap.error("--nome vale para um caminho só")
    todos = True
    for c in a.caminhos:
        try:
            todos &= comparar(c, a.antes, a.depois, a.lado, a.saida, a.nome)
        except FileNotFoundError as e:
            todos = False
            print(f"### {c}: sem render ({Path(e.filename).name}) — rodar render.py com essa etiqueta")
    sys.exit(0 if todos else 1)


if __name__ == "__main__":
    main()
