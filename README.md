# StudyShare — Notes Sharing with AI-Powered Quiz & Exam Generation

A Django web app where students upload and organize study notes by
**subject, instructor, topic, and school year**, search and rate useful notes,
and generate quiz/exam questions with AI. Includes role-based access
(Student / Instructor-Moderator / Administrator), quiz taking with auto-scoring,
progress tracking, content moderation, and system analytics.

## Members

- Andy Coriantumr P. Peduhan
- Rino V. Montalvo
- Jerald C. Macasling

## Features

- **Notes sharing** — upload (pdf/docx/txt/md/images) or paste text, organized by subject, instructor, topic, school year; search, filter chips, sort (newest/oldest/top-rated)
- **Ratings** — 1–5 stars, one per user per note (re-rate updates)
- **AI quiz/exam generator** — per-note quizzes plus multi-note automated exams with printable paper (Name/Date/Score boxes) and instructor answer key; providers: OpenAI, Gemini, OpenRouter, offline local fallback
- **Quiz taking & scores** — auto-graded MCQ/True-False, attempt review, per-student progress page
- **Roles** — Student (default), Instructor/Moderator (review queue, remove content, manage subjects, monitor reports), Administrator (manage users/roles, analytics)
- **Reports & moderation** — report inappropriate/incorrect notes; approve/reject/remove flow
- **Analytics** — users by role, notes by status/subject, attempts charts

## Tech stack

Django 5.2, SQLite (dev) / MySQL optional, Tabler + Bootstrap 5 (no build step),
ApexCharts (analytics), stdlib-only AI clients (no extra dependencies).

## Quick start

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_examples   # demo subjects, notes, quizzes, exams
python manage.py runserver 8000
```

Open http://127.0.0.1:8000/ and log in:

| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `admin12345` |
| Instructor | `instructor` | `ins12345` |
| Student | `student` | `stu12345` |

## AI providers (optional)

Without keys the built-in offline generator is used. To enable cloud AI,
set env vars before `runserver` (never commit keys):

```powershell
$env:OPENAI_API_KEY="sk-..."
$env:GEMINI_API_KEY="AIza..."
$env:OPENROUTER_API_KEY="sk-or-..."
```

Auto mode tries OpenRouter → OpenAI → Gemini, then falls back to local.

## Useful commands

```bash
python manage.py seed_examples                 # idempotent demo data
python manage.py auto_generate_quizzes --limit 10 --provider auto
python -m pytest -q                            # test suite
```

## Docs

- `SQL/studyshare_schema.sql` — database schema, SQLite dialect
- `SQL/studyshare_schema_mysql.sql` — same schema for MySQL/MariaDB (phpMyAdmin import)
