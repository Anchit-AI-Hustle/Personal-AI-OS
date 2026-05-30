#!/usr/bin/env bash
# Pull secrets from Vercel into a local, gitignored .env.local.
# Secrets live ONLY in the Vercel project (never committed). Run this once
# after cloning, and whenever a key rotates:
#
#     bash scripts/sync-env.sh
#
# Requires: `vercel login` (Vercel CLI) and the project linked (.vercel/).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .vercel/project.json ]; then
  echo "Linking to Vercel project (one-time)…"
  vercel link --yes
fi
vercel env pull .env.local --environment=development --yes
echo "✓ Wrote .env.local from Vercel (development env). It is gitignored."
