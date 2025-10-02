import requests
import os 
from dotenv import load_dotenv
from postgres_db import fetch_from_saral_data , data_input , check_completeness, cur, get_connection
import re


load_dotenv()

SERP_API_KEY = os.getenv("SERP_API_KEY")





# def query_making(data):
#       query = "site:linkedin.com/in"

#       if data['job_title']:
#             query += f' "{data["job_title"]}"'
            
#       if data['skills']:
#             for i in data['skills']:
#                   query += f' "{i}"'
            
#       if data.get('experience'):
#         exp = str(data['experience']).lower()
#         if 'fresher' in exp or 'entry' in exp or 'fresh' in exp:
#             query += ' "Fresher"'
#         else:
#             # Normalize ranges: "2 to 3", "2-3" -> "2-3"
#             exp_range = re.sub(r'\s*(to|-)\s*', '-', exp)
#             # Ensure numeric only at start
#             exp_range = re.findall(r'\d+-?\d*\+?', exp_range)
#             if exp_range:
#                 exp_str = exp_range[0]
#                 query += f' "{exp_str} years" OR "{exp_str}+ years"'
            
#       if data['location']:
#             if type(data['location']) == list:
#                   for i in data['location']:
#                         query += f' "{i}"'
#             else:
#                   query += f' "{data["location"]}"'
            
            
#       if data['work_preference']:
#             query += f' "{data["work_preference"]}"'
            
#       if data['job_type']:
#             query += f' "{data["job_type"]}"'
            
      
#       add_keywords = ' -"job" -"jobs" -"hiring" -"vacancy" -"openings" -"career" -"apply"'
#       query += add_keywords
#       # print(query)

#       return query, data['location']


import re

def query_making(data):
    """
    Build a Google dork for LinkedIn profiles similar to:
    site:linkedin.com/in ( "Graphic Designer" ) ( "2 years" OR "2+ years" OR "2 yrs" OR "2yrs" )
    ( "Surat" OR "Surat, Gujarat" OR "Surat Area" ) -site:linkedin.com/jobs -intitle:(...)
    """
    # base
    parts = ['site:linkedin.com/in']

    # job title (put inside its own parentheses)
    job_title = data.get('job_title')
    if job_title:
        # ensure title is quoted and grouped
        parts.append(f'( "{job_title}" )')

    # skills (added as separate quoted tokens - could be many)
    skills = data.get('skills') or []
    for s in skills:
        if s:
            parts.append(f'"{s}"')

    # experience
    exp = data.get('experience')
    if exp:
        exp_str = str(exp).strip().lower()
        if any(w in exp_str for w in ('fresher', 'entry', 'fresh')):
            parts.append('("Fresher")')
        else:
            # normalize "to" and spaced hyphens -> compact, then capture numeric or range like "2", "2-3", "2+"
            norm = re.sub(r'\s*(to|-)\s*', '-', exp_str)
            m = re.search(r'\d+(?:-\d+)?\+?', norm)
            if m:
                base = m.group(0)  # e.g. "2", "2-3", "2+"
                # produce common variants
                variants = [
                    f'"{base} years"',
                    f'"{base}+ years"',
                    f'"{base} yrs"',
                    f'"{base}yrs"'
                ]
                # remove duplicates while preserving order
                seen = set()
                variants = [v for v in variants if not (v in seen or seen.add(v))]
                parts.append('( ' + ' OR '.join(variants) + ' )')

    # location: single or list -> grouped OR (with common variants)
    loc = data.get('location')
    if loc:
        loc_list = loc if isinstance(loc, list) else [loc]
        loc_terms = []
        for l in loc_list:
            if not l:
                continue
            l = l.strip()
            # common location variants for Indian cities (you can add more rules if needed)
            if ',' not in l and not l.lower().endswith('area'):
                loc_terms.append(f'"{l}"')   # optional — only safe for Surat-like cities; adjust if needed
                loc_terms.append(f'"{l} Area"')
            else:
                loc_terms.append(f'"{l}"')
        # dedupe while keeping order
        seen = set()
        loc_terms = [t for t in loc_terms if not (t in seen or seen.add(t))]
        if loc_terms:
            parts.append('( ' + ' OR '.join(loc_terms) + ' )')

    # work preference / job type (optional extra quoted tokens)
    wp = data.get('work_preference')
    if wp:
        parts.append(f'"{wp}"')
    jt = data.get('job_type')
    if jt:
        parts.append(f'"{jt}"')

    # negative filters: avoid job pages and recruiter titles
    negatives = '-site:linkedin.com/jobs -intitle:("jobs" OR "hiring" OR "vacancy" OR "vacancies" OR "career" OR "apply")'
    parts.append(negatives)

    # join with spaces
    query = ' '.join(parts)

    return query, data.get('location')



def serp_api_call(query,start = 0, results_per_page = 10):
      data = None

      # SERP API CALL

      params = {
            "engine": "google",
            "q": query.strip(),
            "api_key": SERP_API_KEY,
            "hl": "en",
            "gl": "in",
            "google_domain": "google.co.in",
            "location": "India",
            "num": results_per_page,
            "start": start,
            "safe": "active"
            
      }

      try:
            response = requests.get("https://serpapi.com/search", params=params)
            if response.status_code == 200:
                  data = response.json()
                  
            else:
                  print(f"Request failed with status code: {response.status_code}")
      except:
            pass

      return data








