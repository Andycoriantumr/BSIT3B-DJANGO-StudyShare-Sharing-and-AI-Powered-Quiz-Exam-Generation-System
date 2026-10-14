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

-- ================= DATA =================

-- auth_user: 4 rows
INSERT INTO `auth_user` (`id`, `password`, `last_login`, `is_superuser`, `username`, `last_name`, `email`, `is_staff`, `is_active`, `date_joined`, `first_name`) VALUES
(1, 'pbkdf2_sha256$1500000$O8dSRmXyUU0MY86hwytQZ6$Ve9qWCFvy+2/wqro6Dr/lOg8x+A9XP7PEhdthiiv2Ng=', '2026-09-09 07:23:35.816542', 1, 'glenn', '', 'glennazuelo1@gmail.com', 1, 1, '2026-05-12 14:04:29.081361', ''),
(2, 'pbkdf2_sha256$1000000$HPTf8ycpKsZHUqY2DNkv3u$cdFrDVtzUxZhYR14r4/pX/Dl36GS2NvJve+muOWlU9U=', '2026-10-14 05:37:47.345112', 1, 'admin', '', 'admin@example.com', 1, 1, '2026-10-14 01:54:55.380817', ''),
(3, 'pbkdf2_sha256$1000000$y9h1LY6g5EyJJFcoYdNydW$1xuv6Z23TltmxmWkL6dW1h2Gr3Bu5mg+EEH6UfrB2Jg=', NULL, 0, 'instructor', '', '', 1, 1, '2026-10-14 02:05:00.056779', ''),
(4, 'pbkdf2_sha256$1000000$eo4oAKdh5H7OxhbNXEVBJg$IECMWkmmDG5JiiZaakbPo+v+YJGayRvn7wvaeIYagvc=', '2026-10-14 02:43:07.826431', 0, 'student', '', '', 0, 1, '2026-10-14 02:05:00.421942', '');

-- tblinfo: 1 rows
INSERT INTO `tblinfo` (`id`, `name`, `age`, `address`, `email`, `created_at`, `updated_at`, `user_id`) VALUES
(1, 'Demo Student', 20, 'Manila, Philippines', 'student@example.com', '2026-10-14 05:43:02.753790', '2026-10-14 05:43:02.753839', 4);

-- users_profile: 4 rows
INSERT INTO `users_profile` (`id`, `role`, `created_at`, `updated_at`, `user_id`) VALUES
(1, 'admin', '2026-10-14 02:03:24.383165', '2026-10-14 02:03:24.383200', 1),
(2, 'admin', '2026-10-14 02:03:24.405005', '2026-10-14 05:37:47.369740', 2),
(3, 'instructor', '2026-10-14 02:05:00.378453', '2026-10-14 02:05:00.830609', 3),
(4, 'student', '2026-10-14 02:05:00.746908', '2026-10-14 02:43:07.854105', 4);

-- notes_subject: 4 rows
INSERT INTO `notes_subject` (`id`, `name`, `code`, `description`, `is_active`, `created_at`, `updated_at`, `created_by_id`) VALUES
(5, 'Biology', 'BIO101', 'Life science fundamentals.', 1, '2026-10-14 02:29:28.311303', '2026-10-14 02:29:28.311328', 3),
(6, 'Mathematics', 'MATH101', 'Algebra and probability basics.', 1, '2026-10-14 02:29:28.314582', '2026-10-14 02:29:28.314600', 3),
(7, 'Philippine History', 'HIST101', 'Key eras in Philippine history.', 1, '2026-10-14 02:29:28.315356', '2026-10-14 02:29:28.315370', 3),
(8, 'IT Capstone', 'IT401', 'Software projects and databases.', 1, '2026-10-14 02:29:28.316044', '2026-10-14 02:29:28.316055', 3);

