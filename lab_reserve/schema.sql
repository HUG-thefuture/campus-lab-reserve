-- =====================================================================
-- 实验室设备预约系统后端 —— MySQL 8.0 建表 SQL（项目交付物）
-- 适用：MySQL 8.0 / 8.4，utf8mb4
-- 执行方式（本机 MySQL 8.4 示例，含中文注释务必加 --default-character-set=utf8mb4）：
--   "C:/Program Files/MySQL/MySQL Server 8.4/bin/mysql.exe" -uroot -proot --default-character-set=utf8mb4 < lab_reserve/schema.sql
--
-- 说明：应用默认使用 SQLite 并在启动时自动建表（SQLAlchemy create_all）；
--       切换 MySQL 时可直接执行本脚本预建表（结构含 ENUM/索引/外键，更贴近生产）。
-- =====================================================================

CREATE DATABASE IF NOT EXISTS lab_reserve DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lab_reserve;

-- 用户表：角色只允许 student / teacher / admin
CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  username      VARCHAR(50)  NOT NULL COMMENT '用户名（唯一）',
  password_hash VARCHAR(256) NOT NULL COMMENT 'PBKDF2-SHA256 哈希（生产建议 BCrypt/argon2）',
  role          ENUM('student','teacher','admin') NOT NULL DEFAULT 'student' COMMENT '角色',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '用户表';

-- 设备表
CREATE TABLE IF NOT EXISTS devices (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name        VARCHAR(100) NOT NULL COMMENT '设备名称',
  capacity    INT          NOT NULL COMMENT '容量（可同时使用人数），>0',
  description VARCHAR(500) NULL COMMENT '描述',
  status      VARCHAR(20)  NOT NULL DEFAULT 'AVAILABLE' COMMENT '设备状态',
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_devices_name (name)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '设备表';

-- 预约表：状态机 PENDING -> APPROVED|REJECTED|CANCELED；APPROVED -> RETURNED
CREATE TABLE IF NOT EXISTS reservations (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    INT UNSIGNED NOT NULL COMMENT '预约人',
  device_id  INT UNSIGNED NOT NULL COMMENT '设备',
  start_time DATETIME     NOT NULL COMMENT '开始时间',
  end_time   DATETIME     NOT NULL COMMENT '结束时间（须晚于开始时间）',
  status     ENUM('PENDING','APPROVED','REJECTED','CANCELED','RETURNED') NOT NULL DEFAULT 'PENDING' COMMENT '状态',
  created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  -- 时段冲突校验核心索引：按设备+时间区间过滤（existing.start_time < new.end_time AND existing.end_time > new.start_time）
  KEY idx_res_device_time (device_id, start_time, end_time),
  KEY idx_res_user (user_id),
  CONSTRAINT fk_res_user   FOREIGN KEY (user_id)   REFERENCES users (id),
  CONSTRAINT fk_res_device FOREIGN KEY (device_id) REFERENCES devices (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '预约表';
