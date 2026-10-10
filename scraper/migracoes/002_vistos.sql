-- O que cada busca igual já mostrou, para marcar "novo desde a última vez". A chave começa pelo
-- usuário: hoje é sempre vazio (global), e quando houver login basta passar o id dele.

CREATE TABLE busca_visto (
  usuario VARCHAR(64) NOT NULL DEFAULT '',
  chave_hash CHAR(64) NOT NULL,
  fonte VARCHAR(32) NOT NULL,
  external_id VARCHAR(64) NOT NULL,
  execucao_id BIGINT UNSIGNED NOT NULL,            -- a primeira busca que mostrou este anúncio
  visto_em DATETIME(3) NOT NULL,
  PRIMARY KEY (usuario, chave_hash, fonte, external_id),
  KEY ix_visto_execucao (execucao_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
