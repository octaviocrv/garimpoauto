# Garimpo Auto

## Contexto

Antes de trabalhar, leia `_memoria/empresa.md`, `_memoria/preferencias.md`, `_memoria/estrategia.md` e a documentação diretamente ligada à tarefa.

## Segurança e fluxo

- Trabalhe somente na cópia principal do repositório. Não crie nem use worktrees para o Garimpo Auto.
- Nunca faça push sem pedido explícito.
- Não rode, escreva nem altere testes, nem rode build ou verificações por conta própria. Quem testa e homologa é o Octavio. Implemente, analise e diga o que ele deve testar.
- Cada entrega gera um único commit depois que todos os testes passam. Não faça commits intermediários.
- O MariaDB/MySQL das portas 3306 e 3307 e os bancos acessados por `mydados` são da empresa. Nunca conecte, consulte, altere, pare ou reinicie esses recursos.
- Use somente o container `garimpo_auto_banco`, banco `garimpo_auto`, em `127.0.0.1:3390`. Testes de banco usam somente `garimpo_auto_teste`.
- Nunca execute `docker-compose down -v`, apague volumes ou use comandos destrutivos no banco sem pedido explícito.
- Senhas e tokens ficam somente em arquivos `.env` ignorados pelo Git.
- Consulte `docs/banco.md` antes de qualquer tarefa relacionada ao banco.

## Produto

- Preserve o tom definido em `_memoria/preferencias.md`.
- Textos da interface não usam travessão, dois pontos, ponto e vírgula nem a palavra "veículo".
- Faça mudanças pequenas e não altere regras de negócio fora do escopo pedido.
