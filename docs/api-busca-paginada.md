# Busca paginada ("Ver mais") e como a tela deve chamar

A tela ainda usa `/buscar/stream`. Este documento descreve o jeito novo, igual ao da OLX, para quando a gente ligar o "Ver mais". Nada aqui exige mudar o stream.

## Endpoints

| Endpoint | Para que serve |
|---|---|
| `GET /buscar/pagina` | Uma página por vez, para o "Ver mais". Novo |
| `GET /buscar/stream` | Várias páginas de uma vez por SSE (até 8). Continua igual |
| `GET /buscar` | O mesmo do stream em um JSON só. Continua igual |
| `GET /anuncio/detalhe` | Lê a página daquele anúncio na OLX ao abrir o Garimpar (ficha, opcionais, localização e descrição) |

Os três usam os mesmos parâmetros de busca (`texto`, que pode vir vazio, veja "Busca sem texto", `marca`, `modelo`, `versao`, `ano_min`, `ano_max`, `preco_min`, `preco_max`, `km_min`, `km_max`, `cambio`, `combustivel`, `anunciante`, `ordenar`, `estado`, `regiao`, `cidade`, `dev`, `atualizar`) e **a mesma sessão de busca no servidor**. Página lida por um deles serve para os outros, e o servidor nunca baixa de novo da OLX uma página que já tem.

## Como a tela chama o "Ver mais"

1. **Primeira vez:** `GET /buscar/pagina?texto=fiat argo&estado=MG&pagina=1`. Sai em poucos segundos (a página 1 não tem pausa).
2. Mostre `anuncios`, a frase `informacao` e, se `tem_mais` for `true`, o botão "Ver mais".
3. **No clique:** repita a **mesma** busca com `pagina=<proxima_pagina>` da resposta anterior. Não calcule o número na tela, use o que o servidor mandou.
4. Se `tem_mais` for `false`, esconda o botão. A frase `informacao` já explica o motivo.
5. **Buscar de novo ignorando o cache:** só na página 1, `atualizar=1`. Não mande `atualizar=1` nas páginas seguintes, senão a busca recomeça.
6. Se vier **uma busca nova** (outro texto ou outro filtro), volte para a página 1 e jogue a lista antiga fora.

A tela pode juntar as páginas numa lista só, anexando `anuncios` de cada resposta. Anúncio repetido entre páginas o servidor já tira.

## Resposta de `/buscar/pagina`

| Campo | O que é |
|---|---|
| `pagina` | A página pedida |
| `anuncios` | Os carros dessa página (já filtrados, sem item cru e sem dado de anunciante) |
| `tem_mais` | `true` se ainda dá para pedir mais |
| `proxima_pagina` | O número a pedir no próximo clique, ou `null`. Se a leitura falhou, é a mesma página, para tentar de novo |
| `entregues` | Quantos carros a pessoa já recebeu somando as páginas até aqui |
| `coletados` | Quantos anúncios vieram da OLX até aqui, antes dos filtros daqui |
| `total_na_fonte` | O total que a OLX informa para a busca (é o mesmo "de 1.413 resultados" do site) |
| `informacao` | Frase pronta para a tela, no tom do Garimpo Auto |
| `avisos` | Avisos de verdade (ex.: filtro que a OLX não entendeu, falha). `detalhe_tecnico` só com `dev=1` |
| `falhou` | `true` se essa página não veio (bloqueio ou erro). Nada é perdido: as anteriores continuam guardadas |
| `motivo_parada` | Preenchido quando a busca acabou: `acabaram_paginas` ou `teto_paginas` |
| `filtros_na_origem`, `filtros_locais` | Onde cada filtro foi aplicado (na OLX ou depois da coleta) |
| `busca`, `estado_aplicado` | O que foi aplicado de fato (estado "todos" quando é Brasil todo) |
| `coletado_em`, `do_cache` | Hora em que essa página foi lida e se veio guardada |
| `novos` | Quantos dos carros entregues até aqui são novos desde a última busca igual |
| `primeira_busca` | `true` se nunca houve busca igual antes (aí ninguém é novo). `null` se o servidor está sem banco |

