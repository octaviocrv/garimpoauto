-- Ocorrências operacionais que impediram a FIPE de chegar ao anúncio.
-- Decisões do casamento continuam em fipe_casamento.

CREATE TABLE fipe_ausencia (
  fonte VARCHAR(32) NOT NULL,
  anuncio_id VARCHAR(96) NOT NULL,
  entrada_hash CHAR(64) NOT NULL,
  motivo VARCHAR(32) NOT NULL,
  detalhe VARCHAR(240) NULL,
  ocorrencias INT UNSIGNED NOT NULL DEFAULT 1,
  primeira_em DATETIME(3) NOT NULL,
  ultima_em DATETIME(3) NOT NULL,
  PRIMARY KEY (fonte, anuncio_id, entrada_hash, motivo),
  KEY ix_fipe_ausencia_motivo (motivo, ultima_em)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
