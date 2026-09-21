# Plano de go-live — `semiconductors-remigration` → `macnicaglobal2/.../semiconductors`

Levantado em 21/09/2026, 13:15–13:45 (BRT), **somente leitura**. Nada foi gravado no AEM.
Scripts em `ferramentas/golive/` e `ferramentas/censo_links*.py`; dados em `dados/golive/` e `dados/links/`.

    origem   /content/copia-teste/americas/mai/en/products/semiconductors-remigration   (T)
    destino  /content/macnicaglobal2/americas/mai/en/products/semiconductors            (G)

---

## 0. O que trava (ler antes do resto)

1. **A Anion está migrando à mão, no destino, as mesmas famílias — AGORA.** `venkatesh`, `mahendra`,
   `taj` e `saichand` (`@anionmarketing.com`) fizeram a `canon` em 18–19/09 e estão no meio da
   `design-gateway` hoje: última gravação às 16:14 GMT, durante este levantamento; 6 páginas ainda são
   casca vazia. **35 páginas nossas já têm homônima lá** (14 canon + 21 design-gateway; lista em
   `dados/golive/colisoes.csv`). O texto é ~97% igual ao nosso — as duas vêm do mesmo GWI.
   As outras 14 famílias nossas (90 páginas sem as de teste) estão livres **hoje**; eles seguem uma
   ordem e podem abrir a próxima a qualquer momento. → Falar com a Anion antes de qualquer cópia.
2. **Não sabemos se o nosso usuário grava no global2.** O cookie é `valter.toffolo`; os grupos dele são
   `macnicagwi-mai-authors`, `content-authors`, `dam-users`… — nenhum de global2. O endpoint
   `privileges-info` está desligado (HTTP 400), então só dá para saber gravando. → Pré-voo (fase 1).
3. **Trocar prefixo não resolve os links** — o global2 tem outra árvore de páginas, outro desenho de DAM
   e nenhuma pasta de XF de site. Precisa de mapa (seção 3).

---

## 1. Estado medido

| | origem (T) | destino (G) |
|---|---|---|
| páginas | 135 + landing; 4.307 nós | 252 + landing |
| famílias | 16 das 18 do GWI (todas menos `sony` e `deepx`) | `sony` 213, `deepx` 1, `canon` 14, `design-gateway` 22, `Titles`, `sony-test` |
| template | `mai-mae-product-page` (135/135) | o mesmo nas 250 páginas de produto |
| publicadas | 0 | 0 |
| edição manual no editor (`jcr:lastModified` no nó) | **0 nós** — o servidor é exatamente a saída dos scripts | — |
| `cq:canonicalUrl`, `sling:vanityPath`, mixins de live copy | nenhum | — |
| tags | namespace `mai:` (42 páginas) | o mesmo `mai:` → **não reescrever** |
| XF embutido | 109 páginas → 4 XFs em `experience-fragments/copia-teste/.../site` | **nenhuma** página do `americas/mai/en` embute XF; só existem `header` e `footer`. A Anion usa botão inline |
| landing | `mai-mae-product-page`, 7 nós | `mai-page-content`, editada pelo `saichand` hoje 10:33 GMT |

De teste, fora da cópia: `/ambarella/test-277-gwi-base-page`, `test-277-product-detail-page`,
`test-autogenerate-list-ambarella-n1-soc-html`, `test-fixed-list-ambarella-n1-soc` (nada aponta para elas).
`canon-li8020sa-250mp-cmos-sensor-0` **não** é duplicata: é o nome do GWI (a Anion tem a mesma).

### Referências gravadas hoje (810; nenhuma quebrada)

| aponta para | refs | o que é | destino |
|---|---|---|---|
| página global2 | 165 | href de `text` (151, com `.html` — R44, certo) e `linkURL` (14) | 98 de 106 alvos passam a existir com a cópia; **8 não** (3.3) |
| página da copia-teste | 139 | `pages` de `list` (R5, proposital) | reescrever para G |
| XF copia-teste | 111 | `fragmentVariationPath` 109 + `successFragmentPath`/`errorFragmentPath` | XF novo no global2 (3.2) |
| DAM copia-teste | 325 (259 assets) | `fileReference`, href de download | copiar + reescrever (3.1) |
| DAM **do GWI** | 33 (30 assets) | HTML cru em 7 páginas: 18 `<img src>` em tabela, 13 downloads da `altera-soc-courses`, 2 `linkURL` da `/toppan…` | copiar + reescrever (3.1) |
| página do GWI | 3 | `linkURL` dos botões, **dentro dos 2 XFs de contato** | `/contact-us` e `/request-a-quote` |

---

## 2. Decisões do Hazael (com a recomendação)

