import streamlit as st
import re
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import json
from nlp_parsed import parse_recruiter_query,prompt_enhancer
from SERP import query_making, serp_api_call
from apify import apify_call
from validate import validate_function, score_candidates
from postgres_db import fetch_from_saral_data, check_completeness, data_input, cur, conn, store_prompt


st.set_page_config(page_title="LinkedIn Recruiter Assistant", page_icon="🎯")


if "parsed_data" not in st.session_state:
    st.session_state.parsed_data = {}


if "matched_results" not in st.session_state:
    st.session_state.matched_results = []
if "unmatched_results" not in st.session_state:
    st.session_state.unmatched_results = []
    
    
if "progress_placeholder" not in st.session_state:
    st.session_state.progress_placeholder = None
if "progress" not in st.session_state:
    st.session_state.progress = None
    

if "current_page" not in st.session_state:
    st.session_state.current_page = 0
if "run_search" not in st.session_state:
    st.session_state.run_search = False
    
    
if "user_input" not in st.session_state:
    st.session_state.user_input = ""
    

st.header("Saral AI")

user_input = st.text_area(
    "Enter your query here:",
    placeholder="Enter your query here",
    key="user_input_box",
    value=st.session_state.user_input  # always pull from session_state
)


st.session_state.user_input = user_input


