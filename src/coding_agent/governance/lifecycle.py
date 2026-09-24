from __future__ import annotations

from ..models import LifecycleState


class LifecycleTransitionError(ValueError):
    pass


_ALLOWED_TRANSITIONS: dict[LifecycleState, set[LifecycleState]] = {
    LifecycleState.IDLE: {LifecycleState.ANALYZING, LifecycleState.PLANNING},
    LifecycleState.ANALYZING: {LifecycleState.VALIDATING, LifecycleState.PLANNING, LifecycleState.BLOCKED, LifecycleState.FAILED},
    LifecycleState.PLANNING: {LifecycleState.READY, LifecycleState.EXECUTING, LifecycleState.BLOCKED, LifecycleState.FAILED, LifecycleState.COMPLETED},
    LifecycleState.READY: {LifecycleState.EXECUTING, LifecycleState.BLOCKED, LifecycleState.FAILED},
    LifecycleState.EXECUTING: {LifecycleState.VALIDATING, LifecycleState.REPAIRING, LifecycleState.BLOCKED, LifecycleState.FAILED, LifecycleState.COMPLETED},
    LifecycleState.VALIDATING: {LifecycleState.REPAIRING, LifecycleState.BLOCKED, LifecycleState.FAILED, LifecycleState.COMPLETED, LifecycleState.PLANNING},
    LifecycleState.REPAIRING: {LifecycleState.EXECUTING, LifecycleState.VALIDATING, LifecycleState.BLOCKED, LifecycleState.FAILED},
    LifecycleState.BLOCKED: {LifecycleState.PLANNING, LifecycleState.EXECUTING, LifecycleState.COMPLETED, LifecycleState.FAILED},
    LifecycleState.COMPLETED: set(),
    LifecycleState.FAILED: {LifecycleState.PLANNING, LifecycleState.EXECUTING, LifecycleState.BLOCKED},
}


def assert_transition(current: LifecycleState, target: LifecycleState) -> None:
    if current == target:
        return
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise LifecycleTransitionError(f"Invalid lifecycle transition: {current.value} -> {target.value}")
