Sobre os MCPs no Garimpo Auto

Os MCPs mercadolibre-devsite-mcp e marketplaces-br são ferramentas do agente, pra usar só aqui no chat. Eles ajudam a construir o Garimpo Auto, mas não fazem parte dele. O sistema final nunca chama MCP.

Quem busca anúncio de verdade no sistema é o coletor em Python (pasta scraper/sources), que devolve tudo no formato único em Pydantic pro C# chamar em paralelo. Nunca sugira o backend ou o coletor depender de MCP.

Como usar cada um

1. mercadolibre-devsite-mcp lê a documentação oficial da API do Mercado Livre. Use pra tirar dúvida de endpoint, autenticação, campos e categorias de veículos, e pra responder a decisão em aberto se a API oficial libera a busca de carros. Sempre consulte antes de escrever o coletor do Mercado Livre.

2. marketplaces-br busca anúncios reais do Mercado Livre e da OLX. Use só pra conferência, por exemplo rodar a mesma busca nele e comparar com o que o coletor trouxe. Também serve pra garimpar um carro na mão quando o Octavio pedir.

Ordem de trabalho do Mercado Livre

Primeiro confirmar na documentação se a API oficial atende a busca de veículos. Se atender, o coletor usa a API. Se bloquear, aí sim cai pro Scrapling. Depois de pronto, conferir o resultado com o marketplaces-br.

Lembrete

O Octavio quer praticar o desenvolvimento de ponta a ponta, então o código do coletor e da API é sempre dele. O MCP ajuda a entender e a conferir, mas não substitui o código.