| # | decisão | recomendação |
|---|---|---|
| D1 | `canon` e `design-gateway`: fica a da Anion, entra a nossa, ou página a página? | **Não copiar as duas até falar com a Anion.** Nunca sobrescrever: a cópia aborta se o destino existe. Se a nossa entrar, é com o ok deles, eles parados, e backup do que é deles |
| D2 | Combinar com a Anion quem faz as 14 famílias restantes | Pedir que **não abram** família nova; nós entregamos as 14 |
| D3 | Landing `/semiconductors` | **Não copiar** — a da Anion está viva e foi editada hoje |
| D4 | Bloco de contato: XF no global2 ou botão inline como a Anion | **XF** em `experience-fragments/macnicaglobal2/americas/mai/en/site/` — 1 lugar para manter, 109 páginas, é o que foi revisado. A pasta raiz de XF do global2 já permite o template `xf-web-variation`. Confirmar com a Anion |
| D5 | Desenho do DAM | Adotar o da Anion: `dam/macnicaglobal2/americas/mai/en/products/semiconductors/<família>/{images,pdfs,logos,downloads}/`, nome em minúscula-com-hífen (144 de 289 mudam de nome). Proposta pronta em `dados/golive/mapa_assets.csv` |
| D6 | As 2 páginas de `ip-software` que não existem (`v-by-oner-hs-ip` 5 links, `munvme-ip-core` 1) | Apontar para `G/../ip-software` (existe) até alguém criá-las |
| D7 | Quem executa a gravação no global2 | Pré-voo com o nosso cookie; se negar, a mesma ferramenta roda com o cookie de quem tem direito |

---

## 3. Mapa de reescrita

### 3.1 Assets — 289 distintos (189 das famílias livres, 100 de canon+design-gateway)
- 288 são usados por **uma** família só → caem na pasta da família. O único compartilhado é
  `macnica-workflow-diagram.jpg` (6 famílias) → `…/semiconductors/common/images/`.
- 29 têm arquivo de mesmo nome já no DAM do global2, mas 21 são de canon/design-gateway e os outros estão
  em `eu/` ou `apac/` — **não reaproveitar asset de outra região**; copiar o nosso.
- **14 destinos recebem 2 origens** depois de normalizar o nome (ex.: `banners/IP00C755.png` e
  `images/products/ip00C755.png` → `i-chips/images/ip00c755.png`). Na execução: comparar `dam:sha1`;
  igual → um asset só; diferente → sufixo `-2`. Nunca decidir pelo nome.
- Origem dupla: 259 vêm de `dam/copia-teste`, 30 de `dam/macnicagwi` (estes em HTML cru de `text`, com
  `%20` — decodificar antes de comparar; o regex tem que pegar `src=` e `href=`).
- Cópia servidor-a-servidor (`:operation=copy`), sem baixar nada. Esperar `dam:assetState=processed`
  antes de conferir.

### 3.2 XFs — 4
`products-contact-block` (105 páginas), `signup-and-contact-experience-fragment` (4), `popups/form-success`
e `popups/form-error` (1 página: `macnica-and-adi`). Copiar para `…/macnicaglobal2/americas/mai/en/site/`.
Na cópia: `linkURL` dos botões → `G/../contact-us` e `G/../request-a-quote` (é o que a Anion usa;
`/contact/form` dá 404 no global2); `sling:resourceType` do `jcr:content` `page` → `xfpage` (é o que o
`footer` do global2 tem).

### 3.3 Alvos de página que a cópia NÃO cria
| gravado hoje | refs | vira |
|---|---|---|
| `<mai/en>/contact/form` | 10 | `<mai/en>/contact-us` |
| `/content/macnicaglobal2/europe/atd-europe/en` | 1 | `/content/macnicaglobal2/eu/atd-europe/en` |
| `G/sony-image-sensors/sony-imx811-aamr` (landing) | 1 | `G/sony/sony-image-sensors/sony-imx811-aamr` — só importa se a landing for copiada (D3) |
| `<mai/en>/products/ip-software/{v-by-oner-hs-ip,munvme-ip-core}` | 6 | D6 |
| `<mai/en>/request-a-quote`, `/products/boards-modules/terasic`, `/services/automotive` | 6 | já existem — nada |

### 3.4 Troca simples de prefixo
`pages` de `list`: `T/…` → `G/…` (139). Externos (33), âncoras, tags: não tocar.

---

## 4. Fases — cada uma só começa com a anterior conferida

**Princípio: reescrever numa cópia DENTRO da copia-teste e só então copiar para o global2.** O global2
recebe páginas já prontas, numa janela curta, e nunca fica com página pela metade; a árvore revisada
(`semiconductors-remigration`) não é tocada e continua sendo a referência.

