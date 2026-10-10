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
