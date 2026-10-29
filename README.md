# StudyShare — Notes Sharing with AI-Powered Quiz & Exam Generation

A Django web app where students upload and organize study notes by
**subject, instructor, topic, and school year**, search and rate useful notes,
and generate quiz/exam questions with AI. Guests can use the full study
experience without signing in; creating an account keeps their work.
Includes role-based access (Student / Instructor-Moderator / Administrator),
quiz taking with auto-scoring, progress tracking, content moderation, and
system analytics.

## Members

- Andy Coriantumr P. Peduhan
- Rino V. Montalvo
- Jerald C. Macasling

## Features

- **Notes sharing** — upload (pdf/docx/txt/md/images) or paste text, organized by subject, instructor, topic, school year; search, filter chips, sort (newest/oldest/top-rated)
- **Guest-first access** — open the app and start studying immediately; a temporary guest account is created behind the scenes, and signing in or registering keeps the chats, notes, and quiz attempts you already made
- **Ratings** — 1–5 stars, one per user per note (re-rate updates)
- **AI quiz/exam generator** — per-note quizzes plus multi-note automated exams with printable paper (Name/Date/Score boxes) and instructor answer key; providers: OpenAI, Gemini, OpenRouter, offline local fallback
- **AI study chat** — dashboard prompt starts a saved conversation, follows up with context from previous turns, and searches StudyShare notes for relevant excerpts; uploading a file automatically generates an answerable practice quiz from its contents (choose 1–50 questions), then shows the score and answer key after submission and saves a viewable, printable attempt to My Quizzes and My Progress; uploaded files appear in Uploaded Notes with private preview, download, and delete actions; chat history appears in the sidebar and replies use the same providers (offline note-summary fallback)
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

Open http://127.0.0.1:8000/ and start studying as a guest. To try a role-based
account, sign in with one of the demo accounts:

| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `admin12345` |
| Instructor | `instructor` | `ins12345` |
| Student | `student` | `stu12345` |

