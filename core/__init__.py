"""Core reconciliation engine: config, schema resolution, I/O, and matching.

Kept separate from app.py / pages/ so the matching logic can be unit tested
without a running Streamlit session, and so it's reusable if this ever needs
to run outside Streamlit (e.g. a scheduled batch job).
"""
