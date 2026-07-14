import json
import os

from groq import Groq

from retry import retry_on_rate_limit

MODEL = "openai/gpt-oss-120b"

INITIATIVES_SCHEMA = {
    "type": "object",
    "properties": {
        "initiatives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "timeframe": {"type": ["string", "null"]},
                    "description": {"type": "string"},
                    "concepts": {"type": "array", "items": {"type": "string"}},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": [
                    "title",
                    "company",
                    "timeframe",
                    "description",
                    "concepts",
                    "tags",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["initiatives"],
    "additionalProperties": False,
}

EXTRACTION_PROMPT = """You are an expert resume parser. Extract the candidate's \
work experience and personal projects as a list of "initiatives".

Rules:
- One initiative per distinct role or project (not per bullet point).
- "concepts" = the technical concepts a candidate should be ready to explain in an
  interview because of this initiative (e.g. "event-driven architecture", "caching
  strategies", "OAuth2"). 3-8 per initiative.
- "tags" = short technology/skill labels (e.g. "Kafka", "FastAPI", "React"). 3-8 per initiative.
- "description" = 1-3 sentences summarizing what was built and the impact.
- If company is not applicable (e.g. a personal project), use "Personal Project".
- If no timeframe is stated (common for personal projects), use null.
- Do not invent facts not present in the resume text.

Resume text:
---
__RESUME_TEXT__
---
"""


@retry_on_rate_limit
def extract_initiatives(resume_text: str) -> dict:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.replace("__RESUME_TEXT__", resume_text),
            }
        ],
        temperature=0.2,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "initiatives_extraction",
                "strict": True,
                "schema": INITIATIVES_SCHEMA,
            },
        },
    )

    raw = response.choices[0].message.content
    return json.loads(raw)
