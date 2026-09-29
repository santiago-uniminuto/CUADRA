-- Ejecutar UNA vez en MySQL Workbench (conectado como root) en el computador de cada desarrollador.
-- Clave '1234' y usa la MISMA clave en tu archivo .env (DB_PASSWORD).
CREATE DATABASE IF NOT EXISTS cuadra_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'cuadra_user'@'localhost' IDENTIFIED BY '1234';
GRANT ALL PRIVILEGES ON cuadra_db.* TO 'cuadra_user'@'localhost';
FLUSH PRIVILEGES;
