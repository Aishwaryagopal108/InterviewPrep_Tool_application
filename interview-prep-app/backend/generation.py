import json
import os

from groq import Groq

MODEL = "openai/gpt-oss-120b"


def _client() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def _json_schema_call(*, prompt: str, schema_name: str, schema: dict) -> dict:
    response = _client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        },
    )
    return json.loads(response.choices[0].message.content)


# --- Study mode ---------------------------------------------------------

STUDY_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "how_it_works": {"type": "string"},
        "trade_offs": {"type": "string"},
        "common_pitfalls": {"type": "string"},
        "interview_angle": {"type": "string"},
    },
    "required": [
        "explanation",
        "why_it_matters",
        "how_it_works",
        "trade_offs",
        "common_pitfalls",
        "interview_angle",
    ],
    "additionalProperties": False,
}

STUDY_PROMPT = """You are an expert interview coach. Produce a multi-dimension study \
deep dive on the concept "{concept}" so a candidate can confidently discuss it in a \
technical interview.

{context_block}

Fill in each field:
- explanation: a clear, precise explanation of the concept (2-4 sentences)
- why_it_matters: why this concept matters in practice / when you'd reach for it
- how_it_works: the mechanics, 3-5 sentences, technical but readable
- trade_offs: trade-offs vs. alternatives
- common_pitfalls: mistakes or misconceptions people commonly run into
- interview_angle: how this concept is likely to come up in an interview, including \
one example question an interviewer might ask about it
"""


def generate_study(concept: str, context: str | None = None) -> dict:
    context_block = (
        f'The candidate encountered this concept in the context of: "{context}"'
        if context
        else "No additional project context was given — explain the concept generally."
    )
    prompt = STUDY_PROMPT.format(concept=concept, context_block=context_block)
    return _json_schema_call(prompt=prompt, schema_name="study_deep_dive", schema=STUDY_SCHEMA)


# --- Story mode (STAR-style) --------------------------------------------

STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "objective": {"type": "string"},
        "data": {"type": "string"},
        "methodology": {"type": "string"},
        "results": {"type": "string"},
        "challenges": {"type": "string"},
        "future_scope": {"type": "string"},
    },
    "required": [
        "objective",
        "data",
        "methodology",
        "results",
        "challenges",
        "future_scope",
    ],
    "additionalProperties": False,
}

STORY_PROMPT = """You are an expert interview coach. Write a STAR-style story the \
candidate can tell in an interview about this project/role, based only on the facts \
given below. Do not invent facts not implied by the input.

Title: {title}
Company: {company}
Timeframe: {timeframe}
Description: {description}
Concepts involved: {concepts}
Tags/technologies: {tags}

Fill in each field as 2-4 sentences, written in first person as something the \
candidate would say out loud:
- objective: what problem/goal this initiative addressed
- data: what data/inputs/systems were involved
- methodology: the approach and technical decisions made
- results: the outcome/impact, quantified if the description supports it
- challenges: a real obstacle faced and how it was handled
- future_scope: what could be improved or extended next
"""


def generate_story(initiative: dict) -> dict:
    prompt = STORY_PROMPT.format(
        title=initiative["title"],
        company=initiative["company"],
        timeframe=initiative.get("timeframe") or "not specified",
        description=initiative["description"],
        concepts=", ".join(initiative.get("concepts", [])),
        tags=", ".join(initiative.get("tags", [])),
    )
    return _json_schema_call(prompt=prompt, schema_name="star_story", schema=STORY_SCHEMA)


# --- Q&A (shared shape for project and resume-wide) ----------------------

QA_SCHEMA = {
    "type": "object",
    "properties": {
        "qa_pairs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                },
                "required": ["question", "answer"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["qa_pairs"],
    "additionalProperties": False,
}

PROJECT_QA_PROMPT = """You are an expert interview coach. Generate likely interview \
questions and strong candidate answers about this specific project/role, based only \
on the facts given below. Do not invent facts not implied by the input.

Title: {title}
Company: {company}
Timeframe: {timeframe}
Description: {description}
Concepts involved: {concepts}
Tags/technologies: {tags}

Generate 5-8 question/answer pairs. Questions should range from "walk me through this
project" to probing technical/design-decision questions an interviewer would actually
ask about this work. Answers should be strong, specific, first-person sample answers.
"""


def generate_project_qa(initiative: dict) -> dict:
    prompt = PROJECT_QA_PROMPT.format(
        title=initiative["title"],
        company=initiative["company"],
        timeframe=initiative.get("timeframe") or "not specified",
        description=initiative["description"],
        concepts=", ".join(initiative.get("concepts", [])),
        tags=", ".join(initiative.get("tags", [])),
    )
    return _json_schema_call(prompt=prompt, schema_name="project_qa", schema=QA_SCHEMA)


RESUME_QA_PROMPT = """You are an expert interview coach. Based on this candidate's \
full resume text below, generate likely resume-wide technical interview questions \
and strong answers — the kind that span multiple projects or probe the candidate's \
overall technical breadth, not questions about a single project in isolation.

Resume text:
---
{resume_text}
---

Generate 6-10 question/answer pairs. Answers should be strong, specific, first-person
sample answers grounded only in what the resume text supports.
"""


def generate_resume_qa(resume_text: str) -> dict:
    prompt = RESUME_QA_PROMPT.format(resume_text=resume_text)
    return _json_schema_call(prompt=prompt, schema_name="resume_qa", schema=QA_SCHEMA)
