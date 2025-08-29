from flask import Flask, render_template, request, jsonify, session
import os
import traceback
from dotenv import load_dotenv

load_dotenv()

# Try to import modules with error handling
try:
    from nlp_parsed import parse_recruiter_query, prompt_enhancer
    print("✓ NLP module imported successfully")
except Exception as e:
    print(f"✗ Error importing nlp_parsed: {e}")
    def parse_recruiter_query(query): 
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
    
    def prompt_enhancer(query): return query

try:
    from SERP import query_making, serp_api_call
    print("✓ SERP module imported successfully")
except Exception as e:
    print(f"✗ Error importing SERP: {e}")
    def query_making(data): return "", []
    def serp_api_call(query, start=0, results_per_page=10): return None

try:
    from apify import apify_call
    print("✓ Apify module imported successfully")
except Exception as e:
    print(f"✗ Error importing apify: {e}")
    def apify_call(serp_json): return []

try:
    from validate import validate_function, score_candidates
    print("✓ Validate module imported successfully")
except Exception as e:
    print(f"✗ Error importing validate: {e}")
    def validate_function(location, candidates): return candidates, []
    def score_candidates(parsed_data, matched): return matched

try:
    from postgres_db import fetch_from_saral_data, data_input, store_prompt, conn
    print("✓ Database module imported successfully")
except Exception as e:
    print(f"✗ Error importing postgres_db: {e}")
    def fetch_from_saral_data(serp_data, conn): return [], []
    def data_input(candidates): pass
    def store_prompt(conn, query, parsed_data): pass
    conn = None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "a-secret-key-for-saral-ai")

@app.route('/')
def index():
    """Main page to display the search interface"""
    return render_template('index.html')

@app.route('/parse_query', methods=['POST'])
def parse_query():
    """Parse user query and return structured data"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'Please enter a valid query'}), 400
            
        parsed_data = parse_recruiter_query(query)
        
        if "error" in parsed_data:
            return jsonify({'error': parsed_data["error"]}), 400
            
        # Store parsed data in session for later use
        session['parsed_data'] = parsed_data
        session['user_query'] = query
        
        return jsonify({
            'success': True,
            'parsed_data': parsed_data,
            'is_indian': parsed_data.get('is_indian', True)
        })
        
    except Exception as e:
        return jsonify({'error': f'Error parsing query: {str(e)}'}), 500

@app.route('/enhance_prompt', methods=['POST'])
def enhance_prompt():
    """Enhance user prompt for better clarity"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'error': 'Please enter a valid query'}), 400
            
        enhanced = prompt_enhancer(query)
        return jsonify({
            'success': True,
            'enhanced_query': enhanced
        })
        
    except Exception as e:
        return jsonify({'error': f'Error enhancing prompt: {str(e)}'}), 500

@app.route('/search', methods=['POST'])
def search_profiles():
    """Main search function that processes the entire workflow"""
    try:
        # Ensure we always return JSON
        data = request.get_json()
        if data is None:
            return jsonify({'error': 'Invalid JSON data'}), 400
            
        query = data.get('query', '').strip()
        page = int(data.get('page', 0))
        
        print(f"🔍 Search request: query='{query}', page={page}")
        
        if not query:
            return jsonify({'error': 'Please enter a valid query'}), 400
            
        # Parse the query
        print("📝 Parsing query...")
        parsed_data = parse_recruiter_query(query)
        print(f"✓ Parsed data: {parsed_data}")
        
        if "error" in parsed_data:
            return jsonify({'error': parsed_data["error"]}), 400
            
        if parsed_data.get("is_indian") is False:
            return jsonify({'error': 'Our platform currently supports searches within India only'}), 400
            
        # Store prompt in database
        print("💾 Storing prompt in database...")
        try:
            store_prompt(conn, query, parsed_data)
        except Exception as e:
            print(f"⚠️ Warning: Could not store prompt: {e}")
        
        # Generate search query
        print("🔗 Generating search query...")
        search_query, location = query_making(parsed_data)
        print(f"✓ Search query: {search_query}")
        
        # Pagination setup
        results_per_page = 10
        start = page * results_per_page
        
        # SERP API call
        print(f"🌐 Calling SERP API (start={start}, per_page={results_per_page})...")
        serp_data = serp_api_call(search_query, start=start, results_per_page=results_per_page)
        
        if not serp_data:
            return jsonify({
                'success': True,
                'matched_profiles': [],
                'unmatched_profiles': [],
                'matched_count': 0,
                'unmatched_count': 0,
                'current_page': page + 1,
                'total_pages': 1,
                'total_results': 0,
                'parsed_data': parsed_data,
                'has_next': False,
                'has_prev': page > 0,
                'message': 'No search results found'
            })
            
        print(f"✓ SERP data received: {len(serp_data.get('organic_results', []))} results")
        
        # Check database for existing profiles
        print("🔍 Checking database for existing profiles...")
        saral_data, remain_urls = fetch_from_saral_data(serp_data, conn)
        print(f"✓ Found {len(saral_data)} existing profiles, {len(remain_urls)} new URLs")
        
        # Fetch new profiles from Apify if needed
        apify_json = []
        if remain_urls:
            print(f"🤖 Fetching {len(remain_urls)} new profiles from Apify...")
            try:
                serp_json = {idx: url for idx, url in enumerate(remain_urls, start=1)}
                apify_json = apify_call(serp_json)
                print(f"✓ Apify returned {len(apify_json)} profiles")
            except Exception as e:
                print(f"⚠️ Warning: Apify call failed: {e}")
                apify_json = []
            
        # Combine all candidates
        if apify_json:
            total_candidates = saral_data + apify_json
        else:
            total_candidates = saral_data
            
        print(f"✓ Total candidates: {len(total_candidates)}")
        
        # Store new candidates in database
        if total_candidates:
            print("💾 Storing new candidates in database...")
            try:
                data_input(total_candidates)
            except Exception as e:
                print(f"⚠️ Warning: Could not store candidates: {e}")
            
        # Validate and score candidates
        print("🎯 Validating and scoring candidates...")
        matched, unmatched = validate_function(location, total_candidates)
        matched = score_candidates(parsed_data, matched)
        
        print(f"✓ Results: {len(matched)} matched, {len(unmatched)} unmatched")
        
        # Check if there are more results by looking at SERP data
        total_serp_results = serp_data.get('search_information', {}).get('total_results', 0)
        if total_serp_results == 0:
            total_serp_results = len(serp_data.get('organic_results', []))
            
        has_next = (page + 1) * results_per_page < total_serp_results
        total_pages = max(1, (total_serp_results + results_per_page - 1) // results_per_page) if total_serp_results > 0 else 1
        
        return jsonify({
            'success': True,
            'matched_profiles': matched,
            'unmatched_profiles': unmatched,
            'matched_count': len(matched),
            'unmatched_count': len(unmatched),
            'current_page': page + 1,
            'total_pages': total_pages,
            'total_results': total_serp_results,
            'parsed_data': parsed_data,
            'has_next': has_next,
            'has_prev': page > 0
        })
        
    except Exception as e:
        # Log the full traceback for debugging
        print(f"❌ Search error: {str(e)}")
        print(f"📋 Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'Search failed: {str(e)}',
            'traceback': traceback.format_exc() if app.debug else None
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Saral AI Flask API is running'})

if __name__ == '__main__':
    # Use 0.0.0.0 to bind to all interfaces for Replit
    app.run(host='0.0.0.0', port=5000, debug=True)