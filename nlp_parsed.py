import re 
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import json
from postgres_db import store_prompt, conn
from candidates import candidates


load_dotenv()

SERP_API_KEY = os.getenv("SERP_API_KEY")
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
api_version = os.getenv("AZURE_OPENAI_API_VERSION")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

client = None  # Initialize client as None

try:
    client = AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=endpoint)
except Exception as e:
    print(f"Failed to initialize Azure OpenAI client: {e}")
    client = None
    

def parse_recruiter_query(query):
    """Parse recruiter query using AI to extract structured data"""
    if not client:
        # Mock function when Azure OpenAI is not available
        import re
        words = query.lower().split()
        
        # Extract job title (basic pattern matching)
        job_title = "Developer"
        if "python" in words: job_title = "Python Developer"
        elif "java" in words: job_title = "Java Developer"
        elif "data" in words: job_title = "Data Scientist"
        elif "frontend" in words: job_title = "Frontend Developer"
        elif "backend" in words: job_title = "Backend Developer"
        
        # Extract skills
        skills = []
        if "python" in words: skills.append("Python")
        if "java" in words: skills.append("Java")
        if "javascript" in words: skills.append("JavaScript")
        if "react" in words: skills.append("React")
        if "django" in words: skills.append("Django")
        
        # Extract experience
        experience = "2"
        for i, word in enumerate(words):
            if word.isdigit() and i+1 < len(words) and ("year" in words[i+1] or "yr" in words[i+1]):
                experience = word
                break
        if "fresher" in words: experience = "fresher"
        
        # Extract location
        location = []
        indian_cities = ["mumbai", "delhi", "bangalore", "pune", "hyderabad", "chennai", "kolkata", "ahmedabad", "surat", "gurgaon"]
        for city in indian_cities:
            if city in words:
                location.append(city.title())
        
        return {
            "job_title": job_title,
            "skills": skills,
            "experience": experience,
            "location": location,
            "work_preference": "remote" if "remote" in words else None,
            "job_type": "full-time" if "full-time" in words else None,
            "is_indian": True
        }

    try:
        system_prompt = """You are an AI assistant that extracts structured recruitment information from natural language queries.

        Fields to extract:
        - job_title: ONLY the exact position title they're hiring for (e.g., "Python Developer", "Data Scientist"). 
        DO NOT include phrases like "looking for", "need a", "hiring", etc.
        - skills: Array of required technical skills mentioned (e.g., ["Python", "Django", "SQL"])
        - experience: Required experience in years (numeric value or range). For fresher candidates, use "fresher" exactly.
        - location: Array of city names if multiple cities are mentioned, or single city name as Array if only one city is mentioned.
        - work_preference: Work mode preference - one of: "remote", "onsite", "hybrid", null
        - job_type: Employment type - one of: "full-time", "part-time", "contract", "internship", null
        - is_indian: true if the job location(s) are in India, false otherwise. 
                    IMPORTANT: If no location is mentioned, always set is_indian = true.
        - is_valid: true if the query is related to jobs/recruitment, false otherwise.

        CRITICAL INSTRUCTIONS:
        1. For job_title, NEVER include phrases like "looking for", "need", "hiring", etc.
        2. For experience, if the query mentions "fresher", "fresh graduate", "entry level", use exactly "fresher"
        3. For is_indian, check the location(s). If the location(s) are Indian cities or the query context is India-based, return true. 
        If no location is mentioned at all, default to true.
        4. For is_valid:
        - true if the query clearly refers to a job role, hiring, recruitment, skills, or candidates.
        - false if the query is unrelated to jobs (e.g., "this is a dog", "the monkey is dancing").
        5. Return ONLY valid JSON without any explanation or additional text.
        6. Use your knowledge to recognize job titles across all industries and domains."""


        user_prompt = f"""Extract recruitment information from this query: "{query}"

        Examples of correct extraction:

        Input: "We are looking for a Python developer with 3 years experience from Mumbai"
        Output: {{"job_title": "Python Developer", "skills": ["Python"], "experience": "3", "location": ["Mumbai"], "work_preference": null, "job_type": null, "is_indian": true, "is_valid": true}}

        Input: "Need a senior React frontend developer with Redux, TypeScript, 5+ years"
        Output: {{"job_title": "React Frontend Developer", "skills": ["React", "Redux", "TypeScript"], "experience": "5+", "location": null, "work_preference": null, "job_type": null, "is_indian": true, "is_valid": true}}

        Input: "python developer with 2 year of experience from surat, ahmedabad and mumbai"
        Output: {{"job_title": "Python Developer", "skills": ["Python"], "experience": "2", "location": ["Surat", "Ahmedabad", "Mumbai"], "work_preference": null, "job_type": null, "is_indian": true, "is_valid": true}}

        Input: "Remote React developer needed, 5 years experience, Redux, TypeScript"
        Output: {{"job_title": "React Developer", "skills": ["React", "Redux", "TypeScript"], "experience": "5", "location": null, "work_preference": "remote", "job_type": null, "is_indian": true, "is_valid": true}}

        Input: "Looking for fresher Java developer from Delhi"
        Output: {{"job_title": "Java Developer", "skills": ["Java"], "experience": "fresher", "location": ["Delhi"], "work_preference": null, "job_type": null, "is_indian": true, "is_valid": true}}

        Input: "This is a dancing monkey"
        Output: {{"job_title": null, "skills": null, "experience": null, "location": null, "work_preference": null, "job_type": null, "is_indian": true, "is_valid": false}}

        Input: "I like pizza and cold coffee"
        Output: {{"job_title": null, "skills": null, "experience": null, "location": null, "work_preference": null, "job_type": null, "is_indian": true, "is_valid": false}}

        Input: "Let's play cricket tomorrow evening"
        Output: {{"job_title": null, "skills": null, "experience": null, "location": null, "work_preference": null, "job_type": null, "is_indian": true, "is_valid": false}}

        Now extract from the query: "{query}"

        Remember: 
        1. Extract ONLY the job title without any prefixes like "looking for", "need", etc.
        2. Extract ONLY the city/location name without additional text.
        3. For fresher candidates, use exactly "fresher" as experience value.
        4. For is_indian: true if job location(s) are Indian, false otherwise. If no location is provided, always return true.
        5. For is_valid: true only if the query is job/recruitment-related, false otherwise.
        6. Return ONLY valid JSON."""


        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=500
        )

        return json.loads(response.choices[0].message.content)

    except json.JSONDecodeError:
        return {"error": "Invalid JSON returned from AI"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}



