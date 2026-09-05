"""Apply the reviewed September 2026 sign presence migration once.

Run with uv. Existing observation dates, notes, IDs, and geometry are preserved.
The CSV records every classification decision. This is a historical migration,
not a rule for interpreting future field notes.
"""

import argparse
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Exact observation and tree UUID pairs prevent species-level corrections from
# leaking into other physical locations with the same tree_id.
REVIEWED = {
    26: (
        "{c3359863-8181-49a6-9500-32277511d011}",
        "Present",
        "Sign card has wrong family",
    ),
    46: (
        "{dbe4259c-f5f7-486a-a9f5-3f8a10960a6e}",
        "Unknown",
        "Note explicitly asks whether a sign is present",
    ),
    60: ("{2e0ba497-f878-4fdf-9d3d-7d3b85b415eb}", "Present", "Sign needs backing out"),
    96: (
        "{914c1eaf-47d6-4913-a6e2-17014ffe3403}",
        "Absent",
        "New species note explicitly says needs sign",
    ),
    124: (
        "{5a7a9a05-0c63-4fa0-9128-454635ee7702}",
        "Absent",
        "Observer took sign away for reinstallation",
    ),
    141: (
        "{38296329-e0c4-498b-9704-7eaadb8a9200}",
        "Absent",
        "Observer took sign away after screws broke",
    ),
    146: (
        "{890b4369-7b8b-43ca-9b3d-54ff8f8d56d7}",
        "Present",
        "Sign missing bottom screw",
    ),
    147: (
        "{797c75a6-c100-417b-a607-67e31ad2a0aa}",
        "Present",
        "Sign missing bottom screw",
    ),
    151: (
        "{b3acedcb-4aa8-47ca-b298-a3e951388314}",
        "Present",
        "Sign has screw, vegetation, and text issues",
    ),
    152: (
        "{4a7be455-e92c-4a93-af8b-dbebc053baa7}",
        "Present",
        "Sign has wrong family name",
    ),
    154: (
        "{c3359863-8181-49a6-9500-32277511d011}",
        "Present",
        "Sign has wrong family name",
    ),
    159: (
        "{9f16f47b-d3e3-4b44-a813-deeeff331b4a}",
        "Present",
        "Sign missing bottom screw",
    ),
    172: (
        "{8d9e66a5-4a87-4166-b03b-e524ca9f4725}",
        "Present",
        "Sign is present but overgrown",
    ),
    174: ("{5cb79cc2-6673-44ad-bcc6-7f59b8df1298}", "Present", "Sign is overgrown"),
    193: (
        "{95869303-0b9a-4a82-8944-104f5cae75ae}",
        "Present",
        "Owner confirmed name-check note implies sign present",
    ),
    194: (
        "{acb77fcc-1eb4-482a-b31d-3b2328c6b344}",
        "Present",
        "Owner confirmed identifying plaque counts as a sign",
    ),
}
MAINTENANCE = {
    170: "{4efd937d-4de9-4bc4-9ee8-d73dd0af79e0}",
    175: "{daeefb53-b752-4fc3-889f-696e5c0fa071}",
    183: "{678f768e-ee5a-4da5-a55d-9803872d6668}",
    184: "{a737794f-1ee5-40c1-8d22-735e92bb3f5a}",
}


def migrate(package: Path, report: Path) -> int:
    with sqlite3.connect(
        f"{package.resolve().as_uri()}?mode=rw", uri=True
    ) as connection:
        connection.row_factory = sqlite3.Row
        if "sign_presence" in {
            r["name"] for r in connection.execute("PRAGMA table_info(observations)")
        }:
            print("Sign presence already exists. No historical corrections reapplied.")
            return 0
        rows = connection.execute("SELECT * FROM observations ORDER BY fid").fetchall()
        by_id = {r["fid"]: r for r in rows}
        for fid, (uuid, _, _) in REVIEWED.items():
            if fid not in by_id or by_id[fid]["tree_uuid"] != uuid:
                raise ValueError(
                    f"Observation {fid} does not match the reviewed tree UUID"
                )
        for fid, uuid in MAINTENANCE.items():
            if (
                fid not in by_id
                or by_id[fid]["tree_uuid"] != uuid
                or by_id[fid]["status"] != "OK"
            ):
                raise ValueError(
                    f"Maintenance observation {fid} has changed since review"
                )

        decisions = []
        for row in rows:
            status = row["status"]
            presence = "Unknown"
            reason = "No explicit evidence of sign presence"
            if row["tree_uuid"] and status == "OK":
                presence, reason = (
                    "Present",
                    "Historical OK classification indicates signed tree",
                )
            elif status == "No Sign":
                presence, reason = "Absent", "Historical No Sign classification"
                status = "Needs Attention"
            if row["fid"] in REVIEWED:
                _, presence, reason = REVIEWED[row["fid"]]
            if row["fid"] in MAINTENANCE:
                status = "Needs Attention"
                reason += ". Unresolved maintenance or identification note"
            decisions.append(
                {
                    "observation_fid": row["fid"],
                    "tree_uuid": row["tree_uuid"],
                    "tree_id": row["tree_id"],
                    "point_id": row["point_id"],
                    "dateobserved": row["dateobserved"],
                    "previous_status": row["status"],
                    "status": status,
                    "sign_presence": presence,
                    "reason": reason,
                }
            )

        # Explicit transaction includes DDL, so failed backfills roll back too.
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("""ALTER TABLE observations ADD COLUMN sign_presence TEXT
            NOT NULL DEFAULT 'Unknown'
            CHECK (sign_presence IN ('Present', 'Absent', 'Unknown'))""")
        connection.executemany(
            "UPDATE observations SET status = :status, sign_presence = :sign_presence WHERE fid = :observation_fid",
            decisions,
        )
        connection.execute(
            "UPDATE gpkg_contents SET last_change = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE table_name = 'observations'"
        )
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(decisions[0]))
            writer.writeheader()
            writer.writerows(decisions)
    print(f"Classified {len(decisions)} observations. Review log saved to {report}.")
    return len(decisions)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=ROOT / "map/cuesta-trees.gpkg")
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "reference/sign_presence_migration_20260904.csv",
    )
    args = parser.parse_args()
    migrate(args.package, args.report)