# Show query parsing immediately (live preview)
if user_input.strip():
    parsed_data = parse_recruiter_query(user_input)
    
    
    
    st.session_state.parsed_data = parsed_data

    if "error" in parsed_data:
        st.error(parsed_data["error"])
    else:
        with st.expander("Query", expanded=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown(f'**Job Title:** {parsed_data.get("job_title", "None")}')
                st.markdown(f'**Skills:** {parsed_data.get("skills", "None")}')
                st.markdown(
                    f'**Experience:** {parsed_data.get("experience","None")} years of Experience'
                )
            with col2:
                st.markdown(f'**Location:** {parsed_data.get("location", "None")}')
                st.markdown(
                    f'**Work Preference:** {parsed_data.get("work_preference", "None")}'
                )
                st.markdown(f'**Job Type:** {parsed_data.get("job_type", "None")}')



# Enhance prompt button
if st.button("Enhance Prompt", use_container_width=True):
    enhanced = prompt_enhancer(st.session_state.user_input)

    # Store only in your own session_state variable
    st.session_state.user_input = enhanced

    # force rerun so text_area shows updated text
    # st.experimental_rerun()
    
    

# Only fetch SERP + Apify when button clicked
if st.button("Enter",use_container_width=True):
    st.session_state.current_page = 0  # reset pagination
    st.session_state.run_search = True 


if st.session_state.run_search:
    if not user_input.strip():
        st.warning("Please enter a valid query.")
        st.stop()

    store_prompt(conn,user_input,parsed_data)
    
    # Progress bar
    st.session_state.progress_placeholder = st.empty()
    st.session_state.progress = st.session_state.progress_placeholder.progress(0)
    status = st.empty()

    if user_input.strip() and "error" not in parsed_data:
        query, location = query_making(parsed_data) # getting query like https:://linkedin.com --- AND location list 
        
        print(query)
 
        
        ### pagination concept 
        
        if st.session_state.current_page >= 0 :
            results_per_page = 10
            start = st.session_state.current_page * results_per_page
            
            serp_data = serp_api_call(
                query,
                start= start,
                results_per_page=10
            )
            
        
            saral_data, remain_urls = fetch_from_saral_data(serp_data, conn)
            
            print(remain_urls)
            
            
            st.session_state.progress.progress(30)
            
            serp_json = {}
            
            apify_json = {}
            
            if len(remain_urls) >= 1:
                for idx, i in enumerate(remain_urls,start=1):
                    serp_json[idx] = i
                    
                apify_json = apify_call(serp_json)
                st.session_state.progress.progress(70)
                

            if apify_json:
                total_candidates = saral_data + apify_json
                
            else:
                total_candidates = saral_data
             
            data_input(total_candidates)

            # Validate funciton (location)
            matched, unmatched = validate_function(location, total_candidates)
            st.session_state.progress.progress(70)
            
            
            
            matched = score_candidates(parsed_data , matched)
            
            st.session_state.matched_results = matched
            st.session_state.unmatched_results = unmatched
            
            st.session_state.progress.progress(100)
            st.session_state.progress_placeholder.empty()
            st.session_state.progress = None
            st.session_state.progress_placeholder = None

    else:
        st.warning("Please enter a valid query.")


if st.session_state.matched_results:
    
    # length of Matched and unmatched profiles
    col1, col2 = st.columns([1, 1])
    with col1:
        st.success(f"Matched Profiles: {len(st.session_state.matched_results)}")
    with col2:
        st.warning(f"Unmatched Profiles: {len(st.session_state.unmatched_results)}")
    
    
    
    
    col1, col2, col3 = st.columns([1,2,1])
    with col1:
        if st.button("< Previous") and st.session_state.current_page > 0:
            st.session_state.current_page -= 1
            st.session_state.run_search = True 
        
    with col2:
        st.write(f'Current Page {st.session_state.current_page + 1}')

    with col3:
        if st.button("Next >"):
            st.session_state.current_page += 1
            st.session_state.run_search = True 
           

    st.subheader("Candidates Profiles")
    for idx, profiles in enumerate(st.session_state.matched_results, start=1):
        with st.expander(f"{idx}. {profiles.get('fullName', 'Unknown')}"):
            st.json(profiles)
            
        with st.expander(
            f"{idx}. {profiles.get('fullName', 'Unknown')} • Score: {profiles.get('score','None')} ", expanded=True
        ):
            col1, col2 = st.columns([1, 2])
            with col1:
                image = profiles.get("profilePic")

                temp_image = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRDVO09x_DXK3p4Mt1j08Ab0R875TdhsDcG2A&s"

                if profiles.get("profilePic"):
                    st.image(profiles.get("profilePic"), width=150)
                else:
                    st.image(temp_image, width=150)

                st.markdown(f"**Location:** {profiles.get('addressWithCountry','-')}")
                st.markdown(f"**Email:** {profiles.get('email','None')}")
                st.markdown(
                    f"**LinkedIn:** [LinkedIn]({profiles.get('linkedinUrl','')})"
                )

            with col2:
                st.markdown(f"### {profiles.get('fullName')}")
                if profiles.get("headline"):
                    st.markdown(f"*{profiles.get('headline')}*")

                skills_raw = profiles.get("skills", [])
                skill_titles = [
                    s.get("title")
                    for s in skills_raw
                    if isinstance(s, dict) and "title" in s
                ]
                if skill_titles:
                    st.markdown("**Skills:** " + " • ".join(skill_titles[:10]))

                if profiles.get("about"):
                    about = profiles.get("about")
                    st.markdown(
                        "**About:** " + (about[:250] + "..." if len(about) > 250 else about)
                    )

                if profiles.get("experiences"):
                    st.markdown("**Experience**")
                    for exp in profiles["experiences"]:
                        title = exp.get("title", "")
                        subtitle = exp.get("subtitle") or exp.get("metadata", "")
                        caption = exp.get("caption", "")

                        # Print main line
                        st.write(f"• {title} at {subtitle} — {caption}")

                        # Print description if available
                        if exp.get("description"):
                            for desc in exp["description"]:
                                if isinstance(desc, dict) and "text" in desc:
                                    st.markdown(f"    - {desc['text']}")

                if profiles.get("is_complete"):
                    st.markdown(f'{profiles.get("is_complete")}')

    if st.session_state.unmatched_results:
        st.subheader("Unmatched Profiles")
        for idx, profiles in enumerate(st.session_state.unmatched_results, start=1):

            st.markdown(
                f"{idx}, {profiles.get('fullName', 'Unknown')} - {profiles.get('addressWithCountry', 'Unknown')} [LINKEDIN]({profiles.get('linkedinUrl', 'Unknown')})"
            )


