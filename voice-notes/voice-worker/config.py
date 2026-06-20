"""Config for the voice-worker, read from env (.env in this folder)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

SUPABASE_URL = os.environ["SUPABASE_URL"]
# service-role key: the worker is a trusted backend, runs alongside the
# existing Personal-AI-OS service on your own machine. NEVER ship this to a client.
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "voice-notes")

# the worker now polls AssemblyAI for transcript completion (the edge function
# only submits the job). Tagging via Gemini is optional/best-effort.
ASSEMBLYAI_API_KEY = os.environ["ASSEMBLYAI_API_KEY"]
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# matching thresholds (cosine similarity, embeddings are unit-norm)
SIM_HIGH = float(os.getenv("SIM_HIGH", "0.78"))   # confident -> auto link to named speaker
SIM_LOW = float(os.getenv("SIM_LOW", "0.62"))     # plausible -> link but treat as suggestion

POLL_SECONDS = int(os.getenv("POLL_SECONDS", "15"))
# the owner's display name (their own voice), from the existing lexicon
SELF_NAME = os.getenv("SELF_NAME", "Anchit")
