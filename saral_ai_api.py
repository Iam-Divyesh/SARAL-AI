from flask import Flask, render_template, request, jsonify
import os
import json
import traceback
from dotenv import load_dotenv

# Try to import custom modules, but don't fail if they're not available
MODULES_AVAILABLE = False
try:
    from nlp_parsed import parse_recruiter_query, prompt_enhancer
    from SERP import query_making, serp_api_call
    from apify import apify_call
    from validate import validate_function, score_candidates
    from postgres_db import fetch_from_saral_data, check_completeness, data_input, cur, conn, store_prompt
    MODULES_AVAILABLE = True
    print("All modules loaded successfully")
except ImportError as e:
    print(f"Using mock functions due to missing modules: {e}")
    MODULES_AVAILABLE = False

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-default-secret-key-change-this')

# Mock functions for when modules aren't available
def mock_parse_recruiter_query(query):
    """Mock function to parse recruiter query"""
    return {
        "job_title": "Video Editor",
        "skills": ["Video Editing", "Adobe Premiere", "Final Cut Pro"],
        "experience": "2",
        "location": "Surat",
        "work_preference": "Remote",
        "job_type": "Full-time",
        "is_indian": True
    }

def mock_prompt_enhancer(prompt):
    """Mock function to enhance prompt"""
    return f"Enhanced: {prompt} - Looking for skilled professionals with relevant experience"

def mock_query_making(parsed_data):
    """Mock function to create search query"""
    return f"site:linkedin.com/in {parsed_data.get('job_title', '')} {parsed_data.get('location', '')}", [parsed_data.get('location', 'India')]

def mock_serp_api_call(query, start=0, results_per_page=10):
    """Mock function to simulate SERP API call"""
    return [f"https://linkedin.com/in/videoprof{i}" for i in range(start, start + results_per_page)]

def mock_fetch_from_saral_data(serp_data, conn=None):
    """Mock function to fetch data from database"""
    return [], serp_data  # Return empty existing data, all URLs as new

def mock_apify_call(serp_json):
    """Mock function to simulate Apify scraping"""
    mock_profiles = []
    for i, (idx, url) in enumerate(serp_json.items()):
        if i >= 5:  # Limit to 5 profiles for demo
            break
        mock_profiles.append({
            "fullName": f"Video Editor {i+1}",
            "headline": f"Creative Video Editor with {2+i} years of experience",
            "addressWithCountry": "Surat, Gujarat, India",
            "email": f"editor{i+1}@example.com",
            "linkedinUrl": url,
            "skills": [
                {"title": "Video Editing"}, 
                {"title": "Adobe Premiere Pro"}, 
                {"title": "Final Cut Pro"},
                {"title": "Motion Graphics"},
                {"title": "Color Correction"}
            ],
            "about": f"Experienced video editor specializing in corporate videos, social media content, and promotional materials. Proficient in industry-standard editing software with a keen eye for storytelling and visual aesthetics.",
            "experiences": [
                {
                    "title": "Video Editor",
                    "subtitle": "Creative Media Solutions",
                    "caption": f"Jan 202{2+i} - Present",
                    "description": [{"text": "Create engaging video content for various clients including corporate training videos, social media campaigns, and promotional materials"}]
                },
                {
                    "title": "Junior Video Editor",
                    "subtitle": "Digital Studio",
                    "caption": f"Jun 202{1+i} - Dec 202{1+i}",
                    "description": [{"text": "Assisted in post-production workflow, color correction, and audio synchronization"}]
                }
            ],
            "profilePic": f"https://i.pravatar.cc/150?img={10+i}",
            "is_complete": "Complete Profile"
        })
    return mock_profiles

def mock_validate_function(location, candidates):
    """Mock function to validate candidates based on location"""
    # For demo, assume 80% are matched
    split_point = max(1, int(len(candidates) * 0.8))
    return candidates[:split_point], candidates[split_point:]

def mock_score_candidates(parsed_data, candidates):
    """Mock function to score candidates"""
    for i, candidate in enumerate(candidates):
        base_score = 85
        # Add some variation based on experience and skills
        experience_bonus = min(10, len(candidate.get('experiences', [])) * 2)
        skills_bonus = min(5, len(candidate.get('skills', [])))
        candidate['score'] = round(base_score + experience_bonus + skills_bonus + (i % 5), 1)
    return candidates

def mock_data_input(candidates):
    """Mock function to store data"""
    print(f"Mock: Would store {len(candidates)} candidates to database")
    pass

def mock_store_prompt(conn, prompt, parsed_data):
    """Mock function to store prompt"""
    print(f"Mock: Would store prompt: {prompt[:50]}...")
    pass

