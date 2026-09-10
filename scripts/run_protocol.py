"""
Walker-Gait Protocol Runner
=============================
Guides you through all 6 blocks interactively, names sessions automatically,
tracks completion, and handles rest breaks between trials and blocks.

Usage:
    python scripts/run_protocol.py --participant P001
    python scripts/run_protocol.py --participant P001 --start-block 3
    python scripts/run_protocol.py --participant P001 --start-block 4 --affected-side right
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

# Path to the root of this repo
ROOT          = Path(__file__).resolve().parent.parent
PROTOCOL_FILE = ROOT / "configs" / "protocol.yaml"
DATA_ROOT     = ROOT / "data" / "raw_video"
SESSION_DIR_RE = re.compile(r"^session_(\d+)$")

# ANSI colours for terminal output
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# Helper function to apply ANSI colours to text
def c(text, colour):
    return f"{colour}{text}{RESET}"

# Load the protocol configuration
def load_protocol() -> dict:
    with open(PROTOCOL_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)

# Build the path to a session directory
def session_dir_path(participant: str, session_id: int) -> Path:
    return DATA_ROOT / participant / f"session_{session_id:02d}"

# List existing sessions for a participant
def list_sessions(participant: str) -> list[int]:
    """Return sorted session ids that already exist for this participant."""
    participant_dir = DATA_ROOT / participant
    if not participant_dir.exists():
        return []
    ids = []
    for entry in participant_dir.iterdir():
        if entry.is_dir():
            m = SESSION_DIR_RE.match(entry.name)
            if m:
                ids.append(int(m.group(1)))
    return sorted(ids)

# Check if a session is complete based on the completion log and protocol
def is_session_complete(participant: str, session_id: int, protocol: dict) -> bool:
    log = load_completion_log(participant, session_id)
    n_trials = protocol["n_trials_per_condition"]
    for block in protocol["blocks"]:
        for cond in block["conditions"]:
            key = f"b{block['id']}_{cond['condition_slug']}"
            if len(log.get(key, [])) < n_trials:
                return False
    return True

# Resolve the session ID based on the participant, protocol, and command-line arguments
def resolve_session_id(participant: str, protocol: dict, args) -> int:
    """Decide which session directory this run should target."""
    existing = list_sessions(participant)

    if args.session_id is not None:
        return args.session_id

    if args.new_session:
        return (max(existing) + 1) if existing else 1

    if not existing:
        return 1

    latest = max(existing)
    if is_session_complete(participant, latest, protocol):
        return latest + 1
    return latest

# Build the path to a session directory for a specific trial
def get_session_dir(participant: str, session_id: int, block_id: int, block_name: str,
                    condition_slug: str, trial_n: int, affected_side: str) -> Path:
    """Build the output directory path for one trial."""
    side_suffix = f"_{affected_side}" if affected_side and affected_side != "none" else ""
    trial_dir = (
        session_dir_path(participant, session_id)
        / f"block{block_id}_{block_name}"
        / f"{condition_slug}{side_suffix}"
        / f"trial_{trial_n:02d}"
    )
    return trial_dir

# Load the completion log for a participant's session
def load_completion_log(participant: str, session_id: int) -> dict:
    """Load the completion log for this participant's session."""
    log_path = session_dir_path(participant, session_id) / "completion_log.json"
    if log_path.exists():
        with open(log_path, encoding="utf-8") as f:
            return json.load(f)
    return {}

# Save the completion log for a participant's session
def save_completion_log(participant: str, session_id: int, log: dict):
    log_path = session_dir_path(participant, session_id) / "completion_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

# Load session information for a participant's session
def load_session_info(participant: str, session_id: int) -> dict:
    info_path = session_dir_path(participant, session_id) / "session_info.json"
    if info_path.exists():
        with open(info_path, encoding="utf-8") as f:
            return json.load(f)
    return {}

