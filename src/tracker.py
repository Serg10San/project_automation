"""
Project lifecycle tracker.

Tracks when a project is first created, when features are added,
and when the project is marked complete. Data is persisted in a
local SQLite database at .tracker/projects.db.

Optionally syncs every state change to a central projects.json registry.
Set the IRE_PROJECTS_JSON environment variable (or pass registry_path= to
the constructor) to enable this. The tracker merges its state into the JSON
file while preserving any registry-only fields (slug, project_path).

Usage
-----
    from src.tracker import ProjectTracker

    tracker = ProjectTracker()

    # Start tracking a new project
    tracker.create("my-project", "A short description")

    # Log a feature addition
    tracker.add_feature("my-project", "user-auth", "Add JWT authentication")

    # Mark the project complete
    tracker.complete("my-project")

    # Inspect a project
    project = tracker.get("my-project")
    print(project)
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = Path(__file__).parent.parent / ".tracker" / "projects.db"

# Sentinel — distinguishes "argument not provided" from explicit None
_REGISTRY_DEFAULT = object()

REGISTRY_ENV_VAR = "IRE_PROJECTS_JSON"


def _default_registry_path() -> "Path | None":
    env = os.environ.get(REGISTRY_ENV_VAR, "").strip()
    return Path(env).resolve() if env else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return {col[0]: val for col, val in zip(cursor.description, row)}


class ProjectAlreadyExistsError(Exception):
    pass


class ProjectNotFoundError(Exception):
    pass


class ProjectAlreadyCompleteError(Exception):
    pass


class ProjectTracker:
    """Lightweight SQLite-backed project lifecycle tracker."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH, registry_path=_REGISTRY_DEFAULT) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # registry_path semantics:
        #   not provided  → read IRE_PROJECTS_JSON env var (None if unset)
        #   explicit None → disable JSON sync
        #   explicit Path → sync to that file
        if registry_path is _REGISTRY_DEFAULT:
            self.registry_path: "Path | None" = _default_registry_path()
        else:
            self.registry_path = Path(registry_path) if registry_path is not None else None

        self._init_db()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    name        TEXT PRIMARY KEY,
                    description TEXT NOT NULL DEFAULT '',
                    status      TEXT NOT NULL DEFAULT 'active',
                    started_at  TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS features (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL REFERENCES projects(name),
                    name         TEXT NOT NULL,
                    description  TEXT NOT NULL DEFAULT '',
                    added_at     TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL REFERENCES projects(name),
                    event_type   TEXT NOT NULL,
                    detail       TEXT NOT NULL DEFAULT '{}',
                    occurred_at  TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL REFERENCES projects(name),
                    body         TEXT NOT NULL,
                    created_at   TEXT NOT NULL
                );
            """)

    # ------------------------------------------------------------------
    # Event logging
    # ------------------------------------------------------------------

    def _emit_event(self, conn: sqlite3.Connection, project_name: str,
                    event_type: str, detail: dict) -> None:
        """Insert one audit event row. Must be called within an open connection."""
        conn.execute(
            "INSERT INTO events (project_name, event_type, detail, occurred_at) VALUES (?, ?, ?, ?)",
            (project_name, event_type, json.dumps(detail, ensure_ascii=False), _now_iso()),
        )

    # ------------------------------------------------------------------
    # Registry sync
    # ------------------------------------------------------------------

    def _sync_to_registry(self, project_name: str) -> None:
        """Push the current project state to the central projects.json.

        Reads the existing JSON entry first so registry-only fields (slug,
        project_path) are preserved. Creates a minimal entry if the project
        is not yet in the registry (tracker-only workflow).
        Failures are suppressed — the SQLite database remains authoritative.
        """
        if not self.registry_path:
            return
        project = self.get(project_name)
        if not project:
            return
        try:
            reg_file = self.registry_path
            reg_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                data: dict = json.loads(reg_file.read_text(encoding="utf-8")) if reg_file.exists() else {"projects": []}
            except (json.JSONDecodeError, OSError):
                data = {"projects": []}

            idx = next(
                (i for i, p in enumerate(data.get("projects", [])) if p["name"] == project_name),
                -1,
            )

            tracker_fields = {
                "status": project["status"],
                "started_at": project["started_at"],
                "completed_at": project["completed_at"],
                "features": project["features"],
                "description": project["description"],
            }

            if idx >= 0:
                # Preserve registry-only fields (slug, project_path, etc.)
                data["projects"][idx].update(tracker_fields)
            else:
                slug = project_name.lower().replace(" ", "-").replace("_", "-")
                data.setdefault("projects", []).append(
                    {"name": project_name, "slug": slug, "project_path": "", **tracker_fields}
                )

            tmp = reg_file.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            os.replace(tmp, reg_file)
        except Exception:  # noqa: BLE001
            pass  # Registry sync is best-effort

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, name: str, description: str = "") -> dict:
        """Register a new project and record its start time.

        Raises ProjectAlreadyExistsError if the project name is taken.
        """
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT name FROM projects WHERE name = ?", (name,)
            ).fetchone()
            if existing:
                raise ProjectAlreadyExistsError(f"Project '{name}' is already tracked.")

            started_at = _now_iso()
            conn.execute(
                "INSERT INTO projects (name, description, started_at) VALUES (?, ?, ?)",
                (name, description, started_at),
            )
            self._emit_event(conn, name, "created", {"description": description})

        result = self.get(name)  # type: ignore[return-value]
        self._sync_to_registry(name)
        return result

    def add_feature(
        self, project_name: str, feature_name: str, description: str = ""
    ) -> dict:
        """Log a new feature added to the project.

        Raises ProjectNotFoundError if the project does not exist.
        Raises ProjectAlreadyCompleteError if the project is already complete.
        """
        with self._connect() as conn:
            project = conn.execute(
                "SELECT status FROM projects WHERE name = ?", (project_name,)
            ).fetchone()
            if not project:
                raise ProjectNotFoundError(f"Project '{project_name}' not found.")
            if project["status"] == "complete":
                raise ProjectAlreadyCompleteError(
                    f"Project '{project_name}' is already complete."
                )

            conn.execute(
                """INSERT INTO features (project_name, name, description, added_at)
                   VALUES (?, ?, ?, ?)""",
                (project_name, feature_name, description, _now_iso()),
            )
            self._emit_event(conn, project_name, "feature_added",
                             {"feature": feature_name, "description": description})

        result = self.get(project_name)  # type: ignore[return-value]
        self._sync_to_registry(project_name)
        return result

    def complete(self, project_name: str) -> dict:
        """Mark a project as complete and record the completion timestamp.

        Raises ProjectNotFoundError if the project does not exist.
        Raises ProjectAlreadyCompleteError if already complete.
        """
        with self._connect() as conn:
            project = conn.execute(
                "SELECT status FROM projects WHERE name = ?", (project_name,)
            ).fetchone()
            if not project:
                raise ProjectNotFoundError(f"Project '{project_name}' not found.")
            if project["status"] == "complete":
                raise ProjectAlreadyCompleteError(
                    f"Project '{project_name}' is already complete."
                )

            conn.execute(
                "UPDATE projects SET status = 'complete', completed_at = ? WHERE name = ?",
                (_now_iso(), project_name),
            )
            self._emit_event(conn, project_name, "completed", {})

        result = self.get(project_name)  # type: ignore[return-value]
        self._sync_to_registry(project_name)
        return result

    def get(self, project_name: str) -> Optional[dict]:
        """Return full project details including features, or None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE name = ?", (project_name,)
            ).fetchone()
            if not row:
                return None

            project = dict(row)
            features = conn.execute(
                "SELECT name, description, added_at FROM features "
                "WHERE project_name = ? ORDER BY added_at",
                (project_name,),
            ).fetchall()
            project["features"] = [dict(f) for f in features]

        return project

    def list_projects(self) -> list[dict]:
        """Return a summary list of all tracked projects."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, description, status, started_at, completed_at "
                "FROM projects ORDER BY started_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def history(self, project_name: str) -> list[dict]:
        """Return the full audit log for a project, oldest first.

        Raises ProjectNotFoundError if the project does not exist.
        Each entry contains: event_type, detail (dict), occurred_at.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name FROM projects WHERE name = ?", (project_name,)
            ).fetchone()
            if not row:
                raise ProjectNotFoundError(f"Project '{project_name}' not found.")

            rows = conn.execute(
                "SELECT event_type, detail, occurred_at FROM events "
                "WHERE project_name = ? ORDER BY occurred_at",
                (project_name,),
            ).fetchall()

        result = []
        for r in rows:
            entry = dict(r)
            try:
                entry["detail"] = json.loads(entry["detail"])
            except (json.JSONDecodeError, TypeError):
                entry["detail"] = {}
            result.append(entry)
        return result

    def update(self, project_name: str, description: str) -> dict:
        """Update the description of an existing project.

        Records a description_updated event with the before/after values.
        Raises ProjectNotFoundError if the project does not exist.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT description FROM projects WHERE name = ?", (project_name,)
            ).fetchone()
            if not row:
                raise ProjectNotFoundError(f"Project '{project_name}' not found.")

            old_description = row["description"]
            conn.execute(
                "UPDATE projects SET description = ? WHERE name = ?",
                (description, project_name),
            )
            self._emit_event(conn, project_name, "description_updated", {
                "before": old_description,
                "after": description,
            })

        result = self.get(project_name)  # type: ignore[return-value]
        self._sync_to_registry(project_name)
        return result

    def add_note(self, project_name: str, body: str) -> dict:
        """Attach a free-text note to a project.

        Raises ProjectNotFoundError if the project does not exist.
        Returns the saved note as a dict with id, body, created_at.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name FROM projects WHERE name = ?", (project_name,)
            ).fetchone()
            if not row:
                raise ProjectNotFoundError(f"Project '{project_name}' not found.")

            created_at = _now_iso()
            cursor = conn.execute(
                "INSERT INTO notes (project_name, body, created_at) VALUES (?, ?, ?)",
                (project_name, body, created_at),
            )
            self._emit_event(conn, project_name, "note_added", {"body": body})
            note_id = cursor.lastrowid

        return {"id": note_id, "body": body, "created_at": created_at}

    def get_notes(self, project_name: str) -> list[dict]:
        """Return all notes for a project, oldest first.

        Raises ProjectNotFoundError if the project does not exist.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name FROM projects WHERE name = ?", (project_name,)
            ).fetchone()
            if not row:
                raise ProjectNotFoundError(f"Project '{project_name}' not found.")

            rows = conn.execute(
                "SELECT id, body, created_at FROM notes "
                "WHERE project_name = ? ORDER BY created_at",
                (project_name,),
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_list(tracker: ProjectTracker, _args) -> None:
    projects = tracker.list_projects()
    if not projects:
        print("No projects tracked yet.")
        return
    width = 64
    print(f"\n{'─' * width}")
    print(f"  {'Name':<28}  {'Status':<10}  Started")
    print(f"{'─' * width}")
    for p in projects:
        started = (p.get("started_at") or "")[:10]
        print(f"  {p['name']:<28}  {p['status']:<10}  {started}")
    print(f"{'─' * width}\n")


def _cmd_create(tracker: ProjectTracker, args) -> None:
    project = tracker.create(args.name, args.description or "")
    print(f"✔  Created '{project['name']}' (started {project['started_at'][:10]})")


def _cmd_add_feature(tracker: ProjectTracker, args) -> None:
    tracker.add_feature(args.name, args.feature, args.description or "")
    print(f"✔  Feature '{args.feature}' added to '{args.name}'")


def _cmd_complete(tracker: ProjectTracker, args) -> None:
    project = tracker.complete(args.name)
    print(f"✔  '{project['name']}' marked complete ({project['completed_at'][:10]})")


def _cmd_show(tracker: ProjectTracker, args) -> None:
    project = tracker.get(args.name)
    if not project:
        print(f"Project '{args.name}' not found.")
        raise SystemExit(1)
    print(json.dumps(project, indent=2))


def _cmd_history(tracker: ProjectTracker, args) -> None:
    events = tracker.history(args.name)
    if not events:
        print(f"No history recorded for '{args.name}'.")
        return
    width = 72
    print(f"\n  History: {args.name}")
    print(f"{'─' * width}")
    for e in events:
        ts = e["occurred_at"][:19].replace("T", " ")
        detail_parts = ", ".join(f"{k}={v!r}" for k, v in e["detail"].items() if v)
        detail_str = f"  ({detail_parts})" if detail_parts else ""
        print(f"  {ts}  {e['event_type']:<20}{detail_str}")
    print(f"{'─' * width}\n")


def _cmd_update(tracker: ProjectTracker, args) -> None:
    project = tracker.update(args.name, args.description)
    print(f"✔  Updated description for '{project['name']}'")


def _cmd_add_note(tracker: ProjectTracker, args) -> None:
    note = tracker.add_note(args.name, args.body)
    print(f"✔  Note added to '{args.name}' ({note['created_at'][:10]})")


def _cmd_notes(tracker: ProjectTracker, args) -> None:
    notes = tracker.get_notes(args.name)
    if not notes:
        print(f"No notes for '{args.name}'.")
        return
    width = 72
    print(f"\n  Notes: {args.name}")
    print(f"{'─' * width}")
    for n in notes:
        ts = n["created_at"][:19].replace("T", " ")
        print(f"  [{ts}]  {n['body']}")
    print(f"{'─' * width}\n")


def main() -> None:
    # Ensure Unicode output works on Windows terminals and in subprocess capture
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="IRE project lifecycle tracker (SQLite-backed)"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to the SQLite database "
            "(default: .tracker/projects.db relative to this file)"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all tracked projects")

    p_show = sub.add_parser("show", help="Show full project details as JSON")
    p_show.add_argument("name", help="Project name")

    p_hist = sub.add_parser("history", help="Show full audit log for a project")
    p_hist.add_argument("name", help="Project name")

    p_update = sub.add_parser("update", help="Update a project's description")
    p_update.add_argument("name", help="Project name")
    p_update.add_argument("description", help="New description")

    p_note = sub.add_parser("add-note", help="Attach a free-text note to a project")
    p_note.add_argument("name", help="Project name")
    p_note.add_argument("body", help="Note text")

    p_notes = sub.add_parser("notes", help="List all notes for a project")
    p_notes.add_argument("name", help="Project name")

    p_create = sub.add_parser("create", help="Start tracking a new project")
    p_create.add_argument("name", help="Project name")
    p_create.add_argument("description", nargs="?", default="", help="Short description")

    p_feat = sub.add_parser("add-feature", help="Log a feature addition")
    p_feat.add_argument("name", help="Project name")
    p_feat.add_argument("feature", help="Feature name")
    p_feat.add_argument("description", nargs="?", default="", help="Feature description")

    p_comp = sub.add_parser("complete", help="Mark a project as complete")
    p_comp.add_argument("name", help="Project name")

    args = parser.parse_args()

    kwargs: dict = {}
    if args.db:
        kwargs["db_path"] = args.db

    tracker = ProjectTracker(**kwargs)

    dispatch = {
        "list": _cmd_list,
        "show": _cmd_show,
        "history": _cmd_history,
        "create": _cmd_create,
        "add-feature": _cmd_add_feature,
        "complete": _cmd_complete,
        "update": _cmd_update,
        "add-note": _cmd_add_note,
        "notes": _cmd_notes,
    }
    try:
        dispatch[args.command](tracker, args)
    except (ProjectAlreadyExistsError, ProjectNotFoundError, ProjectAlreadyCompleteError) as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
