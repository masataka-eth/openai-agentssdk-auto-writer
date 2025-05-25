CREATE DATABASE IF NOT EXISTS ai_writer_db;
USE ai_writer_db;

CREATE TABLE articles (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  title       VARCHAR(255) NOT NULL UNIQUE,
  slug        VARCHAR(255),
  posted_at   DATETIME,
  status      ENUM('saved','error') DEFAULT 'saved'
); 