Cada carro em `anuncios` traz também `novo` (`true` ou `false`). `/buscar` e o `fim` do stream trazem `novos` e `primeira_busca`, e cada evento `pagina` do stream traz `novos`.

A busca não traz FIPE. Ela chega só no Garimpar, junto com a página do anúncio (veja abaixo).

### Página do anúncio no Garimpar

`GET /anuncio/detalhe?fonte=olx&id=<external_id>&url=<url do anúncio>` lê **só aquele anúncio**, e só
quando a pessoa abre o Garimpar. Nenhuma busca pede detalhe de anúncio.

- O `url` precisa ser https da OLX e terminar no mesmo `id`. Query e âncora são descartadas. Qualquer
  outro endereço volta 422 sem pedido à OLX.
- A página traz o JSON `initial-data`. O servidor confere que o `listId` dele é o `id` pedido.
- Resposta: `source`, `external_id`, `url`, `detalhes` (categoria, modelo, marca, tipo, ano, km, potencia,
  combustivel, cambio, direcao, cor, portas, final_placa, kit_gnv), `opcionais`, `outras` (aceita trocas,
  IPVA pago, único dono e o que mais vier marcado como Sim), `localizacao` (bairro, cidade, estado, cep),
  `descricao`, `referencia_preco`, `coletado_em` e `do_cache`. Campo que o anúncio não tem vem `null` ou lista vazia.
- `referencia_preco` é o quadro "Referência de preço" da OLX (`abuyFipePrice` e `abuyPriceRef` do
  `initial-data`): `preco_anuncio`, `fipe`, `media_olx`, `menor`, `corte_baixo`, `corte_alto`, `maior`,
  `carros` e `mes_referencia` (`"2026-09"`). Vem `null` quando a OLX não mostra FIPE nem média. Detalhes em
  [fipe.md](fipe.md).
- Telefone e e-mail escritos na descrição viram "(contato no anúncio original)". Nome e contato do
  anunciante nunca são lidos.
- Bloqueio ou falha de rede repetem uma vez, com a mesma espera do "Ver mais". Se ainda falhar, volta
  503 com `erro` pronto para a tela. Anúncio removido (404 ou 410) volta 404 sem repetir.
- O resultado fica guardado em memória por 20 minutos (`CACHE_TTL_SEGUNDOS`). Falha não é guardada,
  então "Tentar de novo" lê de novo. Pedidos simultâneos do mesmo anúncio fazem uma leitura só.

No Garimpar, **Buscar carros iguais** abre uma busca por marca, modelo e ano do anúncio. Estado,
região, zona e cidade são preservados. Versão, preço, km, câmbio, combustível e tipo de anunciante
saem do pedido para não enfraquecer a amostra usada pela mediana.

### Frases de `informacao`
- Tem mais: "Mostrando 50 de 1.413 carros. Toca em Ver mais pra ver o resto."
- Acabou: "Achei 80 carros. Esses são todos."
- Acabou, mas a OLX contava mais do que entregou: "Achei 1.360 carros. A OLX fala em 1.413, mas só mostra esses." (usa quando o total da OLX passa do que veio por mais de 1%, e no mínimo 3 anúncios)
- Parou no teto de páginas: "Mostrei 1.500 de 28.839 carros. Essa busca é grande demais pra mostrar tudo, refina por ano ou preço pra ver os outros."
- Filtros daqui tiraram carros: acrescenta "Alguns ficaram de fora dos filtros que você pôs."
- Falha: "Não consegui buscar mais agora, tenta de novo daqui a pouco?" (ou "Não achei esse carro agora, tenta de novo?" se foi na página 1)
- Sem nada: "Não achei nenhum carro com esses filtros. Que tal afrouxar algum?"

