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
    


# def profile_summary(profiles: list, client=None, deployment=None):
#       """
#       Generate structured profile summary and evaluation for multiple candidates.
#       Each profile should be a dict inside the list.
#       """
#       results = []
#       system_prompt = """
#         You are an expert AI recruiter specializing in comprehensive candidate analysis.
#         TASK:
#         For each candidate profile JSON, return ONLY a valid JSON object with the following structure:
#         {
#         "profile_summary": "2-3 sentence (must have 200 characters) overview of candidate's professional background and key value proposition",
#         "saral_insight": {
#           "strengths": ["point1", "point2", "point3"],
#           "red_flags": ["flag1", "flag2"],
#           "best_fit_roles": ["Role1", "Role2"]
#         },
#         "professional_experience": [
#           {
#           "job_title": "Senior Full Stack Developer",
#           "duration": "2.5 years",
#           "company_and_dates": "TechCorp • 2022 - Present"
#           }
#         ],
#         "career_stability_overview": {
#           "average_tenure": "X.X years",
#           "current_role": "X.X years", 
#           "total_experience": "X.X years"
#         },
#         "one_line_overview": "Dynamic stability assessment based on actual career pattern"
#         }
#         RULES:
#         1. STRICTLY return only valid JSON. No explanations, no markdown, no text outside the JSON.
#         2. "one_line_overview" must be contextual and vary based on actual career patterns and must be less than 100 characters.
#         3. Calculate actual numbers from the professional experience and incorporate them into the assessment.
#         4. "saral_insight.strengths" min 2 and max 4 concise (best try to get 4 points, should), quantifiable skill/experience highlights explaine in 10 to 12 words per each point.
#         5. "saral_insight.red_flags" rules:
#           - If the candidate is a fresher (no prior work experience), mark it as a red flag.
#           - If the candidate has switched across unrelated fields (e.g., Design → Marketing → Tech), mark it as a red flag.
#           - If the candidate shows inconsistent career patterns (multiple short stints under 1 year, frequent changes), mark it as a red flag.
#           - If the candidate has significant career gaps (over 6 months), mark it as a red flag.
#           - Each red flag must be expressed as a clear, concise sentence of 10–12 words (e.g., "Lacks professional industry experience" or "Frequent job changes raise stability concerns").
#           - If none of the above apply, use "None identified".
#         6. "saral_insight.best_fit_roles" must contain exactly 2 roles with strict restrictions:
#           - DO NOT repeat ANY role titles from the candidate's work history (current OR past positions).
#           - DO NOT use synonyms, variations, or near-matches of existing/past job titles.
#           - DO NOT suggest irrelevant, highly specialized, or unrelated roles (e.g., Technical Architect, Tech Evangelist, Research Scientist) unless the profile explicitly shows expertise in that domain.
#           - Roles must reflect **natural career progression** (e.g., Engineer → Manager/Lead, Analyst → Strategist) or **adjacent functional moves** (e.g., Product → Business Analysis, Operations, Strategy).
#           - Prioritize **managerial, analytical, or strategic roles** over niche technical tracks unless the candidate’s experience justifies it.
#         7. "professional_experience" must cover the entire work history with job_title, duration, and company_and_dates format.
#         8. "career_stability_overview" must calculate average_tenure, current_role, and total_experience in "X.X years" format, following these rules:
#           - Use months as the base unit for all calculations.
#             • Example: 1.2 years = 14 months (12 months + 2 months), 2.7 years = 31 months (24 months + 7 months).
#           - If multiple roles overlap in dates (including within the same company), count overlapping time only once for total_experience.
#           - total_experience = sum of all non-overlapping durations across the entire career (in months → then converted to years).
#           - average_tenure = total_experience ÷ number of distinct roles (count roles, but avoid double-counting overlapping months).
#           - current_role = duration of the most recent role.
#           - Ensure consistency: 
#             • The sum of non-overlapping months should closely match total_experience.
#             • Average tenure must logically align with total_experience ÷ roles.
#           - Convert months to mentioned at the final step, (e.g., 1 year 5 months , 2 years 7 months , 0 years 11 months).
#         9. Return results for multiple candidates as a JSON array of objects.
#         """
#       try:
#         user_prompt = f"""
#         Candidate profiles JSON list:
#         {json.dumps(profiles, indent=2)}
#         Now return ONLY the JSON list as per the defined schema.
#         """
#         response = client.chat.completions.create(
#           model=deployment,
#           messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt}
#           ],
#           temperature=0.0,
#           max_tokens=1500
#         )
#         # Parse AI response
#         result = json.loads(response.choices[0].message.content.strip())
#         results = result
#       except json.JSONDecodeError:
#         results = {"error": "Invalid JSON returned from AI"}
#       except Exception as e:
#         results = {"error": f"Unexpected error: {str(e)}"}
   
#       return results



