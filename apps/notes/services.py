"""Quiz generation service.

Strategy (no extra dependencies, stdlib urllib only):
- provider="auto" (default): try OpenRouter -> OpenAI -> Gemini (whichever has
  an API key configured), then fall back to the deterministic local generator.
  AI_PROVIDER=local forces auto requests to use the local generator immediately.
- provider="openai" / "gemini" / "openrouter": try that provider, fall back to
  local on any failure so demos never break.
- provider="local": always use the offline generator.

Env / settings keys:
  OPENAI_API_KEY / OPENAI_MODEL (default gpt-4o-mini)
  GEMINI_API_KEY / GEMINI_MODEL (default gemini-flash-latest)
  OPENROUTER_API_KEY / OPENROUTER_MODEL (default openai/gpt-4o-mini)
  OPENROUTER_SITE_URL / OPENROUTER_APP_NAME (optional OpenRouter headers)
"""

from functools import lru_cache
import json
import os
import re
import urllib.error
import urllib.request

from django.conf import settings

MAX_SOURCE_CHARS = 12000
GENERIC_DISTRACTORS = [
    'None of these',
    'A different concept',
    'Not stated in the notes',
    'Cannot be determined',
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
        'For multiple-choice questions, write every option in UPPERCASE, '
        'make all four choices unique within the question, and do not reuse '
        'the same set of choices across questions. Never include both '
        '"ALL OF THE ABOVE" and "NONE OF THE ABOVE" in one question. '
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
    if provider == 'auto' and _cfg('AI_PROVIDER', 'auto').lower() == 'local':
        provider = 'local'
    num_questions = max(1, min(int(num_questions or 5), 50))
    cleaned = (source_text or '').strip()
    if len(cleaned) < 40:
        cleaned = (
            cleaned
            + '\nGeneral study skills: time management, active recall, spaced repetition, '
              'summarization, and practice testing improve long-term retention.'
        )
    if provider == 'local':
        return _quiz_result(
            _generate_local(cleaned, num_questions, question_type), 'local'
        )

    # Explicit provider request: try it, fall back to local.
    if provider in ('openai', 'gemini', 'openrouter'):
        try:
            questions = _try_provider(provider, cleaned, num_questions, question_type)
            if questions:
                return _quiz_result(questions, provider)
        except Exception:
            pass
        return _quiz_result(
            _generate_local(cleaned, num_questions, question_type), 'local'
        )

    # auto: OpenRouter -> OpenAI -> Gemini -> local.
    for name in ('openrouter', 'openai', 'gemini'):
        try:
            questions = _try_provider(name, cleaned, num_questions, question_type)
            if questions:
                return _quiz_result(questions, name)
        except Exception:
            continue
    return _quiz_result(
        _generate_local(cleaned, num_questions, question_type), 'local'
    )


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
        'options': [str(o) for o in options[:6]],
        'correct_answer': str(q.get('correct_answer', '')).strip(),
        'explanation': str(q.get('explanation', '')).strip(),
        'order': i,
    }


@lru_cache(maxsize=4096)
def _option_key(value):
    text = re.sub(r'[\W_]+', ' ', str(value or '').casefold())
    return ' '.join(text.split())


def _clean_mcq_options(raw_options, correct_answer):
    """Strip, uppercase, and de-duplicate MCQ choices."""
    options = []
    seen = set()
    for raw in raw_options or []:
        text = str(raw or '').strip()
        key = _option_key(text)
        if not key or key in seen:
            continue
        seen.add(key)
        options.append(text.upper())

    # "All of the above" and "None of the above" together are contradictory.
    answer_key = _option_key(correct_answer)
    if 'ALL OF THE ABOVE' in options and 'NONE OF THE ABOVE' in options:
        for redundant in ('NONE OF THE ABOVE', 'ALL OF THE ABOVE'):
            if answer_key != _option_key(redundant):
                options.remove(redundant)
                break

    if len(options) < 2:
        options = ['OPTION A', 'OPTION B', 'OPTION C', 'OPTION D']
    return options