## Tempo, pausa e cache
- **Página 1:** sem pausa. Se a busca tem marca ou modelo, o servidor consulta as listas de códigos da OLX antes (uma vez por marca, guardada por 12 h), também sem pausa.
- **Da página 2 em diante:** o servidor garante uma pausa de 2 a 4 s (`GARIMPO_PAUSA_VER_MAIS_SEGUNDOS`) desde a última leitura **da mesma busca**, descontando o tempo que a pessoa já levou para clicar. Quem demora mais que a pausa não espera nada. Quem clica rápido espera só o que falta.
- **Cache:** por página, e a sessão inteira vale 20 minutos (`CACHE_TTL_SEGUNDOS`), contados a partir da hora da página 1. Pedir uma página já lida volta na hora. A chave considera texto, filtros, estado e ordenação. Com o banco ligado ele é compartilhado e sobrevive a reinício (veja a seção abaixo).
- **Teto:** o "Ver mais" vai até `GARIMPO_MAX_PAGINAS_SOB_DEMANDA` páginas por busca (padrão 70, veja os testes de confiança abaixo).
- **Fila:** só uma leitura real da OLX por vez no servidor. Uma busca nunca fica travada na pausa de outra, porque a pausa acontece antes de entrar na fila.

## Busca sem texto (a vitrine)

A tela abre mostrando uma vitrine, igual à OLX: `GET /buscar/pagina?texto=&estado=MG&pagina=1`.

- **`texto` pode vir vazio, mas o parâmetro continua obrigatório.** `texto=` vale. Esquecer o parâmetro continua dando 422. Espaços sozinhos contam como vazio. Vale nos três endpoints (`/buscar/pagina`, `/buscar/stream` e `/buscar`).
- **Na OLX:** sem texto o servidor não manda `q`, e a OLX lista a categoria de carros do estado, por exemplo `.../carros-vans-e-utilitarios/estado-mg?sf=1`. Conferido com uma chamada real em 10 de outubro de 2026: 50 carros, todos de MG, total 73.619. A resposta salva está em `scraper/tests/fixtures/olx_vitrine_mg.json`.
- **Frase de `informacao`:** a de sempre, "Mostrando 50 de 73.619 carros. Toca em Ver mais pra ver o resto."
- **Cache e "novo desde a última vez":** a busca vazia é uma busca como outra qualquer. A chave fica `texto=|estado=mg|ordenar=recentes`, não divide cache com busca de texto nem com outro filtro, e tem o próprio histórico de novos.
- **Filtro sem texto:** com filtro e sem texto, a busca usa o filtro (`texto=&ano_min=2018` pede só o ano). A vitrine pura é só sem texto e sem filtro.
- **Na tela:** a vitrine carrega uma vez ao abrir, só a página 1. O "Ver mais" continua manual. Buscar com o campo vazio e sem filtro volta para ela. Uma busca nova no meio da carga cancela a vitrine, como qualquer outra busca em andamento.
- **O que não tem:** a vitrine não separa usados, seminovos e novos, porque o anúncio não traz campo de condição.

## Região e cidade (filtradas na própria OLX)

A OLX aceita região e cidade na URL, no caminho `estado-xx/região/zona/cidade`. O servidor monta esse caminho sozinho.

- **Seletor de região da tela:** `GET /regioes?estado=MG` devolve `{"estado": "MG", "regioes": [{"slug": "belo-horizonte-e-regiao", "nome": "Belo Horizonte e região"}, ...]}`. Mande o `slug` no parâmetro `regiao` das buscas. Sem `estado`, usa o padrão do servidor. Os 27 estados têm lista (67 regiões no total, Minas tem 7).
- **`regiao`:** aceita o `slug` ou o nome (sem acento também). Se a região não existe naquele estado, o servidor responde 422 com "Não achei essa região nesse estado, escolhe uma da lista?". Isso importa porque a OLX, com região errada na URL, **devolve o Brasil todo sem avisar**.
- **`cidade`:** se a OLX tem página da cidade, o filtro vai na URL e já chega filtrado: `total_na_fonte`, `informacao` e a paginação são os da cidade (ex.: Contagem, 239 anúncios de "fiat argo"). `filtros_na_origem` traz `"cidade"`.
- **Cidade sem página na OLX:** vale o filtro depois da coleta e vem o aviso `filtro_aproximado` ("Não achei a cidade X na lista da OLX, então filtrei por aqui. Pode ter ficado algum carro de fora."), com `filtros_locais` trazendo `"cidade"`. Se a pessoa escolheu uma região, a busca já vem restrita a ela.
- **Quem não tem página própria:** a OLX só tem página para parte das cidades (em MG, 154 locais de uns 850 municípios). **Belo Horizonte não é uma página só**: a capital é dividida em 9 zonas (Barreiro, Centro-Sul, Leste, Nordeste, Noroeste, Norte, Oeste, Pampulha e Venda Nova).
- **Sem estado** ("Brasil todo") não dá para procurar a cidade na lista, então ela segue filtrada depois da coleta, sem aviso. `filtros_locais` mostra isso.

