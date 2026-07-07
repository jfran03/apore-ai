"""Domain workspace store tests. All tests run against a tmp APORE_DATA_DIR."""

import json

import pytest

from apore.domains import store


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("APORE_DATA_DIR", str(tmp_path))
    return tmp_path


def _create(name="Discrete Math"):
    return store.create_domain(
        name=name,
        objective="Learn discrete mathematics for proof-based CS.",
        teaching_style="socratic",
        teaching_prompt="Teach through Socratic questioning.",
        model_preference="auto",
    )


def test_create_domain_scaffolds_folder(data_root):
    rec = _create()
    assert rec.path.parent == data_root
    assert rec.path.name == rec.domain_id
    assert rec.domain_id.startswith("discrete-math-")
    assert (rec.path / "domain.json").is_file()
    assert (rec.path / "sessions").is_dir()
    assert (rec.path / "sources").is_dir()
    assert (rec.path / "knowledge").is_dir()
    payload = json.loads((rec.path / "domain.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["name"] == "Discrete Math"
    assert payload["teaching_style"] == "socratic"
    assert payload["created_at"]


def test_create_domain_collision_gets_fresh_suffix():
    a = _create()
    b = _create()
    assert a.domain_id != b.domain_id


def test_list_domains_scans_root():
    a = _create("Alpha")
    b = _create("Beta")
    domains, invalid = store.list_domains()
    assert {d.domain_id for d in domains} == {a.domain_id, b.domain_id}
    assert invalid == []


def test_list_domains_reports_invalid_folder(data_root):
    _create("Good")
    bad = data_root / "hand-pasted"
    bad.mkdir()
    (bad / "domain.json").write_text("{not json", encoding="utf-8")
    naked = data_root / "no-manifest"
    naked.mkdir()

    domains, invalid = store.list_domains()
    assert len(domains) == 1
    reasons = {i.domain_id: i.reason for i in invalid}
    assert "hand-pasted" in reasons
    assert "no-manifest" in reasons


def test_load_domain_roundtrip():
    rec = _create()
    loaded = store.load_domain(rec.domain_id)
    assert loaded.name == rec.name
    assert loaded.objective == rec.objective
    assert loaded.path == rec.path


def test_load_domain_missing_raises():
    with pytest.raises(FileNotFoundError):
        store.load_domain("nope-0000")


def test_path_helpers():
    rec = _create()
    assert store.sessions_dir(rec) == rec.path / "sessions"
    assert store.sources_dir(rec) == rec.path / "sources"
    assert store.chapters_dir(rec) == rec.path / "knowledge" / "chapters"


def test_slug_is_filesystem_safe():
    rec = _create(name="  Näive / Set: Theory!  ")
    assert rec.domain_id == rec.path.name
    # slug chars only: lowercase alnum + hyphen
    slug = rec.domain_id.rsplit("-", 1)[0]
    assert all(c.isalnum() or c == "-" for c in slug)
