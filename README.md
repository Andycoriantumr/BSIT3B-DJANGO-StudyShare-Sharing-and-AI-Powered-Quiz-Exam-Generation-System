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
- **AI study chat** — dashboard prompt starts a saved conversation, follows up with context from previous turns, and searches StudyShare notes for relevant excerpts; chat history appears in the sidebar and replies use the same providers (offline note-summary fallback)
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

Without keys the built-in offline generator is used. The same keys power the
AI study chat; without them, chat replies summarise matching notes instead.
To enable cloud AI, copy `.env.example` to `.env` and fill in at least one key
(never commit `.env` — it is already gitignored):

```powershell
Copy-Item .env.example .env
```

```ini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-flash-latest
# Optional fallbacks
OPENAI_API_KEY=
OPENROUTER_API_KEY=
```

The chat prefers **Gemini → OpenRouter → OpenAI**, then falls back to the
offline note assistant. Set `AI_PROVIDER=gemini` (or another provider) to pin
one explicitly. Gemini requests use the `x-goog-api-key` header and disable
thinking so the full output budget goes to the visible answer. You can also
export the same variables in your shell instead of using `.env`.

## Useful commands

```bash
python manage.py seed_examples                 # idempotent demo data
python manage.py auto_generate_quizzes --limit 10 --provider auto
python -m pytest -q                            # test suite
```

## Docs

- `SQL/studyshare_schema.sql` — SQLite schema + data (all 10 tables with INSERTs; import with sqlite3, NOT phpMyAdmin)
- `SQL/studyshare_schema_mysql.sql` — MySQL/MariaDB schema + data (all 10 tables with INSERTs; phpMyAdmin import)