### Zona (entre a região e a cidade)

A zona é uma divisão da região, e a OLX a aceita no caminho: `estado-mg/belo-horizonte-e-regiao/barreiro`. Belo Horizonte, por exemplo, é dividida em 9 zonas (Barreiro, Pampulha, Venda Nova, Centro-Sul, Leste, Nordeste, Noroeste, Norte e Oeste), e cada uma tem só anúncios da capital.

- **Seletor:** `GET /zonas?estado=MG&regiao=belo-horizonte-e-regiao` devolve `{"estado", "regiao", "zonas": [{"slug", "nome"}, ...]}`. A região é obrigatória (sem ela, 422 com "Pra escolher a zona, escolhe a região primeiro."). Região sem zonas devolve lista vazia. Os nomes com acento estão coletados para Minas. Nos outros estados o nome sai do endereço (às vezes sem acento) até rodar `gerar_localidades.py --zonas UF`.
- **`zona`:** parâmetro novo de `/buscar`, `/buscar/pagina` e `/buscar/stream`. Aceita o `slug` ou o nome da zona. Só vale junto com `regiao`. Zona sem região dá 422 com a mesma frase acima. Zona que não existe naquela região dá 422 com "Não achei essa zona, escolhe uma da lista?" e a busca nem começa.
- **Só MG tem as zonas conferidas.** Em Minas (`zonas_conferidas` no `localidades.json`) o seletor mostra só as zonas que a OLX serve de verdade e com o nome certo. **Os outros estados usam a lista crua do sitemap**, que traz zonas que a OLX responde com o Brasil todo e nomes às vezes sem acento. Isso só muda quando alguém roda `gerar_localidades.py --zonas UF` para aquele estado. Até lá, em outro estado, uma zona da lista pode não existir de verdade. A proteção da primeira página (abaixo) evita carro de outro estado na lista, mas a busca recua para a região e avisa com `filtro_aproximado`.
- **Com zona:** o `total_na_fonte`, a frase `informacao` e a paginação são os da zona, e `filtros_na_origem` traz `"zona"` junto de `"regiao"`.
- **Só entram zonas que a OLX serve.** O sitemap lista zonas que a OLX responde com o **Brasil todo**. Em Minas, só a região de BH tem zonas de verdade (14 de 37, mais Manhuaçu em Governador Valadares), e as outras 22 ficam fora da lista. Nos demais estados as zonas ainda são as do sitemap, até rodar `gerar_localidades.py --zonas UF`.
- **Proteção na primeira página:** quando a busca tem região, zona ou cidade, o servidor confere o estado dos anúncios que chegaram. Se vier outro estado, a OLX não conhecia o local e respondeu o Brasil todo. O servidor recua um nível (cidade, depois zona, depois região), pede de novo, volta a filtrar aquele nível depois da coleta e avisa com o `filtro_aproximado` ("Não achei a zona X na lista da OLX..."). Nenhum anúncio de outro estado chega na lista.
- **Zona e cidade juntas:** se a cidade fica nessa zona, vai até a cidade. Se não, a zona manda e a cidade é filtrada depois da coleta.
- **`/buscar/pagina` e o cache:** zona entra na chave, e escrever a zona de outro jeito ("Zona Centro Sul" ou `zona-centro-sul`) cai no mesmo cache.

A lista de locais vem de `scraper/dados_olx/localidades.json`, gerada por `gerar_localidades.py` a partir dos sitemaps da OLX (rodar de vez em quando).

### Exemplo real (fiat argo, MG, cidade Contagem)
- **Antes** (filtro depois da coleta): a OLX devolvia 399 de 1.407 carros do estado (8 páginas) e **sobravam 66 de Contagem**.
- **Agora** (cidade na URL): a OLX diz que tem 239 e entregou **233, todos de Contagem**.
- O filtro de depois mostrava 28% do que existia.