-- notes_note: 10 rows
INSERT INTO `notes_note` (`id`, `title`, `subject`, `instructor`, `topic`, `school_year`, `description`, `content`, `file`, `is_public`, `created_at`, `updated_at`, `uploaded_by_id`, `status`) VALUES
(11, 'Photosynthesis Fundamentals', 'Biology', 'Prof. Santos', 'Photosynthesis', '2024-2025', 'How plants convert light into chemical energy.', 'Photosynthesis converts light energy into chemical energy stored in glucose. Chlorophyll absorbs sunlight inside the chloroplasts of plant cells. Carbon dioxide enters through the stomata while water is absorbed by the roots. The light-dependent reactions produce ATP and NADPH in the thylakoid membranes. The Calvin cycle fixes carbon dioxide into sugar in the stroma of the chloroplast. Oxygen is released as a byproduct that most living organisms depend on for respiration.', '', 1, '2026-10-14 02:29:28.316983', '2026-10-14 02:29:28.317002', 3, 'approved'),
(12, 'Mitosis and Cell Division', 'Biology', 'Prof. Santos', 'Mitosis', '2024-2025', 'Stages of mitosis and why they matter.', 'Mitosis produces two genetically identical daughter cells from one parent cell. During prophase, chromatin condenses into visible chromosomes and the spindle forms. In metaphase, chromosomes line up along the equatorial plate of the cell. Sister chromatids separate and move to opposite poles during anaphase. Telophase reforms the nuclear envelope around each set of chromosomes. Cytokinesis then divides the cytoplasm to complete the process of cell division.', '', 1, '2026-10-14 02:29:28.318451', '2026-10-14 02:29:28.318467', 3, 'approved'),
(13, 'Human Digestive System Overview', 'Biology', 'Prof. Santos', 'Digestion', '2024-2025', 'Organs and enzymes of digestion.', 'Digestion mechanically and chemically breaks food into absorbable nutrients. Salivary amylase in the mouth begins the chemical digestion of starch. Hydrochloric acid and pepsin in the stomach digest proteins into peptides. The small intestine absorbs most nutrients through villi into the bloodstream. Bile from the liver emulsifies fats to increase the surface area for enzymes. Undigested material passes into the large intestine where water is reabsorbed.', '', 1, '2026-10-14 02:29:28.319306', '2026-10-14 02:29:28.319320', 3, 'approved'),
(14, 'Solving Quadratic Equations', 'Mathematics', 'Prof. Reyes', 'Quadratics', '2024-2025', 'Factoring, completing the square, and the formula.', 'A quadratic equation has the standard form ax squared plus bx plus c equals zero. Factoring rewrites the quadratic as a product of two linear binomial expressions. Completing the square converts the equation into a perfect square trinomial form. The quadratic formula gives solutions using negative b plus or minus the discriminant. The discriminant b squared minus 4ac determines the number of real solutions. A positive discriminant means two real roots while zero means exactly one repeated root.', '', 1, '2026-10-14 02:29:28.320067', '2026-10-14 02:29:28.320079', 3, 'approved'),
(15, 'Basic Probability Rules', 'Mathematics', 'Prof. Reyes', 'Probability', '2024-2025', 'Sample spaces, independent events, expected value.', 'Probability measures the likelihood of an event on a scale from zero to one. The sample space is the set of all possible outcomes of a random experiment. Two events are independent when the occurrence of one does not affect the other. The addition rule finds the probability that at least one of two events occurs. Conditional probability measures the chance of an event given that another occurred. Expected value is the long-run average outcome of a repeated random process.', '', 1, '2026-10-14 02:29:28.320859', '2026-10-14 02:29:28.320874', 3, 'approved'),
(16, 'The Philippine Revolution', 'Philippine History', 'Prof. Aquino', 'Revolution', '2024-2025', 'Causes and key events of the 1896 revolution.', 'The Philippine Revolution began in 1896 against more than three centuries of Spanish rule. The Katipunan was a secret society founded by Andres Bonifacio to organize the uprising. The Cry of Pugad Lawin symbolized the start of open revolt in August 1896. Jose Rizal advocated reforms through education before his execution in December 1896. Emilio Aguinaldo later led revolutionary forces and declared independence in June 1898. The revolution shifted into resistance against the United States after the Treaty of Paris.', '', 1, '2026-10-14 02:29:28.321677', '2026-10-14 02:29:28.321690', 3, 'approved'),
(17, 'The Post-War Philippine Republic', 'Philippine History', 'Prof. Aquino', 'Post-War Republic', '2024-2025', 'Rebuilding the republic after World War II.', 'The Third Philippine Republic was inaugurated on July 4, 1946 after independence. Manuel Roxas became the first president of the newly independent republic. War rehabilitation funds helped rebuild infrastructure destroyed during the occupation. The Bell Trade Act shaped early economic relations between the Philippines and America. Land reform debates grew as tenant farmers demanded fair ownership of farmland. Democratic institutions expanded even as regional inequalities remained a challenge.', '', 1, '2026-10-14 02:29:28.322423', '2026-10-14 02:29:28.322435', 3, 'approved'),
(18, 'SDLC Overview for Capstone', 'IT Capstone', 'Prof. Cruz', 'SDLC', '2024-2025', 'Planning through maintenance in software projects.', 'The software development life cycle organizes work from planning through maintenance. Requirements gathering captures what stakeholders need the system to accomplish. System design translates requirements into architecture, modules, and data models. Implementation writes and reviews code according to the approved technical design. Testing verifies that each feature meets its acceptance criteria before release. Deployment and maintenance deliver the system and fix issues discovered in production.', '', 1, '2026-10-14 02:29:28.323299', '2026-10-14 02:29:28.323313', 3, 'approved'),
(19, 'Database Normalization Basics', 'IT Capstone', 'Prof. Cruz', 'Normalization', '2024-2025', 'First through third normal forms with examples.', 'Normalization organizes relational tables to reduce redundancy and anomalies. First normal form requires atomic values with no repeating groups in any row. Second normal form removes partial dependencies on only part of a composite key. Third normal form eliminates transitive dependencies between non-key attributes. A primary key uniquely identifies each row while foreign keys link related tables. Denormalization is sometimes used to improve read performance for reporting queries.', '', 1, '2026-10-14 02:29:28.324059', '2026-10-14 02:29:28.324072', 3, 'approved'),
(20, 'Agile Scrum in Student Teams', 'IT Capstone', 'Prof. Cruz', 'Scrum', '2024-2025', 'Sprints, roles, and ceremonies that work for class projects.', 'Scrum divides capstone work into short sprints that each deliver a usable increment. The product owner prioritizes the backlog by value to the users of the system. The scrum master removes blockers so the team can sustain steady progress. Daily standups keep every member aware of yesterday, today, and impediments. Sprint reviews demonstrate completed features to stakeholders for fast feedback. Retrospectives help student teams improve collaboration before the next sprint begins.', '', 1, '2026-10-14 02:29:28.324773', '2026-10-14 02:29:28.324786', 3, 'approved');

-- notes_noterating: 18 rows
INSERT INTO `notes_noterating` (`id`, `score`, `comment`, `created_at`, `updated_at`, `note_id`, `user_id`) VALUES
(19, 5, '', '2026-10-14 02:29:28.326442', '2026-10-14 02:29:28.326457', 11, 1),
(20, 4, '', '2026-10-14 02:29:28.327513', '2026-10-14 02:29:28.327528', 11, 2),
(21, 3, '', '2026-10-14 02:29:28.328338', '2026-10-14 02:29:28.328351', 11, 4),
(22, 4, '', '2026-10-14 02:29:28.329192', '2026-10-14 02:29:28.329205', 12, 1),
(23, 3, '', '2026-10-14 02:29:28.329965', '2026-10-14 02:29:28.329976', 12, 2),
(24, 5, '', '2026-10-14 02:29:28.330771', '2026-10-14 02:29:28.330784', 12, 4),
(25, 3, '', '2026-10-14 02:29:28.331653', '2026-10-14 02:29:28.331667', 13, 1),
(26, 5, '', '2026-10-14 02:29:28.332566', '2026-10-14 02:29:28.332579', 13, 2),
(27, 4, '', '2026-10-14 02:29:28.333356', '2026-10-14 02:29:28.333368', 13, 4),
(28, 5, '', '2026-10-14 02:29:28.334341', '2026-10-14 02:29:28.334358', 14, 1),
(29, 4, '', '2026-10-14 02:29:28.335229', '2026-10-14 02:29:28.335243', 14, 2),
(30, 3, '', '2026-10-14 02:29:28.336220', '2026-10-14 02:29:28.336235', 14, 4),
(31, 4, '', '2026-10-14 02:29:28.337064', '2026-10-14 02:29:28.337077', 15, 1),
(32, 3, '', '2026-10-14 02:29:28.337938', '2026-10-14 02:29:28.337952', 15, 2),
(33, 5, '', '2026-10-14 02:29:28.338812', '2026-10-14 02:29:28.338826', 15, 4),
(34, 3, '', '2026-10-14 02:29:28.339674', '2026-10-14 02:29:28.339687', 16, 1),
(35, 5, '', '2026-10-14 02:29:28.340528', '2026-10-14 02:29:28.340542', 16, 2),
(36, 4, '', '2026-10-14 02:29:28.341343', '2026-10-14 02:29:28.341356', 16, 4);

-- notes_notereport: 1 rows
INSERT INTO `notes_notereport` (`id`, `reason`, `details`, `status`, `reviewed_at`, `created_at`, `note_id`, `reporter_id`, `reviewed_by_id`) VALUES
(1, 'other', 'Demo report for export purposes.', 'pending', NULL, '2026-10-14 05:43:02.771408', 20, 4, NULL);

