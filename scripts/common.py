# scripts/common.py — Shared utilities for Python scripts
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from rich.console import Console

load_dotenv()
console = Console()

def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("Missing Supabase credentials in environment.")
    return create_client(url, key)

def get_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("Missing Gemini API key.")
    return key
