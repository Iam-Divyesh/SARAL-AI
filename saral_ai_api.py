from flask import Flask, render_template, request, jsonify, session
import os
from dotenv import load_dotenv
from nlp_parsed import parse_recruiter_query, prompt_enhancer
from SERP import query_making, serp_api_call
from apify import apify_call
from validate import validate_function, score_candidates
from postgres_db import fetch_from_saral_data, data_input, store_prompt, conn

load_dotenv()

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
        data = request.get_json()
        query = data.get('query', '').strip()
        page = int(data.get('page', 0))
        
        if not query:
            return jsonify({'error': 'Please enter a valid query'}), 400
            
        # Parse the query
        parsed_data = parse_recruiter_query(query)
        
        if "error" in parsed_data:
            return jsonify({'error': parsed_data["error"]}), 400
            
        if parsed_data.get("is_indian") is False:
            return jsonify({'error': 'Our platform currently supports searches within India only'}), 400
            
        # Store prompt in database
        store_prompt(conn, query, parsed_data)
        
        # Generate search query
        search_query, location = query_making(parsed_data)
        
        # Pagination setup
        results_per_page = 10
        start = page * results_per_page
        
        # SERP API call
        serp_data = serp_api_call(search_query, start=start, results_per_page=results_per_page)
        
        if not serp_data:
            return jsonify({'error': 'No search results found'}), 404
            
        # Check database for existing profiles
        saral_data, remain_urls = fetch_from_saral_data(serp_data, conn)
        
        # Fetch new profiles from Apify if needed
        apify_json = []
        if remain_urls:
            serp_json = {idx: url for idx, url in enumerate(remain_urls, start=1)}
            apify_json = apify_call(serp_json)
            
        # Combine all candidates
        if apify_json:
            total_candidates = saral_data + apify_json
        else:
            total_candidates = saral_data
            
        # Store new candidates in database
        if total_candidates:
            data_input(total_candidates)
            
        # Validate and score candidates
        matched, unmatched = validate_function(location, total_candidates)
        matched = score_candidates(parsed_data, matched)
        
        # Check if there are more results by looking at SERP data
        total_serp_results = serp_data.get('search_information', {}).get('total_results', 0)
        has_next = (page + 1) * results_per_page < total_serp_results
        
        return jsonify({
            'success': True,
            'matched_profiles': matched,
            'unmatched_profiles': unmatched,
            'matched_count': len(matched),
            'unmatched_count': len(unmatched),
            'current_page': page + 1,
            'total_pages': (total_serp_results + results_per_page - 1) // results_per_page,
            'total_results': total_serp_results,
            'parsed_data': parsed_data,
            'has_next': has_next,
            'has_prev': page > 0
        })
        
    except Exception as e:
        return jsonify({'error': f'Search failed: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Saral AI Flask API is running'})

if __name__ == '__main__':
    # Use 0.0.0.0 to bind to all interfaces for Replit
    app.run(host='0.0.0.0', port=5000, debug=True)