-- notes_quizset: 17 rows
INSERT INTO `notes_quizset` (`id`, `title`, `num_questions`, `question_type`, `provider`, `created_at`, `created_by_id`, `note_id`, `exam_subject`, `is_exam`, `source_note_ids`) VALUES
(13, 'Mixed Quiz — Photosynthesis Fundamentals', 5, 'mixed', 'local', '2026-10-14 02:29:28.342679', 3, 11, '', 0, '[]'),
(14, 'Mixed Quiz — Mitosis and Cell Division', 5, 'mixed', 'local', '2026-10-14 02:29:28.344612', 3, 12, '', 0, '[]'),
(15, 'Mixed Quiz — Human Digestive System Overview', 5, 'mixed', 'local', '2026-10-14 02:29:28.345956', 3, 13, '', 0, '[]'),
(16, 'Mixed Quiz — Solving Quadratic Equations', 5, 'mixed', 'local', '2026-10-14 02:29:28.347265', 3, 14, '', 0, '[]'),
(17, 'Mixed Quiz — Basic Probability Rules', 5, 'mixed', 'local', '2026-10-14 02:29:28.348539', 3, 15, '', 0, '[]'),
(18, 'Mixed Quiz — The Philippine Revolution', 5, 'mixed', 'local', '2026-10-14 02:29:28.349807', 3, 16, '', 0, '[]'),
(19, 'Mixed Quiz — The Post-War Philippine Republic', 5, 'mixed', 'local', '2026-10-14 02:29:28.351334', 3, 17, '', 0, '[]'),
(20, 'Mixed Quiz — SDLC Overview for Capstone', 5, 'mixed', 'local', '2026-10-14 02:29:28.352765', 3, 18, '', 0, '[]'),
(21, 'Mixed Quiz — Database Normalization Basics', 5, 'mixed', 'local', '2026-10-14 02:29:28.354000', 3, 19, '', 0, '[]'),
(22, 'Mixed Quiz — Agile Scrum in Student Teams', 5, 'mixed', 'local', '2026-10-14 02:29:28.355259', 3, 20, '', 0, '[]'),
(23, 'Exam — Biology (20 Qs, 3 sources)', 20, 'mixed', 'local', '2026-10-14 02:29:28.356874', 3, 11, 'Biology', 1, '[11, 12, 13]'),
(24, 'Exam — IT Capstone (20 Qs, 3 sources)', 20, 'mixed', 'local', '2026-10-14 02:29:28.360096', 3, 18, 'IT Capstone', 1, '[18, 19, 20]'),
(25, 'Mcq Quiz — SDLC Overview for Capstone', 20, 'mcq', 'local', '2026-10-14 02:34:12.094566', 2, 18, '', 0, '[]'),
(26, 'Mcq Quiz — SDLC Overview for Capstone', 3, 'mcq', 'local', '2026-10-14 02:38:53.827617', 2, 18, '', 0, '[]'),
(27, 'Exam — Mixed Subjects (10 Qs, 2 sources)', 10, 'mcq', 'local', '2026-10-14 02:45:16.078237', 4, 16, 'Mixed Subjects', 1, '[16, 15]'),
(28, 'Exam — IT Capstone (10 Qs, 3 sources)', 10, 'mixed', 'openrouter', '2026-10-14 02:46:52.967785', 4, 20, 'IT Capstone', 1, '[20, 19, 18]'),
(30, 'Mixed Quiz — Agile Scrum in Student Teams', 5, 'mixed', 'local', '2026-10-14 05:41:01.942597', 4, 20, '', 0, '[]');

