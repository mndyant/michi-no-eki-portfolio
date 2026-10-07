"""Build the existing Next frontend as static files for Vercel's CDN."""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
env = {**os.environ, "NEXT_PUBLIC_DEMO": "1", "NEXT_PUBLIC_API_BASE_URL": "", "NEXT_TELEMETRY_DISABLED": "1"}
npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
if not npm:
    raise RuntimeError("Node.js/npm is required to build the frontend")
subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=ROOT / "frontend", env=env, check=True)
subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", env=env, check=True)
# Register this generated directory with FastAPI StaticFiles so Vercel collects
# it after the build (public/ files are otherwise discovered before generation).
shutil.copytree(ROOT / "frontend/out", ROOT / "site", dirs_exist_ok=True)
