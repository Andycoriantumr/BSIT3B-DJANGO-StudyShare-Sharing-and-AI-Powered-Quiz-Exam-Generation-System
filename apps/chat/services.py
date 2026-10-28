"""AI chat service for StudyShare.

Gemini is preferred when GEMINI_API_KEY is configured, then OpenRouter, then
OpenAI. The configured model is tried first; Gemini requests use the
``x-goog-api-key`` header and disable thinking so chat replies arrive complete.
When no provider is available (or every call fails), a deterministic offline
reply summarises matching StudyShare notes so the workflow always responds.

The assistant also performs a lightweight note lookup: keywords from the
student's question become an OR query across note titles, subjects, topics,
descriptions, and content. The top matching notes are supplied to the model
as context, and linked from offline answers.
"""

import json
import logging
import re
import urllib.error
import urllib.request

from django.db.models import Q

from apps.notes.models import Note
from apps.notes.services import (
    _cfg,
    get_gemini_config,
    get_note_source_text,
    get_openai_config,
    get_openrouter_config,
)

from .models import Message

MAX_HISTORY_MESSAGES = 20
MAX_MESSAGE_CHARS = 4000
MAX_CONTEXT_CHARS = 6000
NOTE_LIMIT = 3
MAX_TOKENS = 900

logger = logging.getLogger(__name__)

# Gemini is the recommended provider; the other two remain as fallbacks.
_PROVIDER_ORDER = ('gemini', 'openrouter', 'openai')

SYSTEM_PROMPT = (
    'You are StudyShare AI, a friendly study assistant for students using the '
    'StudyShare notes-sharing app. Answer clearly and concisely in Markdown. '
    'When note excerpts are supplied, ground your answer in them and mention the '
    'note titles you used. If the excerpts do not cover the question, say so '
    'briefly, then answer from general knowledge. Never invent note titles or '
    'citations. For maths and code, show the key steps. When it helps, end with '
    'one short follow-up suggestion.'
)

_STOPWORDS = {
    'about', 'after', 'again', 'also', 'another', 'answer', 'anything', 'around',
    'because', 'been', 'before', 'being', 'between', 'both', 'could', 'does',
    'doing', 'during', 'each', 'from', 'further', 'give', 'have', 'having',
    'here', 'into', 'itself', 'just', 'know', 'like', 'make', 'many', 'might',
    'more', 'most', 'much', 'must', 'need', 'only', 'other', 'over', 'please',
    'same', 'should', 'some', 'such', 'than', 'that', 'their', 'them', 'then',
    'there', 'these', 'they', 'thing', 'things', 'this', 'those', 'through',
    'under', 'until', 'very', 'want', 'were', 'what', 'when', 'where', 'which',
    'while', 'with', 'would', 'your', 'yours',
}

_WORD = re.compile(r"[A-Za-z][A-Za-z\-']{3,}")
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')
_GENERIC_NOTE_TERMS = {
    'note', 'notes', 'summarize', 'summary', 'latest', 'recent',
    'concept', 'concepts', 'topic', 'topics',
}


def _query_terms(query, limit=8):
    terms = []
    for word in _WORD.findall(query or ''):
        lowered = word.lower()
        if lowered in _STOPWORDS or lowered in terms:
            continue
        terms.append(lowered)
        if len(terms) >= limit:
            break
    return terms


def build_note_context(user, query):
    """Return (context text, matching notes) for a student's question."""
    terms = _query_terms(query)
    if not terms:
        return '', []

    topic_terms = [
        term for term in terms if term not in _GENERIC_NOTE_TERMS
    ]

    lookup = Q()
    for term in topic_terms:
        lookup |= (
            Q(title__icontains=term)
            | Q(subject__icontains=term)
            | Q(topic__icontains=term)
            | Q(description__icontains=term)
            | Q(content__icontains=term)
        )

    visible_notes = Note.objects.filter(
        Q(status=Note.STATUS_APPROVED, is_public=True) | Q(uploaded_by=user)
    )
    notes = []
    if topic_terms:
        notes = list(
            visible_notes.filter(lookup).order_by('-created_at')[:NOTE_LIMIT]
        )
    if not notes and _GENERIC_NOTE_TERMS.intersection(terms):
        # "Summarize my notes" has no topic keywords; use the newest notes.
        notes = list(visible_notes.order_by('-created_at')[:2])
    if not notes:
        return '', []

    chunks = []
    for note in notes:
        text = get_note_source_text(note, max_chars=2200)
        chunks.append(
            f'=== NOTE: {note.title} | Subject: {note.subject} | '
            f'Topic: {note.topic} ===\n{text}'
        )
    context = '\n\n'.join(chunks)[:MAX_CONTEXT_CHARS]
    return context, notes


