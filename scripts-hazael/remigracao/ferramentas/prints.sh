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
  [ "${SIDE:-both}" != dest ] && python3 aem_screenshot.py "$G$r" -o "$OUT/${nome}__gwi.png"  --full --publicado >/dev/null 2>&1 || echo "falhou gwi $rel"
  [ "${SIDE:-both}" != gwi ] && python3 aem_screenshot.py "$D$r" -o "$OUT/${nome}__dest.png" --full --publicado >/dev/null 2>&1 || echo "falhou dest $rel"
  echo "ok $rel"
done
