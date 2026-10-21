# FIPE no Garimpo Auto

## De onde vem

A FIPE vem pronta da própria OLX. A página de cada anúncio de carro tem o quadro **Referência de
preço**, com o preço do anúncio, o "Preço Médio OLX", o "preço fipe" e uma régua em 3 trechos.

O Garimpo Auto lê esse quadro do JSON `initial-data` da página, e não das classes CSS:

| Campo na OLX | Campo no Garimpo | O que é |
|---|---|---|
| `priceValue` | `preco_anuncio` | Preço do anúncio |
| `abuyFipePrice.fipePrice` | `fipe` | Preço FIPE que a OLX mostra para a versão do anúncio |
| `abuyPriceRef.price_p50` | `media_olx` | "Preço Médio OLX" |
| `abuyPriceRef.price_min` | `menor` | Começo da régua |
| `abuyPriceRef.price_p33` | `corte_baixo` | Fim do 1º trecho |
| `abuyPriceRef.price_p66` | `corte_alto` | Fim do 2º trecho |
| `abuyPriceRef.price_max` | `maior` | Fim da régua |
| `abuyPriceRef.vehicle_count` | `carros` | Quantos carros a OLX usou na conta |
| `abuyPriceRef.year_month_ref` | `mes_referencia` | Mês da conta da OLX, como `"2026-09"` |

Não há consulta a nenhuma API de FIPE. A integração antiga com a fipe.online (casamento de versões,
catálogo no banco, orçamento diário e aquecimento) foi removida.

## Quando consulta

Só ao abrir o **Garimpar** de um anúncio. O quadro chega junto com a página do anúncio, em
`GET /anuncio/detalhe`, no campo `referencia_preco`. É a mesma leitura da ficha, sem pedido extra à OLX,
e fica guardada em memória por 20 minutos como o resto do detalhe.

A lista e a vitrine não leem página de anúncio, então não trazem FIPE. Depois que um Garimpar abre e a
referência chega, ela passa a valer também no card daquele anúncio (`Anuncio.referencia_preco`) e no
veredito.

## Na tela

- O Garimpar mostra o bloco **Referência de preço** dentro de "O que o anúncio conta", com a régua, o
  preço do anúncio, o preço médio OLX e o preço FIPE.
- A régua tem 3 trechos iguais (menor até corte baixo, corte baixo até corte alto, corte alto até maior),
  como a da OLX. O trecho onde o preço do anúncio cai fica em destaque e o pino anda dentro dele.

## No veredito

O veredito do Garimpar (`apps/web/src/busca/analise.ts`) usa só o que a OLX entrega. O Garimpo não
compara mais o preço com os carros carregados na lista, não calcula mediana e não estima margem.

Critérios que vêm do quadro Referência de preço:

| Critério | A favor | Atenção |
|---|---|---|
| Preço comparado à FIPE | 10% ou mais abaixo | acima da FIPE, ou 30% ou mais abaixo (preço suspeito) |
| Preço comparado à média da OLX | 10% ou mais abaixo | acima da média, ou 30% ou mais abaixo |
| Régua da OLX | no 1º trecho (entre os mais baratos) | no 3º trecho (entre os mais caros) |

Critérios que vêm do resto da página do anúncio e da lista: km por ano, frescor, vendedor, fotos,
palavras de risco no título e na descrição, o que o anunciante marcou em Outras características
(IPVA pago, único dono, quitado, revisões, garantia, manual e chave reserva contam a favor; leilão,
multas e financiado pedem atenção), carro completo nos opcionais e anúncio repetido.

Nível:

- **Quente** quando o preço está abaixo de todas as referências que a OLX mostrou, pelo menos uma
  delas 10% ou mais, no 1º trecho da régua e sem nenhum critério de atenção.
- **Boa** quando o preço está abaixo de todas as referências que a OLX mostrou e não há alerta forte.
- Sem nível quando falta a referência, quando o preço está na linha ou acima, quando as referências
  divergem ou quando há alerta forte (preço suspeito, leilão, palavra de risco ou anúncio repetido).

Antes da página do anúncio abrir, o veredito fica em "Lendo a referência da OLX". O card da lista só
ganha nível depois que o Garimpar daquele anúncio é aberto.

## Quando falta

Os campos são internos da OLX e podem faltar ou mudar sem aviso.

- Sem FIPE e sem média, `referencia_preco` vem `null` e o bloco não aparece.
- Com parte dos números, a tela mostra o que tem. Sem os cortes, a régua some e as caixas ficam.
- Sem FIPE ou sem média, o critério correspondente fica sem dado e o veredito usa o que sobrou.
  Sem nenhuma das duas, o veredito fica "Sem referência da OLX".
- A OLX não informa o código FIPE nem o mês da tabela FIPE. O mês mostrado é o da conta de mercado
  da OLX.

## Banco

As tabelas `fipe_*` criadas pelas migrations `003_fipe.sql` e `004_ausencia_fipe.sql` ficaram sem
uso. Elas foram mantidas para não apagar dado com migration. Remover só com pedido explícito.
Páginas de busca guardadas antes da troca ainda podem ter `fipe` no JSON, e o servidor ignora esse
campo ao carregar.
