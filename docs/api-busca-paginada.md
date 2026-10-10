# Busca paginada ("Ver mais") e como a tela deve chamar

A tela ainda usa `/buscar/stream`. Este documento descreve o jeito novo, igual ao da OLX, para quando a gente ligar o "Ver mais". Nada aqui exige mudar o stream.

## Endpoints

| Endpoint | Para que serve |
|---|---|
| `GET /buscar/pagina` | Uma página por vez, para o "Ver mais". Novo |
| `GET /buscar/stream` | Várias páginas de uma vez por SSE (até 8). Continua igual |
| `GET /buscar` | O mesmo do stream em um JSON só. Continua igual |

Os três usam os mesmos parâmetros de busca (`texto`, `marca`, `modelo`, `versao`, `ano_min`, `ano_max`, `preco_min`, `preco_max`, `km_min`, `km_max`, `cambio`, `combustivel`, `anunciante`, `ordenar`, `estado`, `regiao`, `cidade`, `dev`, `atualizar`) e **a mesma sessão de busca no servidor**. Página lida por um deles serve para os outros, e o servidor nunca baixa de novo da OLX uma página que já tem.

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

### Frases de `informacao`
- Tem mais: "Mostrando 50 de 1.413 carros. Toca em Ver mais pra ver o resto."
- Acabou: "Achei 80 carros. Esses são todos."
- Parou no teto de páginas: "Mostrei 1.500 de 28.839 carros. Essa busca é grande demais pra mostrar tudo, refina por ano ou preço pra ver os outros."
- Filtros daqui tiraram carros: acrescenta "Alguns ficaram de fora dos filtros que você pôs."
- Falha: "Não consegui buscar mais agora, tenta de novo daqui a pouco?" (ou "Não achei esse carro agora, tenta de novo?" se foi na página 1)
- Sem nada: "Não achei nenhum carro com esses filtros. Que tal afrouxar algum?"

## Tempo, pausa e cache
- **Página 1:** sem pausa. Se a busca tem marca ou modelo, o servidor consulta as listas de códigos da OLX antes (uma vez por marca, guardada por 12 h), também sem pausa.
- **Da página 2 em diante:** o servidor garante o mesmo intervalo de 6 a 14 s desde a última leitura **da mesma busca**, descontando o tempo que a pessoa já levou para clicar. Quem demora mais que a pausa não espera nada. Quem clica rápido espera só o que falta.
- **Cache:** por página, e a sessão inteira vale 20 minutos (`CACHE_TTL_SEGUNDOS`), contados a partir da hora da página 1. Pedir uma página já lida volta na hora. A chave considera texto, filtros, estado e ordenação.
- **Teto:** o "Ver mais" vai até `GARIMPO_MAX_PAGINAS_SOB_DEMANDA` páginas por busca (veja o resultado do teste de paginação abaixo).
- **Fila:** só uma leitura real da OLX por vez no servidor. Uma busca nunca fica travada na pausa de outra, porque a pausa acontece antes de entrar na fila.

## O que acontece quando a lista da OLX muda no meio
Entre uma página e outra, anúncios novos entram no topo e empurram a lista. Resultado:
- **Repetição:** coberta. O mesmo `listId` que reaparece na página seguinte é descartado, e o mesmo carro anunciado de novo por outra loja vem marcado em `repetido_de` (e não some).
- **Omissão:** não coberta. Se um anúncio é renovado e sobe para uma página que a pessoa já passou, ele não aparece nessa sessão. Também pode escapar um anúncio quando outro sai do ar e a lista anda para cima. É raro e some ao usar `atualizar=1`, que recomeça a busca na hora.
- Uma página que só traz repetidos encerra a busca, com o aviso "A página só tinha anúncios repetidos".

## E o `/buscar/stream`?
Continua igual para a tela de hoje (eventos `pagina`, `fim` e `erro`, mesmos campos). Por dentro agora ele lê as páginas da mesma sessão que o "Ver mais". Duas diferenças boas: se a pessoa fecha a tela ou cancela, o servidor para de ler (antes a coleta ia até o fim), e a falha no meio guarda as páginas boas e a busca seguinte continua de onde parou.

## Teste de paginação na OLX real (10 de outubro de 2026)
Busca "fiat argo" em MG, mais recentes, páginas 1 a 30 com a pausa normal, sem repetir tentativa.
- **Nenhum bloqueio.** Todas as 29 páginas pedidas vieram com status 200.
- **A OLX entregou 28 páginas.** 27 cheias (50 por página, algumas com 49 por causa de repetido), a 28ª com 14, e a 29ª vazia. Total listado: **1.360 carros**.
- **O total da OLX fica um pouco acima do que ela lista:** 1.411 a 1.413 no fim, contra 1.360 listados (cerca de 3,6% a menos). Não sei explicar a diferença. Pode ser anúncio que sai do ar durante a leitura ou item contado e não listado. O total oscilou entre 1.411 e 1.413 durante a leitura.
- **Total confere com o site:** a página 1 mostra "1 - 50 de 1.413 resultados" no texto, e nós lemos `totalOfAds` 1.413.
- **Repetido por lista deslocada apareceu de verdade:** 5 páginas vieram com 49 novos em vez de 50 (um anúncio já visto reapareceu), e o tratamento por `listId` descartou todos.
- **Teto da OLX:** não apareceu nenhum nesta busca, porque a lista acabou antes (página 28). Para buscas muito grandes (como "onix", 28 mil) o teto continua desconhecido além da página 30.
- **Ajuste feito por causa do teste:** página menor que a 1ª agora conta como a última, em vez de gastar uma leitura extra para descobrir.

## Tempos medidos (OLX real)
- Página 1: cerca de 2 s (1,8 s no teste pelo servidor).
- Página já lida: cerca de 20 ms.
- Página 2 clicada logo depois da 1: cerca de 8 s (a pausa de 6 a 14 s valendo).
