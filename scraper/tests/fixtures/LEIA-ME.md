# Fixtures da OLX

Páginas reais coletadas em 10 de outubro de 2026, guardadas só com o que o coletor lê: o array `ads`
(sem nome nem telefone de anunciante, com até 2 fotos por anúncio) e o total que a OLX informa.

| Arquivo | Busca na OLX |
|---|---|
| `olx_civic_p1.json`, `olx_civic_p2.json` | `q=civic 2018`, MG, mais recentes (`sf=1`), páginas 1 e 2. Total 78 (50 + 28) |
| `olx_poucos.json` | `q=civic`, MG, ano 2018, até R$ 100.000, Honda Civic (`vb=33&vm=3`). Total 10 |
| `olx_contagem.json` | `q=civic`, MG, cidade Contagem na URL (`estado-mg/belo-horizonte-e-regiao/grande-belo-horizonte/contagem`). Total 146, 50 anúncios, todos de Contagem |
| `olx_zero.json` | busca que não acha nada. Total 0, `ads` vazio |
| `olx_api_marcas.json`, `olx_api_modelos_honda.json`, `olx_api_versoes_civic.json` | respostas de `/api/filters/v1/attributes/{carbrand,carmodel,carversion}`, usadas para achar os códigos de marca, modelo e versão |
| `olx_listagem.html` | página antiga com 5 anúncios, usada nos primeiros testes |
| `olx_anuncio.json` | o objeto `ad` do `initial-data` da página de um anúncio (Onix 2024, `listId` 1546298897), usado no Garimpar. Telefone da descrição trocado por um falso e links das propriedades removidos |

Bloqueio nunca foi visto de verdade. Os testes simulam com 403, 429 e página sem `ads`.