def _resolve_mcq_answer(answer, options):
    """Map the stored answer to its uppercase option text."""
    answer = str(answer or '').strip()
    answer_key = _option_key(answer)
    if answer_key:
        for option in options:
            if _option_key(option) == answer_key:
                return option

    letter = re.fullmatch(
        r'(?:OPTION\s+)?([A-D])(?:[\.\):\-])?', answer, re.IGNORECASE
    )
    if letter:
        index = ord(letter.group(1).upper()) - ord('A')
        if 0 <= index < len(options):
            return options[index]

    if not answer:
        return ''
    upper = answer.upper()
    if _option_key(upper) not in {_option_key(option) for option in options}:
        if len(options) < 4:
            options.append(upper)
        elif options:
            options[-1] = upper
    return upper


def _resolve_true_false_answer(answer):
    key = _option_key(answer)
    if key in ('true', 't', 'yes', 'y', '1', 'correct', 'right'):
        return 'TRUE'
    if key in ('false', 'f', 'no', 'n', '0', 'incorrect', 'wrong'):
        return 'FALSE'
    return str(answer or '').strip().upper() or 'TRUE'


def _finalize_questions(questions):
    """Apply consistent choice casing and remove redundant options."""
    finalized = []
    for index, raw in enumerate(questions or []):
        question = dict(raw)
        qtype = str(question.get('question_type', 'mcq')).lower()
        if qtype not in ('mcq', 'true_false', 'short_answer', 'essay'):
            qtype = 'mcq'
        answer = str(question.get('correct_answer', '') or '').strip()

        if qtype == 'mcq':
            options = _clean_mcq_options(question.get('options') or [], answer)
            answer = _resolve_mcq_answer(answer, options)
            if answer in options:
                answer_index = options.index(answer)
                if answer_index >= 4:
                    options.insert(0, options.pop(answer_index))
            options = options[:4]
        elif qtype == 'true_false':
            options = ['TRUE', 'FALSE']
            answer = _resolve_true_false_answer(answer)
        else:
            options = []

        question.update({
            'question_type': qtype,
            'options': options,
            'correct_answer': answer,
            'order': question.get('order', index),
        })
        finalized.append(question)
    return finalized


def _quiz_result(questions, provider):
    return {'questions': _finalize_questions(questions), 'provider': provider}


# ---------------------------------------------------------------------------
# Local fallback generator
# ---------------------------------------------------------------------------

_SENT_SPLIT = re.compile(r'(?<=[.!?])(?:\s+|(?=[A-Z][a-z]))')
_TERM_RE = re.compile(r"\b(?:[A-Z]{2,6}|[A-Za-z][A-Za-z\-']{3,})\b")
_PHRASE_RE = re.compile(
    r"\b([A-Za-z][A-Za-z\-']{3,})\s+([A-Za-z][A-Za-z\-']{3,})\b"
)
_META_LINE = re.compile(
    r'^(?:(?:Title|Subject|Topic|Instructor|School Year|File):|=== SOURCE:).*$',
    re.IGNORECASE | re.MULTILINE,
)

_STOPWORDS = frozenset('''
a about above across active after again against all almost along already also
although always am among an and another any anyone anything are around as at be
because been before being below between both but by can cannot could did do does
doing done down during each either else enough entire even ever every few final
first for from further general had has have having he her here hers herself him
himself his high higher how however i if important in indirect into is it its
itself just know known large like long low lower main major many may me might
minor more most much
must my myself near need negative never new no nor not now of off on once only
or other our ours ourselves out over own passive positive primary same secondary
she should similar simple since single small social some specific such than that
the their theirs them themselves then there these they this those through thus
to too total under until up upon us used using various very was we were what when
where which while who whom why will with within without would you your yours
yourself yourselves
'''.split())

_VERB_STOPWORDS = frozenset('''
absorb absorbs according added adds allow allows appears applied applies
become becomes begin begins bind binds break breaks built call called calls
capture captures carry carries cause causes change changed changes come comes
compare compared consist consists contain contains continue control controls
convert converts create creates depend depends describe describes determine
determines differ differs emit emits enter enters form forms get gets give
gives go goes help helps hold holds improve improves include includes increase
increases indicate indicates involve involves leave leaves known maintain
maintains make makes mean means move moves occur occurs pass passes produce
produces protect protects provide provides refer refers reflect reflects
regulate regulates release releases remain remains require requires result
results show shows speed speeds spread spreads store stores support supports
take takes tend tends transport transports turn turns use uses work works
'''.split())

