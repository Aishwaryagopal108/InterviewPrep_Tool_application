"""
Throwaway validation script (build order step 1 in CLAUDE.md).

Takes sample resume text, sends it to Groq, and checks whether the model
reliably returns the structured JSON shape we need:
    { "initiatives": [ { title, company, timeframe, description, concepts, tags } ] }

Run: python validate_extraction.py
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

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

SAMPLE_RESUME_TEXT = """
Aishwarya Gopal
Software Engineer

Experience

Backend Engineer, Acme Analytics (Jun 2023 - Present)
Led migration of the event-ingestion pipeline from a monolithic cron job to a
Kafka-based streaming architecture, cutting end-to-end latency from 12 minutes
to under 30 seconds. Designed the schema registry and backpressure handling
using Kafka Streams and Postgres for state storage. Wrote the on-call runbook
and mentored two junior engineers on distributed systems debugging.

Software Engineer Intern, DataForge Inc (May 2022 - Aug 2022)
Built a REST API in FastAPI to serve model predictions from a fraud-detection
model, adding request validation, rate limiting, and Redis-based caching.
Reduced p95 latency by 40% and wrote integration tests with pytest achieving
90% coverage on the new service.

Projects

Personal Finance Tracker (2021)
Built a full-stack web app (React + Node.js + MongoDB) to track expenses
across accounts, with OAuth login via Google and automated monthly reports
emailed via a cron job on a small VPS.
"""

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


REQUIRED_FIELDS = {"title", "company", "timeframe", "description", "concepts", "tags"}


def validate_shape(data: dict) -> list[str]:
    """Return a list of problems found; empty list means the shape is good."""
    problems = []

    if "initiatives" not in data:
        return ["missing top-level 'initiatives' key"]

    if not isinstance(data["initiatives"], list):
        return ["'initiatives' is not a list"]

    if len(data["initiatives"]) == 0:
        problems.append("'initiatives' list is empty")

    for i, item in enumerate(data["initiatives"]):
        if not isinstance(item, dict):
            problems.append(f"initiative[{i}] is not an object")
            continue

        missing = REQUIRED_FIELDS - item.keys()
        if missing:
            problems.append(f"initiative[{i}] missing fields: {sorted(missing)}")

        for list_field in ("concepts", "tags"):
            if list_field in item and not isinstance(item[list_field], list):
                problems.append(f"initiative[{i}].{list_field} is not a list")

    return problems


def main():
    if not os.environ.get("GROQ_API_KEY"):
        raise SystemExit(
            "GROQ_API_KEY not set. Add it to interview-prep-app/.env as "
            "GROQ_API_KEY=gsk_... and rerun."
        )

    print(f"Calling Groq ({MODEL})...\n")
    data = extract_initiatives(SAMPLE_RESUME_TEXT)

    print("--- Raw parsed JSON ---")
    print(json.dumps(data, indent=2))

    print("\n--- Shape validation ---")
    problems = validate_shape(data)
    if problems:
        print("FAILED:")
        for p in problems:
            print(f"  - {p}")
    else:
        n = len(data["initiatives"])
        print(f"OK: {n} initiative(s), all required fields present.")


if __name__ == "__main__":
    main()
