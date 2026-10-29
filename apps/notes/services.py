"""Quiz generation service.

Strategy (no extra dependencies, stdlib urllib only):
- provider="auto" (default): try OpenRouter -> OpenAI -> Gemini (whichever has
  an API key configured), then fall back to the deterministic local generator.
- provider="openai" / "gemini" / "openrouter": try that provider, fall back to
  local on any failure so demos never break.
- provider="local": always use the offline generator.

Env / settings keys:
  OPENAI_API_KEY / OPENAI_MODEL (default gpt-4o-mini)
  GEMINI_API_KEY / GEMINI_MODEL (default gemini-flash-latest)
  OPENROUTER_API_KEY / OPENROUTER_MODEL (default openai/gpt-4o-mini)
  OPENROUTER_SITE_URL / OPENROUTER_APP_NAME (optional OpenRouter headers)
"""

import json
import os
import re
import urllib.error
import urllib.request

from django.conf import settings

MAX_SOURCE_CHARS = 12000
GENERIC_DISTRACTORS = [
    'None of the above',
    'All of the above',
    'Insufficient information',
    'Depends on context',
]

VALID_PROVIDERS = ('auto', 'local', 'openai', 'gemini', 'openrouter')


def _output_token_budget(num_questions):
    """Give larger quizzes enough room for their JSON answer."""
    return min(8192, max(2000, int(num_questions) * 180))


def _provider_timeout(num_questions, minimum=40, maximum=60):
    return min(maximum, max(minimum, int(num_questions) * 2))


def _cfg(name, default=''):
    """Read a setting first; only fall back to os.environ when it is absent.

    Settings are populated from the environment (and .env) at startup, so this
    keeps explicit overrides -- including tests -- authoritative.
    """
    value = getattr(settings, name, None)
    if value is None:
        value = os.environ.get(name, '')
    return (value or default).strip()


def get_openai_config():
    return _cfg('OPENAI_API_KEY'), (_cfg('OPENAI_MODEL', 'gpt-4o-mini') or 'gpt-4o-mini')


def get_gemini_config():
    return _cfg('GEMINI_API_KEY'), (_cfg('GEMINI_MODEL', 'gemini-flash-latest') or 'gemini-flash-latest')


def get_openrouter_config():
    return _cfg('OPENROUTER_API_KEY'), (_cfg('OPENROUTER_MODEL', 'openai/gpt-4o-mini') or 'openai/gpt-4o-mini')


def get_note_source_text(note, max_chars=MAX_SOURCE_CHARS):
    """Combine note metadata + text + readable upload into one prompt string."""
    parts = [
        f'Title: {note.title}',
        f'Subject: {note.subject}',
        f'Topic: {note.topic}',
        f'Instructor: {note.instructor}',
        f'School Year: {note.school_year}',
    ]
    if note.description:
        parts.append(f'Description: {note.description}')
    if note.content:
        parts.append(f'Notes:\n{note.content}')
    file_text = _read_upload_text(note)
    if file_text:
        parts.append(f'Uploaded file excerpt:\n{file_text}')
    combined = '\n\n'.join(parts)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + '\n...[truncated]'
    return combined


def _read_upload_text(note):
    if not note.file:
        return ''
    try:
        name = (note.file.name or '').lower()
    except Exception:
        return ''
    try:
        if name.endswith(('.txt', '.md')):
            note.file.open('rb')
            try:
                raw = note.file.read(20000)
            finally:
                note.file.close()
            return raw.decode('utf-8', errors='ignore')[:8000]
        if name.endswith('.pdf'):
            return _read_pdf_text(note)
    except Exception:
        return ''
    return ''


def _read_pdf_text(note):
    """Best-effort PDF text extraction if pypdf/PyPDF2 is installed."""
    text = ''
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader  # type: ignore
        note.file.open('rb')
        try:
            reader = PdfReader(note.file)
            for page in reader.pages[:5]:
                try:
                    text += (page.extract_text() or '') + '\n'
                except Exception:
                    continue
                if len(text) > 8000:
                    break
        finally:
            note.file.close()
    except Exception:
        return ''
    return text[:8000]