_NOUN_SUFFIXES = (
    'tion', 'sion', 'ment', 'ness', 'ity', 'ism', 'ance', 'ence',
    'ology', 'graphy', 'sis', 'plasm', 'some', 'ase', 'ose', 'ide',
    'meter', 'scope', 'troph', 'lysis', 'philia', 'ria',
)

_ADJECTIVE_SUFFIXES = (
    'al', 'ar', 'ive', 'ous', 'ful', 'less', 'able', 'ible', 'ic',
    'ary', 'ory', 'ent', 'ant',
)


def _sentences(text):
    text = _META_LINE.sub(' ', text or '')
    text = re.sub(r'[\u2022\u25cf\u25aa\u25e6]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    out, seen = [], set()
    for sentence in _SENT_SPLIT.split(text):
        sentence = sentence.strip(' \t-–—')
        sentence = re.sub(r'^(?:\d+[.)]\s*|[-*]\s*)', '', sentence)
        if len(sentence) < 40:
            continue
        if len(sentence) > 360:
            sentence = sentence[:357].rstrip() + '...'
        key = sentence.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(sentence)
        if len(out) >= 60:
            break
    return out


def _is_content_term(term):
    term = term.strip()
    if not term or "'" in term:
        return False
    key = _option_key(term)
    if not key or key in _STOPWORDS or key in _VERB_STOPWORDS:
        return False
    letters = key.replace(' ', '')
    if len(letters) < 4 and not (
        term.isupper() and 2 <= len(term) <= 6
    ):
        return False
    return True


def _looks_adjective(key):
    last = key.rsplit(' ', 1)[-1]
    if last.endswith(_NOUN_SUFFIXES):
        return False
    return last.endswith(_ADJECTIVE_SUFFIXES)


def _phrase_candidates(sentence):
    """Adjacent content words that read as a compound concept."""
    phrases, seen = [], set()
    for match in _PHRASE_RE.finditer(sentence):
        first, second = match.group(1), match.group(2)
        if not _is_content_term(first) or not _is_content_term(second):
            continue
        first_key = _option_key(first)
        second_key = _option_key(second)
        if first_key in _VERB_STOPWORDS:
            continue
        if second_key in _VERB_STOPWORDS or _looks_adjective(second_key):
            continue
        phrase = f'{first} {second}'
        key = _option_key(phrase)
        if not key or key in seen or len(key) > 40:
            continue
        seen.add(key)
        phrases.append(phrase)
    return phrases


def _sentence_index(sentence):
    """Keys, families, and tokens that already appear in the sentence."""
    keys = {_option_key(raw) for raw in _TERM_RE.findall(sentence)}
    keys.update(_option_key(phrase) for phrase in _phrase_candidates(sentence))
    keys.discard('')
    families = {_term_family(key) for key in keys}
    tokens = {
        token for key in keys for token in key.split() if len(token) >= 4
    }
    return keys, families, tokens


def _overlaps_sentence(term_key, sentence_tokens):
    for token in sentence_tokens:
        if term_key == token:
            return True
        if len(term_key) >= 4 and (
            term_key in token or token in term_key
        ):
            return True
    return False


def _term_score(term, count):
    key = term.casefold()
    norm = _option_key(term)
    last = norm.rsplit(' ', 1)[-1]
    score = min(count, 6) * 1.3
    score += min(len(norm), 20) * 0.12
    if term.isupper() and len(term) >= 2:
        score += 2.0
    if ' ' in norm:
        score += 0.8
    if last.endswith(_NOUN_SUFFIXES):
        score += 1.6
    if '-' in key:
        score += 0.4
    if key.endswith('ly'):
        score -= 0.8
    if _looks_adjective(norm):
        score -= 1.1
    return score


def _term_family(key):
    """Collapse simple plural forms so close variants are not both offered."""
    if key.endswith('ies') and len(key) > 4:
        return key[:-3] + 'y'
    if key.endswith(('ses', 'xes', 'zes', 'ches', 'shes')) and len(key) > 4:
        return key[:-2]
    if key.endswith('s') and not key.endswith('ss') and len(key) > 4:
        return key[:-1]
    return key


def _distractor_score(answer_key, term_key):
    """Prefer distractors that look like the answer (length and ending)."""
    score = 0.0
    if len(answer_key) >= 3 and len(term_key) >= 3:
        if answer_key[-3:] == term_key[-3:]:
            score += 2.2
        elif answer_key[-2:] == term_key[-2:]:
            score += 1.1
    score += max(0.0, 1.4 - 0.2 * abs(len(answer_key) - len(term_key)))
    if answer_key[:1] == term_key[:1]:
        score += 0.25
    if term_key.endswith(_NOUN_SUFFIXES):
        score += 0.2
    return score


def _blank_answer(sentence, answer):
    """Blank the answer in place, ignoring case, and return None if absent."""
    if not answer:
        return None
    pattern = re.compile(
        r'(?<![A-Za-z0-9])' + re.escape(answer) + r'(?![A-Za-z0-9])',
        re.IGNORECASE,
    )
    blanked, count = pattern.subn('_____', sentence, count=1)
    return blanked if count else None


def _match_case(original, replacement):
    if replacement.isupper():
        return replacement
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement[:1].lower() + replacement[1:]


def _ranked_terms(sentences):
    freq, first = {}, {}
    for sentence in sentences:
        terms = [
            raw for raw in _TERM_RE.findall(sentence)
            if _is_content_term(raw)
        ]
        terms.extend(_phrase_candidates(sentence))
        for raw in terms:
            key = _option_key(raw)
            if not key:
                continue
            freq[key] = freq.get(key, 0) + 1
            first.setdefault(key, raw)
    ranked = [
        (_term_score(term, freq[key]), term.casefold(), term)
        for key, term in first.items()
    ]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [term for _, _, term in ranked]


def _sentence_terms(sentence, ranked_terms):
    keys, _, _ = _sentence_index(sentence)
    terms = [term for term in ranked_terms if _option_key(term) in keys]
    phrases = _phrase_candidates(sentence)
    if terms and phrases:
        phrase_keys = {_option_key(phrase) for phrase in phrases}
        phrase_tokens = {
            token for key in phrase_keys for token in key.split()
        }
        terms = [
            term for term in terms
            if _option_key(term) in phrase_keys
            or not set(_option_key(term).split()).issubset(phrase_tokens)
        ]
    if terms:
        return terms
    fallback, seen = [], set()
    for raw in _TERM_RE.findall(sentence):
        if not _is_content_term(raw):
            continue
        key = _option_key(raw)
        if key in seen:
            continue
        seen.add(key)
        fallback.append(raw)
    return fallback


def _keywords(text, exclude=''):
    """Ordered fallback terms for text with no recognised key concepts."""
    seen, out = set(), []
    excl = _option_key(exclude)
    for raw in _TERM_RE.findall(text):
        key = _option_key(raw)
        if not key or key == excl or key in seen:
            continue
        seen.add(key)
        out.append(raw)
        if len(out) >= 60:
            break
    return out


def _generate_local(source_text, num_questions, question_type):
    sentences = _sentences(source_text)
    if not sentences:
        sentences = [
            'Active recall and spaced repetition improve long-term retention.'
        ]
    ranked_terms = _ranked_terms(sentences)
    if not ranked_terms:
        ranked_terms = _keywords(source_text)
    sentence_terms = [
        _sentence_terms(sentence, ranked_terms) for sentence in sentences
    ]
    order_map = {'mcq': 0, 'true_false': 1, 'short_answer': 2, 'essay': 3}
    questions = []
    used_options = set()
    used_texts = set()
    usage = [0] * len(sentences)
    for i in range(num_questions):
        index = i % len(sentences)
        sentence = sentences[index]
        variant = usage[index]
        usage[index] += 1
        terms = sentence_terms[index]
        if question_type in order_map:
            kind = question_type
        else:
            kind = ['mcq', 'true_false', 'short_answer', 'essay'][i % 4]
        if kind == 'mcq':
            question = _make_mcq(
                sentence, terms, ranked_terms, i, variant,
                used_options, used_texts,
            )
        elif kind == 'true_false':
            question = _make_tf(
                sentence, terms, ranked_terms, i, variant, used_texts
            )
        elif kind == 'short_answer':
            question = _make_short(sentence, i, variant)
        else:
            question = _make_essay(sentence, i, variant)
        used_texts.add(question['question_text'].casefold())
        questions.append(question)
    return questions


_MCQ_PROMPTS = (
    'Which term best completes the statement? "{}"',
    'Fill in the blank: "{}"',
    'Which word is missing from this statement? "{}"',
    'Choose the word that correctly completes this sentence: "{}"',
    'Based on the notes, which term belongs in the blank? "{}"',
)

_SHORT_PROMPTS = (
    'In your own words, explain: "{}"',
    'Summarize this idea from the notes: "{}"',
    'Describe what this statement means: "{}"',
)

_ESSAY_PROMPTS = (
    'Discuss the significance of the following concept and give an example: "{}"',
    'Explain this idea in detail and support it with an example: "{}"',
)


def _mcq_distractor_pool(answer, sentence, ranked_terms, used_options):
    """Terms that are safe, plausible distractors for the answer."""
    answer_key = _option_key(answer)
    banned_families = {_term_family(answer_key)}
    for raw in _TERM_RE.findall(sentence):
        key = _option_key(raw)
        if key:
            banned_families.add(_term_family(key))

    candidates, seen_families = [], set(banned_families)
    for term in ranked_terms:
        key = _option_key(term)
        if not key:
            continue
        family = _term_family(key)
        if family in seen_families:
            continue
        seen_families.add(family)
        candidates.append(term)

    def rank(term):
        return (
            -_distractor_score(answer_key, _option_key(term)),
            _option_key(term),
        )

    fresh = [
        term for term in candidates if _option_key(term) not in used_options
    ]
    stale = [
        term for term in candidates if _option_key(term) in used_options
    ]
    return sorted(fresh, key=rank) + sorted(stale, key=rank)


def _make_mcq(sentence, terms, ranked_terms, i, variant=0,
              used_options=None, used_texts=None):
    used_options = used_options if used_options is not None else set()
    used_texts = used_texts if used_texts is not None else set()
    terms = terms or _keywords(sentence) or ['the main concept']
    start = variant % len(terms)
    ordered_terms = terms[start:] + terms[:start]
    prompt_start = variant % len(_MCQ_PROMPTS)

    chosen = None
    for term in ordered_terms:
        blanked = _blank_answer(sentence, term)
        if not blanked:
            continue
        for offset in range(len(_MCQ_PROMPTS)):
            prompt = _MCQ_PROMPTS[
                (prompt_start + offset) % len(_MCQ_PROMPTS)
            ]
            text = prompt.format(blanked)
            if text.casefold() not in used_texts:
                chosen = (term, text)
                break
        if chosen:
            break
    if not chosen:
        answer = ordered_terms[0]
        blanked = _blank_answer(sentence, answer)
        if blanked:
            text = _MCQ_PROMPTS[prompt_start].format(blanked)
        else:
            text = (
                'Which term is most closely associated with this '
                f'statement? "{sentence}"'
            )
        chosen = (answer, text)
    answer, question_text = chosen

    pool = _mcq_distractor_pool(
        answer, sentence, ranked_terms, used_options
    )
    answer_key = _option_key(answer)
    distractors, used_families = [], set()
    for term in pool:
        key = _option_key(term)
        family = _term_family(key)
        if key == answer_key or family in used_families:
            continue
        used_families.add(family)
        distractors.append(term)
        if len(distractors) == 3:
            break

    for generic in GENERIC_DISTRACTORS:
        if len(distractors) >= 3:
            break
        key = _option_key(generic)
        family = _term_family(key)
        if key == answer_key or family in used_families:
            continue
        used_families.add(family)
        distractors.append(generic)

    fallback_number = 1
    while len(distractors) < 3:
        fallback = f'OPTION {fallback_number}'
        fallback_number += 1
        key = _option_key(fallback)
        family = _term_family(key)
        if key == answer_key or family in used_families:
            continue
        used_families.add(family)
        distractors.append(fallback)

    options = [answer] + distractors[:3]
    shift = variant % len(options)
    options = options[shift:] + options[:shift]
    used_options.update(_option_key(option) for option in options)
    return {
        'question_type': 'mcq',
        'question_text': question_text,
        'options': options,
        'correct_answer': answer,
        'explanation': f'Based on the notes: "{sentence[:220]}"',
        'order': i,
    }


def _make_tf(sentence, terms, ranked_terms, i, variant=0, used_texts=None):
    used_texts = used_texts if used_texts is not None else set()
    true_text = f'True or False: {sentence}'
    is_true = (i % 2 == 0)
    if is_true and true_text.casefold() in used_texts:
        is_true = False
    if is_true:
        return {
            'question_type': 'true_false',
            'question_text': true_text,
            'options': ['True', 'False'],
            'correct_answer': 'True',
            'explanation': 'This statement is directly supported by the notes.',
            'order': i,
        }

    sentence_keys = {
        _option_key(term) for term in _TERM_RE.findall(sentence)
    }
    banned_families = {_term_family(key) for key in sentence_keys}
    replacements = [
        term for term in ranked_terms
        if _term_family(_option_key(term)) not in banned_families
    ]

    in_order, seen = [], set()
    for raw in _TERM_RE.findall(sentence):
        key = _option_key(raw)
        if key in seen or not _is_content_term(raw):
            continue
        seen.add(key)
        in_order.append(raw)
    originals = []
    if in_order:
        first_noun = next(
            (
                term for term in in_order
                if not _looks_adjective(_option_key(term))
            ),
            in_order[0],
        )
        originals.append(first_noun)
        first_key = _option_key(first_noun)
        for term in terms:
            if _option_key(term) != first_key:
                originals.append(term)
                break
    if not originals:
        originals = terms[:2]

    statement = None
    explanation = (
        'Review the notes — the original statement was altered '
        'with a negation.'
    )
    if originals and replacements:
        original = originals[variant % len(originals)]
        original_key = _option_key(original)
        ranked_replacements = sorted(
            replacements,
            key=lambda term: (
                -_distractor_score(original_key, _option_key(term)),
                _option_key(term),
            ),
        )[:6]
        replacement = ranked_replacements[
            variant % len(ranked_replacements)
        ]
        pattern = re.compile(
            r'(?<![A-Za-z0-9])' + re.escape(original) + r'(?![A-Za-z0-9])',
            re.IGNORECASE,
        )
        candidate, count = pattern.subn(
            _match_case(original, replacement), sentence, count=1
        )
        if count and candidate.casefold() != sentence.casefold():
            statement = candidate
            explanation = f'Not quite — the notes say "{sentence[:220]}".'
    if statement is None:
        statement = (
            'It is not true that '
            + sentence[:1].lower()
            + sentence[1:]
        )
    return {
        'question_type': 'true_false',
        'question_text': f'True or False: {statement}',
        'options': ['True', 'False'],
        'correct_answer': 'False',
        'explanation': explanation,
        'order': i,
    }


def _make_short(sentence, i, variant=0):
    prompt = _SHORT_PROMPTS[variant % len(_SHORT_PROMPTS)]
    return {
        'question_type': 'short_answer',
        'question_text': prompt.format(sentence[:220]),
        'options': [],
        'correct_answer': sentence[:300],
        'explanation': 'Compare your answer against the reference statement above.',
        'order': i,
    }


def _make_essay(sentence, i, variant=0):
    prompt = _ESSAY_PROMPTS[variant % len(_ESSAY_PROMPTS)]
    return {
        'question_type': 'essay',
        'question_text': prompt.format(sentence[:220]),
        'options': [],
        'correct_answer': '',
        'explanation': 'A strong answer defines the concept, explains why it matters, and gives an example.',
        'order': i,
    }
