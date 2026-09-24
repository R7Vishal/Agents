import pytest

from coding_agent.lifecycle import LifecycleTransitionError, assert_transition
from coding_agent.models import LifecycleState


def test_valid_transition_passes() -> None:
    assert_transition(LifecycleState.PLANNING, LifecycleState.EXECUTING)


def test_invalid_transition_raises() -> None:
    with pytest.raises(LifecycleTransitionError):
        assert_transition(LifecycleState.COMPLETED, LifecycleState.EXECUTING)