def _build_prompt(source_text, num_questions, question_type):
    return (
        'You generate quiz/exam review questions from study notes. '
        f'Return STRICT JSON: a list of {num_questions} objects with keys: '
        'question_type (one of mcq, true_false, short_answer, essay), '
        'question_text, options (array of 4 strings for mcq, else []), '
        'correct_answer, explanation. '
        f'Question mix requested: {question_type}. Keep questions grounded in the notes.\n\n'
        f'NOTES:\n{source_text[:8000]}'
    )


def _parse_json_list(content, num_questions):
    content = (content or '').strip()
    content = re.sub(r'^```(?:json)?\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    parsed = json.loads(content)
    if isinstance(parsed, dict) and 'questions' in parsed:
        parsed = parsed['questions']
    return [_normalize_q(q, i) for i, q in enumerate(parsed[:num_questions])]


def build_exam_source(notes, max_chars=MAX_SOURCE_CHARS):
    """Combine multiple notes into one exam source with a fair per-note budget."""
    notes = list(notes or [])
    if not notes:
        return ''
    per_note = max(500, max_chars // max(1, len(notes)))
    chunks = []
    for note in notes:
        text = get_note_source_text(note, max_chars=per_note)
        chunks.append(f'=== SOURCE: {note.title} ({note.subject} / {note.topic}) ===\n{text}')
    combined = '\n\n'.join(chunks)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + '\n...[truncated]'
    return combined


def generate_quiz(source_text, num_questions=5, question_type='mixed', provider='auto'):
    """Public entry: try cloud provider(s), fall back to local generator."""
    provider = (provider or 'auto').strip().lower()
    if provider not in VALID_PROVIDERS:
        provider = 'auto'
    num_questions = max(1, min(int(num_questions or 5), 50))
    cleaned = (source_text or '').strip()
    if len(cleaned) < 40:
        cleaned = (
            cleaned
            + '\nGeneral study skills: time management, active recall, spaced repetition, '
              'summarization, and practice testing improve long-term retention.'
        )
    if provider == 'local':
        return {'questions': _generate_local(cleaned, num_questions, question_type), 'provider': 'local'}

    # Explicit provider request: try it, fall back to local.
    if provider in ('openai', 'gemini', 'openrouter'):
        try:
            questions = _try_provider(provider, cleaned, num_questions, question_type)
            if questions:
                return {'questions': questions, 'provider': provider}
        except Exception:
            pass
        return {'questions': _generate_local(cleaned, num_questions, question_type), 'provider': 'local'}

    # auto: OpenRouter -> OpenAI -> Gemini -> local.
    for name in ('openrouter', 'openai', 'gemini'):
        try:
            questions = _try_provider(name, cleaned, num_questions, question_type)
            if questions:
                return {'questions': questions, 'provider': name}
        except Exception:
            continue
    return {'questions': _generate_local(cleaned, num_questions, question_type), 'provider': 'local'}


def _try_provider(name, source_text, num_questions, question_type):
    if name == 'openai':
        api_key, model = get_openai_config()
        if not api_key:
            raise ValueError('missing OPENAI_API_KEY')
        return _generate_with_openai(source_text, num_questions, question_type, api_key, model)
    if name == 'gemini':
        api_key, model = get_gemini_config()
        if not api_key:
            raise ValueError('missing GEMINI_API_KEY')
        return _generate_with_gemini(source_text, num_questions, question_type, api_key, model)
    if name == 'openrouter':
        api_key, model = get_openrouter_config()
        if not api_key:
            raise ValueError('missing OPENROUTER_API_KEY')
        return _generate_with_openrouter(source_text, num_questions, question_type, api_key, model)
    raise ValueError(f'unknown provider {name}')


# ---------------------------------------------------------------------------
# OpenAI (stdlib, no dependency)
# ---------------------------------------------------------------------------

def _generate_with_openai(source_text, num_questions, question_type, api_key, model):
    prompt = _build_prompt(source_text, num_questions, question_type)
    payload = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'You output only valid JSON, no markdown fences.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.7,
        'max_tokens': _output_token_budget(num_questions),
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.openai.com/v1/chat/completions',
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        },
        method='POST',
    )
    with urllib.request.urlopen(
        req, timeout=_provider_timeout(num_questions)
    ) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    content = data['choices'][0]['message']['content'].strip()
    return _parse_json_list(content, num_questions)


