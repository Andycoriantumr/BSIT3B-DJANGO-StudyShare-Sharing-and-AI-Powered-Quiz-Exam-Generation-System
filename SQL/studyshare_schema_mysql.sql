-- =====================================================================
-- StudyShare schema — MySQL / MariaDB dialect
-- Generated from Django models on 2026-10-14. Engine: InnoDB, utf8mb4.
-- How to use: create an empty database in phpMyAdmin, select it, then
-- Import this file. (SQLite version: studyshare_schema.sql)
-- Legacy tbl* tables from bsitcrud.sql are intentionally excluded.
-- =====================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- CREATE DATABASE IF NOT EXISTS studyshare CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- USE studyshare;

CREATE TABLE `auth_user` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `password` VARCHAR(128) NOT NULL,
  `last_login` DATETIME NULL,
  `is_superuser` TINYINT(1) NOT NULL,
  `username` VARCHAR(150) NOT NULL UNIQUE,
  `first_name` VARCHAR(150) NOT NULL,
  `last_name` VARCHAR(150) NOT NULL,
  `email` VARCHAR(254) NOT NULL,
  `is_staff` TINYINT(1) NOT NULL,
  `is_active` TINYINT(1) NOT NULL,
  `date_joined` DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `tblinfo` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(255) NOT NULL,
  `age` INT UNSIGNED NOT NULL,
  `address` VARCHAR(255) NOT NULL,
  `email` VARCHAR(255) NOT NULL,
  `user_id` INT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  CONSTRAINT `fk_tblinfo_user` FOREIGN KEY (`user_id`)
    REFERENCES `auth_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `users_profile` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `role` VARCHAR(20) NOT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  `user_id` INT NOT NULL UNIQUE,
  CONSTRAINT `fk_profile_user` FOREIGN KEY (`user_id`)
    REFERENCES `auth_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `notes_subject` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(120) NOT NULL UNIQUE,
  `code` VARCHAR(30) NOT NULL,
  `description` TEXT NOT NULL,
  `is_active` TINYINT(1) NOT NULL,
  `created_by_id` INT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  CONSTRAINT `fk_subject_user` FOREIGN KEY (`created_by_id`)
    REFERENCES `auth_user` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `notes_note` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `title` VARCHAR(255) NOT NULL,
  `subject` VARCHAR(120) NOT NULL,
  `instructor` VARCHAR(120) NOT NULL,
  `topic` VARCHAR(255) NOT NULL,
  `school_year` VARCHAR(30) NOT NULL,
  `description` TEXT NOT NULL,
  `content` TEXT NOT NULL,
  `file` VARCHAR(100) NULL,
  `is_public` TINYINT(1) NOT NULL,
  `status` VARCHAR(20) NOT NULL,
  `uploaded_by_id` INT NOT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  CONSTRAINT `fk_note_uploader` FOREIGN KEY (`uploaded_by_id`)
    REFERENCES `auth_user` (`id`) ON DELETE CASCADE,
  KEY `idx_note_subject_year` (`subject`, `school_year`),
  KEY `idx_note_instructor` (`instructor`),
  KEY `idx_note_topic` (`topic`),
  KEY `idx_note_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `notes_noterating` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `note_id` BIGINT NOT NULL,
  `user_id` INT NOT NULL,
  `score` SMALLINT UNSIGNED NOT NULL,
  `comment` TEXT NOT NULL,
  `created_at` DATETIME NOT NULL,
  `updated_at` DATETIME NOT NULL,
  CONSTRAINT `fk_rating_note` FOREIGN KEY (`note_id`)
    REFERENCES `notes_note` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rating_user` FOREIGN KEY (`user_id`)
    REFERENCES `auth_user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `unique_note_user_rating` UNIQUE (`note_id`, `user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `notes_notereport` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `note_id` BIGINT NOT NULL,
  `reporter_id` INT NOT NULL,
  `reason` VARCHAR(20) NOT NULL,
  `details` TEXT NOT NULL,
  `status` VARCHAR(20) NOT NULL,
  `reviewed_by_id` INT NULL,
  `reviewed_at` DATETIME NULL,
  `created_at` DATETIME NOT NULL,
  CONSTRAINT `fk_report_note` FOREIGN KEY (`note_id`)
    REFERENCES `notes_note` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_report_reporter` FOREIGN KEY (`reporter_id`)
    REFERENCES `auth_user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_report_reviewer` FOREIGN KEY (`reviewed_by_id`)
    REFERENCES `auth_user` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `notes_quizset` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `note_id` BIGINT NOT NULL,
  `created_by_id` INT NOT NULL,
  `title` VARCHAR(255) NOT NULL,
  `num_questions` SMALLINT UNSIGNED NOT NULL,
  `question_type` VARCHAR(20) NOT NULL,
  `provider` VARCHAR(20) NOT NULL,
  `is_exam` TINYINT(1) NOT NULL DEFAULT 0,
  `exam_subject` VARCHAR(120) NOT NULL DEFAULT '',
  `source_note_ids` JSON NOT NULL,
  `created_at` DATETIME NOT NULL,
  CONSTRAINT `fk_quizset_note` FOREIGN KEY (`note_id`)
    REFERENCES `notes_note` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_quizset_creator` FOREIGN KEY (`created_by_id`)
    REFERENCES `auth_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `notes_question` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `quiz_id` BIGINT NOT NULL,
  `question_type` VARCHAR(20) NOT NULL,
  `question_text` TEXT NOT NULL,
  `options` JSON NOT NULL,
  `correct_answer` TEXT NOT NULL,
  `explanation` TEXT NOT NULL,
  `order` INT UNSIGNED NOT NULL,
  CONSTRAINT `fk_question_quiz` FOREIGN KEY (`quiz_id`)
    REFERENCES `notes_quizset` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `notes_quizattempt` (
  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
  `quiz_id` BIGINT NOT NULL,
  `taker_id` INT NOT NULL,
  `score` INT UNSIGNED NOT NULL,
  `total` INT UNSIGNED NOT NULL,
  `percentage` DOUBLE NOT NULL,
  `answers` JSON NOT NULL,
  `submitted_at` DATETIME NOT NULL,
  CONSTRAINT `fk_attempt_quiz` FOREIGN KEY (`quiz_id`)
    REFERENCES `notes_quizset` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_attempt_taker` FOREIGN KEY (`taker_id`)
    REFERENCES `auth_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;
