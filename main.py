from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os
import httpx
import asyncio
from google import generativeai as genai

load_dotenv()

# Load API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WHOIS_API_KEY = os.getenv("WHOIS_API_KEY")

# type: ignore[attr-defined]
# Setup Gemini
genai.configure(api_key=GEMINI_API_KEY)  # type: ignore[attr-defined]
model = genai.GenerativeModel(model_name="gemini-2.0-flash")  # type: ignore[attr-defined]

# FastAPI app
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/generate", response_class=HTMLResponse)
async def generate(request: Request, prompt: str = Form(...)):
    domain_ideas = await get_domain_suggestions(prompt)
    gemini_domains = await check_availability(domain_ideas)
    available_domains = [d for d in gemini_domains if d.get("available") == True]
    print(f"\nGemini domains ============ : \n{gemini_domains}")
    print(f"\nAvailable domains ============ : \n{available_domains}")

    return templates.TemplateResponse("index.html", {
        "request": request,
        "prompt": prompt,
        "results": available_domains
    })


async def get_domain_suggestions(prompt: str):
    full_prompt = f"""
You are an AI that suggests unique, brandable, and **available** domain names for the following business idea: "{prompt}".

Follow these rules:
- Include TLDs like .co, .biz, .xyz, .app or .dev
- Avoid famous brand names or trademarks. The names should be catchy, easy to remember, and pronounceable.
- Include unique prefixes or suffixes (get, try, hq, labs, hq, app) to make the names more distinctive.
- For each domain name, include a 1 to 2 sentence explanation about why the suggested domain name is a good fit.

Generate 5 domain names that are likely to be available.  Respond strictly in this format only:
domain1.tld - short explanation
domain2.tld - short explanation
...
"""
    response = model.generate_content(full_prompt)
    lines = response.text.strip().split("\n")
    suggestions = []

    for line in lines:
        if "-" in line:
            name, reason = line.split("-", 1)
            suggestions.append({
                "domain": name.strip(),
                "reason": reason.strip()
            })
    return suggestions


async def check_availability(domains):
    async with httpx.AsyncClient() as client:
        tasks = []
        for d in domains:
            url = f"https://domain-availability.whoisxmlapi.com/api/v1?apiKey={WHOIS_API_KEY}&domainName={d['domain']}&outputFormat=JSON"
            tasks.append(client.get(url))

        responses = await asyncio.gather(*tasks)

        for i, resp in enumerate(responses):
            try:
                data = resp.json()
                domains[i]["available"] = data.get("DomainInfo", {}).get("domainAvailability", "UNKNOWN") == "AVAILABLE"
            except:
                domains[i]["available"] = False
    return domains
