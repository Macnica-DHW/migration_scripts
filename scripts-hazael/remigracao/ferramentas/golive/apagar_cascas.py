#!/usr/bin/env python3
"""
apagar_cascas.py [--executar] — apaga as 4 páginas de nome errado/sobrando do global2. Dry-run por padrão.

Autorizado pelo Hazael em 21/09/2026 ("Yes, you can go ahead and delete the 4 pages"), depois de ver a
lista de dados/golive/cascas_nome_errado_2026-09-21.json. NÃO mexe no post do blog que aponta para uma
delas: é da Anion, que já foi avisada para trocar os links para minúscula (ordem dele).

Travas: só os 4 caminhos EXATOS abaixo; nada com `macnicagwi` (REGRA MESTRA); o estado é relido AO VIVO
e tem de ser o MESMO da lista que ele aprovou (mesmo cq:lastModified, mesmo nº de componentes, sem
página-filha, não publicada) — mudou, ABORTA essa página; backup da página INTEIRA conferido antes do
delete; 404 conferido depois. Restaurar: POST no pai com :operation=import, :contentType=json,
:name=<nome>, :content=<o "pagina" do backup>.
"""
import datetime, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import direto as DIR
from aem_lib import build_session

LISTA = DIR.DADOS / "cascas_nome_errado_2026-09-21.json"
APROVADAS = {f"{DIR.MAI}/technology/Broadcast-ProAV-Solutions",
             f"{DIR.MAI}/technology/SmartCity-Mobility",
             f"{DIR.MAI}/services/Imaging-and-Vision-Engineering-Services",
             f"{DIR.MAI}/technology/macnica-iot-solutions"}
BACKUPS = DIR.BACKUPS / "apagadas"


def main():
    executar = "--executar" in sys.argv
    s, _auth = build_session(prompt_if_missing=False, verbose=False)
    aprovado = {d["caminho"]: d for d in json.load(open(LISTA))}
    assert set(aprovado) == APROVADAS, "a lista aprovada não bate com os 4 caminhos"
    alvo = DIR.Alvo(s, "technology", [])            # só para ler; a escrita daqui NÃO usa a lista branca dele
    feitas = 0
    for p in sorted(APROVADAS):
        if "macnicagwi" in p or not p.startswith(DIR.MAI + "/"):
            DIR.aborta(f"caminho fora do global2: {p}")
        st, pg = alvo.ler(p, ".infinity.json")
        if not isinstance(pg, dict):                # HTTP 300: lista de profundidades
            st, pg = alvo.ler(p, ".60.json")
        if st == 404:
            print(f"  [já não existe] {p[len(DIR.MAI):]}"); continue
        if st != 200 or not isinstance(pg, dict) or "jcr:content" not in pg:
            print(f"  [PULADA] HTTP {st} ao ler {p}"); continue
        jc, era = pg["jcr:content"], aprovado[p]
        filhas = [k for k, v in pg.items() if isinstance(v, dict) and v.get("jcr:primaryType") == "cq:Page"]
        agora = f"{jc.get('cq:lastModified')} por {jc.get('cq:lastModifiedBy')}"
        motivos = []
        if agora != era["modificada"]: motivos.append(f"modificada depois da lista: {agora}")
        if DIR.componentes_de_conteudo(jc) != era["componentes"]: motivos.append("nº de componentes mudou")
        if filhas: motivos.append(f"tem página-filha: {filhas}")
        if jc.get("cq:lastReplicationAction") == "Activate": motivos.append("está PUBLICADA")
        if motivos:
            print(f"  [PULADA — não é mais o que foi aprovado] {p[len(DIR.MAI):]}: {'; '.join(motivos)}"); continue
        print(f"  {'apagar' if executar else '[dry-run] apagaria'} {p[len(DIR.MAI):]:58} {era['componentes']:3} componentes, {agora}")
        if not executar:
            continue
        BACKUPS.mkdir(parents=True, exist_ok=True)
        arq = BACKUPS / (p[len(DIR.MAI):].strip("/").replace("/", "__") + ".json")
        arq.write_text(json.dumps({"caminho": p, "lido_em": datetime.datetime.now().isoformat(timespec="seconds"),
                                   "pagina": pg}, indent=1, ensure_ascii=False))
        volta = json.loads(arq.read_text())["pagina"]["jcr:content"]
        if DIR.componentes_de_conteudo(volta) != era["componentes"] or volta.get("jcr:title") != era["titulo"]:
            DIR.aborta(f"o backup não confere com a página: {arq}")
        r = s.post(DIR._url(p), data={":operation": "delete"}, timeout=120)
        st2, _ = alvo.ler(p, ".0.json")
        alvo._registra("pagina-apagada", None, p, r.status_code, {"backup": f"apagadas/{arq.name}", "depois": st2})
        print(f"         delete HTTP {r.status_code}; relida: HTTP {st2}; backup {arq.name} ({arq.stat().st_size} bytes)")
        if r.status_code not in (200, 204) or st2 != 404:
            DIR.aborta(f"a página não saiu como esperado: {p}")
        feitas += 1
    print(f"\n  {'apagadas' if executar else 'a apagar'}: {feitas if executar else len(APROVADAS)}")


if __name__ == "__main__":
    main()
