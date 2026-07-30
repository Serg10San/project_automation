"""Tests for src/tracker.py"""

import json
import subprocess
import sys
import pytest
from pathlib import Path

from src.tracker import (
    ProjectTracker,
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
    ProjectAlreadyCompleteError,
)


@pytest.fixture
def tracker(tmp_path: Path) -> ProjectTracker:
    """Return a tracker backed by a temporary database (no registry sync)."""
    return ProjectTracker(db_path=tmp_path / "test_projects.db", registry_path=None)


@pytest.fixture
def registry_path(tmp_path: Path) -> Path:
    return tmp_path / "projects.json"


@pytest.fixture
def tracker_with_registry(tmp_path: Path, registry_path: Path) -> ProjectTracker:
    """Return a tracker that also syncs to a temporary projects.json."""
    return ProjectTracker(
        db_path=tmp_path / "test_projects.db",
        registry_path=registry_path,
    )


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------

class TestCreate:
    def test_creates_project_with_status_active(self, tracker):
        project = tracker.create("alpha")
        assert project["name"] == "alpha"
        assert project["status"] == "active"

    def test_records_started_at(self, tracker):
        project = tracker.create("alpha")
        assert project["started_at"] is not None

    def test_stores_description(self, tracker):
        project = tracker.create("alpha", "My first project")
        assert project["description"] == "My first project"

    def test_completed_at_is_none_on_creation(self, tracker):
        project = tracker.create("alpha")
        assert project["completed_at"] is None

    def test_starts_with_no_features(self, tracker):
        project = tracker.create("alpha")
        assert project["features"] == []

    def test_raises_if_duplicate_name(self, tracker):
        tracker.create("alpha")
        with pytest.raises(ProjectAlreadyExistsError):
            tracker.create("alpha")


# ---------------------------------------------------------------------------
# add_feature()
# ---------------------------------------------------------------------------

class TestAddFeature:
    def test_feature_appears_in_project(self, tracker):
        tracker.create("alpha")
        tracker.add_feature("alpha", "login", "User login flow")
        project = tracker.get("alpha")
        assert len(project["features"]) == 1
        assert project["features"][0]["name"] == "login"

    def test_multiple_features_ordered_by_time(self, tracker):
        tracker.create("alpha")
        tracker.add_feature("alpha", "login")
        tracker.add_feature("alpha", "logout")
        names = [f["name"] for f in tracker.get("alpha")["features"]]
        assert names == ["login", "logout"]

    def test_feature_records_added_at(self, tracker):
        tracker.create("alpha")
        tracker.add_feature("alpha", "login")
        feature = tracker.get("alpha")["features"][0]
        assert feature["added_at"] is not None

    def test_raises_for_unknown_project(self, tracker):
        with pytest.raises(ProjectNotFoundError):
            tracker.add_feature("ghost", "feature")

    def test_raises_if_project_complete(self, tracker):
        tracker.create("alpha")
        tracker.complete("alpha")
        with pytest.raises(ProjectAlreadyCompleteError):
            tracker.add_feature("alpha", "late-feature")


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------

class TestComplete:
    def test_status_becomes_complete(self, tracker):
        tracker.create("alpha")
        project = tracker.complete("alpha")
        assert project["status"] == "complete"

    def test_completed_at_is_set(self, tracker):
        tracker.create("alpha")
        project = tracker.complete("alpha")
        assert project["completed_at"] is not None

    def test_raises_for_unknown_project(self, tracker):
        with pytest.raises(ProjectNotFoundError):
            tracker.complete("ghost")

    def test_raises_if_already_complete(self, tracker):
        tracker.create("alpha")
        tracker.complete("alpha")
        with pytest.raises(ProjectAlreadyCompleteError):
            tracker.complete("alpha")


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestGet:
    def test_returns_none_for_unknown_project(self, tracker):
        assert tracker.get("ghost") is None

    def test_returns_full_project_dict(self, tracker):
        tracker.create("alpha", "desc")
        tracker.add_feature("alpha", "feat-a")
        project = tracker.get("alpha")
        assert project["name"] == "alpha"
        assert project["description"] == "desc"
        assert len(project["features"]) == 1


# ---------------------------------------------------------------------------
# list_projects()
# ---------------------------------------------------------------------------

