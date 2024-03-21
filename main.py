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


class Context(BaseModel):
    linkedinURL: str
    jobpostDesc: str


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


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/generate")
async def generate(context: Context):
    # Get linkedin DATA with (Harry) code
    try:
        api = Linkedin(LINKEDIN_ACC_EMAIL, LINKEDIN_ACC_PASS)
        split_username = context.linkedinURL.split("/")
        if split_username[-1] == "":
            username = split_username[-2]
        else:
            username = split_username[-1]
        profile = api.get_profile(username)
        userDetails = {}
        if "summary" in profile:
            userDetails["summary"] = profile["summary"]
        if profile["experience"] != []:
            if (
                "companyName" in profile["experience"][0]
                and "description" in profile["experience"][0]
            ):
                userDetails["experience1"] = (
                    profile["experience"][0]["companyName"]
                    + "doing "
                    + profile["experience"][0]["description"]
                )
            if len(profile["experience"]) >= 2:
                if (
                    "companyName" in profile["experience"][1]
                    and "description" in profile["experience"][1]
                ):
                    userDetails["experience2"] = (
                        profile["experience"][1]["companyName"]
                        + "doing "
                        + profile["experience"][1]["description"]
                    )
        if profile["projects"] != []:
            if (
                "title" in profile["projects"][0]
                and "description" in profile["projects"][0]
            ):
                userDetails["project1"] = (
                    profile["projects"][0]["title"]
                    + ": "
                    + profile["projects"][0]["description"]
                )
        if profile["education"] != []:
            if (
                "fieldOfStudy" in profile["education"][0]
                and "schoolName" in profile["education"][0]
            ):
                userDetails["education1"] = (
                    profile["education"][0]["fieldOfStudy"]
                    + "at "
                    + profile["education"][0]["schoolName"]
                )
                if len(profile["education"]) >= 2:
                    if (
                        "fieldOfStudy" in profile["education"][1]
                        and "schoolName" in profile["education"][1]
                    ):
                        userDetails["education2"] = (
                            profile["education"][1]["fieldOfStudy"]
                            + "at "
                            + profile["education"][1]["schoolName"]
                        )
    except Exception as e:
        print(e)
        userDetails = {
            "summary": "",
            "experience1": "",
            "experience2": "",
            "project1": "",
            "education1": "",
            "education2": "",
        }

    # Convert the details dict into a string so it can be passed passed to gemini
    details_as_string = user_details_to_string(userDetails)

    # Generate prompt and make call to gemini
    # TODO: Include information about job role that user is seeking
    prompt = generate_prompt(
        details_as_string,
        "Software engineer at Tesla",
    )
    responses = model.generate_content(prompt, stream=True)

    logging.info(context)

    return StreamingResponse(
        (response.text for response in responses),
        media_type="text/event-stream",
    )
