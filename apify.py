from apify_client import ApifyClient
from dotenv import load_dotenv
import os

load_dotenv()

APIFY_API_KEY = os.getenv("APIFY_API_TOKEN")


linkedin_profiles = {
    "1": "https://linkedin.com/in/ramya-rajendran-730b46a9",
    "2": "https://linkedin.com/in/dhruv-patel-39a333263",
    "3": "https://linkedin.com/in/harsh-patel9797",
    "4": "https://linkedin.com/in/denish-patel-64a8bb183",
    "5": "https://linkedin.com/in/swapnildjoshi",
    "6": "https://linkedin.com/in/bhavin-vaghasiya-82839522a",
    "7": "https://linkedin.com/in/dharmesh-sharma-6a09a0192",
    "8": "https://linkedin.com/in/bhawanii-raajpurohit-72991b1b5",
    "9": "https://linkedin.com/in/trushali-miyani-69aa26276",
    "10": "https://linkedin.com/in/isha-bhanderi-244638246",
}

client = ApifyClient(APIFY_API_KEY)

def apify_call(linkedin_profiles):
      list_links = list(linkedin_profiles.values())
      
      print(list_links)

      run_input = {
            "profileUrls": list_links
      }

      run = client.actor("2SyF0bVxmgGr8IVCZ").call(run_input=run_input)

      cleaned_profiles = []


      for idx, item in enumerate(client.dataset(run["defaultDatasetId"]).iterate_items(),start=1):
            # apify_json[idx] = item

            # raw_skills = item.get("skills", [])
            # skill_titles = [s.get("title") for s in raw_skills if "title" in s]

            # profile_data = {
            #       "fullName":item.get("fullName"),
            #       "profilePic": item.get("profilePic"),
            #       "linkedinUrl":item.get("linkedinUrl"),
            #       "headline":item.get("headline"),
            #       "about":item.get("about"),
            #       "skills":skill_titles,
            #       "email": item.get("email"),
            #       "addressWithCountry": item.get("addressWithCountry"),
            #       "experience": item.get("experience")
            # }

            # profile_data = {k: v for k, v in profile_data.items() if v}
            cleaned_profiles.append(item)



      
      return cleaned_profiles
            

