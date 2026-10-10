# Banco de dados do Garimpo Auto

## Pra que serve

O banco guarda duas coisas.

1. **As buscas já feitas.** Quando alguém busca "fiat argo", o servidor lê a OLX e guarda as páginas. Se outra pessoa fizer a mesma busca em até 20 minutos, ela recebe as mesmas páginas na hora. Se o servidor reiniciar, nada se perde.
2. **O que cada busca já mostrou.** Com isso o Garimpo Auto diz quais carros são **novos desde a última vez** que alguém fez a mesma busca.

Ele não guarda os carros para sempre. As páginas somem quando a busca vence.

---

> ## ⚠️ Regras da empresa. Leia antes de mexer
>
> - **O MariaDB/MySQL do PC é da empresa.** Os containers das portas **3306 e 3307** são da empresa. **Não se mexe neles.** Nada de conectar, criar, apagar, parar ou reiniciar.
> - **O banco do Garimpo Auto é outro.** Container próprio `garimpo_auto_banco`, banco `garimpo_auto`, porta **3390 só em `127.0.0.1`** (ninguém de fora da máquina acessa), usuário exclusivo `garimpo`.
> - **Senhas só no `.env`**, que fica fora do git. Nunca em código, doc, commit ou conversa.
> - **Na dúvida sobre algo que possa afetar o banco da empresa, pare e pergunte.** Isso vale para porta, container, volume, usuário e qualquer comando que não seja só do `garimpo_auto_banco`.

---

## Subir, parar e conferir

Rode na pasta raiz do projeto (a que tem o `docker-compose.yml`). O arquivo `.env` com as senhas precisa existir (modelo em `.env.example`).

**Antes de subir pela primeira vez, confira que a porta está livre:**

```bash
ss -ltn | grep 3390     # não deve aparecer nada
```

**Subir:**

```bash
docker-compose up -d banco
```

**Parar** (os dados continuam guardados):

```bash
docker-compose stop banco
```

**Ver se está de pé e saudável:**

```bash
docker ps --format '{{.Names}} {{.Ports}}'                         # garimpo_auto_banco 127.0.0.1:3390->3306/tcp
docker inspect -f '{{.State.Health.Status}}' garimpo_auto_banco    # healthy
```

**Ver o que tem dentro:**

```bash
docker exec garimpo_auto_banco sh -c 'mariadb -ugarimpo -p"$MARIADB_PASSWORD" garimpo_auto -e "show tables"'
```

**Ver os avisos do banco:**

```bash
docker logs --tail 50 garimpo_auto_banco
```

> Cuidado: `docker-compose down -v` **apaga todos os dados** do Garimpo Auto (o volume `garimpo_auto_garimpo_auto_dados`). Só use se for de propósito. Ele só afeta o projeto `garimpo_auto`.

Sem o banco ligado o servidor continua funcionando, só que guardando tudo na memória (veja mais abaixo).

## As tabelas

O banco tem 5 tabelas. Toda tabela tem um **id** (a chave primária): é o que identifica cada linha e não se repete.

### `busca_sessao`: a busca em andamento

Uma linha por busca (texto, filtros, estado e ordem iguais). É a "ficha" da busca.

| Campo | O que é |
|---|---|
| **`id`** | Número da sessão |
| `chave_hash` | Código curto que identifica a busca (único: só existe uma sessão por busca) |
| `chave` | A busca escrita por extenso, para a gente ler |
| `busca` | O pedido completo (texto e filtros) |
| `execucao_id` | A execução a que ela pertence (veja abaixo) |
| `anterior_em` | Quando começou a busca igual anterior. Vazio na primeira vez |
| `criada_em` | Quando foi aberta |
| `valida_ate` | Até quando vale. Começa a contar quando a página 1 chega (20 minutos) |
| `total_ads` | O total que a OLX diz ter para essa busca |
| `estado_cursor` | De onde a busca continua. É o que permite seguir depois de um reinício |

### `busca_pagina`: as páginas lidas

Uma linha por página que o servidor já leu. Quando a sessão vence ou é apagada, as páginas dela vão junto.

| Campo | O que é |
|---|---|
| **`sessao_id` + `numero`** | O id desta tabela é o par: de qual sessão e qual página (1, 2, 3...) |
| `conteudo` | Os carros da página (sem os dados crus da OLX) |
| `tempo_segundos` | Quanto tempo a leitura levou |
| `coletada_em` | A hora em que a página foi lida |

### `busca_execucao`: cada vez que a busca recomeça

Uma linha cada vez que uma busca igual começa do zero (busca nova, busca vencida ou `atualizar=1`). Serve para saber **qual foi a busca anterior**.

| Campo | O que é |
|---|---|
| **`id`** | Número da execução (cresce a cada nova) |
| `usuario` | Quem fez a busca. **Vazio hoje** (vale para todo mundo) |
| `chave_hash` | Qual busca é |
| `iniciada_em` | Quando começou |

### `busca_visto`: o que a busca já mostrou

Uma linha por carro mostrado, por busca e por usuário. É a "memória" do que não é mais novidade.

| Campo | O que é |
|---|---|
| **`usuario` + `chave_hash` + `fonte` + `external_id`** | O id desta tabela é o conjunto: quem, qual busca, de qual site (OLX) e qual anúncio |
| `execucao_id` | A primeira execução que mostrou esse carro |
| `visto_em` | Quando foi visto pela primeira vez |

### `schema_migracoes`: controle do banco

Lista as migrations (mudanças no formato do banco) que já foram aplicadas. Veja o último tópico.

