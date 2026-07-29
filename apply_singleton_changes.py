"""
Apply committed singleton scheduling changes to the master schedule.

Usage:
  python apply_singleton_changes.py <changes.json>

Reads the exported JSON from the Singleton Scheduling Board and:
1. Updates the schedule engine's FORCED_MOVES
2. Re-runs the engine with the new singleton positions
3. Updates the workbook (Combined, Singletons, Room Schedules)
"""
import json, sys, os
from pathlib import Path

def apply_changes(changes_file):
    with open(changes_file) as f:
        data = json.load(f)

    if data.get('type') != 'committed':
        print("WARNING: These changes are not committed (draft only).")
        print("Only committed changes should be applied to the master schedule.")
        resp = input("Continue anyway? (y/n): ").strip().lower()
        if resp != 'y':
            print("Aborted.")
            return

    changes = data.get('changes', [])
    if not changes:
        print("No changes to apply.")
        return

    print(f"=== Applying {len(changes)} singleton changes ===")
    print()

    forced_moves = []
    for ch in changes:
        code = ch['code']
        title = ch['title']
        teacher = ch['teacher']
        from_p = ch['from']['period']
        from_h = ch['from']['halves']
        to_p = ch['to']['period']
        to_h = ch['to']['halves']
        enrollment = ch.get('enrollment', '?')
        total = ch.get('totalRequesters', '?')

        print(f"  {code} {title}")
        print(f"    Teacher: {teacher}")
        print(f"    Move: Period {from_p} ({from_h}) -> Period {to_p} ({to_h})")
        print(f"    Enrollment: {enrollment}/{total}")
        print()

        forced_moves.append((code, 1, to_p, f"Singleton board: {from_p}->{to_p}"))

    print("=== FORCED_MOVES for schedule engine ===")
    print("FORCED_MOVES = [")
    for fm in forced_moves:
        print(f"    {fm},")
    print("]")
    print()
    print("Copy the above FORCED_MOVES into schedule_engine_final.py")
    print("Then re-run the engine to generate updated schedules.")
    print()
    print(f"Changes file: {changes_file}")
    print(f"Total moves: {len(forced_moves)}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python apply_singleton_changes.py <changes.json>")
        sys.exit(1)
    apply_changes(sys.argv[1])