# ---------------------------------------------------------------------------
# Gemini (Google Generative Language API, stdlib only)
# ---------------------------------------------------------------------------

def _generate_with_gemini(source_text, num_questions, question_type, api_key, model):
    prompt = _build_prompt(source_text, num_questions, question_type) + (
        '\nOutput ONLY a JSON array. No markdown, no explanation.'
    )
    # If a retired model name is configured, fall back to the rolling alias.
    models_to_try = [model]
    if model != 'gemini-flash-latest':
        models_to_try.append('gemini-flash-latest')
    last_exc = None
    for m in models_to_try:
        payload = json.dumps({
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {
                'temperature': 0.7,
                'maxOutputTokens': _output_token_budget(num_questions),
                # Leave the full budget for the JSON answer.
                'thinkingConfig': {'thinkingBudget': 0},
            },
        }).encode('utf-8')
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent'
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'x-goog-api-key': api_key,
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(
                req, timeout=_provider_timeout(num_questions)
            ) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode()[:500]
            except Exception:
                body = ''
            if m != 'gemini-flash-latest' and (
                e.code in (404, 503)
                or 'not found' in body.lower()
                or 'no longer available' in body.lower()
            ):
                last_exc = e
                continue
            raise
        try:
            content = data['candidates'][0]['content']['parts'][0]['text']
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f'unexpected Gemini response: {str(data)[:300]}') from exc
        return _parse_json_list(content, num_questions)
    raise last_exc


# ---------------------------------------------------------------------------
# OpenRouter (OpenAI-compatible Chat Completions, stdlib only)
# ---------------------------------------------------------------------------

def _generate_with_openrouter(source_text, num_questions, question_type, api_key, model):
    prompt = _build_prompt(source_text, num_questions, question_type)
    payload = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'You output only valid JSON, no markdown fences.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.7,
        'max_tokens': _output_token_budget(num_questions),
    }).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }
    site_url = _cfg('OPENROUTER_SITE_URL')
    app_name = _cfg('OPENROUTER_APP_NAME')
    if site_url:
        headers['HTTP-Referer'] = site_url
    if app_name:
        headers['X-Title'] = app_name
    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/chat/completions',
        data=payload, headers=headers, method='POST',
    )
    with urllib.request.urlopen(
        req, timeout=_provider_timeout(num_questions, minimum=60)
    ) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    content = data['choices'][0]['message']['content'].strip()
    return _parse_json_list(content, num_questions)


def _normalize_q(q, i):
    qtype = str(q.get('question_type', 'mcq')).lower()
    if qtype not in ('mcq', 'true_false', 'short_answer', 'essay'):
        qtype = 'mcq'
    options = q.get('options') or []
    if qtype == 'mcq' and len(options) < 2:
        options = ['Option A', 'Option B', 'Option C', 'Option D']
    return {
        'question_type': qtype,
        'question_text': str(q.get('question_text', f'Question {i + 1}')).strip(),
        'options': [str(o) for o in options[:4]],
        'correct_answer': str(q.get('correct_answer', '')).strip(),
        'explanation': str(q.get('explanation', '')).strip(),
        'order': i,
    }


# ---------------------------------------------------------------------------
# Local fallback generator
# ---------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')
_WORD = re.compile(r"[A-Za-z][A-Za-z\-']{3,}")


def _sentences(text):
    raw = _SENT_SPLIT.split(re.sub(r'\s+', ' ', text))
    return [s.strip() for s in raw if len(s.strip()) >= 40][:30]


