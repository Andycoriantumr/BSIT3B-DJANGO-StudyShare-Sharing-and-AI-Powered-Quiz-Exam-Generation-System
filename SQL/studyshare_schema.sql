-- StudyShare schema (generated from live db.sqlite3 on 2026-10-14)
-- SQLite dialect. Tables: auth_user, tblinfo, users_profile, notes_subject, notes_note, notes_noterating, notes_notereport, notes_quizset, notes_question, notes_quizattempt
-- Legacy tbl* tables from bsitcrud.sql are intentionally excluded.
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE "auth_user" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "password" varchar(128) NOT NULL, "last_login" datetime NULL, "is_superuser" bool NOT NULL, "username" varchar(150) NOT NULL UNIQUE, "last_name" varchar(150) NOT NULL, "email" varchar(254) NOT NULL, "is_staff" bool NOT NULL, "is_active" bool NOT NULL, "date_joined" datetime NOT NULL, "first_name" varchar(150) NOT NULL);
CREATE TABLE "tblinfo" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(255) NOT NULL, "age" integer unsigned NOT NULL CHECK ("age" >= 0), "address" varchar(255) NOT NULL, "email" varchar(255) NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "user_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "users_profile" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "role" varchar(20) NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "user_id" integer NOT NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "notes_subject" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(120) NOT NULL UNIQUE, "code" varchar(30) NOT NULL, "description" text NOT NULL, "is_active" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "created_by_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "notes_note" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "title" varchar(255) NOT NULL, "subject" varchar(120) NOT NULL, "instructor" varchar(120) NOT NULL, "topic" varchar(255) NOT NULL, "school_year" varchar(30) NOT NULL, "description" text NOT NULL, "content" text NOT NULL, "file" varchar(100) NULL, "is_public" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "uploaded_by_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "status" varchar(20) NOT NULL);
CREATE TABLE "notes_noterating" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "score" smallint unsigned NOT NULL CHECK ("score" >= 0), "comment" text NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "note_id" bigint NOT NULL REFERENCES "notes_note" ("id") DEFERRABLE INITIALLY DEFERRED, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_note_user_rating" UNIQUE ("note_id", "user_id"));
CREATE TABLE "notes_notereport" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "reason" varchar(20) NOT NULL, "details" text NOT NULL, "status" varchar(20) NOT NULL, "reviewed_at" datetime NULL, "created_at" datetime NOT NULL, "note_id" bigint NOT NULL REFERENCES "notes_note" ("id") DEFERRABLE INITIALLY DEFERRED, "reporter_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "reviewed_by_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "notes_quizset" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "title" varchar(255) NOT NULL, "num_questions" smallint unsigned NOT NULL CHECK ("num_questions" >= 0), "question_type" varchar(20) NOT NULL, "provider" varchar(20) NOT NULL, "created_at" datetime NOT NULL, "created_by_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "note_id" bigint NOT NULL REFERENCES "notes_note" ("id") DEFERRABLE INITIALLY DEFERRED, "exam_subject" varchar(120) NOT NULL, "is_exam" bool NOT NULL, "source_note_ids" text NOT NULL CHECK ((JSON_VALID("source_note_ids") OR "source_note_ids" IS NULL)));
CREATE TABLE "notes_question" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "question_type" varchar(20) NOT NULL, "question_text" text NOT NULL, "options" text NOT NULL CHECK ((JSON_VALID("options") OR "options" IS NULL)), "correct_answer" text NOT NULL, "explanation" text NOT NULL, "order" integer unsigned NOT NULL CHECK ("order" >= 0), "quiz_id" bigint NOT NULL REFERENCES "notes_quizset" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "notes_quizattempt" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "score" integer unsigned NOT NULL CHECK ("score" >= 0), "total" integer unsigned NOT NULL CHECK ("total" >= 0), "percentage" real NOT NULL, "answers" text NOT NULL CHECK ((JSON_VALID("answers") OR "answers" IS NULL)), "submitted_at" datetime NOT NULL, "quiz_id" bigint NOT NULL REFERENCES "notes_quizset" ("id") DEFERRABLE INITIALLY DEFERRED, "taker_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE INDEX "tblinfo_user_id_4a36749d" ON "tblinfo" ("user_id");
CREATE INDEX "notes_question_quiz_id_6d386476" ON "notes_question" ("quiz_id");
CREATE INDEX "notes_noterating_note_id_5c63c566" ON "notes_noterating" ("note_id");
CREATE INDEX "notes_noterating_user_id_c19907d5" ON "notes_noterating" ("user_id");
CREATE INDEX "notes_note_subject_0ddaf5eb" ON "notes_note" ("subject");
CREATE INDEX "notes_note_instructor_3d364417" ON "notes_note" ("instructor");
CREATE INDEX "notes_note_topic_f8237e04" ON "notes_note" ("topic");
CREATE INDEX "notes_note_school_year_f076a280" ON "notes_note" ("school_year");
CREATE INDEX "notes_note_uploaded_by_id_6ccfdcce" ON "notes_note" ("uploaded_by_id");
CREATE INDEX "notes_note_subject_bee999_idx" ON "notes_note" ("subject", "school_year");
CREATE INDEX "notes_note_instruc_a6c3d8_idx" ON "notes_note" ("instructor");
CREATE INDEX "notes_note_topic_9e51e1_idx" ON "notes_note" ("topic");
CREATE INDEX "notes_note_status_8ff649_idx" ON "notes_note" ("status");
CREATE INDEX "notes_notereport_note_id_1ab1980f" ON "notes_notereport" ("note_id");
CREATE INDEX "notes_notereport_reporter_id_b4ba3a0a" ON "notes_notereport" ("reporter_id");
CREATE INDEX "notes_notereport_reviewed_by_id_2a21cd5f" ON "notes_notereport" ("reviewed_by_id");
CREATE INDEX "notes_quizattempt_quiz_id_11c28cf1" ON "notes_quizattempt" ("quiz_id");
CREATE INDEX "notes_quizattempt_taker_id_33f9f4af" ON "notes_quizattempt" ("taker_id");
CREATE INDEX "notes_subject_created_by_id_9feef113" ON "notes_subject" ("created_by_id");
CREATE INDEX "notes_quizset_created_by_id_e1f58b26" ON "notes_quizset" ("created_by_id");
CREATE INDEX "notes_quizset_note_id_7f12a044" ON "notes_quizset" ("note_id");
COMMIT;
