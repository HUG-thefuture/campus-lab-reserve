-- =====================================================================
-- 自习打卡统计接口 —— MySQL 8.0 建表 SQL（项目交付物）
-- 执行方式（本机 MySQL 8.4 示例，含中文注释务必加 --default-character-set=utf8mb4）：
--   "C:/Program Files/MySQL/MySQL Server 8.4/bin/mysql.exe" -uroot -proot --default-character-set=utf8mb4 < study_checkin/schema.sql
-- =====================================================================

CREATE DATABASE IF NOT EXISTS study_checkin DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE study_checkin;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  username      VARCHAR(50)  NOT NULL COMMENT '用户名（唯一）',
  password_hash VARCHAR(256) NOT NULL COMMENT 'PBKDF2-SHA256 哈希',
  role          ENUM('student','teacher','admin') NOT NULL DEFAULT 'student' COMMENT '角色',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '用户表';

-- 打卡记录表
-- 简历承诺：唯一约束 UniqueConstraint(user_id, checkin_date) 保证每天只能打卡一次，
--           重复打卡由应用层转 409 "今日已打卡"
CREATE TABLE IF NOT EXISTS checkins (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id      INT UNSIGNED NOT NULL COMMENT '打卡人',
  checkin_date DATE         NOT NULL COMMENT '打卡日期（自然日）',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '打卡时间',
  PRIMARY KEY (id),
  UNIQUE KEY uq_user_checkin_date (user_id, checkin_date),
  CONSTRAINT fk_checkins_user FOREIGN KEY (user_id) REFERENCES users (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '打卡记录表';
