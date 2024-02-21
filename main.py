import os
import time
from fastapi.responses import JSONResponse
import openai
import logging
from fastapi import FastAPI
from starlette.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Imports the Cloud Logging client library
import google.cloud.logging

if "GCP_PROJECT" in os.environ:
    # Instantiates a client
    client = google.cloud.logging.Client()

    client.setup_logging()
else:
    logging.basicConfig(level=logging.INFO)


load_dotenv()
openai.api_key = os.environ.get("OPEN_AI_API_KEY")


class Context(BaseModel):
    linkedinURL: str
    jobpostDesc: str


app = FastAPI()

origins = [
    "http://localhost:5173",  # origin of frontend application
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Allow credentials (e.g., cookies) in the request
    allow_methods=["*"],  # Allow all HTTP methods, or specify specific methods
    allow_headers=["*"],  # Allow all headers, or specify specific headers
)


def get_generic_cover_letter():
    cover_letter = """
    [Your Name]
    [Your Address]
    [City, State, ZIP Code]
    [Your Email Address]
    [Your Phone Number]
    
    [Date]

    [Recipient's Name]
    [Company Name]
    [Company Address]
    [City, State, ZIP Code]

    Dear [Recipient's Name],

    I am writing to express my interest in the [Job Title] position at [Company Name], as advertised on [where you found the job posting]. With a strong background in [Your Relevant Skills and Experience], I am confident in my ability to contribute effectively to your team.

    Throughout my career, I have demonstrated [Key Achievements or Skills] that align with the requirements of the [Job Title] position. My commitment to [Company's Values or Mission] and my passion for [Relevant Industry or Field] make me an ideal candidate for this role.

    In my previous role at [Previous Company], I successfully [Highlight an Achievement or Responsibility], which resulted in [Quantifiable Result or Impact]. My ability to [Another Key Skill] and my strong [Additional Skill] would enable me to thrive in the dynamic environment at [Company Name].

    I am excited about the opportunity to contribute my skills to [Company Name] and am confident in my ability to make meaningful contributions to your team. Thank you for considering my application. I look forward to the opportunity to discuss how my skills and experiences align with your needs.

    Sincerely,

    [Your Full Name]
    """

    return cover_letter.split("\n")


def generate_mock_cover_letter():
    for line in get_generic_cover_letter():
        yield line + "\n"
        time.sleep(0.5)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/generate")
async def generate(context: Context):
    print(context)

    return StreamingResponse(
        generate_mock_cover_letter(),
        media_type="text/event-stream",
    )
