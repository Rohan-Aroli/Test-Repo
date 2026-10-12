from pathlib import Path
import os
from dotenv import load_dotenv

# Multi-path .env resolution
_BACKEND_DIR = Path(__file__).resolve().parent
_FACE_DIR = _BACKEND_DIR.parent
_ROOT_DIR = _FACE_DIR.parent

if (_FACE_DIR / ".env").exists():
    load_dotenv(_FACE_DIR / ".env")
if (_ROOT_DIR / ".env").exists():
    load_dotenv(_ROOT_DIR / ".env")
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


class DummyResponse:
    def __init__(self, data=None):
        self.data = data or []


class DummyQuery:
    def __init__(self, table_name=""):
        self.table_name = table_name

    def select(self, *args, **kwargs):
        return self

    def insert(self, payload, *args, **kwargs):
        return self

    def update(self, payload, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def is_(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def single(self, *args, **kwargs):
        return self

    def execute(self):
        return DummyResponse([])


class DummyStorageBucket:
    def upload(self, *args, **kwargs):
        return None

    def get_public_url(self, *args, **kwargs):
        return ""


class DummyStorage:
    def from_(self, bucket_name):
        return DummyStorageBucket()


class DummySupabaseClient:
    def __init__(self):
        self.storage = DummyStorage()

    def table(self, name):
        return DummyQuery(name)


supabase = None

if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[SUPABASE CONNECTED SUCCESSFULLY]")
    except Exception as e:
        print(f"[SUPABASE CONNECTION WARNING]: {e}. Operating with fallback client.")
        supabase = DummySupabaseClient()
else:
    print("[SUPABASE WARNING]: SUPABASE_URL or SUPABASE_KEY missing. Operating with fallback client.")
    supabase = DummySupabaseClient()