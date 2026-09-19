# lista_do_dry.py <dry.txt> — páginas que mudam DE VERDADE no dry-run do diff_payload
# (ignora a "adição" de propriedade vazia, ex. `alt = `: o JCR não guarda string vazia, então ela aparece sempre)
import re, sys
txt = open(sys.argv[1]).read()
for b in re.split(r"\n(?=### )", txt):
    m = re.match(r"### (\S+)", b); c = re.search(r"chaves: \+(\d+) -(\d+) ~(\d+)", b)
    if not m or not c: continue
    a, r, ch = map(int, c.groups())
    if a:
        sec = re.search(r"\+ adicionadas:\n(.*?)(?=\n    \S|\Z)", b, re.S)
        linhas = [l for l in (sec.group(1).split("\n") if sec else []) if l.strip()]
        a = sum(1 for l in linhas if not re.match(r"^\s+\S+ = \s*$", l))
    if a or r or ch:
        print(m.group(1))
