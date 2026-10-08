# Arquitetura inicial

## Ponto de partida

`apps/web` é a primeira aplicação executável do Garimpo Auto. Ela começa com uma landing page e evolui para a busca de carros.

`identidade/landing-page` é a fonte visual inicial. Mantenha nessa pasta
os arquivos originais de referência. Assets usados pela aplicação devem ser
copiados para `apps/web/public` para serem servidos pelo Vite.

`identidade/brand-kit` reúne os materiais da marca, do mascote e os tokens e
componentes usados como referência visual.

## Próximas partes

1. Tela de busca com filtros básicos
2. API em ASP.NET Core para expor resultados tratados
3. Coletor em Python para a primeira fonte de anúncios
4. MySQL para anúncios normalizados e deduplicados
5. Integração das demais fontes quando a primeira estiver estável

## Regras de organização

- Código de produto fica em `apps/`.
- Cada aplicação mantém seu próprio `package.json` e `.env.example`.
- Segredos ficam somente em arquivos `.env` ignorados pelo Git.
- Material de referência visual não deve ser importado diretamente de
  `identidade/brand-kit` ou `identidade/landing-page` pelo app.
- Antes de adicionar uma dependência, confirme que ela suporta Node 18 enquanto o ambiente não migrar para Node 20 LTS.