# Pesquisa redonda, critérios

Como conferir que a busca da OLX está confiável. As buscas de referência ficam em `buscas.json`
(as cinco que já rodamos, com uma delas trocada por uma busca com marca e filtros). O que dá para
medir sozinho é medido por `verificar_referencia.py`. O resto é conferido na mão e marcado aqui.

| # | Critério | Como se confere |
|---|---|---|
| 1 | Bate com o site: o total da OLX (`total_na_fonte`) é o mesmo que a pesquisa mostra no navegador, e pelo menos 90% dos 50 primeiros ids da busca aparecem na mesma pesquisa aberta no site | Total: automático (compara com a página 1). Ids: manual, ou pelo MCP de OLX do agente |
| 2 | Filtro certo: com marca, ano e preço, 100% dos carros devolvidos estão dentro do filtro e o funil explica quem foi cortado | Automático |
| 3 | Nada cortado em silêncio: se parou antes de acabar, `motivo_parada` e os avisos dizem isso, e coletados menos cortes dá os finais | Automático |
| 4 | Sem repetido: zero id repetido. Mesmo carro em lojas diferentes só marcado, nunca apagado | Automático |
| 5 | Campos principais: preço, ano, km, cidade e modelo preenchidos em pelo menos 99%, o resto marcado como incompleto | Automático |
| 6 | Falha vira resultado parcial: com bloqueio simulado, o servidor devolve o que juntou e o aviso certo | Teste offline |
| 7 | Repetir é rápido: a mesma busca dentro do cache volta em menos de 1 s | Automático |
| 8 | Tempo previsível: busca nova de 8 páginas termina em cerca de 2 minutos | Automático |
| 9 | O que a pessoa pediu é o que foi aplicado: o resultado informa estado, ordenação e hora da coleta | Automático |

## Última verificação (10 de outubro de 2026, OLX real, ordem por mais recentes)

| # | Resultado |
|---|---|
| 1 | Total da OLX lido em todas as buscas (121, 28.839, 11.214, 6.154 e 320). Ids contra o site: **não deu para medir** nesta rodada, fica manual |
| 2 | **Passou** nas 5, inclusive a com marca, modelo, ano, preço e estado (320 de 320 dentro do filtro) |
| 3 | **Passou.** O funil fechou em todas e as 3 buscas que bateram no teto de 8 páginas trouxeram o aviso `teto_paginas` |
| 4 | **Passou.** Zero id repetido. Mesmo carro em outro anúncio marcado: 0, 15, 6, 1 e 3 |
| 5 | **Passou.** Mínimo de 99,2% (preço da busca de gol, 1 anúncio sem preço), o resto em 100% |
| 6 | **Passou** nos testes offline (bloqueio na 1ª e na 2ª página, página sem anúncios) |
| 7 | **Passou.** Busca repetida no cache em menos de 1 ms |
| 8 | **Passou.** 16 s a 90 s (menor universo, menos páginas). As de 8 páginas ficaram entre 75 s e 85 s |
| 9 | **Passou.** O resultado traz estado aplicado, ordenação e hora da coleta |

Ordem por mais recentes: nas 5 buscas as datas vieram em ordem decrescente. As 8 páginas (cerca de 400 anúncios) cobrem 4 horas no onix, cerca de 10 horas na hilux e cerca de 30 horas no fiat uno.
Cuidado: em busca ampla, quase tudo em `sf=1` vem com `isFeatured` (onix: 50 de 50 na página 1, 340 de 397 no total). São anúncios de loja renovados, então "mais recentes" mostra o que foi renovado ou impulsionado, não só o que é novo.
