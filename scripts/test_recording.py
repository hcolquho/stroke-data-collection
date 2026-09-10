"""
Quick test recording — 10 seconds, saves to data/raw_video/test/trial_00.
Run this to confirm record_session.py works end to end before real sessions.

Usage:
    python scripts/test_recording.py
"""

from pathlib import Path
import subprocess
import sys

ROOT        = Path(__file__).resolve().parent.parent
RECORD      = ROOT / "scripts" / "record_session.py"
VERIFY      = ROOT / "scripts" / "verify_session.py"
SESSION_DIR = ROOT / "data" / "raw_video" / "test" / "trial_00"

print(f"\nTest recording → {SESSION_DIR}\n")

# ── Record 10 seconds ─────────────────────────────────────────────────────────
subprocess.run([
    sys.executable, str(RECORD),
    "--session",   str(SESSION_DIR),
    "--duration",  "10",
    "--subject",   "test",
    "--condition", "test_recording",
    "--notes",     "automated test — not real data",
    "--no-preview",   # headless so it runs without a display window
], check=False)

# ── Verify immediately ────────────────────────────────────────────────────────
print("\n" + "="*60)
print("  Verifying test recording...")
print("="*60)

subprocess.run([
    sys.executable, str(VERIFY),
    "--session", str(SESSION_DIR),
], check=False)