| Campo | O que é |
|---|---|
| **`versao`** | Nome do arquivo da migration (ex.: `001_cache_de_busca`) |
| `aplicada_em` | Quando foi aplicada |

## Como as tabelas se ligam

Sim, o banco é **relacional**: as tabelas se ligam por campos em comum, e dá para cruzar uma com a outra. O MariaDB é um banco desse tipo.

Mas só **uma ligação é "travada" pelo banco** (a página não existe sem a sessão). As outras são ligações combinadas pelo servidor, pelo mesmo `chave_hash` ou `execucao_id`.

```
                busca_execucao
                  id  usuario  chave_hash  iniciada_em
                   ▲               ▲
                   │ execucao_id   │ mesmo chave_hash
                   │               │ (ligação combinada)
 busca_sessao ─────┘               │
  id  chave_hash  ...              │
   ▲                               │
   │ sessao_id (ligação travada:   │
   │ apagou a sessão, as páginas   │
   │ vão junto)                    │
 busca_pagina                  busca_visto
  sessao_id + numero            usuario + chave_hash + fonte + external_id
  conteudo  coletada_em         execucao_id  visto_em
                                    │
                                    └── execucao_id volta para busca_execucao

 schema_migracoes: separada, só controla as migrations.
```

Na prática:

- A **sessão** é a busca de agora. Ela tem as **páginas**.
- A **execução** é o "carimbo" de quando a busca começou. A sessão aponta para ela.
- Os **vistos** lembram os carros de todas as execuções da mesma busca. É assim que, na próxima vez, o servidor sabe o que já tinha aparecido.
- Sessão e páginas **vencem e são apagadas**. Execuções e vistos **ficam**.

## Decisões tomadas

- **"Novo" usa visto + data.** Um carro é novo quando existe uma busca igual anterior, ele não apareceu em nenhuma delas **e** foi anunciado (ou renovado) depois que a última começou. Se o carro não tem data, vale só o "não apareceu antes". Sem a data, um carro antigo do fundo da lista, que a busca anterior nem chegou a ler, apareceria como novo por engano.
- **Primeira busca: ninguém é novo.** Não há com o que comparar. A resposta traz `primeira_busca: true`.
- **Global por enquanto, com a coluna `usuario` pronta para o login.** Hoje "busca igual" vale para qualquer pessoa, então um usuário "gasta" o novo do outro. A coluna `usuario` já existe nas tabelas de execução e de vistos (vazia). Quando houver login, o servidor passa o id da pessoa e cada um tem o seu histórico, sem refazer o banco. Um detalhe: hoje o `novo` fica guardado dentro da página, que é compartilhada. Na troca para "por usuário", ele passa a ser calculado na hora de responder.
- **Banco fora do ar: cai para a memória, com aviso no log.** A busca continua funcionando, sem esperar o banco. O log diz uma vez "Banco fora do ar" e, quando volta, "Banco voltou". O servidor não tenta reconectar a cada busca. Uma checagem em segundo plano olha a cada 30 segundos (`GARIMPO_BANCO_CONFERE_SEGUNDOS`). Enquanto o banco está fora, `primeira_busca` vem `null` e ninguém é marcado como novo.
- **Validade de 20 minutos**, contados a partir da página 1. Quem pede `atualizar=1` troca a busca para todos.
- **Porta 3390, só em 127.0.0.1.** A 3307 já era da empresa.
- **Testes têm banco separado** (`garimpo_auto_teste`), apagado e refeito a cada teste. Nunca usam o `garimpo_auto`. Sem o banco de pé, esses testes são pulados.

## O que ainda não existe

- **Vistos que não expiram.** Os carros vistos ficam para sempre. Quando a tabela crescer demais, dá para apagar os mais velhos. O único efeito é alguns carros antigos aparecerem como novos uma vez.
- **Login.** Não há usuário de verdade. Tudo é global.
- **Histórico de preço.** O banco não guarda o preço dos carros ao longo do tempo. As páginas somem quando a busca vence.

## Migrations

**O que são:** arquivos que descrevem como o banco é montado, passo a passo. Em vez de criar tabela à mão, a gente escreve um arquivo e o servidor aplica. Assim todo ambiente (o seu, o de teste, o de amanhã) fica igual.

**Onde ficam:** `scraper/migracoes/`, com nomes `001_nome.sql`, `002_nome.sql`... Hoje:

- `001_cache_de_busca.sql`: sessão, páginas e execução.
- `002_vistos.sql`: o que a busca já viu.

**Como funcionam:**

1. Os arquivos são aplicados em ordem, **cada um uma vez só**.
2. A tabela `schema_migracoes` anota o que já foi aplicado.
3. Se o banco já está em dia, nada acontece.
4. Dois servidores subindo juntos não se atropelam: o banco deixa um de cada vez.

**Quando rodam:** sozinhas, na primeira vez que o servidor fala com o banco. Também dá para rodar à mão:

```bash
cd scraper
.venv/bin/python migrar.py
```

Ele diz o que aplicou, ou "nenhuma, já estava em dia". Se não conseguir falar com o banco, avisa e para.

**Para mudar o banco:**

- Crie um arquivo novo com o próximo número (ex.: `003_historico_de_preco.sql`).
- **Nunca edite uma migration que já foi aplicada.** Mudança nova é arquivo novo.
- Prefira migrations pequenas, uma mudança por arquivo.
- Rode `migrar.py` e confira com `show tables`.
- Comentários no SQL começam com `--`.
