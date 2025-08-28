from flask import Flask, render_template, request, jsonify, session
import re
import os
import json
import traceback
from dotenv import load_dotenv
from openai import AzureOpenAI

# Import your custom modules (make sure these are available)
try:
    from nlp_parsed import parse_recruiter_query, prompt_enhancer
    from SERP import query_making, serp_api_call
    from apify import apify_call
    from validate import validate_function, score_candidates
    from postgres_db import fetch_from_saral_data, check_completeness, data_input, cur, conn, store_prompt
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some modules not available: {e}")
    MODULES_AVAILABLE = False

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Mock functions for when modules aren't available (for testing)
def mock_parse_recruiter_query(query):
    return {
        "job_title": "Software Engineer",
        "skills": ["Python", "Flask"],
        "experience": "3-5",
        "location": "Mumbai",
        "work_preference": "Remote",
        "job_type": "Full-time",
        "is_indian": True
    }

def mock_prompt_enhancer(prompt):
    return f"Enhanced: {prompt} - Looking for skilled professionals"

def mock_query_making(parsed_data):
    return "https://linkedin.com/search", ["Mumbai", "Delhi"]

def mock_serp_api_call(query, start=0, results_per_page=10):
    return [f"https://linkedin.com/in/user{i}" for i in range(start, start + results_per_page)]

def mock_fetch_from_saral_data(serp_data, conn):
    return [], serp_data  # Return empty saral_data, all URLs as remaining

def mock_apify_call(serp_json):
    mock_profiles = []
    for i in range(min(5, len(serp_json))):
        mock_profiles.append({
            "fullName": f"John Doe {i+1}",
            "headline": "Software Engineer with 5+ years experience",
            "addressWithCountry": "Mumbai, India",
            "email": f"john{i+1}@example.com",
            "linkedinUrl": f"https://linkedin.com/in/johndoe{i+1}",
            "skills": [{"title": "Python"}, {"title": "Flask"}, {"title": "JavaScript"}],
            "about": "Experienced software developer with expertise in web technologies...",
            "experiences": [
                {
                    "title": "Senior Software Engineer",
                    "subtitle": "Tech Company",
                    "caption": "Jan 2020 - Present",
                    "description": [{"text": "Developed web applications using Python and Flask"}]
                }
            ],
            "profilePic": "https://via.placeholder.com/150",
            "is_complete": "Complete Profile"
        })
    return mock_profiles

def mock_validate_function(location, candidates):
    # Split candidates into matched and unmatched (80% matched, 20% unmatched)
    split_point = int(len(candidates) * 0.8)
    return candidates[:split_point], candidates[split_point:]

def mock_score_candidates(parsed_data, candidates):
    for i, candidate in enumerate(candidates):
        candidate['score'] = round(85 + (i % 15), 1)  # Scores between 85-100
    return candidates

def mock_data_input(candidates):
    pass

def mock_store_prompt(conn, prompt, parsed_data):
    pass

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parse_query', methods=['POST'])
def parse_query():
    try:
        data = request.json
        user_input = data.get('query', '').strip()
        
        if not user_input:
            return jsonify({'error': 'Please enter a valid query'})
        
        if MODULES_AVAILABLE:
            parsed_data = parse_recruiter_query(user_input)
        else:
            parsed_data = mock_parse_recruiter_query(user_input)
        
        return jsonify({'success': True, 'parsed_data': parsed_data})
    
    except Exception as e:
        return jsonify({'error': f'Error parsing query: {str(e)}'})

@app.route('/enhance_prompt', methods=['POST'])
def enhance_prompt():
    try:
        data = request.json
        user_input = data.get('query', '').strip()
        
        if not user_input:
            return jsonify({'error': 'Please enter a valid query'})
        
        if MODULES_AVAILABLE:
            enhanced = prompt_enhancer(user_input)
        else:
            enhanced = mock_prompt_enhancer(user_input)
        
        return jsonify({'success': True, 'enhanced_query': enhanced})
    
    except Exception as e:
        return jsonify({'error': f'Error enhancing prompt: {str(e)}'})

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.json
        user_input = data.get('query', '').strip()
        current_page = data.get('page', 0)
        
        if not user_input:
            return jsonify({'error': 'Please enter a valid query'})
        
        # Parse query
        if MODULES_AVAILABLE:
            parsed_data = parse_recruiter_query(user_input)
            print(parsed_data)
        else:
            parsed_data = mock_parse_recruiter_query(user_input)
            print(parsed_data)
        
        if "error" in parsed_data:
            return jsonify({'error': parsed_data["error"]})
        
        if parsed_data.get("is_indian") == False:
            return jsonify({'error': 'Our platform is not allowing search outside of India'})
        
        # Store prompt
        if MODULES_AVAILABLE:
            store_prompt(conn, user_input, parsed_data)
        else:
            mock_store_prompt(None, user_input, parsed_data)
        
        # Get query and location
        if MODULES_AVAILABLE:
            query, location = query_making(parsed_data)
            print(query)
            
        else:
            query, location = mock_query_making(parsed_data)
            print(query)
            
        
        # Pagination
        results_per_page = 10
        start = current_page * results_per_page
        
        # Get SERP data
        if MODULES_AVAILABLE:
            serp_data = serp_api_call(query, start=start, results_per_page=results_per_page)
            saral_data, remain_urls = fetch_from_saral_data(serp_data, conn)
        else:
            serp_data = mock_serp_api_call(query, start=start, results_per_page=results_per_page)
            saral_data, remain_urls = mock_fetch_from_saral_data(serp_data, None)
        
        # Process remaining URLs with Apify
        apify_json = {}
        if len(remain_urls) >= 1:
            serp_json = {idx: url for idx, url in enumerate(remain_urls, start=1)}
            
            if MODULES_AVAILABLE:
                apify_json = apify_call(serp_json)
            else:
                apify_json = mock_apify_call(serp_json)
        
        # Combine data
        if apify_json:
            total_candidates = saral_data + apify_json
        else:
            total_candidates = saral_data
        
        # Store data
        if MODULES_AVAILABLE:
            data_input(total_candidates)
        else:
            mock_data_input(total_candidates)
        
        # Validate and score
        if MODULES_AVAILABLE:
            matched, unmatched = validate_function(location, total_candidates)
            matched = score_candidates(parsed_data, matched)
        else:
            matched, unmatched = mock_validate_function(location, total_candidates)
            matched = mock_score_candidates(parsed_data, matched)
        
        return jsonify({
            'success': True,
            'parsed_data': parsed_data,
            'matched_results': matched,
            'unmatched_results': unmatched,
            'current_page': current_page
        })
    
    except Exception as e:
        print(f"Error in search: {traceback.format_exc()}")
        return jsonify({'error': f'Search error: {str(e)}'})

# if __name__ == '__main__':
#     # Ensure templates directory exists
#     if not os.path.exists('templates'):
#         os.makedirs('templates')
    
#     app.run(debug=True, host='0.0.0.0', port=5000)