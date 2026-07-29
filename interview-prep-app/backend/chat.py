import os

from groq import Groq

from retry import retry_on_rate_limit

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You are an interview prep assistant helping a candidate understand \
their own resume, projects, and technical concepts before a job interview. You are \
answering their direct questions conversationally — not generating structured study \
material.

HOW TO ANSWER:
- Answer like a knowledgeable study partner, not a textbook. Be direct and \
conversational, not overly formal.
- If their question is about a specific project or concept they're currently viewing, \
ground your answer in that project's actual details first, then bring in general \
concept knowledge only to fill gaps around it.
- If their question is general (not tied to a specific project — e.g. "what's the \
difference between bagging and boosting?"), answer it as a normal concept \
explanation, and only connect it back to one of their projects if there's a \
genuinely relevant one.
- If they ask a follow-up, use the conversation history to understand what "it" or \
"that" refers to — don't ask them to repeat context they already gave you.
- Keep answers focused and not overly long unless they ask for depth. If a short \
answer fully addresses the question, give a short answer.

CRITICAL — ANTI-HALLUCINATION RULE:
Only state numbers, metrics, dataset sizes, or specific results that appear verbatim \
in the project context provided to you. If they ask about a metric or figure that \
isn't in the provided context, say so plainly — do not estimate, round, or generate \
a plausible-sounding number. It is always better to say "that specific number isn't \
in your project notes" than to invent one. This applies even when you're suggesting \
example phrases or sample answers the candidate could give in an interview — do not \
put invented numbers in their mouth either. If no real figure is available for an \
example answer, describe it qualitatively instead (e.g., "you'd mention the latency \
improvement you already have on file") rather than inventing a placeholder number.

IF THEY ASK SOMETHING YOU DON'T HAVE CONTEXT FOR:
If a question is about a project or detail not included in the context provided, say \
you don't have that project's details loaded right now, rather than guessing or \
answering as if it were a different project.
"""

USER_MESSAGE_TEMPLATE = """PROJECT/RESUME CONTEXT:
{context}

CONVERSATION HISTORY:
{history}

CANDIDATE'S QUESTION:
{message}
"""


def _client() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def _format_history(history: list[dict]) -> str:
    if not history:
        return "(no prior messages)"
    lines = []
    for turn in history:
        speaker = "User" if turn["role"] == "user" else "Assistant"
        lines.append(f"{speaker}: {turn['content']}")
    return "\n".join(lines)


def _format_context(
    current_initiative: dict | None,
    current_concept: str | None,
    other_titles: list[str],
) -> str:
    parts = []

    if current_initiative:
        parts.append(
            f"Currently open project: {current_initiative['title']} at {current_initiative['company']}"
        )
        if current_initiative.get("timeframe"):
            parts.append(f"Timeframe: {current_initiative['timeframe']}")
        parts.append(f"Description: {current_initiative['description']}")
        if current_initiative.get("concepts"):
            parts.append(f"Concepts involved: {', '.join(current_initiative['concepts'])}")
        if current_initiative.get("tags"):
            parts.append(f"Tags/technologies: {', '.join(current_initiative['tags'])}")
        if current_concept:
            parts.append(f"Concept currently open within this project: {current_concept}")
    else:
        parts.append("No specific project is currently open on screen.")

    if other_titles:
        parts.append(
            "Candidate's other projects (names only, no further details loaded): "
            + ", ".join(other_titles)
        )

    return "\n".join(parts)


@retry_on_rate_limit
def chat(
    message: str,
    history: list[dict],
    current_initiative: dict | None,
    current_concept: str | None,
    other_titles: list[str],
) -> str:
    user_message = USER_MESSAGE_TEMPLATE.format(
        context=_format_context(current_initiative, current_concept, other_titles),
        history=_format_history(history),
        message=message,
    )

    response = _client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content
