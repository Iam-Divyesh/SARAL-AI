import requests
import os 
from dotenv import load_dotenv
from postgres_db import fetch_from_saral_data , data_input , check_completeness, cur, get_connection
import re


load_dotenv()

SERP_API_KEY = os.getenv("SERP_API_KEY")





def query_making(data):
      query = "site:linkedin.com/in"

      if data['job_title']:
            query += f' "{data["job_title"]}"'
            
      if data['skills']:
            for i in data['skills']:
                  query += f' "{i}"'
            
      if data.get('experience'):
        exp = str(data['experience']).lower()
        if 'fresher' in exp or 'entry' in exp or 'fresh' in exp:
            query += ' "Fresher"'
        else:
            # Normalize ranges: "2 to 3", "2-3" -> "2-3"
            exp_range = re.sub(r'\s*(to|-)\s*', '-', exp)
            # Ensure numeric only at start
            exp_range = re.findall(r'\d+-?\d*\+?', exp_range)
            if exp_range:
                exp_str = exp_range[0]
                query += f' "{exp_str} years" OR "{exp_str}+ years"'
            
      if data['location']:
            if type(data['location']) == list:
                  for i in data['location']:
                        query += f' "{i}"'
            else:
                  query += f' "{data["location"]}"'
            
            
      if data['work_preference']:
            query += f' "{data["work_preference"]}"'
            
      if data['job_type']:
            query += f' "{data["job_type"]}"'
            
      
      add_keywords = ' -"job" -"jobs" -"hiring" -"vacancy" -"openings" -"career" -"apply"'
      query += add_keywords
      # print(query)

      return query, data['location']


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








