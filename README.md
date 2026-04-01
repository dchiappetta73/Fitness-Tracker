# Fitness-Tracker

A Streamlit app for a 12-week recomp tracker with cloud data storage in Supabase.

## Local setup
1. Create a virtual environment.
2. Install packages:
   pip install -r requirements.txt
3. Create `.streamlit/secrets.toml`
4. Run:
   streamlit run tracker.py

## Required secrets
```toml
SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_KEY"
```

## Deployment
Push this repo to GitHub, deploy on Streamlit Community Cloud, and add the same secrets in the app settings.
