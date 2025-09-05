import psycopg2
import json
from datetime import datetime, timedelta



hostname = "13.233.107.79"
database = "saral_ai"
username = "saral_user"
pwd = "8k$ScgT97y9£>D"
port_id = 5432



conn = None
cur = None


def get_connection():
    return psycopg2.connect(
        host=hostname,
        dbname=database,
        user=username,
        password=pwd,
        port=port_id
    )

def check_completeness(cur, name, location, linkedin_url, headline, skills, experience):
    is_complete = True
    message = "this data is complete"

    required_fields = [name, location, linkedin_url]
    for field in required_fields:
        if field in [None, "", []]:
            is_complete = False
            message = "missing required fields"
            break

    cur.execute("SELECT id FROM profiles WHERE linkedin_url = %s", (linkedin_url,))
    existing = cur.fetchone()
    if existing:
        return False, "this data is duplicate", False

    optional_fields = [headline, skills, experience]
    for field in optional_fields:
        if field in [None, "", []]:
            is_complete = False
            message = "some optional fields missing"
            break

    return True, message, is_complete







def data_input(json_data):
      insert_script = '''
            INSERT INTO profiles
            (name, location, email, linkedin_url, headline, skills, about, experience, profile_pic, is_complete, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      '''    
      with conn.cursor() as cur:
            for d in json_data:
                  name = d.get("fullName")
                  location = d.get("addressWithCountry")
                  email = d.get("email")
                  linkedin_url = d.get("linkedinUrl")
                  headline = d.get("headline")
                  profile_pic = d.get("profilePic")

                  # Safe parsing of skills
                  skills_raw = d.get("skills", [])
                  if isinstance(skills_raw, str):
                        try:
                              skills_raw = json.loads(skills_raw)
                        except:
                              skills_raw = []
                  skills_list = [s.get("title") for s in skills_raw if isinstance(s, dict)]
                  skills = json.dumps(skills_list)

                  # Safe parsing of experiences
                  experience_raw = d.get("experiences", [])
                  if isinstance(experience_raw, str):
                        try:
                              experience_raw = json.loads(experience_raw)
                        except:
                              experience_raw = []
                  experience = json.dumps(experience_raw)

                  about = d.get("about")

                  success, message, is_complete = check_completeness(
                        cur, name, location, linkedin_url, headline, skills_list, experience_raw
                  )
                  print(message)
                  
                  if not is_complete:  
                        continue 

                  created_at = datetime.now()
                  cur.execute(
                        insert_script,
                        (
                              name, location, email, linkedin_url, headline,
                              skills, about, experience, profile_pic, is_complete, created_at
                        )
                  )
                  
                  conn.commit()

            

def fetch_from_saral_data(serp_data, conn):
      if not serp_data or not isinstance(serp_data, dict):
        print("⚠️ fetch_from_saral_data: serp_data is None or not a dict")
        return [], []   # return empty lists safely
  
      results = []
      remaining = []
      one_month_ago = datetime.now() - timedelta(days=30)

      serp_json = {}
      for idx, result in enumerate(serp_data.get("organic_results", []), start=1):
            link = result.get("link")
            if link and ("linkedin.com/in/" in link or "in.linkedin.com/in/" in link):
                  clean_link = link.replace("in.linkedin.com", "linkedin.com")
                  serp_json[idx] = clean_link

      # create a fresh cursor
      with conn.cursor() as cur:
            for link in serp_json.values():
                  cur.execute("""
                        SELECT name, location, email, linkedin_url, headline, skills, about, experience, profile_pic, is_complete, created_at
                        FROM saral_data
                        WHERE linkedin_url = %s AND created_at >= %s

                  """, (link, one_month_ago))

                  row = cur.fetchone()
                  if row:
                        results.append({
                        "fullName": row[0] if row[0] else "Unknown",
                        "addressWithCountry": row[1] if row[1] else "Unknown",
                        "email": row[2] if row[2] else "-",
                        "linkedinUrl": row[3] if row[3] else "-",
                        "headline": row[4] if row[4] else "-",
                        "skills": row[5] if row[5] else [],
                        "about": row[6] if row[6] else "",
                        "experiences": row[7] if row[7] else [],
                        "profilePic": row[8] if row[8] else None,   
                        "is_complete": row[9],
                        "created_at": row[10]
                        })


                  else:
                        remaining.append(link)

      return results, remaining


def store_prompt(conn, prompt: str, parsed_json: dict):
    job_title = parsed_json.get("job_title")
    skills = parsed_json.get("skills", [])
    experience = parsed_json.get("experience")
    location = parsed_json.get("location", [])
    work_preference = parsed_json.get("work_preference")
    job_type = parsed_json.get("job_type")
    is_indian = parsed_json.get("is_indian")

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO profiles
                (prompt, job_title, skills, experience, location, work_preference, job_type, created_at,is_indian)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s,%s)
            """, (
                prompt,
                job_title,
                json.dumps(skills) if skills else None,   # ensure proper type
                experience,
                location if location else None,
                work_preference,
                job_type,
                datetime.now(),
                is_indian
            ))
        conn.commit()
    except Exception as e:
        print("Error inserting prompt:", e)
        conn.rollback()   




try:
      conn = psycopg2.connect(
            host=hostname, dbname=database, user=username, password=pwd, port=port_id
      )

      cur = conn.cursor()

      create_script = """
                  CREATE TABLE IF NOT EXISTS profiles (
                  id SERIAL PRIMARY KEY,
                  name TEXT,
                  location TEXT,
                  email TEXT,
                  linkedin_url TEXT,
                  headline TEXT,
                  skills JSONB,
                  about TEXT,
                  experience JSONB,
                  profile_pic TEXT,          
                  is_complete BOOLEAN,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                  );
            """
      
      # cur.execute(create_script)
            
      
      

      conn.commit()
      
      
      
      
except Exception as error:
    print(error)


finally:
#     if cur is not None:
#         cur.close()
#     if conn is not None:
#         conn.close()
      pass






