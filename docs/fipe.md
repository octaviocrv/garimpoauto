# FIPE no Garimpo Auto

## De onde vem

O Garimpo Auto consulta a API gratuita da fipe.online em
`https://fipe.parallelum.com.br/api/v2`.

Só o servidor fala com essa fonte. A tela recebe apenas a referência já conferida e guardada.

O token gratuito é opcional e fica em `GARIMPO_FIPE_TOKEN`. Sem token, o Garimpo Auto usa no máximo
450 chamadas por dia. Com token, usa no máximo 900. A margem evita encostar nos limites externos de
500 e 1.000 chamadas.

## O que fica guardado

Marcas, modelos, anos, combustíveis e preços ficam no banco por mês de referência. Quando chega um
mês novo, o catálogo antigo continua guardado e o preço novo só é buscado quando alguém precisar.

O resultado do casamento também fica guardado por anúncio. Abrir a mesma página não consulta a
FIPE de novo.

## Como o casamento decide

O Garimpo Auto confere nesta ordem.

1. Marca
2. Modelo base
3. Ano e combustível
4. Motor, portas, câmbio e acabamento
5. Similaridade do texto para desempatar

Campos separados da OLX valem mais que o título. Candidatos incompatíveis com motor, portas ou
câmbio saem antes das consultas de anos para economizar o limite diário.

O nome da marca aceita complementos do catálogo quando a correspondência continua única, como
`Chevrolet` e `GM - Chevrolet`. Os modelos são procurados primeiro pela família e depois ranqueados
pela versão completa. Abreviações de pelo menos três letras, diferenças de pontuação e caixa não
criam regras específicas por carro.

### Confiança alta

Marca, modelo, ano e combustível conferem. A versão tem uma diferença clara para a segunda opção.
Só esta confiança chega à tela.

### Confiança média

Há um candidato provável, mas outra versão ficou perto ou houve empate. Fica guardado para
diagnóstico e não aparece na tela.

### Confiança baixa

A versão ficou pouco parecida. Não aparece na tela.

### Sem candidato

Faltou dado ou nenhuma opção foi compatível. Não aparece na tela.

## Casos que não viram selo

- Anúncio promocional ou com preço de entrada
- Carro com pelo menos dois anos e menos de 1.000 km
- Ano impossível
- Preço menor que metade da FIPE
- Confiança média ou baixa

Preço abaixo de 50% da FIPE fica marcado como estranho. O carro continua na lista.

## Tempo e falhas

O servidor dedica por padrão até 4 segundos à FIPE por página e usa no máximo duas consultas ao
mesmo tempo. Quem não terminar nesse tempo fica sem FIPE naquela página.

Sem banco, nenhuma chamada é feita. Erro de rede, resposta 429 ou orçamento esgotado não derrubam a
busca. A página segue sem a referência que faltou.

## Aquecer antes da vitrine

Depois de abrir a vitrine ou fazer buscas, rode dentro de `scraper`.

```bash
.venv/bin/python aquecer_fipe.py --orcamento 100
```

O script lê os anúncios das páginas ainda guardadas, começa pelos modelos mais comuns e respeita
tanto o orçamento da execução quanto o limite diário. Pode parar e rodar de novo. Casamentos já
guardados não gastam chamadas novamente.

No fim ele mostra quantos anúncios ficaram com confiança alta, média, baixa e sem candidato.

## Trocar a fonte

O contrato está em `scraper/sources/fipe.py`, no protocolo `FonteFipe`. Uma fonte por CSV ou outro
provedor precisa implementar referências, marcas, modelos, anos e preço. O cache, o casamento, a
API e a tela não precisam mudar.

## Variáveis

| Variável | Padrão | Para que serve |
|---|---:|---|
| `GARIMPO_FIPE_TOKEN` | vazio | Token opcional da fonte |
| `GARIMPO_FIPE_LIMITE_DIA` | 450 ou 900 | Teto local diário |
| `GARIMPO_FIPE_TIMEOUT_REQUISICAO_SEGUNDOS` | 10 | Tempo de uma chamada |
| `GARIMPO_FIPE_TEMPO_PAGINA_SEGUNDOS` | 4 | Tempo total da FIPE numa página |
| `GARIMPO_FIPE_PAUSA_SEGUNDOS` | 0,2 | Pausa curta entre chamadas |
| `GARIMPO_FIPE_REPETICOES` | 1 | Repetição depois de 429 ou rede |
| `GARIMPO_FIPE_BACKOFF_SEGUNDOS` | 1 | Primeira espera antes da repetição |