def calculate_career_stability(professional_experience):
    """
    Calculate career stability overview from professional experience data.
    
    Args:
        professional_experience: List of work experience dictionaries with 'duration' field
        
    Returns:
        Dict with average_tenure, current_role, and total_experience in "X years Y months" format
    """
    if not professional_experience:
        return {
            "average_tenure": "0 years 0 months",
            "current_role": "0 years 0 months", 
            "total_experience": "0 years 0 months"
        }
    
    def parse_duration_to_months(duration_str):
        """Parse duration string to total months"""
        if not duration_str:
            return 0
            
        duration_str = duration_str.lower().strip()
        total_months = 0
        
        # Extract years (handle both "years", "year", "yrs", "yr")
        year_match = re.search(r'(\d+)\s*(?:years?|yrs?)', duration_str)
        if year_match:
            total_months += int(year_match.group(1)) * 12
            
        # Extract months (handle both "months", "month", "mos", "mo")
        month_match = re.search(r'(\d+)\s*(?:months?|mos?)', duration_str)
        if month_match:
            total_months += int(month_match.group(1))
            
        # If only a number is provided, assume it's years
        if not year_match and not month_match:
            number_match = re.search(r'(\d+(?:\.\d+)?)', duration_str)
            if number_match:
                years = float(number_match.group(1))
                total_months = int(years * 12)
                
        return total_months
    
    def months_to_duration_string(months):
        """Convert months to 'X years Y months' format"""
        if months == 0:
            return "0 years 0 months"
            
        years = months // 12
        remaining_months = months % 12
        
        if years == 0:
            return f"0 years {remaining_months} months"
        elif remaining_months == 0:
            return f"{years} years 0 months"
        else:
            return f"{years} years {remaining_months} months"
    
    # Calculate total experience in months
    total_months = 0
    for exp in professional_experience:
        duration = exp.get('duration', '')
        months = parse_duration_to_months(duration)
        total_months += months
    
    # Current role is the first entry (most recent)
    current_role_months = parse_duration_to_months(professional_experience[0].get('duration', ''))
    
    # Average tenure
    num_roles = len(professional_experience)
    average_months = total_months // num_roles if num_roles > 0 else 0
    
    return {
        "average_tenure": months_to_duration_string(average_months),
        "current_role": months_to_duration_string(current_role_months),
        "total_experience": months_to_duration_string(total_months)
    }


def profile_summary(profiles: list, client=None, deployment=None):
      """
      Generate structured profile summary and evaluation for multiple candidates.
      Each profile should be a dict inside the list.
      """
      results = []
      system_prompt = """
        You are an expert AI recruiter specializing in comprehensive candidate analysis.
        TASK:
        For each candidate profile JSON, return ONLY a valid JSON object with the following structure:
        {
        "profile_summary": "2-3 sentence (must have 200 characters) overview of candidate's professional background and key value proposition",
        "saral_insight": {
          "strengths": ["point1", "point2", "point3"],
          "red_flags": ["flag1", "flag2"],
          "best_fit_roles": ["Role1", "Role2"]
        },
        "professional_experience": [
          {
          "job_title": "Senior Full Stack Developer",
          "duration": "2.5 years",
          "company_and_dates": "TechCorp • 2022 - Present"
          }
        ],
        "career_stability_overview": {
          "average_tenure": "X.X years",
          "current_role": "X.X years", 
          "total_experience": "X.X years"
        },
        "one_line_overview": "Dynamic stability assessment based on actual career pattern"
        }
        RULES:
        1. STRICTLY return only valid JSON. No explanations, no markdown, no text outside the JSON.
        2. "one_line_overview" must be contextual and vary based on actual career patterns and must be less than 100 characters.
        3. Calculate actual numbers from the professional experience and incorporate them into the assessment.
        4. "saral_insight.strengths" min 2 and max 4 concise (best try to get 4 points, should), quantifiable skill/experience highlights explaine in 10 to 12 words per each point.
        5. "saral_insight.red_flags" rules:
          - If the candidate is a fresher (no prior work experience), mark it as a red flag.
          - If the candidate has switched across unrelated fields (e.g., Design → Marketing → Tech), mark it as a red flag.
          - If the candidate shows inconsistent career patterns (multiple short stints under 1 year, frequent changes), mark it as a red flag.
          - If the candidate has significant career gaps (over 6 months), mark it as a red flag.
          - Each red flag must be expressed as a clear, concise sentence of 10–12 words (e.g., "Lacks professional industry experience" or "Frequent job changes raise stability concerns").
          - If none of the above apply, use "None identified".
        6. "saral_insight.best_fit_roles" must contain exactly 2 roles with strict restrictions:
          - DO NOT repeat ANY role titles from the candidate's work history (current OR past positions).
          - DO NOT use synonyms, variations, or near-matches of existing/past job titles.
          - DO NOT suggest irrelevant, highly specialized, or unrelated roles (e.g., Technical Architect, Tech Evangelist, Research Scientist) unless the profile explicitly shows expertise in that domain.
          - Roles must reflect **natural career progression** (e.g., Engineer → Manager/Lead, Analyst → Strategist) or **adjacent functional moves** (e.g., Product → Business Analysis, Operations, Strategy).
          - Prioritize **managerial, analytical, or strategic roles** over niche technical tracks unless the candidate’s experience justifies it.
        7. "professional_experience" must cover the entire work history with job_title, duration, and company_and_dates format.
        8. "career_stability_overview" will be calculated separately - just provide the professional_experience data.
        9. Return results for multiple candidates as a JSON array of objects.
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
        
        # If result is a single object, convert to list for processing
        if isinstance(result, dict):
            result = [result]
        
        # Calculate career stability for each profile
        for profile_result in result:
            if 'professional_experience' in profile_result:
                career_stability = calculate_career_stability(profile_result['professional_experience'])
                profile_result['career_stability_overview'] = career_stability
        
        results = result
      except json.JSONDecodeError:
        results = {"error": "Invalid JSON returned from AI"}
      except Exception as e:
        results = {"error": f"Unexpected error: {str(e)}"}

      return results

