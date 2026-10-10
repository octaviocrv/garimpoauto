-- Cache de busca compartilhado: a sessão de busca, as páginas já lidas e a execução (cada vez que
-- uma busca igual recomeça do zero). Datas em UTC.

CREATE TABLE busca_execucao (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  usuario VARCHAR(64) NOT NULL DEFAULT '',         -- vazio = global, até existir login
  chave_hash CHAR(64) NOT NULL,                    -- sha256 da chave de busca
  iniciada_em DATETIME(3) NOT NULL,
  KEY ix_execucao_busca (usuario, chave_hash, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE busca_sessao (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  chave_hash CHAR(64) NOT NULL,
  chave TEXT NOT NULL,                             -- a chave de busca, legível
  busca LONGTEXT NOT NULL,                         -- o pedido (JSON)
  execucao_id BIGINT UNSIGNED NOT NULL,
  anterior_em DATETIME(3) NULL,                    -- início da busca igual anterior (vazio = 1ª vez)
  criada_em DATETIME(3) NOT NULL,
  valida_ate DATETIME(3) NULL,                     -- começa a contar quando a 1ª página chega
  total_ads INT NULL,                              -- total que a fonte diz ter
  estado_cursor LONGTEXT NULL,                     -- de onde a busca continua (JSON)
  UNIQUE KEY ux_sessao_chave (chave_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE busca_pagina (
  sessao_id BIGINT UNSIGNED NOT NULL,
  numero INT UNSIGNED NOT NULL,
  conteudo LONGTEXT NOT NULL,                      -- a página inteira (JSON), sem o item cru da fonte
  tempo_segundos DOUBLE NOT NULL,
  coletada_em DATETIME(3) NOT NULL,
  PRIMARY KEY (sessao_id, numero),
  CONSTRAINT fk_pagina_sessao FOREIGN KEY (sessao_id) REFERENCES busca_sessao (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