## O que acontece quando a lista da OLX muda no meio
Entre uma página e outra, anúncios novos entram no topo e empurram a lista. Resultado:
- **Repetição:** coberta. O mesmo `listId` que reaparece na página seguinte é descartado, e o mesmo carro anunciado de novo por outra loja vem marcado em `repetido_de` (e não some).
- **Omissão:** não coberta. Se um anúncio é renovado e sobe para uma página que a pessoa já passou, ele não aparece nessa sessão. Também pode escapar um anúncio quando outro sai do ar e a lista anda para cima. É raro e some ao usar `atualizar=1`, que recomeça a busca na hora.
- Uma página que só traz repetidos encerra a busca, com o aviso "A página só tinha anúncios repetidos".

## Banco de dados e "novo desde a última vez"

O cache de busca fica num banco, compartilhado entre os usuários, e sobrevive a reinício. Como subir, as tabelas, as regras da empresa e as migrations estão em [banco.md](banco.md). Aqui só o que a tela sente.

- **Cache de todos:** `do_cache: true` aparece mais, porque a busca de uma pessoa serve para as outras por 20 minutos. `atualizar=1` troca a busca para todos.
- **`novo`:** cada carro traz `true` ou `false`. Vale "não apareceu em busca igual anterior e foi anunciado depois dela". A regra completa está em [banco.md](banco.md#decisões-tomadas).
- **`primeira_busca`:** `true` quando nunca houve busca igual antes (ninguém é novo). `null` quando o servidor está sem banco. A tela deve tratar `null` como "não sei" e não mostrar selo de novo.
- **Valor fixo:** ler a mesma página de novo, ou depois de um reinício, dá a mesma resposta de `novo`.
- **Banco fora do ar:** a busca continua normal, só em memória. Não vem erro, mas `primeira_busca` vem `null` e `novos` vem 0.

## Quando a OLX falha no meio
Falha é 403, 429, 500, captcha, página sem os dados, JSON fora do formato, timeout ou rede que caiu. Em todos os casos a resposta é a mesma.
- **`falhou: true`**, sem anúncios nessa página. As páginas já lidas ficam guardadas e contam em `entregues`.
- **`proxima_pagina`** é a mesma página que falhou. A tela pede de novo e o servidor tenta ela outra vez.
- **Texto:** "Não consegui buscar mais agora, tenta de novo daqui a pouco?" (da página 2 em diante) ou "Não achei esse carro agora, tenta de novo?" (na página 1). O motivo técnico só vem com `dev=1`.
- **Repetição no "Ver mais" (página 2 em diante):** 1 repetição só, depois de 5 a 10 segundos. Muda com `GARIMPO_REPETICOES_VER_MAIS` e `GARIMPO_ESPERA_REPETICAO_VER_MAIS_SEGUNDOS`.
- **Página 1 e `/buscar/stream`:** 2 repetições, com espera crescente (cerca de 20 e 40 segundos).
- **Lista parcial nunca passa por completa.** Em `/buscar` e no stream o `fim` traz `falha_fonte` e o aviso "A OLX não respondeu direito no meio da busca, então a lista pode estar incompleta."

### Página vazia no meio
A OLX lista de 92% a 96% do que conta. Por isso página vazia não é sempre o fim.
- **Abaixo de 80% do total lido:** conta como falha e dá pra tentar de novo.
- **Segunda vez vazia na mesma página:** encerra a busca, com a frase "Achei N carros. A OLX fala em X, mas só mostra esses."
- **Busca sem nenhum carro** (total 0) continua sendo vazia de verdade, sem falha.

### Anúncio fora do formato
Um anúncio só é marcado como visto depois da página inteira ser lida. Se um deles quebrar a leitura, a nova tentativa não perde os que vieram antes dele.

## E o `/buscar/stream`?
Continua igual para a tela de hoje (eventos `pagina`, `fim` e `erro`, mesmos campos). Por dentro agora ele lê as páginas da mesma sessão que o "Ver mais". Duas diferenças boas: se a pessoa fecha a tela ou cancela, o servidor para de ler (antes a coleta ia até o fim), e a falha no meio guarda as páginas boas e a busca seguinte continua de onde parou.

## Teste de paginação na OLX real (10 de outubro de 2026)
Busca "fiat argo" em MG, mais recentes, páginas 1 a 30 com a pausa normal, sem repetir tentativa.
- **Nenhum bloqueio.** Todas as 29 páginas pedidas vieram com status 200.
- **A OLX entregou 28 páginas.** 27 cheias (50 por página, algumas com 49 por causa de repetido), a 28ª com 14, e a 29ª vazia. Total listado: **1.360 carros**.
- **O total da OLX fica um pouco acima do que ela lista:** 1.411 a 1.413 no fim, contra 1.360 listados (cerca de 3,6% a menos). Não sei explicar a diferença. Pode ser anúncio que sai do ar durante a leitura ou item contado e não listado. O total oscilou entre 1.411 e 1.413 durante a leitura.
- **Total confere com o site:** a página 1 mostra "1 - 50 de 1.413 resultados" no texto, e nós lemos `totalOfAds` 1.413.
- **Repetido por lista deslocada apareceu de verdade:** 5 páginas vieram com 49 novos em vez de 50 (um anúncio já visto reapareceu), e o tratamento por `listId` descartou todos.
- **Teto da OLX:** não apareceu nenhum nesta busca, porque a lista acabou antes (página 28). Veja os testes de confiança abaixo para buscas gigantes.
- **Ajuste feito por causa do teste:** página menor que a 1ª agora conta como a última, em vez de gastar uma leitura extra para descobrir.

## Tempos medidos (OLX real)
- Página 1: cerca de 2 s (1,8 s no teste pelo servidor).
- Página já lida: cerca de 20 ms.
- Página 2 clicada logo depois da 1: cerca de 8 s (a pausa valendo, na época ainda de 6 a 14 s, hoje de 2 a 4 s).

## Testes de confiança (10 de outubro de 2026)

### 1. Os dados batem com o anúncio no site?
Sim. Peguei 10 anúncios da página 1 de "fiat argo" em MG e abri a página de cada um. Em **10 de 10** bateram id, preço, ano, km e cidade. O MCP de detalhe da OLX não serve para essa conferência (devolve o valor da parcela como se fosse o preço e não traz ano nem km), então a conferência foi feita lendo a própria página do anúncio.

### 2. De onde vem a diferença entre o total da OLX e o que ela lista?
Não é culpa da coleta. A OLX **conta mais anúncios do que entrega** nas páginas, e isso aparece sempre que a busca é grande:

| Busca (MG) | Total que a OLX diz | Listados até a página vazia |
|---|---|---|
| fiat argo, tudo | 1.411 a 1.413 | 1.360 (96,4%) |
| fiat argo, ano 2026 | 404 | 394 |
| fiat argo, ano 2025 | 425 | 390 (a página 8 veio com 40 e a 9 vazia) |
| fiat argo, 2023, 2022, 2021, 2020, 2019, 2018 | 139, 92, 73, 76, 41, 50 | todos |
| onix, tudo | 3.357 | 3.237 (96,4%) |

- Buscas pequenas (até cerca de 140 resultados) listam tudo. Nas grandes sobram uns 3% a 8%.
- Cortar a busca em fatias por ano não recupera quase nada (a soma das fatias listou 1.366 contra 1.360).
- Não é anúncio agrupado (`matchingAds` vem vazio), não é item sem `listId` (só propaganda sem id) e não é repetido nosso (no máximo 1 por página, e todos eram repetidos de verdade).
- O que falta é anúncio contado no total e que a OLX não serve em página nenhuma. Não sei o motivo, só que acontece do lado dela.

### 3. Existe teto de páginas?
Não apareceu um teto fixo. Em "onix" (MG, 3.357 resultados) a OLX serve até a **página 65**, que vem com 37 anúncios (3.237 no total). A página 66 em diante responde 200 com a lista vazia e nenhuma mensagem (sem erro, sem bloqueio). Páginas 30 e 60 vieram cheias. Ou seja, a lista acaba sozinha, perto de 96% do total. O padrão `GARIMPO_MAX_PAGINAS_SOB_DEMANDA` foi de 30 para 70, só como teto de segurança (a lista da OLX acaba sozinha antes).
