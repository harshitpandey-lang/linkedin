from __future__ import annotations

import os
from supabase import Client, create_client


def get_client() -> Client:
    url, key = os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)