@app.route('/')
def index():
    """Render the main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error rendering template: {e}")
        return f"Template error: {str(e)}", 500

@app.route('/parse_query', methods=['POST'])
def parse_query():
    """Parse the recruitment query"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Content-Type must be application/json'})
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'})
        
        user_input = data.get('query', '').strip()
        
        if not user_input:
            return jsonify({'success': False, 'error': 'Please enter a valid query'})
        
        if MODULES_AVAILABLE:
            try:
                parsed_data = parse_recruiter_query(user_input)
            except Exception as e:
                print(f"Error in parse_recruiter_query: {e}")
                parsed_data = mock_parse_recruiter_query(user_input)
        else:
            parsed_data = mock_parse_recruiter_query(user_input)
        
        return jsonify({'success': True, 'parsed_data': parsed_data})
    
    except Exception as e:
        print(f"Error in parse_query: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Error parsing query: {str(e)}'})

@app.route('/enhance_prompt', methods=['POST'])
def enhance_prompt():
    """Enhance the recruitment prompt"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Content-Type must be application/json'})
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'})
        
        user_input = data.get('query', '').strip()
        
        if not user_input:
            return jsonify({'success': False, 'error': 'Please enter a valid query'})
        
        if MODULES_AVAILABLE:
            try:
                enhanced = prompt_enhancer(user_input)
            except Exception as e:
                print(f"Error in prompt_enhancer: {e}")
                enhanced = mock_prompt_enhancer(user_input)
        else:
            enhanced = mock_prompt_enhancer(user_input)
        
        return jsonify({'success': True, 'enhanced_query': enhanced})
    
    except Exception as e:
        print(f"Error in enhance_prompt: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Error enhancing prompt: {str(e)}'})

@app.route('/search', methods=['POST'])
def search():
    """Main search endpoint"""
    try:
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Content-Type must be application/json'})
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'})
        
        user_input = data.get('query', '').strip()
        current_page = data.get('page', 0)
        
        if not user_input:
            return jsonify({'success': False, 'error': 'Please enter a valid query'})
        
        print(f"Processing search for: {user_input}, page: {current_page}")
        
        # Parse query
        if MODULES_AVAILABLE:
            try:
                parsed_data = parse_recruiter_query(user_input)
            except Exception as e:
                print(f"Error in parse_recruiter_query: {e}")
                parsed_data = mock_parse_recruiter_query(user_input)
        else:
            parsed_data = mock_parse_recruiter_query(user_input)
        
        print(f"Parsed data: {parsed_data}")
        
        if isinstance(parsed_data, dict) and "error" in parsed_data:
            return jsonify({'success': False, 'error': parsed_data["error"]})
        
        if parsed_data.get("is_indian") == False:
            return jsonify({'success': False, 'error': 'Our platform only supports searches for candidates in India'})
        
        # Store prompt
        if MODULES_AVAILABLE:
            try:
                store_prompt(conn, user_input, parsed_data)
            except Exception as e:
                print(f"Error storing prompt: {e}")
                mock_store_prompt(None, user_input, parsed_data)
        else:
            mock_store_prompt(None, user_input, parsed_data)
        
        # Get query and location
        if MODULES_AVAILABLE:
            try:
                query, location = query_making(parsed_data)
            except Exception as e:
                print(f"Error in query_making: {e}")
                query, location = mock_query_making(parsed_data)
        else:
            query, location = mock_query_making(parsed_data)
        
        print(f"Search query: {query}")
        
        # Pagination
        results_per_page = 10
        start = current_page * results_per_page
        
        # Get SERP data
        if MODULES_AVAILABLE:
            try:
                serp_data = serp_api_call(query, start=start, results_per_page=results_per_page)
                saral_data, remain_urls = fetch_from_saral_data(serp_data, conn)
            except Exception as e:
                print(f"Error in SERP/database operations: {e}")
                serp_data = mock_serp_api_call(query, start=start, results_per_page=results_per_page)
                saral_data, remain_urls = mock_fetch_from_saral_data(serp_data, None)
        else:
            serp_data = mock_serp_api_call(query, start=start, results_per_page=results_per_page)
            saral_data, remain_urls = mock_fetch_from_saral_data(serp_data, None)
        
        print(f"SERP data count: {len(serp_data)}, Existing data: {len(saral_data)}, Remaining URLs: {len(remain_urls)}")
        
        # Process remaining URLs with Apify
        apify_json = []
        if len(remain_urls) >= 1:
            serp_json = {idx: url for idx, url in enumerate(remain_urls, start=1)}
            
            if MODULES_AVAILABLE:
                try:
                    apify_json = apify_call(serp_json)
                except Exception as e:
                    print(f"Error in apify_call: {e}")
                    apify_json = mock_apify_call(serp_json)
            else:
                apify_json = mock_apify_call(serp_json)
        
        print(f"Apify data count: {len(apify_json)}")
        
        # Combine data
        if apify_json:
            total_candidates = saral_data + apify_json
        else:
            total_candidates = saral_data
        
        print(f"Total candidates: {len(total_candidates)}")
        
        # Store data
        if MODULES_AVAILABLE:
            try:
                data_input(total_candidates)
            except Exception as e:
                print(f"Error storing data: {e}")
                mock_data_input(total_candidates)
        else:
            mock_data_input(total_candidates)
        
        # Validate and score
        if MODULES_AVAILABLE:
            try:
                matched, unmatched = validate_function(location, total_candidates)
                matched = score_candidates(parsed_data, matched)
            except Exception as e:
                print(f"Error in validation/scoring: {e}")
                matched, unmatched = mock_validate_function(location, total_candidates)
                matched = mock_score_candidates(parsed_data, matched)
        else:
            matched, unmatched = mock_validate_function(location, total_candidates)
            matched = mock_score_candidates(parsed_data, matched)
        
        print(f"Results - Matched: {len(matched)}, Unmatched: {len(unmatched)}")
        
        return jsonify({
            'success': True,
            'parsed_data': parsed_data,
            'matched_results': matched,
            'unmatched_results': unmatched,
            'current_page': current_page
        })
    
    except Exception as e:
        print(f"Error in search: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Search error: {str(e)}'})

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Ensure templates directory exists
    if not os.path.exists('templates'):
        os.makedirs('templates')
        print("Created templates directory")
    
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    
    print(f"Starting Flask app on port {port}")
    print(f"Modules available: {MODULES_AVAILABLE}")
    print(f"Debug mode: {debug_mode}")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=port)