# Save session information for a participant's session
def save_session_info(participant: str, session_id: int, info: dict):
    info_path = session_dir_path(participant, session_id) / "session_info.json"
    info_path.parent.mkdir(parents=True, exist_ok=True)
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)

# Utility functions for printing headers, sections, countdowns, and prompting the user
def print_header(text: str):
    width = 60
    print(f"\n{'═' * width}")
    print(f"  {c(text, BOLD)}")
    print(f"{'═' * width}")

# Print a section header
def print_section(text: str):
    print(f"\n{c('── ' + text, CYAN)}")

# Countdown timer for rest breaks
def countdown(seconds: int, label: str = "Resuming in"):
    for remaining in range(seconds, 0, -1):
        print(f"  {label}: {remaining}s ", end="\r")
        time.sleep(1)
    print()

# Prompt the user for input with optional validation
def ask(prompt: str, valid: list[str] | None = None, default: str = "") -> str:
    """Prompt the user and return their input, with optional validation."""
    while True:
        suffix = f" [{'/'.join(valid)}]" if valid else (f" [{default}]" if default else "")
        response = input(f"\n{c('▶', CYAN)} {prompt}{suffix}: ").strip().lower()
        if not response and default:
            return default
        if valid is None or response in valid:
            return response
        print(f"  {c('Please enter one of:', YELLOW)} {', '.join(valid)}")

# Run a single recording session as a subprocess
def run_recording(session_dir: Path, duration: int, condition: dict,
                  participant: str, session_id: int, affected_side: str, trial_n: int) -> bool:
    """
    Launch record_session.py as a subprocess.
    Returns True if the user confirms the trial was good.
    """
    session_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(ROOT / "scripts" / "record_session.py"),
        "--session",   str(session_dir),
        "--duration",  str(duration + 5),      # small safety buffer
        "--subject",   participant,
        "--condition", condition["condition_slug"],
        "--notes",
        f"session={session_id} "
        f"block={condition.get('block_id','?')} "
        f"trial={trial_n} "
        f"affected_side={affected_side} "
        f"bpm={condition.get('metronome_bpm','none')} "
        f"target_asym={condition.get('asymmetry_target_pct','n/a')}%",
    ]

    print(f"\n  {c('Starting recording...', GREEN)}  (Ctrl+C inside to stop early)\n")
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        pass

    # Analysis window is saved automatically by record_session.py
    # ArUco detection only needed if green tape / second operator used
    pass

    # Quick verification
    print(f"\n  {c('Running session verification...', CYAN)}")
    subprocess.run([
            sys.executable, str(ROOT / "scripts" / "verify_session.py"),
            "--session", str(session_dir),
        ], check=False)

    # Ask user to confirm
    response = ask("Was this trial good?", valid=["y", "n", "r"], default="y")
    # y=good, n=bad/discard, r=retry immediately
    return response

