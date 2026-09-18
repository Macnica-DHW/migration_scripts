# Formulário "Request a Quote or Get in Touch" — o que é preciso para migrar

Pesquisa SOMENTE LEITURA de 18/09/2026 (só GETs). Página:
`/analog-devices/macnica-and-adi`. É o único formulário do nosso escopo (no
GWI há 3 em `semiconductors`: adi, sony e deepx, com o mesmo subject/mailto;
sony e deepx são da Anion).

## Origem (GWI)

```
nó      …/macnica-and-adi/jcr:content/root/container/container/container/
        resizablecontainer_1306610631/container_copy
tipo    macnicagwi/components/content/form/container
        -> sling:resourceSuperType core/wcm/components/form/container/v2   (proxy do Core)
filhos  9 × form/text (core form/text/v2) + 1 × form/button (core form/button/v2)
```

| propriedade | valor |
|---|---|
| `actionType` | `macnicagwi/components/content/form/actions/macnicadefault` — action CUSTOMIZADA ("valida o captcha se ligado e manda todos os valores por e-mail") |
| `subject` | `Macnica and ADI Inquiry` |
| `mailto[]` | `digital@anionmarketing.com`, `marketing.mai@macnica.com`, `Carl.Dahlberg@macnica.com`, `adi-quote.mai@macnica.com` |
| `from` | `cmsadmin@macnica.co.jp` |
| `redirect` | `/content/macnicagwi/americas/mai/en/contact/form` |
| **`successFragmentPath`** | `/content/experience-fragments/macnicagwi/americas/mai/en/site/landingpage_popups/form-success/master1` ("Success / Your request was sent…") |
| **`errorFragmentPath`** | `…/landingpage_popups/form-error/master` ("Error / There was an error submitting…") |

Ou seja: **usa Experience Fragments, sim** — dois, como popups de sucesso e
de erro. Eram os textos "Send message"/"Success" que o comparador de conteúdo
contava como faltando.

Campos (`name` · tipo · obrigatório · placeholder): `fullName` text sim "First
Name" · `lastName` text sim · `company` text sim · `title` text NÃO · `email`
email sim · `phoneNumber` text sim · `City` text sim · `State/Province` text
sim · `Message` textarea rows=4 sim. Rótulo = `jcr:title`. Grade: `width=5`
com `offset` 0/1 (2 colunas); Message `width=11`; botão "Send message"
centrado.

Render: `<form method="POST" action="<a própria página>.html" id="new_form"
data-is-recaptcha-enabled="true" …>` com hidden `:formstart`, `_charset_`,
`:redirect`, `g-recaptcha-response`. JS: jQuery validate → `grecaptcha.execute`
→ POST por ajax → abre o popup do XF. Sem honeypot. O JSP da action não pôde
ser lido (HTTP 403 do filtro de reCAPTCHA).

## Destino (macnicaglobal2) — o equivalente EXISTE

- `/apps/macnicaglobal2/components/form/`: `container`, `text`, `options`,
  `hidden`, `button` (proxies do Core v2) e a action **`macnicadefault`**
  (mesmo nome). Não há `mail`/`rpc`.
- O diálogo do container EXIGE `successFragmentPath` e `errorFragmentPath`.
  Propriedades da action: `macnicadefault_subject` (obrig.),
  `macnicadefault_mailto[]` (obrig.), `macnicadefault_mailcc[]`,
  `macnicadefault_includePageTitle`. Não há campo `from`.
- Em uso no global2: 22 containers com `macnicadefault` (EU 7, APAC 14, DHW
  1). O mais parecido com o nosso: `/content/macnicaglobal2/apac/anstek/zh_tw/
  products-support/products/adi/adi-products-list` (consulta ADI dentro de
  página de produto). Convenção: campos SEM `cq:responsive` (1 coluna) e um
  `text` com o aviso do reCAPTCHA dentro do form.
- **Policy do template `mai-mae-product-page`: PERMITE** `form/container` no
  container do corpo (e a policy "Content Form" permite dentro dele
  text/title/button/hidden/options). A do `flexcontaineritem` NÃO — o form não
  pode ir dentro de coluna.
- MAI no global2: nenhum form real. `/americas/mai/en/request-a-quote` e
  `/en/contact-us` EXISTEM e estão VAZIAS; `/en/contact/form` é 404. Não há
  XF de popup para a MAI (só header e footer).
- **O que a Anion fez nas páginas dela:** `deepx` → trocou o form por título +
  texto + botão "Request a quote" apontando para
  `https://www.macnica.com/americas/mai/en/contact/form/` (o site GWI vivo);
  `macnica-and-sony` → seção removida.

## Caminhos, do mais barato ao mais caro

| | caminho | quem | observação |
|---|---|---|---|
| c | trocar o form por CTA (botão) | motor | precedente da Anion (deepx); o alvo interno está vazio, então hoje só funciona apontando para o GWI vivo. Diverge do GWI |
| **a** | **recriar o form** com `macnicaglobal2/components/form/*` | motor | **recomendado.** Mapeamento mecânico: resourceTypes, `actionType` → `…/form/actions/macnicadefault`, `subject` → `macnicadefault_subject`, `mailto[]` → `macnicadefault_mailto[]`; campos copiam `jcr:title/name/type/required/helpMessage/constraintMessage/rows`; descartar `from`, `redirect`, `action`. Fica irmão do título órfão, fora de `flexcontainer`. 1 coluna (dialeto) |
| a1 | …com os XFs de popup do GWI | motor | custo zero; precedente: EU contact-us e DHW fale-conosco apontam para XFs do macnicagwi. Validar o popup do GWI no CSS do global2 |
| a2 | …com XFs novos em `/content/experience-fragments/macnicaglobal2/americas/mai/en/site/popups` | nós ou Anion | escrita FORA de `semiconductors-remigration` — precisa de um sim |
| b | referenciar um XF de formulário pronto | Anion | não existe nenhum no global2 |
| d | embed/iframe do form GWI | — | frágil, sem precedente; não recomendo |

## Riscos antes de qualquer teste

1. **E-MAIL REAL.** Todo submit de teste dispara para `marketing.mai@`,
   `Carl.Dahlberg@`, `adi-quote.mai@` e `digital@anionmarketing.com`. Não
   testar envio sem combinar; confirmar se a lista ainda vale.
2. **reCAPTCHA vem de context-aware config** (`/conf/macnicaglobal2/americas/
   mai`, `enableRecaptcha=true`). `/content/copia-teste` é `sling:Folder` sem
   `sling:configRef`: na copia-teste o form pode renderizar sem site key e o
   backend recusar. O comportamento fiel só aparece na árvore final.
3. O backend (servlet/SMTP) não pôde ser lido; funciona em produção em
   EU/APAC/DHW, mas nenhuma página MAI do global2 está publicada.
4. **Decisão de produto:** a Anion NÃO migrou o form em deepx/sony. Vale
   confirmar se a diretriz da MAI é form ou CTA antes de gastar regra no
   motor — no escopo só esta página tem form.
5. Para o time AEM: `/conf/macnicaglobal2/sling:configs/…CaptchaConfig` expõe
   `recaptchaSecretKey` em claro a qualquer usuário do author.

Hoje, na página migrada: o form vira pendência `tipo_nao_reconhecido`, o
título "Request a Quote or Get in Touch" fica órfão no rodapé e os 3 botões
`#contact-form` rolam até ele.
