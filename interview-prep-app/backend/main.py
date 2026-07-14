import io

import pdfplumber
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from extraction import extract_initiatives
from generation import (
    generate_project_qa,
    generate_resume_qa,
    generate_story,
    generate_study,
)

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://interview-prep-frontend-1r7e.onrender.com",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExtractRequest(BaseModel):
    text: str


class InitiativeInput(BaseModel):
    title: str
    company: str
    timeframe: str | None = None
    description: str
    concepts: list[str] = []
    tags: list[str] = []


class StudyRequest(BaseModel):
    concept: str
    context: str | None = None


class ResumeQARequest(BaseModel):
    resume_text: str


@app.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    contents = await file.read()

    try:
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this PDF")

    if not text.strip():
        raise HTTPException(status_code=422, detail="No extractable text found in PDF")

    return {"filename": file.filename, "text": text}


@app.post("/extract")
async def extract(request: ExtractRequest):
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty")

    try:
        return extract_initiatives(request.text)
    except Exception:
        raise HTTPException(status_code=502, detail="Extraction failed")


@app.post("/study")
async def study(request: StudyRequest):
    if not request.concept.strip():
        raise HTTPException(status_code=422, detail="concept must not be empty")

    try:
        return generate_study(request.concept, request.context)
    except Exception:
        raise HTTPException(status_code=502, detail="Study generation failed")


@app.post("/story")
async def story(initiative: InitiativeInput):
    try:
        return generate_story(initiative.model_dump())
    except Exception:
        raise HTTPException(status_code=502, detail="Story generation failed")


@app.post("/project-qa")
async def project_qa(initiative: InitiativeInput):
    try:
        return generate_project_qa(initiative.model_dump())
    except Exception:
        raise HTTPException(status_code=502, detail="Project Q&A generation failed")


@app.post("/resume-qa")
async def resume_qa(request: ResumeQARequest):
    if not request.resume_text.strip():
        raise HTTPException(status_code=422, detail="resume_text must not be empty")

    try:
        return generate_resume_qa(request.resume_text)
    except Exception:
        raise HTTPException(status_code=502, detail="Resume Q&A generation failed")