# Run all conditions in a block, returning updated completion log
def run_block(block: dict, participant: str, session_id: int, affected_side: str,
              start_condition: int, n_trials: int,
              completion_log: dict) -> dict:

    print_header(block["label"])
    print(f"\n  {c(block['description'].strip(), YELLOW)}\n")

    if block.get("affected_side") == "choose_one" and not affected_side:
        affected_side = ask("Which side is 'affected' for this block?",
                            valid=["left", "right"])

    for condition in block["conditions"]:
        condition["block_id"] = block["id"]

        cond_key = f"b{block['id']}_{condition['condition_slug']}"
        completed_trials = completion_log.get(cond_key, [])
        next_trial = len(completed_trials) + 1

        if next_trial > n_trials:
            print(f"\n  {c('✓', GREEN)} {condition['label']} — already complete ({n_trials} trials)")
            continue

        print_section(f"Condition {condition['id']}: {condition['label']}")

        bpm_str = (f"Metronome: {c(str(condition['metronome_bpm']) + ' BPM', BOLD)}"
                   if condition.get("metronome_bpm") else "No metronome")
        asym_str = (f"  |  Target asymmetry: ~{condition['asymmetry_target_pct']}%"
                    if condition.get("asymmetry_target_pct") else "")

        print(f"  Duration: {c(str(condition['duration_s']) + 's', BOLD)}"
              f"  |  {bpm_str}{asym_str}")
        print(f"\n  {c('Instructions:', BOLD)}")
        for line in condition["instructions"].strip().split("\n"):
            print(f"    {line.strip()}")
        print(f"\n  {c('► Press Q in the preview window after passing the 12m mark.', CYAN)}")

        trial_n = next_trial
        while trial_n <= n_trials:
            print(f"\n  {c(f'Trial {trial_n} of {n_trials}', BOLD)}")

            ready = ask("Ready to start?", valid=["y", "s", "q"], default="y")
            if ready == "q":
                print(c("\nQuitting protocol. Progress saved.", YELLOW))
                save_completion_log(participant, session_id, completion_log)
                sys.exit(0)
            if ready == "s":
                print(f"  Skipping {condition['label']}.")
                break

            session_dir = get_session_dir(
                participant, session_id, block["id"], block["name"],
                condition["condition_slug"], trial_n, affected_side
            )

            result = run_recording(
                session_dir, condition["duration_s"], condition,
                participant, session_id, affected_side, trial_n
            )

            if result in ("r", "n"):
                print(f"  {c('Trial not logged. Retrying.', RED)}")
                continue  # retry same trial_n — do not advance

            # Good trial
            if cond_key not in completion_log:
                completion_log[cond_key] = []
            completion_log[cond_key].append({
                "trial": trial_n,
                "session_dir": str(session_dir),
                "affected_side": affected_side,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            save_completion_log(participant, session_id, completion_log)
            print(f"  {c('✓ Trial logged.', GREEN)}")

            if trial_n < n_trials:
                print(f"\n  {c('Rest break between trials.', CYAN)}")
                countdown(15, "Next trial in")

            trial_n += 1  # only advance on a good trial

    return completion_log

# Pre-session checklist reminders
def pre_session_checklist(protocol: dict):
    print_header("Pre-Session Checklist")
    checklist = protocol.get("pre_session_checklist", [])
    for i, item in enumerate(checklist, 1):
        input(f"  {i}. {item}\n     {c('(Press Enter when done)', CYAN)}")
    print(f"\n  {c('✓ Checklist complete.', GREEN)}")

# Count the number of completed trials and expected trials for a session
def _count_session(participant: str, session_id: int, protocol: dict) -> tuple[int, int]:
    log = load_completion_log(participant, session_id)
    n_trials = protocol["n_trials_per_condition"]
    done = 0
    expected = 0
    for block in protocol["blocks"]:
        for cond in block["conditions"]:
            key = f"b{block['id']}_{cond['condition_slug']}"
            done += len(log.get(key, []))
            expected += n_trials
    return done, expected

# Print a summary of a specific session
def print_session_summary(participant: str, session_id: int, completion_log: dict, protocol: dict):
    print_header(f"Session {session_id:02d} Summary  |  Participant: {participant}")
    n_trials = protocol["n_trials_per_condition"]
    total_done = 0
    total_expected = 0

    for block in protocol["blocks"]:
        for cond in block["conditions"]:
            key = f"b{block['id']}_{cond['condition_slug']}"
            done = len(completion_log.get(key, []))
            total_done += done
            total_expected += n_trials
            status = c("✓", GREEN) if done >= n_trials else c(f"{done}/{n_trials}", YELLOW)
            print(f"  {status}  {block['id']}.{cond['id']} {cond['label']}")

    print(f"\n  Total: {c(str(total_done), BOLD)}/{total_expected} trials recorded")
    print(f"  Log: {session_dir_path(participant, session_id) / 'completion_log.json'}\n")

# Print a summary of all sessions for a participant
def print_all_sessions_summary(participant: str, protocol: dict):
    print_header(f"All Sessions Summary  |  Participant: {participant}")
    sessions = list_sessions(participant)
    if not sessions:
        print(f"\n  No sessions found for {participant}.\n")
        return

    grand_done = 0
    grand_expected = 0
    for session_id in sessions:
        done, expected = _count_session(participant, session_id, protocol)
        grand_done += done
        grand_expected += expected
        status = c("✓ complete", GREEN) if done >= expected else c(f"{done}/{expected}", YELLOW)
        print(f"  session_{session_id:02d}  {status}")

    print(f"\n  Grand total: {c(str(grand_done), BOLD)}/{grand_expected} trials recorded "
          f"across {len(sessions)} session(s)")
    print(f"  Use --session-id N --summary to see per-condition detail for one session.\n")

# Parse command-line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Walker-Gait interactive protocol runner")
    parser.add_argument("--participant", required=True,
                        help="Participant/subject ID (e.g. P001 or 'self')")
    parser.add_argument("--start-block", type=int, default=1,
                        help="Start from this block number (default: 1)")
    parser.add_argument("--affected-side", choices=["left", "right", "none"],
                        default="",
                        help="Pre-set affected side for asymmetry blocks")
    parser.add_argument("--skip-checklist", action="store_true",
                        help="Skip the pre-session checklist")
    parser.add_argument("--summary", action="store_true",
                        help="Show completion summary and exit")
    parser.add_argument("--session-id", type=int, default=None,
                        help="Target a specific session number "
                             "(resumes it if it exists, creates it if not)")
    parser.add_argument("--new-session", action="store_true",
                        help="Start a fresh session even if the latest one "
                             "for this participant is incomplete")
    args = parser.parse_args()

    if args.session_id is not None and args.new_session:
        parser.error("--session-id and --new-session are mutually exclusive")

    return args

# Main function to run the protocol
def main():
    args = parse_args()
    protocol = load_protocol()

    if args.summary:
        if args.session_id is not None:
            completion_log = load_completion_log(args.participant, args.session_id)
            print_session_summary(args.participant, args.session_id, completion_log, protocol)
        else:
            print_all_sessions_summary(args.participant, protocol)
        return

    session_id = resolve_session_id(args.participant, protocol, args)
    completion_log = load_completion_log(args.participant, session_id)
    session_info = load_session_info(args.participant, session_id)

    print_header(f"Walker-Gait Protocol  |  Participant: {args.participant}  |  "
                 f"Session: {session_id:02d}")

    if not args.skip_checklist:
        pre_session_checklist(protocol)

    n_trials = protocol["n_trials_per_condition"]
    affected_side = args.affected_side or session_info.get("affected_side", "")

    session_info["started"] = session_info.get("started", time.strftime("%Y-%m-%dT%H:%M:%S"))
    save_session_info(args.participant, session_id, session_info)

    for block in protocol["blocks"]:
        if block["id"] < args.start_block:
            continue

        completion_log = run_block(
            block, args.participant, session_id, affected_side,
            start_condition=0,
            n_trials=n_trials,
            completion_log=completion_log,
        )

        if affected_side and not session_info.get("affected_side"):
            session_info["affected_side"] = affected_side
        session_info["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        save_session_info(args.participant, session_id, session_info)

        # Block complete — rest break (except after last block)
        if block["id"] < len(protocol["blocks"]):
            rest_s = protocol.get("rest_between_blocks_s", 120)
            block_id = block["id"]
            print(f"\n  {c(f'Block {block_id} complete!', GREEN)}")
            print(f"  {c(f'Rest break: {rest_s // 60} min.', CYAN)}")
            countdown(rest_s, "Next block in")

    session_info["status"] = "complete" if is_session_complete(
        args.participant, session_id, protocol) else "partial"
    session_info["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_session_info(args.participant, session_id, session_info)

    print_session_summary(args.participant, session_id, completion_log, protocol)
    print(c("Protocol complete!", GREEN))


if __name__ == "__main__":
    main()