Guest chats and quizzes are temporary. Registering upgrades the same guest
account in place, while signing in moves guest-owned work into the existing
account. Abandoned guest accounts can be cleaned up with
`python manage.py cleanup_guests --days 30`.

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
python manage.py cleanup_guests --days 30      # remove abandoned guest accounts
python -m pytest -q                            # test suite
```

## Docs

- `SQL/studyshare_schema.sql` — SQLite schema + data (all 10 tables with INSERTs; import with sqlite3, NOT phpMyAdmin)
- `SQL/studyshare_schema_mysql.sql` — MySQL/MariaDB schema + data (all 10 tables with INSERTs; phpMyAdmin import)

## BSIT Class Project Concept Paper

# STUDYSHARE: A WEB-BASED STUDY MATERIAL SHARING AND AI-POWERED QUIZ AND EXAM GENERATION SYSTEM

**Proponents:** Andy Coriantumr P. Peduhan, Rino V. Montalvo, and Jerald Macasling

**BSIT Class Project Concept Paper**

### INTRODUCTION

#### Background of the Project

College students use lecture notes, handouts, and other study materials to review course topics and prepare for assessments. These resources are often distributed through separate platforms, personal devices, or informal group chats. As a result, students may have difficulty finding relevant materials, identifying the subject or topic they cover, and returning to resources shared earlier. Instructors also spend time preparing practice questions, while students may have limited access to immediate practice feedback and a consolidated view of their quiz performance.

StudyShare is a web-based learning support system that will bring organized study materials and AI-assisted study activities into one platform. Users will be able to upload and browse resources organized by subject, instructor, topic, and school year. The system will support AI study chat, generation of practice quizzes and exams from study materials, answer checking, and review of saved attempts and progress. Access roles and content moderation will support responsible sharing within an academic setting.

A working StudyShare application is already represented in the project code. The project work will refine and verify the core workflows, document the system scope, and evaluate usability with intended users. The AI functions will use an external provider when configured and will provide local fallback behavior for supported tasks. Formal user acceptance testing will be conducted as part of the project evaluation; no evaluation results are presented in this concept paper.

#### Statement of the Problem or Project Objectives

The project will address the difficulty of organizing and retrieving course study materials, the time required to prepare practice questions, and the lack of a unified way for students to review quiz attempts and learning progress. The main objective will be to refine and evaluate StudyShare as a web-based platform for study-material sharing and AI-assisted quiz and exam generation.

Specifically, the project will aim to:

1. Refine a web-based repository for uploading, organizing, searching, and browsing study materials by subject, instructor, topic, and school year.
2. Verify AI-assisted study chat and quiz-generation workflows that use uploaded materials or available notes as learning context.
3. Provide practice-quiz and exam workflows with answer submission, automatic scoring where supported, and review of saved attempts and progress.
4. Maintain role-based access and content-review tools for students, instructors or moderators, and administrators.
5. Conduct functional and user acceptance testing to assess usability, reliability, and alignment with the needs of intended users.

#### Significance of the Project

**Students:** StudyShare will help students locate and organize course resources, practice with generated questions, receive feedback on supported question types, and review their saved quiz results and progress.

**Instructors and moderators:** The system will provide tools to contribute or review shared learning materials and will support preparation of practice activities. Moderation features will help manage the quality and appropriateness of shared content.

**Academic administrators:** The platform will provide role-based access and activity information that can support oversight of shared resources and the use of learning activities within the system.

**Future researchers and students:** The project will provide a reference implementation for future work on web-based learning-resource management and AI-supported study tools. It may also serve as a basis for further evaluation of responsible AI use in educational settings.

#### Alignment with Institutional Research Agenda and Sustainable Development Goals

**Institutional Research Agenda Alignment:** The project will support an institutional research priority concerning Information Technology and educational innovation by applying web technologies and AI-assisted functions to organize learning resources and practice activities. The proponents will map this focus to the exact priority-area wording in the institution's currently approved research agenda before final submission.

**Sustainable Development Goal Alignment:** The project will support SDG 4 (Quality Education) by improving access to organized learning resources and practice opportunities. It will also support SDG 9 (Industry, Innovation, and Infrastructure) through the development and evaluation of a digital learning-support platform. These contributions will be limited to the system's intended educational use and will not be presented as a substitute for formal instruction.

### SCOPE AND LIMITATIONS

#### System Scope & Technical Architecture

**Setting and coverage:** The project will focus on a web-based study support platform for students and academic personnel in a college or similar learning environment. Its coverage will include study-resource sharing, AI-assisted study chat and question generation, quiz participation, progress review, and administration of user access and shared content.

**Core modules:** The system will include user accounts and role management; study-note upload and organization; browsing and search; content ratings and moderation; AI study chat; quiz and exam generation; answer submission and scoring for supported quiz types; saved quiz attempts and progress; and administrative monitoring features.

**Technology stack:** The application will use Python and Django for backend processing and SQLite for local development. The project configuration will also support an alternative relational database deployment. The user interface will use HTML, CSS, JavaScript, and the existing Bootstrap/Tabler components. AI-enabled features will connect to supported providers such as Gemini, OpenAI, or OpenRouter when configured, with local fallback behavior for selected functions.

**Target users:** The intended users will include students who share and use study materials, instructors or moderators who contribute to or review content, and administrators who manage accounts and system settings. Guest access may be used for initial study activities; account registration or sign-in will be used to retain work associated with a user account.

**Evaluation:** The project will verify the main user workflows and will conduct user acceptance testing with representative students and academic personnel. Evaluation will focus on functional correctness, usability, and reliability. Testing outcomes will be reported separately after the evaluation has been completed.

**Limitations:** AI-generated responses and questions may contain errors and will require user or instructor review. AI-provider features will depend on provider availability, configuration, and network access; local fallback features may be more limited. Text extraction may not work for scanned or image-only documents. The project will not include institutional student-information-system or learning-management-system integration, automated grading of every open-ended response, or replacement of instructor-led teaching and official assessment processes.
