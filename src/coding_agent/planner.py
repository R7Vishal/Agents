from __future__ import annotations

from .models import MilestoneRecommendation, RepositoryFacts


def recommend_next_milestone(facts: RepositoryFacts) -> MilestoneRecommendation:
    if not facts.test_files:
        return MilestoneRecommendation(
            title="Add baseline verification harness",
            reason="Repository has no discoverable automated tests.",
            acceptance_criteria=[
                "At least one deterministic smoke test exists",
                "Test command is documented and executable",
                "Baseline PASS/FAIL is reported explicitly",
            ],
            likely_files=["tests/", "README.md", "scripts/"],
        )

    if not facts.lifecycle_files:
        return MilestoneRecommendation(
            title="Introduce explicit lifecycle state machine",
            reason="No clear lifecycle/state module detected.",
            acceptance_criteria=[
                "Lifecycle enum with guarded transitions is implemented",
                "State persists across runs",
                "Invalid transitions are rejected with clear errors",
            ],
            likely_files=["src/**/state*.py", "src/**/agent*.py", "tests/"],
        )

    if not facts.safety_files:
        return MilestoneRecommendation(
            title="Add command and write safety layer",
            reason="Safety/invariant guard files are not clearly present.",
            acceptance_criteria=[
                "Dangerous commands are blocked by policy",
                "Protected paths are enforced",
                "Safety behavior is unit tested",
            ],
            likely_files=["src/**/safety*.py", "tests/"],
        )

    return MilestoneRecommendation(
        title="Strengthen repair loop classification",
        reason="Core structure exists; next smallest value is tighter failure diagnosis.",
        acceptance_criteria=[
            "Failure classes are explicit",
            "Minimal repair strategy is documented and tested",
            "Repair budget gates prevent infinite loops",
        ],
        likely_files=["src/**/repair*.py", "src/**/verifier*.py", "tests/"],
    )
