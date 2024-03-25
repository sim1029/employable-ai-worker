import os
import time
from fastapi.responses import JSONResponse
import openai
import logging
from fastapi import FastAPI, Form, UploadFile
from starlette.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from linkedin_api import Linkedin
import google.generativeai as genai
import docx2txt
from PyPDF2 import PdfReader

# Imports the Cloud Logging client library
import google.cloud.logging

# define key and model

if "GCP_PROJECT" in os.environ:
    # Instantiates a client
    client = google.cloud.logging.Client()

    client.setup_logging()
else:
    logging.basicConfig(level=logging.INFO)


load_dotenv()
GEMINI_AI_API_KEY = os.environ.get("GEMINI_AI_API_KEY")
LINKEDIN_ACC_PASS = os.environ.get("LINKEDIN_ACC_PASS")
LINKEDIN_ACC_EMAIL = os.environ.get("LINKEDIN_ACC_EMAIL")

genai.configure(api_key=GEMINI_AI_API_KEY)
model = genai.GenerativeModel("gemini-pro")


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # Allow credentials (e.g., cookies) in the request
    allow_methods=["*"],  # Allow all HTTP methods, or specify specific methods
    allow_headers=["*"],  # Allow all headers, or specify specific headers
)


def generate_prompt(user_details, job_description):
    prompt_pt1 = """
    Please write a cover letter. Some of the information I provide may be extraneous, such as playing sports, or
    running recreation clubs, please avoid using this information in the cover letter. Try to only
    include only the professional information or information that relates to the company or job role (i.e. job experience, skills, school). 
    Please start with a header. Than write about 4-5 paragraphs each being 3-4 sentences long. Include and introduction, conclusion and sign off.
    I am going to provide you with my information as well as a short description about the role I'm pursuing and the company.
    Here is my personal information information (FOCUS ON EXTRACTING THE FIRST AND LAST NAME AT A MINIMUM):
    """
    prompt_pt2 = """
    Here is a description of the role and company I would like to write the cover letter for:
    """
    prompt = prompt_pt1 + user_details + prompt_pt2 + job_description

    return prompt


def check_file_format(filename):
    extension = filename.lower().split(".")[-1]
    if extension == "pdf":
        return "pdf"
    elif extension == "docx":
        return "docx"
    elif extension == "txt":
        return "txt"
    else:
        return "unknown"


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/generate")
async def generate(resumeFile: UploadFile, jobpostDesc: str = Form(...)):
    print("Job Posting Description:", jobpostDesc)
    print("Resume File Name:", resumeFile.filename)

    resume_text = ""
    file_type = check_file_format(resumeFile.filename)
    if file_type == "pdf":
        pdf_reader = PdfReader(resumeFile.file)
        for page_number in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_number]
            resume_text += page.extract_text()
    elif file_type == "docx":
        resume_text = docx2txt.process(resumeFile.file)
    else:
        print("FILE TYPE NOT SUPPORTED")

    print(resume_text)

    # Generate prompt and make call to gemini
    # TODO: Include information about job role that user is seeking
    prompt = generate_prompt(
        resume_text,
        jobpostDesc,
    )
    responses = model.generate_content(prompt, stream=True)

    return StreamingResponse(
        (response.text for response in responses),
        media_type="text/event-stream",
    )