def _provider_order():
    """Return the provider order, honouring an explicit AI_PROVIDER setting."""
    preferred = _cfg('AI_PROVIDER', 'auto').lower()
    if preferred in _PROVIDER_ORDER:
        return (preferred,) + tuple(
            name for name in _PROVIDER_ORDER if name != preferred
        )
    return _PROVIDER_ORDER


def generate_reply(user, conversation, user_message, think=False):
    """Generate a reply for the conversation and return content + provider."""
    system_prompt = SYSTEM_PROMPT
    if think:
        system_prompt += (
            '\nThink through the question step by step before giving the final '
            'answer. Keep the final response focused and readable.'
        )

    has_previous_reply = conversation.messages.filter(
        role=Message.ROLE_ASSISTANT
    ).exists()

    # A follow-up like "give me an example" has no reusable keywords on its
    # own, so search using the last few student messages as well.
    recent_user_messages = list(
        conversation.messages.filter(role=Message.ROLE_USER)
        .order_by('-created_at')[:3]
    )
    recent_user_messages.reverse()
    search_query = (
        ' '.join(
            message.content for message in recent_user_messages if message.content
        ).strip()
        or user_message
    )

    try:
        context, notes = build_note_context(user, search_query)
    except Exception:
        context, notes = '', []

    if context:
        system_prompt += '\n\nRelevant note excerpts from StudyShare:\n' + context

    history = list(
        conversation.messages.order_by('-created_at')[:MAX_HISTORY_MESSAGES]
    )
    history.reverse()
    messages = [
        {'role': message.role, 'content': (message.content or '')[:MAX_MESSAGE_CHARS]}
        for message in history
        if message.role in (Message.ROLE_USER, Message.ROLE_ASSISTANT)
    ]

    for provider in _provider_order():
        try:
            content = _call_provider(provider, system_prompt, messages)
        except Exception as error:
            logger.warning('Chat provider %s failed: %s', provider, error)
            continue
        if content:
            return {'content': content, 'provider': provider}

    return {
        'content': _offline_reply(
            search_query, notes, first=not has_previous_reply
        ),
        'provider': 'local',
    }


# ---------------------------------------------------------------------------
# Provider calls (stdlib only, matching apps.notes.services)
# ---------------------------------------------------------------------------


def _call_provider(name, system_prompt, messages):
    if name == 'openai':
        api_key, model = get_openai_config()
        if not api_key:
            raise ValueError('missing OPENAI_API_KEY')
        return _openai_compatible(
            'https://api.openai.com/v1/chat/completions',
            api_key,
            model,
            system_prompt,
            messages,
            {},
        )

    if name == 'openrouter':
        api_key, model = get_openrouter_config()
        if not api_key:
            raise ValueError('missing OPENROUTER_API_KEY')
        extra_headers = {}
        site_url = _cfg('OPENROUTER_SITE_URL')
        app_name = _cfg('OPENROUTER_APP_NAME')
        if site_url:
            extra_headers['HTTP-Referer'] = site_url
        if app_name:
            extra_headers['X-Title'] = app_name
        return _openai_compatible(
            'https://openrouter.ai/api/v1/chat/completions',
            api_key,
            model,
            system_prompt,
            messages,
            extra_headers,
        )

    if name == 'gemini':
        api_key, model = get_gemini_config()
        if not api_key:
            raise ValueError('missing GEMINI_API_KEY')
        return _gemini_chat(api_key, model, system_prompt, messages)

    raise ValueError(f'unknown provider {name}')


