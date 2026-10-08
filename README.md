# Garimpo Auto

Projeto para buscar anúncios de carros usados em um lugar só, com dados organizados para ajudar revendedores a achar bom negócio.

## Começo rápido

O frontend inicial está em `apps/web` e usa a identidade visual de
`identidade/landing-page` como referência.

```bash
cd apps/web
npm run dev
```

O ambiente atual usa Node 18.20.4. Para manter as ferramentas atualizadas ao longo do projeto, a recomendação é migrar para Node 20 LTS antes de atualizar dependências.

## Estrutura

```text
apps/web/                    Aplicação React e primeira landing page
identidade/brand-kit/        Marca, mascote, tokens e componentes de referência
identidade/landing-page/     Fonte visual da primeira landing page
_memoria/                    Contexto do negócio, preferências e estratégia
dados/                       Arquivos de entrada para análises
marketing/                   Materiais de divulgação
saidas/                      Resultados e documentos gerados
scripts/                     Utilitários do projeto
docs/                        Decisões e visão técnica
```

Leia [a arquitetura inicial](docs/architecture.md) antes de criar novas partes do sistema.
