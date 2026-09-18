#!/bin/bash
# prints.sh <dir-saida-ABSOLUTO> <rel> [<rel>...]  — print GWI x destino, página inteira, --publicado
# SIDE=gwi|dest|both (padrão both). Ex.:  SIDE=dest ./prints.sh /tmp/p /altera /canon
# Depois: python3 fatiar.py /tmp/p   e comparar <nome>__gwi__NN.png x <nome>__dest__NN.png
OUT="$1"; shift
mkdir -p "$OUT"
cd "$(dirname "$(readlink -f "$0")")/../.."   # scripts-hazael/
G=/content/macnicagwi/americas/mai/en/products/semiconductors
D=/content/copia-teste/americas/mai/en/products/semiconductors-remigration
for rel in "$@"; do
  nome=$(echo "$rel" | sed 's#^/##; s#/#__#g'); [ -z "$nome" ] && nome=landing
  r="$rel"; [ "$rel" = "/" ] && r=""
  # o destino normaliza o nome do nó (li8030SA -> li8030sa): sem isto o print sai do 404 ("Loading...")
  rd=$(echo "$r" | tr 'A-Z' 'a-z' | sed -E 's#[^a-z0-9/]+#-#g; s#-+#-#g; s#/-#/#g; s#-(/|$)#\1#g')
  if [ "${SIDE:-both}" != dest ]; then python3 aem_screenshot.py "$G$r" -o "$OUT/${nome}__gwi.png"  --full --publicado >/dev/null 2>&1 || echo "falhou gwi $rel"; fi
  if [ "${SIDE:-both}" != gwi ];  then python3 aem_screenshot.py "$D$rd" -o "$OUT/${nome}__dest.png" --full --publicado >/dev/null 2>&1 || echo "falhou dest $rel"; fi
  echo "ok $rel"
done
