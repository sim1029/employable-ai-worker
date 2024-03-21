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
from linkedin_api import Linkedin
import google.generativeai as genai

# Imports the Cloud Logging client library
import google.cloud.logging

# define key and model
genai.configure(api_key='')
model = genai.GenerativeModel('gemini-pro')


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
    Here is my personal information information:
    """
    prompt_pt2 = """
    Here is a description of the role and company I would like to write the cover letter for:
    """
    prompt = prompt_pt1 + user_details + prompt_pt2 + job_description
    print(prompt + "\n\n\n")

    return prompt


def user_details_to_string(user_info):
    details_string = ""
    for key, value in user_info.items():
        details_string += f"{key}: {value}\n"
    return details_string


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
    # Get linkedin DATA with (Harry) code
    api = Linkedin('discgolfatpitt@gmail.com', 'SlimDogTrillionaire1029')
    split_username = context.linkedinURL.split('/')
    if split_username[-1] == '':
        username  = split_username[-2]
    else: 
        username = split_username[-1]
    profile = api.get_profile(username)
    userDetails = {}
    if "summary" in profile:
        userDetails["summary"]=profile["summary"]
    if profile["experience"] != []:
        if "companyName" in profile["experience"][0] and "description" in profile["experience"][0]:
            userDetails["experience1"]=profile["experience"][0]["companyName"]+"doing "+profile["experience"][0]["description"]
        if len(profile["experience"])>=2:
            if "companyName" in profile["experience"][1] and "description" in profile["experience"][1]:
                userDetails["experience2"]= profile["experience"][1]["companyName"]+"doing "+profile["experience"][1]["description"]
    if profile["projects"] != []:
        if "title" in profile["projects"][0] and "description" in profile["projects"][0]:
            userDetails["project1"]=profile["projects"][0]["title"]+": "+profile["projects"][0]["description"]
    if profile["education"] != []:
        if "fieldOfStudy" in profile["education"][0] and "schoolName" in profile["education"][0]:
            userDetails["education1"]=profile["education"][0]["fieldOfStudy"]+"at "+profile["education"][0]["schoolName"]
            if len(profile["education"])>=2:
                if "fieldOfStudy" in profile["education"][1] and "schoolName" in profile["education"][1]:
                    userDetails["education2"]=profile["education"][1]["fieldOfStudy"]+"at "+profile["education"][1]["schoolName"]

    print("user_details---\n",userDetails.keys(), userDetails)

    # Convert the details dict into a string so it can be passed passed to gemini
    details_as_string = user_details_to_string(userDetails)

    # Generate prompt and make call to gemini
    # TODO: Include information about job role that user is seeking
    prompt = generate_prompt(details_as_string, "Software Engineer at Tesla")
    response = model.generate_content(prompt)

    cover_letter = response.text.replace("*", "")
    print("\ncover_letter---\n")

    # TODO: stream out cover letter

    # Steam response from Vertex AI (Trevor)
    logging.info(context)

    return StreamingResponse(
        generate_mock_cover_letter(),
        media_type="text/event-stream",
    )