-- notes_question: 137 rows
INSERT INTO `notes_question` (`id`, `question_type`, `question_text`, `options`, `correct_answer`, `explanation`, `order`, `quiz_id`) VALUES
(91, 'mcq', 'Which term best completes the statement? "_____ converts light energy into chemical energy stored in glucose."', '["Photosynthesis", "converts", "light", "energy"]', 'Photosynthesis', 'Based on the notes: "Photosynthesis converts light energy into chemical energy stored in glucose."', 0, 13),
(92, 'true_false', 'True or False: It is NOT the case that: Chlorophyll absorbs sunlight inside the chloroplasts of plant cells.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 13),
(93, 'short_answer', 'In your own words, explain: "Carbon dioxide enters through the stomata while water is absorbed by the roots."', '[]', 'Carbon dioxide enters through the stomata while water is absorbed by the roots.', 'Compare your answer against the reference statement above.', 2, 13),
(94, 'essay', 'Discuss the significance of the following concept and give an example: "The light-dependent reactions produce ATP and NADPH in the thylakoid membranes."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 13),
(95, 'mcq', 'Which term best completes the statement? "The _____ cycle fixes carbon dioxide into sugar in the stroma of the chloroplast."', '["Calvin", "Photosynthesis", "converts", "light"]', 'Calvin', 'Based on the notes: "The Calvin cycle fixes carbon dioxide into sugar in the stroma of the chloroplast."', 4, 13),
(96, 'mcq', 'Which term best completes the statement? "_____ produces two genetically identical daughter cells from one parent cell."', '["Mitosis", "produces", "genetically", "identical"]', 'Mitosis', 'Based on the notes: "Mitosis produces two genetically identical daughter cells from one parent cell."', 0, 14),
(97, 'true_false', 'True or False: It is NOT the case that: During prophase, chromatin condenses into visible chromosomes and the spindle forms.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 14),
(98, 'short_answer', 'In your own words, explain: "In metaphase, chromosomes line up along the equatorial plate of the cell."', '[]', 'In metaphase, chromosomes line up along the equatorial plate of the cell.', 'Compare your answer against the reference statement above.', 2, 14),
(99, 'essay', 'Discuss the significance of the following concept and give an example: "Sister chromatids separate and move to opposite poles during anaphase."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 14),
(100, 'mcq', 'Which term best completes the statement? "_____ reforms the nuclear envelope around each set of chromosomes."', '["Telophase", "Mitosis", "produces", "genetically"]', 'Telophase', 'Based on the notes: "Telophase reforms the nuclear envelope around each set of chromosomes."', 4, 14),
(101, 'mcq', 'Which term best completes the statement? "_____ mechanically and chemically breaks food into absorbable nutrients."', '["Digestion", "mechanically", "chemically", "breaks"]', 'Digestion', 'Based on the notes: "Digestion mechanically and chemically breaks food into absorbable nutrients."', 0, 15),
(102, 'true_false', 'True or False: It is NOT the case that: Salivary amylase in the mouth begins the chemical digestion of starch.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 15),
(103, 'short_answer', 'In your own words, explain: "Hydrochloric acid and pepsin in the stomach digest proteins into peptides."', '[]', 'Hydrochloric acid and pepsin in the stomach digest proteins into peptides.', 'Compare your answer against the reference statement above.', 2, 15),
(104, 'essay', 'Discuss the significance of the following concept and give an example: "The small intestine absorbs most nutrients through villi into the bloodstream."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 15),
(105, 'mcq', 'Which term best completes the statement? "Bile from the _____ emulsifies fats to increase the surface area for enzymes."', '["liver", "Digestion", "mechanically", "chemically"]', 'liver', 'Based on the notes: "Bile from the liver emulsifies fats to increase the surface area for enzymes."', 4, 15),
(106, 'mcq', 'Which term best completes the statement? "A _____ equation has the standard form ax squared plus bx plus c equals zero."', '["quadratic", "equation", "standard", "squared"]', 'quadratic', 'Based on the notes: "A quadratic equation has the standard form ax squared plus bx plus c equals zero."', 0, 16),
(107, 'true_false', 'True or False: It is NOT the case that: Factoring rewrites the quadratic as a product of two linear binomial expressions.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 16),
(108, 'short_answer', 'In your own words, explain: "Completing the square converts the equation into a perfect square trinomial form."', '[]', 'Completing the square converts the equation into a perfect square trinomial form.', 'Compare your answer against the reference statement above.', 2, 16),
(109, 'essay', 'Discuss the significance of the following concept and give an example: "The quadratic formula gives solutions using negative b plus or minus the discriminant."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 16),
(110, 'mcq', 'Which term best completes the statement? "The _____ b squared minus 4ac determines the number of real solutions."', '["discriminant", "quadratic", "equation", "standard"]', 'discriminant', 'Based on the notes: "The discriminant b squared minus 4ac determines the number of real solutions."', 4, 16),
(111, 'mcq', 'Which term best completes the statement? "_____ measures the likelihood of an event on a scale from zero to one."', '["Probability", "measures", "likelihood", "event"]', 'Probability', 'Based on the notes: "Probability measures the likelihood of an event on a scale from zero to one."', 0, 17),
(112, 'true_false', 'True or False: It is NOT the case that: The sample space is the set of all possible outcomes of a random experiment.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 17),
(113, 'short_answer', 'In your own words, explain: "Two events are independent when the occurrence of one does not affect the other."', '[]', 'Two events are independent when the occurrence of one does not affect the other.', 'Compare your answer against the reference statement above.', 2, 17),
(114, 'essay', 'Discuss the significance of the following concept and give an example: "The addition rule finds the probability that at least one of two events occurs."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 17),
(115, 'mcq', 'Which term best completes the statement? "_____ probability measures the chance of an event given that another occurred."', '["Conditional", "Probability", "measures", "likelihood"]', 'Conditional', 'Based on the notes: "Conditional probability measures the chance of an event given that another occurred."', 4, 17),
(116, 'mcq', 'Which term best completes the statement? "The _____ Revolution began in 1896 against more than three centuries of Spanish rule."', '["Philippine", "Revolution", "began", "against"]', 'Philippine', 'Based on the notes: "The Philippine Revolution began in 1896 against more than three centuries of Spanish rule."', 0, 18),
(117, 'true_false', 'True or False: It is NOT the case that: The Katipunan was a secret society founded by Andres Bonifacio to organize the uprising.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 18),
(118, 'short_answer', 'In your own words, explain: "The Cry of Pugad Lawin symbolized the start of open revolt in August 1896."', '[]', 'The Cry of Pugad Lawin symbolized the start of open revolt in August 1896.', 'Compare your answer against the reference statement above.', 2, 18),
(119, 'essay', 'Discuss the significance of the following concept and give an example: "Jose Rizal advocated reforms through education before his execution in December 1896."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 18),
(120, 'mcq', 'Which term best completes the statement? "_____ Aguinaldo later led revolutionary forces and declared independence in June 1898."', '["Emilio", "Philippine", "Revolution", "began"]', 'Emilio', 'Based on the notes: "Emilio Aguinaldo later led revolutionary forces and declared independence in June 1898."', 4, 18),
(121, 'mcq', 'Which term best completes the statement? "The _____ Philippine Republic was inaugurated on July 4, 1946 after independence."', '["Third", "Philippine", "Republic", "inaugurated"]', 'Third', 'Based on the notes: "The Third Philippine Republic was inaugurated on July 4, 1946 after independence."', 0, 19),
(122, 'true_false', 'True or False: It is NOT the case that: Manuel Roxas became the first president of the newly independent republic.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 19),
(123, 'short_answer', 'In your own words, explain: "War rehabilitation funds helped rebuild infrastructure destroyed during the occupation."', '[]', 'War rehabilitation funds helped rebuild infrastructure destroyed during the occupation.', 'Compare your answer against the reference statement above.', 2, 19),
(124, 'essay', 'Discuss the significance of the following concept and give an example: "The Bell Trade Act shaped early economic relations between the Philippines and America."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 19),
(125, 'mcq', 'Which term best completes the statement? "Land _____ debates grew as tenant farmers demanded fair ownership of farmland."', '["reform", "Third", "Philippine", "Republic"]', 'reform', 'Based on the notes: "Land reform debates grew as tenant farmers demanded fair ownership of farmland."', 4, 19),
(126, 'mcq', 'Which term best completes the statement? "The _____ development life cycle organizes work from planning through maintenance."', '["software", "development", "cycle", "organizes"]', 'software', 'Based on the notes: "The software development life cycle organizes work from planning through maintenance."', 0, 20),
(127, 'true_false', 'True or False: It is NOT the case that: Requirements gathering captures what stakeholders need the system to accomplish.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 20),
(128, 'short_answer', 'In your own words, explain: "System design translates requirements into architecture, modules, and data models."', '[]', 'System design translates requirements into architecture, modules, and data models.', 'Compare your answer against the reference statement above.', 2, 20),
(129, 'essay', 'Discuss the significance of the following concept and give an example: "Implementation writes and reviews code according to the approved technical design."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 20),
(130, 'mcq', 'Which term best completes the statement? "_____ verifies that each feature meets its acceptance criteria before release."', '["Testing", "software", "development", "cycle"]', 'Testing', 'Based on the notes: "Testing verifies that each feature meets its acceptance criteria before release."', 4, 20),
(131, 'mcq', 'Which term best completes the statement? "_____ organizes relational tables to reduce redundancy and anomalies."', '["Normalization", "organizes", "relational", "tables"]', 'Normalization', 'Based on the notes: "Normalization organizes relational tables to reduce redundancy and anomalies."', 0, 21),
(132, 'true_false', 'True or False: It is NOT the case that: First normal form requires atomic values with no repeating groups in any row.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 21),
(133, 'short_answer', 'In your own words, explain: "Second normal form removes partial dependencies on only part of a composite key."', '[]', 'Second normal form removes partial dependencies on only part of a composite key.', 'Compare your answer against the reference statement above.', 2, 21),
(134, 'essay', 'Discuss the significance of the following concept and give an example: "Third normal form eliminates transitive dependencies between non-key attributes."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 21),
(135, 'mcq', 'Which term best completes the statement? "A _____ key uniquely identifies each row while foreign keys link related tables."', '["primary", "Normalization", "organizes", "relational"]', 'primary', 'Based on the notes: "A primary key uniquely identifies each row while foreign keys link related tables."', 4, 21),
(136, 'mcq', 'Which term best completes the statement? "_____ divides capstone work into short sprints that each deliver a usable increment."', '["Scrum", "divides", "capstone", "short"]', 'Scrum', 'Based on the notes: "Scrum divides capstone work into short sprints that each deliver a usable increment."', 0, 22),
(137, 'true_false', 'True or False: It is NOT the case that: The product owner prioritizes the backlog by value to the users of the system.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 22),
(138, 'short_answer', 'In your own words, explain: "The scrum master removes blockers so the team can sustain steady progress."', '[]', 'The scrum master removes blockers so the team can sustain steady progress.', 'Compare your answer against the reference statement above.', 2, 22),
(139, 'essay', 'Discuss the significance of the following concept and give an example: "Daily standups keep every member aware of yesterday, today, and impediments."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 22),
(140, 'mcq', 'Which term best completes the statement? "_____ reviews demonstrate completed features to stakeholders for fast feedback."', '["Sprint", "Scrum", "divides", "capstone"]', 'Sprint', 'Based on the notes: "Sprint reviews demonstrate completed features to stakeholders for fast feedback."', 4, 22),
(141, 'mcq', 'Which term best completes the statement? "=== _____: Photosynthesis Fundamentals (Biology / Photosynthesis) === Title: Photosynthesis Fundamentals Subject: Biology Topic: Photosynthesis Instructor: Prof."', '["SOURCE", "Photosynthesis", "Fundamentals", "Biology"]', 'SOURCE', 'Based on the notes: "=== SOURCE: Photosynthesis Fundamentals (Biology / Photosynthesis) === Title: Photosynthesis Fundamentals Subject: Biology Topic: Photosynthesis Instructor: Prof."', 0, 23),
(142, 'true_false', 'True or False: It is NOT the case that: Santos School Year: 2024-2025 Description: How plants convert light into chemical energy.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 23),
(143, 'short_answer', 'In your own words, explain: "Notes: Photosynthesis converts light energy into chemical energy stored in glucose."', '[]', 'Notes: Photosynthesis converts light energy into chemical energy stored in glucose.', 'Compare your answer against the reference statement above.', 2, 23),
(144, 'essay', 'Discuss the significance of the following concept and give an example: "Chlorophyll absorbs sunlight inside the chloroplasts of plant cells."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 23),
(145, 'mcq', 'Which term best completes the statement? "_____ dioxide enters through the stomata while water is absorbed by the roots."', '["Carbon", "SOURCE", "Photosynthesis", "Fundamentals"]', 'Carbon', 'Based on the notes: "Carbon dioxide enters through the stomata while water is absorbed by the roots."', 4, 23),
(146, 'true_false', 'True or False: It is NOT the case that: The light-dependent reactions produce ATP and NADPH in the thylakoid membranes.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 5, 23),
(147, 'short_answer', 'In your own words, explain: "The Calvin cycle fixes carbon dioxide into sugar in the stroma of the chloroplast."', '[]', 'The Calvin cycle fixes carbon dioxide into sugar in the stroma of the chloroplast.', 'Compare your answer against the reference statement above.', 6, 23),
(148, 'essay', 'Discuss the significance of the following concept and give an example: "Oxygen is released as a byproduct that most living organisms depend on for respiration."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 7, 23),
(149, 'mcq', 'Which term best completes the statement? "=== _____: Mitosis and Cell Division (Biology / Mitosis) === Title: Mitosis and Cell Division Subject: Biology Topic: Mitosis Instructor: Prof."', '["SOURCE", "Photosynthesis", "Fundamentals", "Biology"]', 'SOURCE', 'Based on the notes: "=== SOURCE: Mitosis and Cell Division (Biology / Mitosis) === Title: Mitosis and Cell Division Subject: Biology Topic: Mitosis Instructor: Prof."', 8, 23),
(150, 'true_false', 'True or False: It is NOT the case that: Santos School Year: 2024-2025 Description: Stages of mitosis and why they matter.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 9, 23),
(151, 'short_answer', 'In your own words, explain: "Notes: Mitosis produces two genetically identical daughter cells from one parent cell."', '[]', 'Notes: Mitosis produces two genetically identical daughter cells from one parent cell.', 'Compare your answer against the reference statement above.', 10, 23),
(152, 'essay', 'Discuss the significance of the following concept and give an example: "During prophase, chromatin condenses into visible chromosomes and the spindle forms."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 11, 23),
(153, 'mcq', 'Which term best completes the statement? "In _____, chromosomes line up along the equatorial plate of the cell."', '["metaphase", "SOURCE", "Photosynthesis", "Fundamentals"]', 'metaphase', 'Based on the notes: "In metaphase, chromosomes line up along the equatorial plate of the cell."', 12, 23),
(154, 'true_false', 'True or False: It is NOT the case that: Sister chromatids separate and move to opposite poles during anaphase.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 13, 23),
(155, 'short_answer', 'In your own words, explain: "Telophase reforms the nuclear envelope around each set of chromosomes."', '[]', 'Telophase reforms the nuclear envelope around each set of chromosomes.', 'Compare your answer against the reference statement above.', 14, 23),
(156, 'essay', 'Discuss the significance of the following concept and give an example: "Cytokinesis then divides the cytoplasm to complete the process of cell division."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 15, 23),
(157, 'mcq', 'Which term best completes the statement? "=== _____: Human Digestive System Overview (Biology / Digestion) === Title: Human Digestive System Overview Subject: Biology Topic: Digestion Instructor: Prof."', '["SOURCE", "Photosynthesis", "Fundamentals", "Biology"]', 'SOURCE', 'Based on the notes: "=== SOURCE: Human Digestive System Overview (Biology / Digestion) === Title: Human Digestive System Overview Subject: Biology Topic: Digestion Instructor: Prof."', 16, 23),
(158, 'true_false', 'True or False: It is NOT the case that: Santos School Year: 2024-2025 Description: Organs and enzymes of digestion.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 17, 23),
(159, 'short_answer', 'In your own words, explain: "Notes: Digestion mechanically and chemically breaks food into absorbable nutrients."', '[]', 'Notes: Digestion mechanically and chemically breaks food into absorbable nutrients.', 'Compare your answer against the reference statement above.', 18, 23),
(160, 'essay', 'Discuss the significance of the following concept and give an example: "Salivary amylase in the mouth begins the chemical digestion of starch."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 19, 23),
(161, 'mcq', 'Which term best completes the statement? "=== _____: SDLC Overview for Capstone (IT Capstone / SDLC) === Title: SDLC Overview for Capstone Subject: IT Capstone Topic: SDLC Instructor: Prof."', '["SOURCE", "Overview", "Capstone", "Title"]', 'SOURCE', 'Based on the notes: "=== SOURCE: SDLC Overview for Capstone (IT Capstone / SDLC) === Title: SDLC Overview for Capstone Subject: IT Capstone Topic: SDLC Instructor: Prof."', 0, 24),
(162, 'true_false', 'True or False: It is NOT the case that: Cruz School Year: 2024-2025 Description: Planning through maintenance in software projects.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 24),
(163, 'short_answer', 'In your own words, explain: "Notes: The software development life cycle organizes work from planning through maintenance."', '[]', 'Notes: The software development life cycle organizes work from planning through maintenance.', 'Compare your answer against the reference statement above.', 2, 24),
(164, 'essay', 'Discuss the significance of the following concept and give an example: "Requirements gathering captures what stakeholders need the system to accomplish."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 24),
(165, 'mcq', 'Which term best completes the statement? "_____ design translates requirements into architecture, modules, and data models."', '["System", "SOURCE", "Overview", "Capstone"]', 'System', 'Based on the notes: "System design translates requirements into architecture, modules, and data models."', 4, 24),
(166, 'true_false', 'True or False: It is NOT the case that: Implementation writes and reviews code according to the approved technical design.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 5, 24),
(167, 'short_answer', 'In your own words, explain: "Testing verifies that each feature meets its acceptance criteria before release."', '[]', 'Testing verifies that each feature meets its acceptance criteria before release.', 'Compare your answer against the reference statement above.', 6, 24),
(168, 'essay', 'Discuss the significance of the following concept and give an example: "Deployment and maintenance deliver the system and fix issues discovered in production."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 7, 24),
(169, 'mcq', 'Which term best completes the statement? "=== _____: Database Normalization Basics (IT Capstone / Normalization) === Title: Database Normalization Basics Subject: IT Capstone Topic: Normalization Instructor: Prof."', '["SOURCE", "Overview", "Capstone", "Title"]', 'SOURCE', 'Based on the notes: "=== SOURCE: Database Normalization Basics (IT Capstone / Normalization) === Title: Database Normalization Basics Subject: IT Capstone Topic: Normalization Instructor: Prof."', 8, 24),
(170, 'true_false', 'True or False: It is NOT the case that: Cruz School Year: 2024-2025 Description: First through third normal forms with examples.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 9, 24),
(171, 'short_answer', 'In your own words, explain: "Notes: Normalization organizes relational tables to reduce redundancy and anomalies."', '[]', 'Notes: Normalization organizes relational tables to reduce redundancy and anomalies.', 'Compare your answer against the reference statement above.', 10, 24),
(172, 'essay', 'Discuss the significance of the following concept and give an example: "First normal form requires atomic values with no repeating groups in any row."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 11, 24),
(173, 'mcq', 'Which term best completes the statement? "_____ normal form removes partial dependencies on only part of a composite key."', '["Second", "SOURCE", "Overview", "Capstone"]', 'Second', 'Based on the notes: "Second normal form removes partial dependencies on only part of a composite key."', 12, 24),
(174, 'true_false', 'True or False: It is NOT the case that: Third normal form eliminates transitive dependencies between non-key attributes.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 13, 24),
(175, 'short_answer', 'In your own words, explain: "A primary key uniquely identifies each row while foreign keys link related tables."', '[]', 'A primary key uniquely identifies each row while foreign keys link related tables.', 'Compare your answer against the reference statement above.', 14, 24),
(176, 'essay', 'Discuss the significance of the following concept and give an example: "Denormalization is sometimes used to improve read performance for reporting queries."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 15, 24),
(177, 'mcq', 'Which term best completes the statement? "=== _____: Agile Scrum in Student Teams (IT Capstone / Scrum) === Title: Agile Scrum in Student Teams Subject: IT Capstone Topic: Scrum Instructor: Prof."', '["SOURCE", "Overview", "Capstone", "Title"]', 'SOURCE', 'Based on the notes: "=== SOURCE: Agile Scrum in Student Teams (IT Capstone / Scrum) === Title: Agile Scrum in Student Teams Subject: IT Capstone Topic: Scrum Instructor: Prof."', 16, 24),
(178, 'true_false', 'True or False: It is NOT the case that: Cruz School Year: 2024-2025 Description: Sprints, roles, and ceremonies that work for class projects.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 17, 24),
(179, 'short_answer', 'In your own words, explain: "Notes: Scrum divides capstone work into short sprints that each deliver a usable increment."', '[]', 'Notes: Scrum divides capstone work into short sprints that each deliver a usable increment.', 'Compare your answer against the reference statement above.', 18, 24),
(180, 'essay', 'Discuss the significance of the following concept and give an example: "The product owner prioritizes the backlog by value to the users of the system."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 19, 24),
(181, 'mcq', 'Which term best completes the statement? "_____: SDLC Overview for Capstone Subject: IT Capstone Topic: SDLC Instructor: Prof."', '["Title", "Overview", "Capstone", "Subject"]', 'Title', 'Based on the notes: "Title: SDLC Overview for Capstone Subject: IT Capstone Topic: SDLC Instructor: Prof."', 0, 25),
(182, 'mcq', 'Which term best completes the statement? "Cruz _____ Year: 2024-2025 Description: Planning through maintenance in software projects."', '["Title", "Overview", "Capstone", "School"]', 'School', 'Based on the notes: "Cruz School Year: 2024-2025 Description: Planning through maintenance in software projects."', 1, 25),
(183, 'mcq', 'Which term best completes the statement? "_____: The software development life cycle organizes work from planning through maintenance."', '["Notes", "Title", "Overview", "Capstone"]', 'Notes', 'Based on the notes: "Notes: The software development life cycle organizes work from planning through maintenance."', 2, 25),
(184, 'mcq', 'Which term best completes the statement? "_____ gathering captures what stakeholders need the system to accomplish."', '["Title", "Overview", "Capstone", "Requirements"]', 'Requirements', 'Based on the notes: "Requirements gathering captures what stakeholders need the system to accomplish."', 3, 25),
(185, 'mcq', 'Which term best completes the statement? "_____ design translates requirements into architecture, modules, and data models."', '["System", "Title", "Overview", "Capstone"]', 'System', 'Based on the notes: "System design translates requirements into architecture, modules, and data models."', 4, 25),
(186, 'mcq', 'Which term best completes the statement? "_____ writes and reviews code according to the approved technical design."', '["Title", "Overview", "Capstone", "Implementation"]', 'Implementation', 'Based on the notes: "Implementation writes and reviews code according to the approved technical design."', 5, 25),
(187, 'mcq', 'Which term best completes the statement? "_____ verifies that each feature meets its acceptance criteria before release."', '["Testing", "Title", "Overview", "Capstone"]', 'Testing', 'Based on the notes: "Testing verifies that each feature meets its acceptance criteria before release."', 6, 25),
(188, 'mcq', 'Which term best completes the statement? "_____ and maintenance deliver the system and fix issues discovered in production."', '["Title", "Overview", "Capstone", "Deployment"]', 'Deployment', 'Based on the notes: "Deployment and maintenance deliver the system and fix issues discovered in production."', 7, 25),
(189, 'mcq', 'Which term best completes the statement? "_____: SDLC Overview for Capstone Subject: IT Capstone Topic: SDLC Instructor: Prof."', '["Title", "Overview", "Capstone", "Subject"]', 'Title', 'Based on the notes: "Title: SDLC Overview for Capstone Subject: IT Capstone Topic: SDLC Instructor: Prof."', 8, 25),
(190, 'mcq', 'Which term best completes the statement? "Cruz _____ Year: 2024-2025 Description: Planning through maintenance in software projects."', '["Title", "Overview", "Capstone", "School"]', 'School', 'Based on the notes: "Cruz School Year: 2024-2025 Description: Planning through maintenance in software projects."', 9, 25);
INSERT INTO `notes_question` (`id`, `question_type`, `question_text`, `options`, `correct_answer`, `explanation`, `order`, `quiz_id`) VALUES
(191, 'mcq', 'Which term best completes the statement? "_____: The software development life cycle organizes work from planning through maintenance."', '["Notes", "Title", "Overview", "Capstone"]', 'Notes', 'Based on the notes: "Notes: The software development life cycle organizes work from planning through maintenance."', 10, 25),
(192, 'mcq', 'Which term best completes the statement? "_____ gathering captures what stakeholders need the system to accomplish."', '["Title", "Overview", "Capstone", "Requirements"]', 'Requirements', 'Based on the notes: "Requirements gathering captures what stakeholders need the system to accomplish."', 11, 25),
(193, 'mcq', 'Which term best completes the statement? "_____ design translates requirements into architecture, modules, and data models."', '["System", "Title", "Overview", "Capstone"]', 'System', 'Based on the notes: "System design translates requirements into architecture, modules, and data models."', 12, 25),
(194, 'mcq', 'Which term best completes the statement? "_____ writes and reviews code according to the approved technical design."', '["Title", "Overview", "Capstone", "Implementation"]', 'Implementation', 'Based on the notes: "Implementation writes and reviews code according to the approved technical design."', 13, 25),
(195, 'mcq', 'Which term best completes the statement? "_____ verifies that each feature meets its acceptance criteria before release."', '["Testing", "Title", "Overview", "Capstone"]', 'Testing', 'Based on the notes: "Testing verifies that each feature meets its acceptance criteria before release."', 14, 25),
(196, 'mcq', 'Which term best completes the statement? "_____ and maintenance deliver the system and fix issues discovered in production."', '["Title", "Overview", "Capstone", "Deployment"]', 'Deployment', 'Based on the notes: "Deployment and maintenance deliver the system and fix issues discovered in production."', 15, 25),
(197, 'mcq', 'Which term best completes the statement? "_____: SDLC Overview for Capstone Subject: IT Capstone Topic: SDLC Instructor: Prof."', '["Title", "Overview", "Capstone", "Subject"]', 'Title', 'Based on the notes: "Title: SDLC Overview for Capstone Subject: IT Capstone Topic: SDLC Instructor: Prof."', 16, 25),
(198, 'mcq', 'Which term best completes the statement? "Cruz _____ Year: 2024-2025 Description: Planning through maintenance in software projects."', '["Title", "Overview", "Capstone", "School"]', 'School', 'Based on the notes: "Cruz School Year: 2024-2025 Description: Planning through maintenance in software projects."', 17, 25),
(199, 'mcq', 'Which term best completes the statement? "_____: The software development life cycle organizes work from planning through maintenance."', '["Notes", "Title", "Overview", "Capstone"]', 'Notes', 'Based on the notes: "Notes: The software development life cycle organizes work from planning through maintenance."', 18, 25),
(200, 'mcq', 'Which term best completes the statement? "_____ gathering captures what stakeholders need the system to accomplish."', '["Title", "Overview", "Capstone", "Requirements"]', 'Requirements', 'Based on the notes: "Requirements gathering captures what stakeholders need the system to accomplish."', 19, 25),
(201, 'mcq', 'Which term best completes the statement? "_____: SDLC Overview for Capstone Subject: IT Capstone Topic: SDLC Instructor: Prof."', '["Title", "Overview", "Capstone", "Subject"]', 'Title', 'Based on the notes: "Title: SDLC Overview for Capstone Subject: IT Capstone Topic: SDLC Instructor: Prof."', 0, 26),
(202, 'mcq', 'Which term best completes the statement? "Cruz _____ Year: 2024-2025 Description: Planning through maintenance in software projects."', '["Title", "Overview", "Capstone", "School"]', 'School', 'Based on the notes: "Cruz School Year: 2024-2025 Description: Planning through maintenance in software projects."', 1, 26),
(203, 'mcq', 'Which term best completes the statement? "_____: The software development life cycle organizes work from planning through maintenance."', '["Notes", "Title", "Overview", "Capstone"]', 'Notes', 'Based on the notes: "Notes: The software development life cycle organizes work from planning through maintenance."', 2, 26),
(204, 'mcq', 'Which term best completes the statement? "=== _____: The Philippine Revolution (Philippine History / Revolution) === Title: The Philippine Revolution Subject: Philippine History Topic: Revolution Instructor: Prof."', '["SOURCE", "Philippine", "Revolution", "History"]', 'SOURCE', 'Based on the notes: "=== SOURCE: The Philippine Revolution (Philippine History / Revolution) === Title: The Philippine Revolution Subject: Philippine History Topic: Revolution Instructor: Prof."', 0, 27),
(205, 'mcq', 'Which term best completes the statement? "_____ School Year: 2024-2025 Description: Causes and key events of the 1896 revolution."', '["SOURCE", "Philippine", "Revolution", "Aquino"]', 'Aquino', 'Based on the notes: "Aquino School Year: 2024-2025 Description: Causes and key events of the 1896 revolution."', 1, 27),
(206, 'mcq', 'Which term best completes the statement? "_____: The Philippine Revolution began in 1896 against more than three centuries of Spanish rule."', '["Notes", "SOURCE", "Philippine", "Revolution"]', 'Notes', 'Based on the notes: "Notes: The Philippine Revolution began in 1896 against more than three centuries of Spanish rule."', 2, 27),
(207, 'mcq', 'Which term best completes the statement? "The _____ was a secret society founded by Andres Bonifacio to organize the uprising."', '["SOURCE", "Philippine", "Revolution", "Katipunan"]', 'Katipunan', 'Based on the notes: "The Katipunan was a secret society founded by Andres Bonifacio to organize the uprising."', 3, 27),
(208, 'mcq', 'Which term best completes the statement? "The Cry of _____ Lawin symbolized the start of open revolt in August 1896."', '["Pugad", "SOURCE", "Philippine", "Revolution"]', 'Pugad', 'Based on the notes: "The Cry of Pugad Lawin symbolized the start of open revolt in August 1896."', 4, 27),
(209, 'mcq', 'Which term best completes the statement? "Jose _____ advocated reforms through education before his execution in December 1896."', '["SOURCE", "Philippine", "Revolution", "Rizal"]', 'Rizal', 'Based on the notes: "Jose Rizal advocated reforms through education before his execution in December 1896."', 5, 27),
(210, 'mcq', 'Which term best completes the statement? "_____ Aguinaldo later led revolutionary forces and declared independence in June 1898."', '["Emilio", "SOURCE", "Philippine", "Revolution"]', 'Emilio', 'Based on the notes: "Emilio Aguinaldo later led revolutionary forces and declared independence in June 1898."', 6, 27),
(211, 'mcq', 'Which term best completes the statement? "The _____ shifted into resistance against the United States after the Treaty of Paris."', '["SOURCE", "Philippine", "History", "revolution"]', 'revolution', 'Based on the notes: "The revolution shifted into resistance against the United States after the Treaty of Paris."', 7, 27),
(212, 'mcq', 'Which term best completes the statement? "=== _____: Basic Probability Rules (Mathematics / Probability) === Title: Basic Probability Rules Subject: Mathematics Topic: Probability Instructor: Prof."', '["SOURCE", "Philippine", "Revolution", "History"]', 'SOURCE', 'Based on the notes: "=== SOURCE: Basic Probability Rules (Mathematics / Probability) === Title: Basic Probability Rules Subject: Mathematics Topic: Probability Instructor: Prof."', 8, 27),
(213, 'mcq', 'Which term best completes the statement? "_____ School Year: 2024-2025 Description: Sample spaces, independent events, expected value."', '["SOURCE", "Philippine", "Revolution", "Reyes"]', 'Reyes', 'Based on the notes: "Reyes School Year: 2024-2025 Description: Sample spaces, independent events, expected value."', 9, 27),
(214, 'mcq', 'What is the primary role of the product owner in Scrum?', '["To facilitate daily standups", "To prioritize the backlog", "To remove blockers", "To demonstrate completed features"]', 'To prioritize the backlog', 'The product owner is responsible for prioritizing the backlog by value to the users of the system.', 0, 28),
(215, 'true_false', 'In Scrum, the scrum master is responsible for creating the product backlog.', '[]', 'False', 'The scrum master helps remove blockers but does not create the product backlog; that is the responsibility of the product owner.', 1, 28),
(216, 'short_answer', 'What does the first normal form (1NF) require in a relational table?', '[]', 'Atomic values with no repeating groups in any row.', 'First normal form requires that all values in the table are atomic and that there are no repeating groups.', 2, 28),
(217, 'essay', 'Explain the importance of retrospectives in Scrum.', '[]', 'Retrospectives help teams improve collaboration and processes for future sprints.', 'Retrospectives provide an opportunity for team members to discuss what went well and what can be improved before the next sprint.', 3, 28),
(218, 'mcq', 'Which of the following is NOT a phase in the SDLC?', '["Requirements Gathering", "Implementation", "Deployment", "Normalization"]', 'Normalization', 'Normalization is a process related to database design and not a phase in the software development life cycle.', 4, 28),
(219, 'true_false', 'Denormalization is used to reduce redundancy in database design.', '[]', 'False', 'Denormalization is sometimes used to improve read performance, not to reduce redundancy.', 5, 28),
(220, 'short_answer', 'What does the third normal form (3NF) eliminate?', '[]', 'Transitive dependencies between non-key attributes.', 'Third normal form eliminates transitive dependencies to ensure that non-key attributes are only dependent on the primary key.', 6, 28),
(221, 'essay', 'Describe the role of testing in the software development life cycle.', '[]', 'Testing verifies that each feature meets its acceptance criteria before release.', 'Testing is crucial in the SDLC as it ensures that the developed features function as intended and meet the requirements set forth.', 7, 28),
(222, 'mcq', 'What is the purpose of daily standups in Scrum?', '["To plan the next sprint", "To review completed features", "To keep team members aware of progress and impediments", "To gather requirements from stakeholders"]', 'To keep team members aware of progress and impediments', 'Daily standups provide a platform for team members to share what they did yesterday, what they will do today, and any impediments they face.', 8, 28),
(225, 'mcq', 'Which term best completes the statement? "_____: Agile Scrum in Student Teams Subject: IT Capstone Topic: Scrum Instructor: Prof."', '["Title", "Agile", "Scrum", "Student"]', 'Title', 'Based on the notes: "Title: Agile Scrum in Student Teams Subject: IT Capstone Topic: Scrum Instructor: Prof."', 0, 30),
(226, 'true_false', 'True or False: It is NOT the case that: Cruz School Year: 2024-2025 Description: Sprints, roles, and ceremonies that work for class projects.', '["True", "False"]', 'False', 'Review the notes — the original statement was altered with a negation.', 1, 30),
(227, 'short_answer', 'In your own words, explain: "Notes: Scrum divides capstone work into short sprints that each deliver a usable increment."', '[]', 'Notes: Scrum divides capstone work into short sprints that each deliver a usable increment.', 'Compare your answer against the reference statement above.', 2, 30),
(228, 'essay', 'Discuss the significance of the following concept and give an example: "The product owner prioritizes the backlog by value to the users of the system."', '[]', '', 'A strong answer defines the concept, explains why it matters, and gives an example.', 3, 30),
(229, 'mcq', 'Which term best completes the statement? "The _____ master removes blockers so the team can sustain steady progress."', '["scrum", "Title", "Agile", "Student"]', 'scrum', 'Based on the notes: "The scrum master removes blockers so the team can sustain steady progress."', 4, 30);

-- notes_quizattempt: 2 rows
INSERT INTO `notes_quizattempt` (`id`, `score`, `total`, `percentage`, `answers`, `submitted_at`, `quiz_id`, `taker_id`) VALUES
(2, 0, 10, 0.0, '{"204": "Philippine", "205": "SOURCE", "206": "Philippine", "207": "SOURCE", "208": "SOURCE", "209": "SOURCE", "210": "Philippine", "211": "Philippine", "212": "Philippine", "213": "Philippine"}', '2026-10-14 02:46:02.783005', 27, 4),
(3, 0, 5, 0.0, '{"214": "To facilitate daily standups", "215": "True", "216": "dsdsd", "217": "dsds", "218": "Implementation", "219": "True", "220": "dsdsd", "221": "sdsds", "222": "To plan the next sprint"}', '2026-10-14 02:47:39.861506', 28, 4);

SET FOREIGN_KEY_CHECKS = 1;
