import json
import os

from groq import Groq

from retry import retry_on_rate_limit

MODEL = "openai/gpt-oss-120b"


def _client() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


@retry_on_rate_limit
def _json_schema_call(*, prompt: str, schema_name: str, schema: dict, system: str | None = None) -> dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = _client().chat.completions.create(
        model=MODEL,
        messages=messages,
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


# --- Study mode (project-grounded) ---------------------------------------

STUDY_SCHEMA = {
    "type": "object",
    "properties": {
        "quick_definition": {"type": "string"},
        "how_they_used_it": {"type": "string"},
        "why_this_choice": {"type": "string"},
        "likely_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "model_answer": {"type": "string"},
                },
                "required": ["question", "model_answer"],
                "additionalProperties": False,
            },
        },
        "follow_up_traps": {"type": "array", "items": {"type": "string"}},
        "avoid_saying": {"type": "string"},
    },
    "required": [
        "quick_definition",
        "how_they_used_it",
        "why_this_choice",
        "likely_questions",
        "follow_up_traps",
        "avoid_saying",
    ],
    "additionalProperties": False,
}

STUDY_SYSTEM_PROMPT = """You are preparing a candidate for a live technical interview \
about their own project. You will be given one concept they used, the specific \
project it came from, and what is known about that project. Your job is to explain \
this concept THROUGH the lens of their project — not as generic textbook material.

Hard rule: if a sentence you're about to write could apply to any resume that mentions \
this concept, delete it and rewrite it so it only makes sense for THIS project.

Generate exactly 2-3 items in likely_questions and 1-2 items in follow_up_traps. \
Every field must reference the project context provided — none should be answerable \
without it.

Field guide:
- quick_definition: 2 sentences max, plain language, no jargon
- how_they_used_it: grounded specifically in their project. Reference their actual \
numbers, method choices, and what problem it solved for them. This is the most \
important field — never leave it generic.
- why_this_choice: what alternative existed, and why theirs was the better call for \
this specific situation. Frame as the argument they'd make to defend the decision, \
not a list of pros/cons.
- likely_questions: a question an interviewer would plausibly ask about this concept \
in the context of their project, with a tight, confident model_answer anchored to \
their actual project details.
- follow_up_traps: a deeper probing question that goes one level past the obvious \
answer, phrased as "be ready for this" — the kind of question that catches people who \
only know the concept at surface level.
- avoid_saying: one specific, concrete misstatement this candidate could make about \
THEIR project (not a generic pitfall) that would make an interviewer doubt they \
actually did the work.
"""

STUDY_PROMPT = """Concept: {concept}
Project: {project_name}

Full project context:
- Company: {company}
- Timeframe: {timeframe}
- Description: {description}
- Tags/technologies: {tags}
{star_context}

Generate the interview prep explanation for this concept.
"""


def generate_study(concept: str, initiative: dict, story: dict | None = None) -> dict:
    star_context = ""
    if story:
        star_lines = []
        if story.get("objective"):
            star_lines.append(f"- Objective: {story['objective']}")
        if story.get("methodology"):
            star_lines.append(f"- Methodology: {story['methodology']}")
        if story.get("results"):
            star_lines.append(f"- Results: {story['results']}")
        if star_lines:
            star_context = "\n" + "\n".join(star_lines)

    prompt = STUDY_PROMPT.format(
        concept=concept,
        project_name=initiative["title"],
        company=initiative["company"],
        timeframe=initiative.get("timeframe") or "not specified",
        description=initiative["description"],
        tags=", ".join(initiative.get("tags", [])),
        star_context=star_context,
    )
    return _json_schema_call(
        prompt=prompt,
        schema_name="study_deep_dive",
        schema=STUDY_SCHEMA,
        system=STUDY_SYSTEM_PROMPT,
    )


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
