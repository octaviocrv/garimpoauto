-- Catálogo mensal da FIPE, casamento dos anúncios e controle do orçamento da fonte.
-- Ao contrário das páginas de busca, estas tabelas não vencem com a sessão.

CREATE TABLE fipe_referencia (
  codigo VARCHAR(16) NOT NULL PRIMARY KEY,
  mes VARCHAR(80) NOT NULL,
  ordem SMALLINT UNSIGNED NOT NULL,
  consultada_em DATETIME(3) NOT NULL,
  KEY ix_fipe_referencia_ordem (ordem)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE fipe_marca (
  referencia_codigo VARCHAR(16) NOT NULL,
  codigo VARCHAR(32) NOT NULL,
  nome VARCHAR(160) NOT NULL,
  carregada_em DATETIME(3) NOT NULL,
  PRIMARY KEY (referencia_codigo, codigo),
  KEY ix_fipe_marca_nome (referencia_codigo, nome)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE fipe_modelo (
  referencia_codigo VARCHAR(16) NOT NULL,
  marca_codigo VARCHAR(32) NOT NULL,
  codigo VARCHAR(32) NOT NULL,
  nome VARCHAR(240) NOT NULL,
  carregado_em DATETIME(3) NOT NULL,
  PRIMARY KEY (referencia_codigo, marca_codigo, codigo),
  KEY ix_fipe_modelo_nome (referencia_codigo, marca_codigo, nome)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE fipe_ano (
  referencia_codigo VARCHAR(16) NOT NULL,
  marca_codigo VARCHAR(32) NOT NULL,
  modelo_codigo VARCHAR(32) NOT NULL,
  codigo VARCHAR(32) NOT NULL,
  nome VARCHAR(120) NOT NULL,
  ano_modelo SMALLINT UNSIGNED NULL,
  combustivel_codigo VARCHAR(16) NULL,
  combustivel VARCHAR(40) NULL,
  carregado_em DATETIME(3) NOT NULL,
  PRIMARY KEY (referencia_codigo, marca_codigo, modelo_codigo, codigo),
  KEY ix_fipe_ano_busca (referencia_codigo, marca_codigo, modelo_codigo, ano_modelo, combustivel)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE fipe_preco (
  referencia_codigo VARCHAR(16) NOT NULL,
  marca_codigo VARCHAR(32) NOT NULL,
  modelo_codigo VARCHAR(32) NOT NULL,
  ano_codigo VARCHAR(32) NOT NULL,
  codigo_fipe VARCHAR(16) NOT NULL,
  preco DECIMAL(12,2) NOT NULL,
  mes_referencia VARCHAR(80) NOT NULL,
  marca VARCHAR(160) NOT NULL,
  modelo VARCHAR(240) NOT NULL,
  ano_modelo SMALLINT UNSIGNED NOT NULL,
  combustivel VARCHAR(40) NOT NULL,
  consultado_em DATETIME(3) NOT NULL,
  PRIMARY KEY (referencia_codigo, marca_codigo, modelo_codigo, ano_codigo),
  KEY ix_fipe_preco_codigo (codigo_fipe, referencia_codigo),
  KEY ix_fipe_preco_modelo (referencia_codigo, marca_codigo, modelo_codigo, ano_modelo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE fipe_cache_estado (
  referencia_codigo VARCHAR(16) NOT NULL,
  tipo VARCHAR(32) NOT NULL,
  chave VARCHAR(160) NOT NULL,
  estado LONGTEXT NULL,
  concluido_em DATETIME(3) NOT NULL,
  PRIMARY KEY (referencia_codigo, tipo, chave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE fipe_casamento (
  fonte VARCHAR(32) NOT NULL,
  anuncio_id VARCHAR(96) NOT NULL,
  entrada_hash CHAR(64) NOT NULL,
  referencia_codigo VARCHAR(16) NULL,
  codigo_fipe VARCHAR(16) NULL,
  preco DECIMAL(12,2) NULL,
  mes_referencia VARCHAR(80) NULL,
  confianca VARCHAR(16) NOT NULL,
  motivo VARCHAR(240) NOT NULL,
  bloqueio VARCHAR(40) NULL,
  preco_estranho BOOLEAN NOT NULL DEFAULT FALSE,
  casado_em DATETIME(3) NOT NULL,
  PRIMARY KEY (fonte, anuncio_id),
  KEY ix_fipe_casamento_hash (entrada_hash),
  KEY ix_fipe_casamento_confianca (confianca, casado_em)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE fipe_requisicao_dia (
  dia DATE NOT NULL PRIMARY KEY,
  requisicoes INT UNSIGNED NOT NULL,
  atualizada_em DATETIME(3) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
