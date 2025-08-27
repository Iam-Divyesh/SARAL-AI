def validate_function(location,apify_json):  
      locations = [loc.lower().strip() for loc in location] if location else []
   
      if not locations:
            locations = ["india"]

      
      match_list = []
      unmatched_list = []
      
      for profile in apify_json:  
        address = profile.get("addressWithCountry", "")

        if not address:
            unmatched_list.append(profile)  # no address → unmatched
            continue

        address_lower = [part.strip().lower() for part in address.split(",")]

        
        if "india" in address_lower or any("india" in part for part in address_lower):
            if any(loc in address_lower for loc in locations):
                match_list.append(profile)
            else:
                unmatched_list.append(profile)
        else:
            unmatched_list.append(profile)  



      return match_list , unmatched_list
            
      

def score_candidates(parsed_data, matched_list):
    job_title = parsed_data.get("job_title", "").lower()
    job_keywords = job_title.split() if job_title else []
    
    required_skills = [s.lower() for s in parsed_data.get("skills", [])]

    for profile in matched_list:
        score = 0
        breakdown = {}

        # Headline check (count occurrences of each keyword)
        headline = (profile.get("headline") or "").lower()
        headline_score = 0
        for kw in job_keywords:
            count = headline.count(kw)
            headline_score += count * 15  # each occurrence worth 15
        score += headline_score
        breakdown["headline_match"] = headline_score

        # About check (count occurrences of each keyword)
        about = (profile.get("about") or "").lower()
        about_score = 0
        for kw in job_keywords:
            count = about.count(kw)
            about_score += count * 10  # each occurrence worth 10
        score += about_score
        breakdown["about_match"] = about_score

        # Skills check (exact match count)
        profile_skills = [
            s.get("title", "").lower()
            for s in profile.get("skills", [])
            if isinstance(s, dict)
        ]
        skill_score = 0
        for req_skill in required_skills:
            skill_score += profile_skills.count(req_skill) * 10  # per match worth 10
        score += skill_score
        breakdown["skills_match"] = skill_score

        # Cap score at 100
        profile["score"] = min(round(score), 100)
        profile["score_breakdown"] = breakdown

    # Sort list in-place by score (highest first)
    matched_list.sort(key=lambda x: x.get("score", 0), reverse=True)

    return matched_list

