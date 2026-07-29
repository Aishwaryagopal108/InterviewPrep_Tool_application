import os

from groq import Groq

from retry import retry_on_rate_limit

MODEL = "canopylabs/orpheus-v1-english"
VOICE = "autumn"


def _client() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


@retry_on_rate_limit
def generate_audio(text: str) -> bytes:
    response = _client().audio.speech.create(
        model=MODEL,
        voice=VOICE,
        input=text,
        response_format="wav",
    )
    return response.read()
