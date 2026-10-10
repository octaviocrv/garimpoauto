-- Roda só na primeira vez que o volume é criado. O banco de teste é apagado e refeito pelos testes,
-- então fica separado do garimpo_auto. O usuário "garimpo" já foi criado pela imagem.
CREATE DATABASE IF NOT EXISTS garimpo_auto_teste CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON garimpo_auto_teste.* TO 'garimpo'@'%';
FLUSH PRIVILEGES;
