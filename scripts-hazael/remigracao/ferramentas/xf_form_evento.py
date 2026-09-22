#!/usr/bin/env python3
"""
xf_form_evento.py [--executar] [--carimbo "<cq:lastModified da página>"] — XF do form "Meeting Request" dos
eventos + o vão abaixo do "Send message" (pedido do Hazael, 22/09/2026). Dry-run por padrão.

Origem: o form inline de about-us/news-events/events-archive/embedded-vision-summit-2025 (copia-teste), montado
à mão pelo Bruno em 22/09. No GWI os 15 eventos têm este mesmo form, cada um com assunto próprio e 5 listas de
destinatários diferentes; decisão do Hazael: UM XF, assunto genérico com o título da página no fim.

Três gravações, cada uma idempotente e com backup antes:

 1. CRIA o XF <ef_root>/event-meeting-request-form (master com xfpage, como os popups) com o form copiado nó a
    nó, na mesma ordem — um POST por nó, porque o Sling não garante a ordem de irmãos criados no mesmo POST.
    Diferenças deliberadas: assunto "Meeting Request" + "Include page title in Subject" ligado (o sufixo é o
    título da página que EMBUTE o XF: o hidden `page-title` vem do currentPage — os forms fantasmas abaixo,
    com recurso no caminho de XF, já imprimem o título do evento); popups -> os do global2; sem a
    propriedade `action` (é o caminho do "store" em usergenerated DAQUELA página; o <form action> renderizado
    é sempre currentPage + .html). Não sobrescreve.
 2. Na página: successFragmentPath/errorFragmentPath do form inline -> popups do global2. Os caminhos de hoje
    (landingpage_popups/..., o nome do GWI com o prefixo trocado) dão 404, e o HTL do form container, sem
    recurso, renderiza O PRÓPRIO FORM em cada gancho: 2 forms fantasmas com 120px de margem cada, e o </form>
    do 1º fecha o form de verdade antes da hora (3 `:formstart` no DOM). A página continua com o form inline
    (decisão do Hazael: a troca pelo XF fica para depois — o Bruno está mexendo em events-archive).
    Só grava com --carimbo igual ao cq:lastModified lido na hora (ler, decidir, gravar).
 3. Nos 2 popups do global2 (XFs nossos, copiados no go-live de 21/09): estilo "No Padding" (1717498056876) no
    root/container. O .cmp-popup é position:fixed + display:none, mas o container em volta tem 50+50px de
    padding: cada popup escondido ocupa 100px abaixo do botão, em todo form que usa esses popups (8 da
    copia-teste + macnica-and-adi do global2). O overlay do popup aberto não muda (é fixed).

Medido a 1400px, ?wcmmode=disabled, do fim do botão ao fim da faixa cinza (GWI: 136 até o rodapé):
  antes  390px = 240 dos 2 forms fantasmas + 120 de `.cmp-form{margin-bottom:90pt}` do tema + 30 da faixa (Small)
  depois 242px = 2 x 46 + 120 + 30 (gravado em 22/09 19:02 -03)
Os 46px de cada popup são `.xf-content-height{min-height:46px;margin:0 -12px}`, CSS do PRODUTO
(/libs/cq/experience-fragments/components/xfpage/content), em volta de todo XF embutido com xfpage — com o
container já sem padding o popup mede 0 e o wrapper continua 46. Os 120px são CSS do tema, iguais em todo form.
Nenhum dos dois sai com conteúdo: 242 é o piso por conteúdo; o resto é CSS em /apps (time AEM da Macnica).

REGRA MESTRA: nada que contenha `macnicagwi` é gravado (checado aqui, além da trava do aem_lib).

  python3 remigracao/ferramentas/xf_form_evento.py                  # dry-run: plano + carimbo atual
  python3 remigracao/ferramentas/xf_form_evento.py --executar --carimbo "Tue Sep 22 2026 21:38:31 GMT+0000"
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_RAIZ / "scripts-bruno"))
from aem_lib import CONFIG, build_session, get_json, post_node  # noqa: E402

PAGINA = "/content/copia-teste/americas/mai/en/about-us/news-events/events-archive/embedded-vision-summit-2025"
FORM_REL = "root/container/text_2_wrap/container"
XF = CONFIG["ef_root"].rstrip("/") + "/event-meeting-request-form"
XF_TITULO = "Event Meeting Request Form"
XF_TEMPLATE = "/conf/macnicaglobal2/settings/wcm/templates/xf-web-variation"
POPUPS = "/content/experience-fragments/macnicaglobal2/americas/mai/en/site/popups"
SUCESSO, ERRO = f"{POPUPS}/form-success/master", f"{POPUPS}/form-error/master"
SEM_PADDING = "1717498056876"          # container, "No Padding" = container-padding-height0
ASSUNTO = "Meeting Request"
PARA = ["Carl.Dahlberg@macnica.com", "motoki.nagashima@macnica.com", "cindy.plante@macnica.com"]
FILHOS_ESPERADOS = 10

# carimbos e metadados que não se copiam: o AEM gera os dele
PULA = ("jcr:created", "jcr:createdBy", "jcr:lastModified", "jcr:lastModifiedBy", "cq:lastModified",
        "cq:lastModifiedBy", "jcr:mixinTypes", "jcr:uuid", "jcr:versionHistory", "jcr:baseVersion",
        "jcr:predecessors", "jcr:isCheckedOut", "cq:isDelivered")
BACKUP = Path(__file__).resolve().parents[1] / "dados" / "golive" / "backup_xf"


def sem_gwi(path):
    if "macnicagwi" in path:
        sys.exit(f"[ABORTADO] caminho do GWI numa escrita — o GWI é SOMENTE LEITURA: {path}")


def props_de(no):
    """Propriedades escalares do nó, com TypeHint para o Sling não trocar o tipo."""
    out = {}
    for k, v in no.items():
        if isinstance(v, dict) or k in PULA or k.startswith("cq:lastReplicat"):
            continue
        if isinstance(v, bool):
            out[k], out[f"{k}@TypeHint"] = ("true" if v else "false"), "Boolean"
        elif isinstance(v, int):
            out[k], out[f"{k}@TypeHint"] = str(v), "Long"
        elif isinstance(v, list):
            out[k], out[f"{k}@TypeHint"] = [str(x) for x in v], "String[]"
        else:
            out[k] = str(v)
    return out


def nos_em_ordem(no, rel):
    """(caminho relativo, props) de cada nó, pai antes dos filhos, irmãos na ordem do JSON (= ordem do JCR)."""
    yield rel, props_de(no)
    for k, v in no.items():
        if isinstance(v, dict):
            yield from nos_em_ordem(v, f"{rel}/{k}")


def gravar(sessao, auth, path, payload, executar, allow_extra=()):
    sem_gwi(path)
    if not executar:
        return "dry"
    st, txt = post_node(sessao, CONFIG["base_url"], path, {**payload, "_charset_": "utf-8"}, auth,
                        allow_extra=allow_extra)
    if st not in (200, 201):
        sys.exit(f"[erro] HTTP {st} gravando {path}: {txt}")
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--executar", action="store_true")
    ap.add_argument("--carimbo", help="cq:lastModified da página, como o dry-run mostrou (passo 2)")
    args = ap.parse_args()
    base = CONFIG["base_url"]
    sessao, auth = build_session(prompt_if_missing=False, verbose=False)
    print("EXECUTANDO" if args.executar else "dry-run (nada é gravado)")

    # ---- leitura + backup (aborta se qualquer lado não vier inteiro) ----
    pag, st = get_json(sessao, f"{base}{PAGINA}/jcr:content.infinity.json", auth)
    if st != 200 or not isinstance(pag, dict) or "root" not in pag:
        sys.exit(f"[erro] HTTP {st} lendo {PAGINA}/jcr:content — nada feito")
    if pag.get("deleted") or pag.get("deletedBy"):
        sys.exit("[erro] a página está soft-deleted — nada feito")
    form = pag
    for k in FORM_REL.split("/"):
        form = form.get(k) if isinstance(form, dict) else None
    if not isinstance(form, dict) or not str(form.get("sling:resourceType", "")).endswith("/form/container"):
        sys.exit(f"[erro] {FORM_REL} não é um form container — a página mudou; nada feito")
    filhos = [k for k, v in form.items() if isinstance(v, dict)]
    if len(filhos) != FILHOS_ESPERADOS:
        sys.exit(f"[erro] esperava {FILHOS_ESPERADOS} campos no form, achei {len(filhos)} — a página mudou")
    carimbo = pag.get("cq:lastModified")
    print(f"página  {PAGINA}\n  último editor {pag.get('cq:lastModifiedBy')} em {carimbo}")

    popups = {}
    for p in (SUCESSO, ERRO):
        j, st = get_json(sessao, f"{base}{p}/jcr:content.infinity.json", auth)
        if st != 200 or not isinstance(j, dict) or not isinstance(j.get("root", {}).get("container"), dict):
            sys.exit(f"[erro] HTTP {st} ou estrutura inesperada em {p} — nada feito")
        popups[p] = j
    if args.executar:
        BACKUP.mkdir(parents=True, exist_ok=True)
        arq = BACKUP / f"xf_form_evento_{datetime.datetime.now():%Y-%m-%d_%H%M%S}.json"
        arq.write_text(json.dumps({"lido_em": datetime.datetime.now().isoformat(timespec="seconds"),
                                   f"{PAGINA}/jcr:content": pag,
                                   **{f"{p}/jcr:content": j for p, j in popups.items()}},
                                  ensure_ascii=False, indent=1))
        print(f"backup  {arq}")

    # ---- 1. o XF ----
    print(f"\n[1] XF {XF}")
    ja, st = get_json(sessao, f"{base}{XF}.json", auth)
    if st == 200:
        print("    JÁ EXISTE — não toco")
    elif st != 404:
        sys.exit(f"[erro] HTTP {st} conferindo {XF} — sem certeza de que está livre, não gravo")
    else:
        nos = list(nos_em_ordem(form, "form"))
        raiz = nos[0][1]
        for k in [k for k in raiz if k == "action" or k.startswith("action@")]:
            del raiz[k]
        raiz.update({"macnicadefault_subject": ASSUNTO, "macnicadefault_includePageTitle": "true",
                     "macnicadefault_mailto": PARA, "macnicadefault_mailto@TypeHint": "String[]",
                     "successFragmentPath": SUCESSO, "errorFragmentPath": ERRO})
        mc = f"{XF}/master/jcr:content"
        passos = [
            (XF, {"jcr:primaryType": "cq:Page",
                  "jcr:content/jcr:primaryType": "cq:PageContent",
                  "jcr:content/jcr:title": XF_TITULO,
                  "jcr:content/cq:template": "/libs/cq/experience-fragments/components/experiencefragment/template",
                  "jcr:content/sling:resourceType": "cq/experience-fragments/components/experiencefragment"}),
            (f"{XF}/master", {"jcr:primaryType": "cq:Page",
                              "jcr:content/jcr:primaryType": "cq:PageContent",
                              "jcr:content/jcr:title": XF_TITULO,
                              "jcr:content/cq:template": XF_TEMPLATE,
                              "jcr:content/cq:xfMasterVariation": "true",
                              "jcr:content/cq:xfMasterVariation@TypeHint": "Boolean",
                              "jcr:content/cq:xfVariantType": "web",
                              # xfpage, não page: com page o XF embute um 2º documento HTML inteiro
                              "jcr:content/sling:resourceType": "macnicaglobal2/components/xfpage"}),
            (f"{mc}/root", {"jcr:primaryType": "nt:unstructured", "layout": "responsiveGrid",
                            "sling:resourceType": "macnicaglobal2/components/content/container"}),
        ] + [(f"{mc}/root/{rel}", p) for rel, p in nos]
        for path, payload in passos:
            rot = path[len(XF):] or "/"
            resumo = payload.get("jcr:title") or payload.get("name") or payload.get("text", "")[:40]
            print(f"    {gravar(sessao, auth, path, payload, args.executar)}  {rot}  {resumo!r}")
        print(f"    form: assunto {ASSUNTO!r} + título da página; para {PARA}; popups do global2")

    # ---- 2. popups do form inline da página ----
    print(f"\n[2] popups do form inline ({FORM_REL})")
    print(f"    success {form.get('successFragmentPath')}\n    error   {form.get('errorFragmentPath')}")
    if form.get("successFragmentPath") == SUCESSO and form.get("errorFragmentPath") == ERRO:
        print("    = já está")
    elif args.executar and args.carimbo != carimbo:
        print(f"    PULADO: --carimbo {args.carimbo!r} != cq:lastModified atual {carimbo!r}"
              f" (último editor {pag.get('cq:lastModifiedBy')}) — rodar o dry-run de novo e decidir")
    else:
        st = gravar(sessao, auth, f"{PAGINA}/jcr:content/{FORM_REL}",
                    {"successFragmentPath": SUCESSO, "errorFragmentPath": ERRO}, args.executar)
        print(f"    {st}  -> {SUCESSO}\n              {ERRO}")

    # ---- 3. No Padding no container em volta de cada popup ----
    print("\n[3] popups do global2: root/container sem padding")
    for p, j in popups.items():
        no = f"{p}/jcr:content/root/container"
        atual = j["root"]["container"].get("cq:styleIds") or []
        atual = [atual] if isinstance(atual, str) else atual
        if SEM_PADDING in atual:
            print(f"    = já está  {no}")
            continue
        alvo = atual + [SEM_PADDING]
        st = gravar(sessao, auth, no, {"cq:styleIds": alvo, "cq:styleIds@TypeHint": "String[]"},
                    args.executar, allow_extra=(no,))
        print(f"    {st}  {no}  cq:styleIds {atual} -> {alvo}")

    if not args.executar:
        print(f"\n(dry-run — para gravar: --executar --carimbo {carimbo!r})")


if __name__ == "__main__":
    main()
