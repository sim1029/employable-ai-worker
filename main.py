import os
from fastapi.responses import JSONResponse
import openai
import requests
import logging
import docx2txt
from PyPDF2 import PdfReader
from fastapi import FastAPI, UploadFile, Form
from bs4 import BeautifulSoup
from starlette.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

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
    company_name: str
    linkedin_profile_url: str


app = FastAPI()

origins = [
    "*",  # origin of frontend application
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Allow credentials (e.g., cookies) in the request
    allow_methods=["*"],  # Allow all HTTP methods, or specify specific methods
    allow_headers=["*"],  # Allow all headers, or specify specific headers
)


def download_webpage_content(url):
    try:
        response = requests.get(url)
        output = ""
        if response.status_code == 200:
            html_page = response.content
            soup = BeautifulSoup(html_page, "html.parser")
            text = soup.find_all(text=True)

            output = ""
            blacklist = [
                "[document]",
                "noscript",
                "header",
                "html",
                "meta",
                "head",
                "input",
                "script",
                # there may be more elements you don't want, such as "style", etc.
            ]

            for t in text:
                if t.parent.name not in blacklist:
                    output += "{} ".format(t)
            return output
        else:
            print(f"Failed to download content. Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


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


def generate_cover_letter(user_data, company_data):
    my_prompt = f"""
    Below is the resume of an individual and a webpage of the job posting they are applying to. Write a cover letter for this applicant which is formatted like the outline below: 
    
    === Outline ===
    Dear Hiring Manager, 
    Paragraph 1 (Introduction)
    Paragraphs 2-4 (Body)
    Paragraph 5 (Conclusion)
    Sincirely, 
        [Applicant Name]
    ===============
    
    Paragraph 1 is an introduction and should state clearly in the opening sentence the purpose for the letter and a brief professional introduction, specify why the candidate is interested in that specific position and organization, and finally provide an overview of the main strengths and skills the candidate brings to the role. 
    
    Paragraphs 2-4 are the body of the letter and should cite a couple of examples from the candidate's experience that supports their ability to be successful in the position or organization. Try not to simply repeat the resume in paragraph form, complement the resume by offering a little more detail about key experiences. Discuss what skills the candidate has developed and connect these back to the target role. 
    
    Paragraph 5 should restate succinctly the candidate's interest in the role and why they are a good candidate and thank the reader for their time and consideration.
    
    There should be no more than 5 paragraphs generated
    
    When generating your response, keep these guidelines in mind: 
    - Focus the letter on the future and what the applicant hopes to accomplish
    - Open the letter strong by outlining why this job is exciting to the applicant and what they bring to the table
    - Convey Enthusiasm by making it clear why the applicant wants the job
    - Keep it short so that it is brief enough someone can read it at a glance
    - Don't make the letter generic, it should contain content that only this applicant could have written
    
    === Resume ===
    {user_data}
    ==============
    
    === Job Posting ===
    {company_data}
    ===================
    """
    completion_stream = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": my_prompt},
        ],
        n=1,
        max_tokens=4000,
        stream=True,
    )
    for event in completion_stream:
        if "content" in event["choices"][0].delta:
            current_response = event["choices"][0].delta.content
            yield current_response


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/generate")
async def upload_file(resumeFile: UploadFile, jobpostURL: str = Form(...)):
    print("Job Posting URL:", jobpostURL)
    print("Resume File Name:", resumeFile.filename)

    text = ""
    file_type = check_file_format(resumeFile.filename)
    if file_type == "pdf":
        pdf_reader = PdfReader(resumeFile.file)
        for page_number in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_number]
            text += page.extract_text()
    elif file_type == "docx":
        text = docx2txt.process(resumeFile.file)
    else:
        print("FILE TYPE NOT SUPPORTED")
    # Set max at 1000 tokens for info about you
    user_data = text[:1500]
    role_data = download_webpage_content(jobpostURL)[:3500]
    print(role_data)

    return StreamingResponse(
        generate_cover_letter(user_data, role_data),
        media_type="text/event-stream",
    )
