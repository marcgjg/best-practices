"""
Backfills the edit_history table from existing best_practices entries.
Creates one history record per existing entry (the original submission).
Run once locally:
    python backfill_history.py <SUPABASE_URL> <SUPABASE_KEY>
"""
import sys
from supabase import create_client

if len(sys.argv) != 3:
    print("Usage: python backfill_history.py <URL> <KEY>")
    sys.exit(1)

url, key = sys.argv[1], sys.argv[2]
db = create_client(url, key)

entries = db.table("best_practices").select("*").execute()
if not entries.data:
    print("No entries found.")
    sys.exit(0)

# Check what's already in history to avoid duplicates
existing = db.table("edit_history").select("entry_id").execute()
already_logged = {r["entry_id"] for r in existing.data}

inserted = 0
skipped  = 0
for row in entries.data:
    if row["id"] in already_logged:
        skipped += 1
        continue
    db.table("edit_history").insert({
        "entry_id":   row["id"],
        "class_name": row["class_name"],
        "category":   row["category"],
        "practice":   row["practice"],
        "edited_by":  row["added_by"],
        "edited_on":  row["added_on"],
    }).execute()
    print(f"  ✅ Logged: [{row['class_name']}] {row['category']} by {row['added_by']}")
    inserted += 1

print(f"\nDone — {inserted} records inserted, {skipped} already existed.")