def prompt_enhancer(prompt: str) -> str:
    """Enhance recruiter prompt to be clearer and more structured"""
    if not client:
        return prompt  # fallback: return original if Azure client not available

    try:
        system_prompt = """You are an AI assistant that enhances recruiter job search prompts.
        Your goal is to:
        1. Clean up grammar and spelling mistakes.
        2. Expand shorthand into full professional wording.
        3. Preserve all important details: job title, skills, experience, location, work mode, job type.
        4. Do NOT invent new requirements — only clarify what's already in the query.
        5. Do not copy examples literally — adapt based on the actual input.
        6. Return ONLY the enhanced recruiter prompt as plain text (no JSON)."""

        user_prompt = f"""Rewrite and enhance this recruiter query for clarity:

        Input: "{prompt}"

        Example Enhancements:
        - "python dev 2yr exp surat" → "Looking for a Python Developer with 2 years of experience in Surat."
        - "need react js fresher remote" → "Hiring a React.js Developer at fresher level for a remote role."
        - "java 5+ exp ahmedabad onsite" → "Looking for a Java Developer with over 5 years of experience for an onsite role in Ahmedabad."
        - "data analyst 3 years bangalore hybrid" → "Seeking a Data Analyst with 3 years of experience for a hybrid position in Bangalore."
        - "ui ux designer fresher mumbai internship" → "Hiring a UI/UX Designer, fresher level, for an internship role in Mumbai."

        Now enhance this query: "{prompt}"
        """

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,   # slightly more creative
            max_tokens=200
        )

        enhanced_prompt = response.choices[0].message.content.strip()
        return enhanced_prompt

    except Exception as e:
        print(f"Error in prompt_enhancer: {e}")
        return prompt  # fallback to original
    


def profile_summary(profiles: list, client=None, deployment=None):
    """
    Generate structured profile summary and evaluation for multiple candidates.
    Each profile should be a dict inside the list.
    """
    results = []
    
    system_prompt = """
    You are an expert AI recruiter.

    TASK:
    For each candidate profile JSON, return ONLY a valid JSON object with the following structure:

    {
      "strengths": ["point1", "point2", "point3"],
      "weaknesses": ["point1", "point2"],
      "saral_summary": {
        "profile_category": "Low/Medium/High",
        "best_fit_roles": ["Role1", "Role2"]
      },
      "overall_verdict": "1–2 sentence recommendation"
    }

    RULES:
    1. STRICTLY return only valid JSON. No explanations, no markdown, no text outside the JSON.
    2. "strengths" must have 3–5 concise, positive skill/experience highlights.
    3. "weaknesses" must have 1–3 realistic improvement areas.
    4. "saral_summary.profile_category" must be derived from `fit_score` (0–30=Low, 31–70=Medium, 71–100=High).
    5. "saral_summary.best_fit_roles" must contain exactly 2 roles related to their domain.
    6. DO NOT repeat the candidate’s current role/headline in best_fit_roles. Instead, suggest alternative but relevant roles
       based on their skills, experience, and career progression. 
       Example: 
       If headline = "Business Development Executive", best_fit_roles can be ["Business Development Manager", "Sales Executive"], but never "Business Development Executive" again.
       
       If headline = "Software Engineer", best_fit_roles can be ["Full Stack Developer", "Backend Developer"], but never "Software Engineer" again.  

       If headline = "Data Analyst", best_fit_roles can be ["Business Intelligence Analyst", "Data Scientist"], but never "Data Analyst" again.  

       If headline = "Graphic Designer", best_fit_roles can be ["UI/UX Designer", "Visual Designer"], but never "Graphic Designer" again.  

       If headline = "HR Executive", best_fit_roles can be ["HR Manager", "Talent Acquisition Specialist"], but never "HR Executive" again.  

       If headline = "Content Writer", best_fit_roles can be ["Copywriter", "Content Strategist"], but never "Content Writer" again.  

    7. Roles must be derived ONLY from the candidate's profile (headline, skills, experience). No invented roles, no unrelated domains.
    8. "overall_verdict" must be a recruiter-ready recommendation in max 2 sentences.
    9. Return results for multiple candidates as a JSON list of objects, one per candidate.
    """

    try:
        user_prompt = f"""
        Candidate profiles JSON list:
        {json.dumps(profiles, indent=2)}

        Now return ONLY the JSON list as per the defined schema.
        """

        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=1500
        )

        # Parse AI response
        result = json.loads(response.choices[0].message.content.strip())
        results = result

    except json.JSONDecodeError:
        results = {"error": "Invalid JSON returned from AI"}
    except Exception as e:
        results = {"error": f"Unexpected error: {str(e)}"}
    
    return results