def _keywords(text, exclude=''):
    words = _WORD.findall(text)
    seen, out = set(), []
    excl = (exclude or '').lower()
    for w in words:
        lw = w.lower()
        if len(w) >= 5 and lw != excl and lw not in seen and len(lw) <= 20:
            seen.add(lw)
            out.append(w)
        if len(out) >= 20:
            break
    return out


def _generate_local(source_text, num_questions, question_type):
    sentences = _sentences(source_text)
    if not sentences:
        sentences = ['Active recall and spaced repetition improve long-term retention.']
    keywords = _keywords(source_text)
    order_map = {'mcq': 0, 'true_false': 1, 'short_answer': 2, 'essay': 3}
    questions = []
    for i in range(num_questions):
        sent = sentences[i % len(sentences)]
        variant = i // len(sentences)
        if question_type in order_map:
            kind = question_type
        else:
            kind = ['mcq', 'true_false', 'short_answer', 'essay'][i % 4]
        if kind == 'mcq':
            questions.append(
                _make_mcq(sent, keywords, source_text, i, variant)
            )
        elif kind == 'true_false':
            questions.append(_make_tf(sent, i))
        elif kind == 'short_answer':
            questions.append(_make_short(sent, i))
        else:
            questions.append(_make_essay(sent, i))
    return questions


_MCQ_PROMPTS = (
    'Which term best completes the statement? "{}"',
    'Fill in the blank: "{}"',
    'Which word is missing from this statement? "{}"',
    'Choose the word that correctly completes this sentence: "{}"',
    'Based on the notes, which term belongs in the blank? "{}"',
)


def _make_mcq(sentence, keywords, full_text, i, variant=0):
    key_terms = _keywords(sentence)
    answer = (
        key_terms[variant % len(key_terms)]
        if key_terms else 'the main concept'
    )
    distractors = [k for k in keywords if k.lower() != answer.lower()][:3]
    while len(distractors) < 3:
        cand = GENERIC_DISTRACTORS[len(distractors) % len(GENERIC_DISTRACTORS)]
        if cand not in distractors:
            distractors.append(cand)
        else:
            break
    options = [answer] + distractors[:3]
    # Deterministic rotation so the answer is not always first.
    shift = variant % len(options)
    options = options[shift:] + options[:shift]
    blanked = sentence.replace(answer, '_____', 1) if answer in sentence else sentence
    prompt = _MCQ_PROMPTS[variant % len(_MCQ_PROMPTS)]
    return {
        'question_type': 'mcq',
        'question_text': prompt.format(blanked),
        'options': options[:4],
        'correct_answer': answer,
        'explanation': f'Based on the notes: "{sentence[:220]}"',
        'order': i,
    }


def _make_tf(sentence, i):
    is_true = (i % 2 == 0)
    if is_true:
        statement = sentence
        answer = 'True'
        expl = 'This statement is directly supported by the notes.'
    else:
        statement = f'It is NOT the case that: {sentence[:200]}'
        answer = 'False'
        expl = 'Review the notes — the original statement was altered with a negation.'
    return {
        'question_type': 'true_false',
        'question_text': f'True or False: {statement}',
        'options': ['True', 'False'],
        'correct_answer': answer,
        'explanation': expl,
        'order': i,
    }


def _make_short(sentence, i):
    return {
        'question_type': 'short_answer',
        'question_text': f'In your own words, explain: "{sentence[:220]}"',
        'options': [],
        'correct_answer': sentence[:300],
        'explanation': 'Compare your answer against the reference statement above.',
        'order': i,
    }


def _make_essay(sentence, i):
    return {
        'question_type': 'essay',
        'question_text': (
            'Discuss the significance of the following concept and give an example: '
            f'"{sentence[:220]}"'
        ),
        'options': [],
        'correct_answer': '',
        'explanation': 'A strong answer defines the concept, explains why it matters, and gives an example.',
        'order': i,
    }
