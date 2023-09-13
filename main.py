import os
import openai
import requests
import logging
from fastapi import FastAPI
from starlette.responses import StreamingResponse
from pydantic import BaseModel
from metaphor_python import Metaphor
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware

# Imports the Cloud Logging client library
import google.cloud.logging

if "GCP_PROJECT" in os.environ:
    # Instantiates a client
    client = google.cloud.logging.Client()

    # Retrieves a Cloud Logging handler based on the environment
    # you're running in and integrates the handler with the
    # Python logging module. By default this captures all logs
    # at INFO level and higher
    client.setup_logging()
else:
    logging.basicConfig(level=logging.INFO)


load_dotenv()
openai.api_key = os.environ.get("OPEN_AI_API_KEY")


class Context(BaseModel):
    company_name: str
    linkedin_profile_url: str


app = FastAPI()
client = Metaphor(api_key=os.environ.get("METAPHOR_API_KEY"))

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


def get_user_information(linkedin_url):
    prospeo_url = "https://api.prospeo.io/linkedin-email-finder"
    prospeo_api_key = os.environ.get("PROSPEO_API_KEY")

    required_headers = {"Content-Type": "application/json", "X-KEY": prospeo_api_key}

    data = {"url": linkedin_url, "profile_only": True}

    res = requests.post(prospeo_url, json=data, headers=required_headers)
    user_dict = res.json()
    user_dict = user_dict.get("response", {})
    about = []
    about.append(user_dict.get("full_name", ""))
    about.append(user_dict.get("job_title", ""))
    for i, education in enumerate(user_dict.get("education", [])):
        date = education.get("date", {})
        start = date.get("start", {})
        end = date.get("end", {})
        school = education.get("school", {})
        about.append(
            f"EDUCATION {i+1}: start month: {start.get('month', '')}, start year: {start.get('year', '')} - end month {end.get('month', '')}, end year: {end.get('year', '')} - {education.get('degree_name', '')} in {education.get('field_of_study')} at {school.get('name', '')}"
        )
    about.append(f"SKILLS: {user_dict.get('skills', '')}")
    for i, experience in enumerate(user_dict.get("work_experience", [])):
        date = experience.get("date", {})
        start = date.get("start", {})
        end = date.get("end", {})
        company = experience.get("company", {})
        positions = experience.get("profile_positions")
        position = positions[0] if positions else {}
        about.append(
            f"EXPERIENCE {i+1}: start month: {start.get('month', '')}, start year: {start.get('year', '')} - end month {end.get('month', '')}, end year: {end.get('year', '')} - {position.get('title', '')} {position.get('employment_type')} in {position.get('location','')} at {company.get('name', '')} in this role I... {position.get('description', '')}"
        )
    return "\n".join(about)


def get_company_information(company_name):
    response = client.search(
        f"Here is information all about the company {company_name}:",
        use_autoprompt=True,
        num_results=2,
    )
    contents_res = response.get_contents()
    res = ""
    for content in contents_res.contents:
        res += f"\nTitle: {content.title}\nURL: {content.url}\nContent:\n{content.extract}\n"
    return res


def clean_company_information(information, company_name):
    my_prompt = f"Below are HTML formatted articles potentially information about the company {company_name}. Generate for me a summary of information about the company {company_name} detailing what the company does: {information}"
    completion = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": my_prompt},
        ],
        n=1,
        max_tokens=3000,
    )
    logging.info(completion.usage)
    logging.info(completion.choices[0].message.content)
    return {"name": company_name, "info": completion.choices[0].message.content}


def generate_cover_letter(company_info, user_info):
    my_prompt = f"Below is information about the company {company_info['name']} formatted between HTML tags which you should ignore. There is also information about a jobseeker looking to apply to roles at this company. Please generate a personalized cover letter based on the information you know about the applicant and the company. The letter should be written in the style an undergraduate university student would write. Do not use every detail of the company info or the user info just keep the relevant parts which are most likely to help the candidate stand out and get hired. Never list any information as true about the candidate that you are not directly given for example only list skills that are explicitly listed in the User Info section. This letter should be no longer than 4 or 5 paragraphs Company Info: {company_info['info']} User Info: {user_info}"
    completion_stream = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
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
async def root(context: Context):
    logging.info(context)
    user_info = get_user_information(context.linkedin_profile_url)
    company_info = get_company_information(context.company_name)
    # clean_info = clean_company_information(company_info, context.company_name) Optional cleaning data setp
    logging.info("Generating...")

    return StreamingResponse(
        generate_cover_letter(
            {"name": context.company_name, "info": company_info}, user_info
        ),
        media_type="text/event-stream",
    )
