from __future__ import annotations

import os
from supabase import Client, create_client


_BOOTSTRAP_KEY = "eyJhbGciOiJub25lIn0.eyJzdWIiOiJjbGllbnQifQ.signature"


def get_client() -> Client:
    url, key = os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    if not key.startswith(("sb_publishable_", "sb_secret_")):
        return create_client(url, key)

    client = create_client(url, _BOOTSTRAP_KEY)
    client.supabase_key = key
    client.options.headers.update({"apiKey": key, "Authorization": f"Bearer {key}"})
    return client
