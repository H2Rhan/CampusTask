import pytest

from app.models.task import TaskStatus
from app.services.state_machine import IllegalTransition, assert_transition, can_transition


def test_happy_path():
    chain = [
        TaskStatus.PENDING, TaskStatus.ACCEPTED, TaskStatus.IN_PROGRESS,
        TaskStatus.ARRIVED_PICKUP, TaskStatus.PICKED_UP, TaskStatus.DELIVERING,
        TaskStatus.PENDING_CONFIRM, TaskStatus.COMPLETED, TaskStatus.SETTLED,
    ]
    for a, b in zip(chain, chain[1:]):
        assert can_transition(a, b), f"{a} -> {b} 应当合法"


def test_illegal_jumps():
    assert not can_transition(TaskStatus.PENDING, TaskStatus.COMPLETED)
    assert not can_transition(TaskStatus.PENDING, TaskStatus.DELIVERING)
    assert not can_transition(TaskStatus.SETTLED, TaskStatus.CANCELLED)
    assert not can_transition(TaskStatus.COMPLETED, TaskStatus.ARBITRATING)
    with pytest.raises(IllegalTransition):
        assert_transition(TaskStatus.PENDING, TaskStatus.PICKED_UP)


def test_arbitration_branch():
    assert can_transition(TaskStatus.IN_PROGRESS, TaskStatus.ARBITRATING)
    assert can_transition(TaskStatus.PENDING_CONFIRM, TaskStatus.ARBITRATING)
    assert can_transition(TaskStatus.ARBITRATING, TaskStatus.CLOSED_BY_ARBITRATION)
    assert not can_transition(TaskStatus.CLOSED_BY_ARBITRATION, TaskStatus.SETTLED)