class TestListProjects:
    def test_empty_when_no_projects(self, tracker):
        assert tracker.list_projects() == []

    def test_lists_all_projects(self, tracker):
        tracker.create("alpha")
        tracker.create("beta")
        names = [p["name"] for p in tracker.list_projects()]
        assert "alpha" in names
        assert "beta" in names

    def test_list_does_not_include_features(self, tracker):
        tracker.create("alpha")
        tracker.add_feature("alpha", "feat-a")
        projects = tracker.list_projects()
        assert "features" not in projects[0]


# ---------------------------------------------------------------------------
# JSON registry sync
# ---------------------------------------------------------------------------

class TestRegistrySync:
    def test_create_writes_to_registry(self, tracker_with_registry, registry_path):
        tracker_with_registry.create("alpha", "desc")
        data = json.loads(registry_path.read_text())
        assert data["projects"][0]["name"] == "alpha"

    def test_create_sets_status_active_in_registry(self, tracker_with_registry, registry_path):
        tracker_with_registry.create("alpha")
        data = json.loads(registry_path.read_text())
        assert data["projects"][0]["status"] == "active"

    def test_add_feature_updates_registry(self, tracker_with_registry, registry_path):
        tracker_with_registry.create("alpha")
        tracker_with_registry.add_feature("alpha", "login", "User login")
        data = json.loads(registry_path.read_text())
        features = data["projects"][0]["features"]
        assert len(features) == 1
        assert features[0]["name"] == "login"

    def test_complete_sets_status_in_registry(self, tracker_with_registry, registry_path):
        tracker_with_registry.create("alpha")
        tracker_with_registry.complete("alpha")
        data = json.loads(registry_path.read_text())
        assert data["projects"][0]["status"] == "complete"
        assert data["projects"][0]["completed_at"] is not None

    def test_sync_preserves_registry_only_fields(self, tracker_with_registry, registry_path):
        """Registry-added fields like project_path and slug must survive a sync."""
        registry_path.write_text(json.dumps({
            "projects": [{
                "name": "alpha",
                "slug": "alpha",
                "description": "",
                "project_path": r"C:\projects\alpha",
                "status": "active",
                "started_at": "2026-01-01T00:00:00+00:00",
                "completed_at": None,
                "features": [],
            }]
        }), encoding="utf-8")

        tracker_with_registry.create("alpha")
        tracker_with_registry.add_feature("alpha", "auth")
        data = json.loads(registry_path.read_text())
        entry = data["projects"][0]
        assert entry["project_path"] == r"C:\projects\alpha"
        assert entry["slug"] == "alpha"

    def test_no_registry_means_no_json_file(self, tracker, tmp_path):
        """When registry_path is None, no JSON is written."""
        tracker.create("alpha")
        json_files = list(tmp_path.glob("*.json"))
        assert json_files == []

    def test_sync_does_not_raise_on_bad_registry_path(self, tmp_path):
        """A bad registry path must not break tracker operations."""
        t = ProjectTracker(
            db_path=tmp_path / "test.db",
            registry_path=tmp_path / "nonexistent_dir" / "projects.json",
        )
        t.create("alpha")
        assert t.get("alpha")["name"] == "alpha"

    def test_registry_path_none_disables_sync(self, tmp_path):
        """Explicit None disables sync regardless of env vars."""
        t = ProjectTracker(db_path=tmp_path / "test.db", registry_path=None)
        assert t.registry_path is None
        t.create("alpha")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

TRACKER_MODULE = "src.tracker"