| fase | o que | onde grava | portão |
|---|---|---|---|
| 0 | Falar com a Anion (D1–D4). Congelar T: nenhum lote mais; tag git `revisado-2026-09-21` | — | decisões fechadas |
| 1 | Pré-voo de permissão: criar e apagar 1 nó de rascunho em G, no DAM e na pasta de XF do global2 | global2 (3 nós, apagados em seguida) — **pede ok explícito** | 3× criado + apagado |
| 2 | Staging: `:operation=copy` de T → `copia-teste/.../semiconductors-golive`, sem as 4 de teste, sem landing, sem as famílias de D1 | copia-teste | nº de páginas e de nós bate com T |
| 3 | Assets: copiar conforme `mapa_assets.csv`; manifesto do que foi criado | DAM global2 (só pastas/arquivos **novos**) | todo destino 200 e `processed`; sha1 = origem |
| 4 | XFs: copiar os 4 + ajustes de 3.2 | XF global2 (pasta `site` nova) | renderizam a 1400px iguais aos da copia-teste |
| 5 | Reescrita no staging, por tabela (3.1–3.4), dry-run por padrão, log `nó · propriedade · antes · depois`, idempotente | copia-teste | dry-run revisto; 2ª execução = 0 mudanças |
| 6 | Conferir o staging: `censo_links.py` na raiz do staging → **0** refs a `copia-teste`, `macnicagwi`, `dam/copia-teste`, `dam/macnicagwi`; todo alvo existe no global2 **ou** está na lista de páginas a criar; imagens carregam (`naturalWidth>0` depois de rolar) e XF aparece, a 1400px. As `list` saem vazias aqui — é esperado, o alvo ainda não existe | — | zero pendência |
| 7 | Cópia final, família a família: `:operation=copy` staging/`<fam>` → G/`<fam>`. **Aborta se o destino existe; nunca `:replace`.** Ordenar as irmãs como no GWI. Janela combinada com a Anion | global2 (14 nós de família novos) | 90 páginas criadas |
| 8 | Conferir em G: censo (todo alvo interno 200, 0 refs para fora); `list` com itens; `ancoras.py`; `alt_faltando --todas` e `serie_twi --todas` = 0; print T × G das 90 (`aem_fidelidade_render`/`prints.sh`) sem diferença; form da `macnica-and-adi` abre os popups; nada publicado | — | relatório |
| 9 | Entrega: manifesto de tudo que criamos (páginas, assets, XFs). **Publicar não é nosso** | — | — |

Ferramentas a escrever (nenhuma existe ainda): `golive/copiar_assets.py`, `golive/copiar_xfs.py`,
`golive/reescrever_refs.py`, `golive/copiar_familias.py`; e parametrizar a raiz do `censo_links.py`.
Todas com dry-run por padrão. A trava `assert_target_is_safe` continua valendo: escrita no global2 só
com `--permitir-escrita-global2 <caminho exato>`, como o `aem_clone_subtree.py` já faz.

Por que cópia servidor-a-servidor e não o motor apontado para o global2: o que foi revisado é o que está
no servidor. `:operation=copy` leva isso byte a byte (tipos, ordem, o fundo da `/ambarella`, que está fora
do motor); regenerar depende de o GWI não ter mudado e refaz 53 regras num lugar onde não dá para errar.

## 5. Desfazer
Só criamos nó novo — nunca sobrescrevemos. Desfazer = apagar o que está no manifesto (14 famílias, as
pastas novas do DAM, a pasta `site` de XF). O staging e T ficam intactos. Se D1 decidir por substituir
página da Anion, isso muda: backup do que é deles (`aem_backup_subtree.py`) antes, e ok deles por escrito.

## 6. Riscos
- **Anion gravando em paralelo** no mesmo ramo: reconferir `inventario.py` imediatamente antes da fase 7.
- **Cookie de ~8h** (hoje: 07:21 → ~15:20). Fases 3 e 7 começam com cookie novo.
- **Launchers de workflow** na criação de página/asset no global2: desconhecido; o pré-voo mostra.
- **Copiar asset dispara reprocessamento**: conferir só depois de `processed`.
- **Nome de nó**: os nossos são minúsculos (`canon-li8030sa-…`), a Anion manteve o do GWI (`…li8030SA…`);
  só aparece nas famílias em colisão, mas muda a URL pública — entra na conversa de D1.
- **Depois do go-live** o motor continua apontado para a copia-teste: correção futura tem que ser
  repetida no global2 (ou a ferramenta passa a aceitar a raiz como parâmetro).
- Links de OUTRAS áreas do global2 para dentro de `/semiconductors` não foram levantados.
