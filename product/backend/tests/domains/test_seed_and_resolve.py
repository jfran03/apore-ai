import pytest

from apore.domains import seed, store
from apore.knowledge.chapter import resolve_chapter
import apore.api.app as app_module

PROGRAM_ROOT = app_module.PROGRAM_ROOT


@pytest.fixture(autouse=True)
def data_root(tmp_path, monkeypatch):
    monkeypatch.setenv("APORE_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def domain():
    return store.create_domain(
        name="Testbed",
        objective="obj",
        teaching_style="socratic",
        teaching_prompt="p",
        model_preference="auto",
    )


def test_seed_copies_chapters_into_workspace(domain):
    # The pytest curriculum fixture is guaranteed present by tests/api/conftest
    # for api tests; here we seed from the real discrete-math tree if present,
    # else from the _pytest tree the api conftest creates.
    source = "discrete-math"
    if not (PROGRAM_ROOT / "domains" / source / "chapters").is_dir():
        source = "_pytest"
    chapters = seed.seed_domain(
        domain, program_root=PROGRAM_ROOT, source_domain_id=source
    )
    assert chapters
    for chapter_id in chapters:
        chapter_root = store.chapters_dir(domain) / chapter_id
        assert chapter_root.is_dir()


def test_seed_missing_source_raises(domain):
    with pytest.raises(FileNotFoundError):
        seed.seed_domain(
            domain, program_root=PROGRAM_ROOT, source_domain_id="no-such-domain"
        )


def test_seed_skips_existing_chapters(domain):
    source = "discrete-math"
    if not (PROGRAM_ROOT / "domains" / source / "chapters").is_dir():
        source = "_pytest"
    first = seed.seed_domain(domain, program_root=PROGRAM_ROOT, source_domain_id=source)
    second = seed.seed_domain(domain, program_root=PROGRAM_ROOT, source_domain_id=source)
    assert first
    assert second == []


def test_resolve_workspace_chapter(domain):
    chapter_root = store.chapters_dir(domain) / "01-intro"
    chapter_root.mkdir(parents=True)
    (chapter_root / "concept-graph.json").write_text("{}", encoding="utf-8")
    ctx = resolve_chapter(f"workspace:{domain.domain_id}/01-intro", PROGRAM_ROOT)
    assert ctx.chapter_root == chapter_root
    assert ctx.knowledge_source == f"workspace:{domain.domain_id}/01-intro"


def test_resolve_workspace_missing_chapter_raises(domain):
    with pytest.raises(FileNotFoundError):
        resolve_chapter(f"workspace:{domain.domain_id}/nope", PROGRAM_ROOT)
