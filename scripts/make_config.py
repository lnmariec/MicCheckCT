"""Write site/config.js with the Supabase URL and PUBLIC key for the website.

Reads SUPABASE_URL and SUPABASE_ANON_KEY from environment variables (as
Cloudflare Pages provides them) or, failing that, from the local .env file.
Refuses a secret key: the website must only ever get the public one.

Run from the project folder:  python scripts/make_config.py
"""

import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "config.js"


def load_env_file():
    path = ROOT / ".env"
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def is_public_key(key):
    if key.startswith("sb_publishable_"):
        return True
    if key.startswith("eyJ"):  # older keys carry their role inside
        try:
            payload = key.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            return json.loads(base64.urlsafe_b64decode(payload)).get("role") == "anon"
        except (IndexError, ValueError):
            return False
    return False


def main():
    file_values = load_env_file()
    url = (os.environ.get("SUPABASE_URL") or file_values.get("SUPABASE_URL", "")).rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY") or file_values.get("SUPABASE_ANON_KEY", "")

    if not url or not key:
        print("SUPABASE_URL and SUPABASE_ANON_KEY are both needed.")
        return 1
    if not is_public_key(key):
        print("SUPABASE_ANON_KEY is not a public key. Never give the website the secret key.")
        return 1

    OUT.write_text(
        "// Written by scripts/make_config.py. Not stored in Git.\n"
        f"window.MICCHECK_CONFIG = {json.dumps({'supabaseUrl': url, 'supabaseKey': key}, indent=2)};\n",
        encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
