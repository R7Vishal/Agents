from coding_agent.models import RepositoryFacts
from coding_agent.planner import recommend_next_milestone


def test_planner_recommends_tests_when_absent() -> None:
    facts = RepositoryFacts(repo_path="repo")
    milestone = recommend_next_milestone(facts)
    assert "verification" in milestone.title.lower() or "baseline" in milestone.title.lower()


def test_planner_recommends_safety_when_tests_present_no_safety() -> None:
    facts = RepositoryFacts(
        repo_path="repo",
        test_files=["tests/test_x.py"],
        lifecycle_files=["src/lifecycle.py"],
    )
    milestone = recommend_next_milestone(facts)
    assert "safety" in milestone.title.lower() or "guard" in milestone.title.lower()