def _openai_compatible(url, api_key, model, system_prompt, messages, extra_headers):
    payload = json.dumps({
        'model': model,
        'messages': [{'role': 'system', 'content': system_prompt}] + messages,
        'temperature': 0.7,
        'max_tokens': MAX_TOKENS,
    }).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    }
    headers.update(extra_headers)

    request = urllib.request.Request(
        url, data=payload, headers=headers, method='POST'
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.loads(response.read().decode('utf-8'))

    content = data['choices'][0]['message'].get('content')
    if isinstance(content, list):
        content = ''.join(
            part.get('text', '') for part in content if isinstance(part, dict)
        )
    content = (content or '').strip()
    if not content:
        raise ValueError('empty provider response')
    return content


def _gemini_chat(api_key, model, system_prompt, messages):
    contents = []
    for message in messages:
        role = 'model' if message['role'] == Message.ROLE_ASSISTANT else 'user'
        contents.append({
            'role': role,
            'parts': [{'text': message['content']}],
        })

    # If a retired model name is configured, fall back to the rolling alias.
    models_to_try = [model]
    if model != 'gemini-flash-latest':
        models_to_try.append('gemini-flash-latest')

    last_error = None
    for candidate in models_to_try:
        payload = json.dumps({
            'systemInstruction': {'parts': [{'text': system_prompt}]},
            'contents': contents,
            'generationConfig': {
                'temperature': 0.7,
                'maxOutputTokens': MAX_TOKENS,
                # Keep the full token budget for the visible answer instead of
                # letting hidden thinking consume it.
                'thinkingConfig': {'thinkingBudget': 0},
            },
        }).encode('utf-8')
        url = (
            'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{candidate}:generateContent'
        )
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'x-goog-api-key': api_key,
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            try:
                body = error.read().decode(errors='replace')[:500]
            except Exception:
                body = ''
            if candidate != 'gemini-flash-latest' and (
                error.code in (404, 503)
                or 'not found' in body.lower()
                or 'no longer available' in body.lower()
            ):
                last_error = error
                continue
            raise

        if not isinstance(data, dict):
            raise ValueError('unexpected Gemini response payload')

        candidates = data.get('candidates') or []
        if not candidates:
            feedback = data.get('promptFeedback') or {}
            reason = feedback.get('blockReason') or 'no candidates'
            raise ValueError(f'Gemini returned no answer ({reason})')

        candidate_data = candidates[0]
        parts = (candidate_data.get('content') or {}).get('parts') or []
        content = ''.join(
            part.get('text', '')
            for part in parts
            if isinstance(part, dict) and not part.get('thought')
        ).strip()
        if not content:
            finish_reason = candidate_data.get('finishReason') or 'unknown'
            raise ValueError(
                f'Gemini returned an empty answer '
                f'(finishReason={finish_reason})'
            )
        return content

    raise last_error or ValueError('Gemini request failed')


# ---------------------------------------------------------------------------
# Offline fallback
# ---------------------------------------------------------------------------


def _offline_reply(query, notes, first=True):
    lines = []

    if first:
        lines.extend([
            "I'm running in **offline mode** right now, so I can't hold a full AI "
            'conversation. Add an AI provider key to unlock complete answers.',
            '',
        ])

    if notes:
        lines.append(
            'Here is what I found in StudyShare notes for your question:'
            if first
            else 'Here is another note-based answer:'
        )
        lines.append('')
        for note in notes:
            snippet = _note_snippet(note, query)
            lines.append(f'**{note.title}** — {note.subject} / {note.topic}')
            if snippet:
                lines.append(f'> {snippet}')
            lines.append(f'[Open note](/notes/{note.pk}/)')
            lines.append('')
        lines.append(
            'Ask about a specific subject, or upload more notes to widen the search.'
        )
    elif first:
        lines.extend([
            "I couldn't find matching notes for that question yet. Try:",
            '',
            '- Naming the subject or topic (for example, "database normalization")',
            '- Uploading or pasting your notes so I can reference them',
            '- Using **New quiz** to turn a note into practice questions',
            '',
            'Once an AI key is configured, I can also answer open-ended study questions.',
        ])
    else:
        lines.append(
            "I'm still offline and couldn't find matching notes for that follow-up. "
            'Try naming the subject or topic, or upload the relevant notes.'
        )

    return '\n'.join(lines).strip()


def _note_snippet(note, query, max_chars=300):
    source = ' '.join(
        part for part in [note.description, note.content] if part
    )
    source = re.sub(r'\s+', ' ', source).strip()
    if not source:
        return ''

    terms = set(_query_terms(query, limit=12))
    sentences = [
        sentence.strip()
        for sentence in _SENTENCE_SPLIT.split(source)
        if len(sentence.strip()) >= 30
    ]
    if not sentences:
        return source[:max_chars]

    ranked = sorted(
        sentences,
        key=lambda sentence: sum(
            1 for term in terms if term in sentence.lower()
        ),
        reverse=True,
    )
    snippet = ' '.join(ranked[:2])
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars].rsplit(' ', 1)[0] + '…'
    return snippet