def _cli(tmp_db: Path, *args) -> subprocess.CompletedProcess:
    """Run tracker CLI with a temp DB and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", TRACKER_MODULE, "--db", str(tmp_db), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class TestCLI:
    def test_list_empty(self, tmp_path):
        result = _cli(tmp_path / "t.db", "list")
        assert result.returncode == 0
        assert "No projects tracked yet" in result.stdout

    def test_create_prints_confirmation(self, tmp_path):
        result = _cli(tmp_path / "t.db", "create", "alpha", "A test project")
        assert result.returncode == 0
        assert "Created 'alpha'" in result.stdout

    def test_create_then_list_shows_project(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        result = _cli(db, "list")
        assert "alpha" in result.stdout
        assert "active" in result.stdout

    def test_create_duplicate_exits_nonzero(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        result = _cli(db, "create", "alpha")
        assert result.returncode != 0
        assert "Error" in result.stdout

    def test_add_feature_prints_confirmation(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        result = _cli(db, "add-feature", "alpha", "login", "User login flow")
        assert result.returncode == 0
        assert "login" in result.stdout

    def test_add_feature_unknown_project_exits_nonzero(self, tmp_path):
        result = _cli(tmp_path / "t.db", "add-feature", "ghost", "feat")
        assert result.returncode != 0

    def test_complete_prints_confirmation(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        result = _cli(db, "complete", "alpha")
        assert result.returncode == 0
        assert "marked complete" in result.stdout

    def test_complete_unknown_project_exits_nonzero(self, tmp_path):
        result = _cli(tmp_path / "t.db", "complete", "ghost")
        assert result.returncode != 0

    def test_show_outputs_valid_json(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha", "My project")
        result = _cli(db, "show", "alpha")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["name"] == "alpha"
        assert data["description"] == "My project"

    def test_show_includes_features(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        _cli(db, "add-feature", "alpha", "login", "User login")
        result = _cli(db, "show", "alpha")
        data = json.loads(result.stdout)
        assert len(data["features"]) == 1
        assert data["features"][0]["name"] == "login"

    def test_show_unknown_project_exits_nonzero(self, tmp_path):
        result = _cli(tmp_path / "t.db", "show", "ghost")
        assert result.returncode != 0

    def test_list_shows_complete_status_after_complete(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        _cli(db, "complete", "alpha")
        result = _cli(db, "list")
        assert "complete" in result.stdout


# ---------------------------------------------------------------------------
# history()
# ---------------------------------------------------------------------------

class TestHistory:
    def test_create_emits_created_event(self, tracker):
        tracker.create("alpha", "desc")
        events = tracker.history("alpha")
        assert len(events) == 1
        assert events[0]["event_type"] == "created"
        assert events[0]["detail"]["description"] == "desc"

    def test_add_feature_emits_feature_added_event(self, tracker):
        tracker.create("alpha")
        tracker.add_feature("alpha", "login", "User login")
        events = tracker.history("alpha")
        assert events[1]["event_type"] == "feature_added"
        assert events[1]["detail"]["feature"] == "login"

    def test_complete_emits_completed_event(self, tracker):
        tracker.create("alpha")
        tracker.complete("alpha")
        events = tracker.history("alpha")
        assert events[-1]["event_type"] == "completed"

    def test_full_lifecycle_event_order(self, tracker):
        tracker.create("alpha")
        tracker.add_feature("alpha", "login")
        tracker.add_feature("alpha", "logout")
        tracker.complete("alpha")
        types = [e["event_type"] for e in tracker.history("alpha")]
        assert types == ["created", "feature_added", "feature_added", "completed"]

    def test_history_raises_for_unknown_project(self, tracker):
        with pytest.raises(ProjectNotFoundError):
            tracker.history("ghost")

    def test_detail_is_dict_not_string(self, tracker):
        tracker.create("alpha", "desc")
        event = tracker.history("alpha")[0]
        assert isinstance(event["detail"], dict)

    def test_events_have_occurred_at_timestamp(self, tracker):
        tracker.create("alpha")
        event = tracker.history("alpha")[0]
        assert event["occurred_at"] is not None


class TestCLIHistory:
    def test_history_shows_created_event(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha", "My project")
        result = _cli(db, "history", "alpha")
        assert result.returncode == 0
        assert "created" in result.stdout

    def test_history_shows_feature_added(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        _cli(db, "add-feature", "alpha", "login", "User login")
        result = _cli(db, "history", "alpha")
        assert "feature_added" in result.stdout
        assert "login" in result.stdout

    def test_history_shows_completed_event(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        _cli(db, "complete", "alpha")
        result = _cli(db, "history", "alpha")
        assert "completed" in result.stdout

    def test_history_unknown_project_exits_nonzero(self, tmp_path):
        result = _cli(tmp_path / "t.db", "history", "ghost")
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_changes_description(self, tracker):
        tracker.create("alpha", "old desc")
        tracker.update("alpha", "new desc")
        assert tracker.get("alpha")["description"] == "new desc"

    def test_update_emits_description_updated_event(self, tracker):
        tracker.create("alpha", "old desc")
        tracker.update("alpha", "new desc")
        events = tracker.history("alpha")
        update_events = [e for e in events if e["event_type"] == "description_updated"]
        assert len(update_events) == 1
        assert update_events[0]["detail"]["before"] == "old desc"
        assert update_events[0]["detail"]["after"] == "new desc"

    def test_update_raises_for_unknown_project(self, tracker):
        with pytest.raises(ProjectNotFoundError):
            tracker.update("ghost", "new desc")

    def test_multiple_updates_all_recorded(self, tracker):
        tracker.create("alpha", "v1")
        tracker.update("alpha", "v2")
        tracker.update("alpha", "v3")
        events = [e for e in tracker.history("alpha") if e["event_type"] == "description_updated"]
        assert len(events) == 2
        assert events[0]["detail"] == {"before": "v1", "after": "v2"}
        assert events[1]["detail"] == {"before": "v2", "after": "v3"}

    def test_update_syncs_to_registry(self, tracker_with_registry, registry_path):
        tracker_with_registry.create("alpha", "old")
        tracker_with_registry.update("alpha", "new")
        data = json.loads(registry_path.read_text())
        assert data["projects"][0]["description"] == "new"


class TestCLIUpdate:
    def test_update_prints_confirmation(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha", "old desc")
        result = _cli(db, "update", "alpha", "new desc")
        assert result.returncode == 0
        assert "Updated" in result.stdout

    def test_update_persists(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha", "old")
        _cli(db, "update", "alpha", "new")
        result = _cli(db, "show", "alpha")
        data = json.loads(result.stdout)
        assert data["description"] == "new"

    def test_update_unknown_project_exits_nonzero(self, tmp_path):
        result = _cli(tmp_path / "t.db", "update", "ghost", "new desc")
        assert result.returncode != 0

    def test_update_recorded_in_history(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha", "old")
        _cli(db, "update", "alpha", "new")
        result = _cli(db, "history", "alpha")
        assert "description_updated" in result.stdout


# ---------------------------------------------------------------------------
# add_note() / get_notes()
# ---------------------------------------------------------------------------

class TestNotes:
    def test_add_note_returns_note_dict(self, tracker):
        tracker.create("alpha")
        note = tracker.add_note("alpha", "First note")
        assert note["body"] == "First note"
        assert note["created_at"] is not None
        assert note["id"] is not None

    def test_get_notes_returns_all_notes(self, tracker):
        tracker.create("alpha")
        tracker.add_note("alpha", "Note 1")
        tracker.add_note("alpha", "Note 2")
        notes = tracker.get_notes("alpha")
        assert len(notes) == 2
        assert notes[0]["body"] == "Note 1"
        assert notes[1]["body"] == "Note 2"

    def test_get_notes_empty_when_none(self, tracker):
        tracker.create("alpha")
        assert tracker.get_notes("alpha") == []

    def test_add_note_emits_note_added_event(self, tracker):
        tracker.create("alpha")
        tracker.add_note("alpha", "My note")
        events = tracker.history("alpha")
        note_events = [e for e in events if e["event_type"] == "note_added"]
        assert len(note_events) == 1
        assert note_events[0]["detail"]["body"] == "My note"

    def test_add_note_raises_for_unknown_project(self, tracker):
        with pytest.raises(ProjectNotFoundError):
            tracker.add_note("ghost", "note")

    def test_get_notes_raises_for_unknown_project(self, tracker):
        with pytest.raises(ProjectNotFoundError):
            tracker.get_notes("ghost")

    def test_notes_ordered_oldest_first(self, tracker):
        tracker.create("alpha")
        tracker.add_note("alpha", "first")
        tracker.add_note("alpha", "second")
        notes = tracker.get_notes("alpha")
        assert notes[0]["body"] == "first"
        assert notes[1]["body"] == "second"


class TestCLINotes:
    def test_add_note_prints_confirmation(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        result = _cli(db, "add-note", "alpha", "First note")
        assert result.returncode == 0
        assert "Note added" in result.stdout

    def test_notes_lists_all_notes(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        _cli(db, "add-note", "alpha", "First note")
        _cli(db, "add-note", "alpha", "Second note")
        result = _cli(db, "notes", "alpha")
        assert result.returncode == 0
        assert "First note" in result.stdout
        assert "Second note" in result.stdout

    def test_notes_empty_message(self, tmp_path):
        db = tmp_path / "t.db"
        _cli(db, "create", "alpha")
        result = _cli(db, "notes", "alpha")
        assert result.returncode == 0
        assert "No notes" in result.stdout

    def test_add_note_unknown_project_exits_nonzero(self, tmp_path):
        result = _cli(tmp_path / "t.db", "add-note", "ghost", "note")
        assert result.returncode != 0

    def test_notes_unknown_project_exits_nonzero(self, tmp_path):
        result = _cli(tmp_path / "t.db", "notes", "ghost")
        assert result.returncode != 0
