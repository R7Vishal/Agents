from __future__ import annotations

from pathlib import Path

from .execution.validation_pipeline import ValidationPipelineResult
from .models import FirstRunAssessment, MilestoneRecommendation, RepositoryFacts
from .models import TaskExecutionResult, TaskStatus


def build_assessment(
    facts: RepositoryFacts,
    baseline_lines: list[str],
    milestone_title: str,
    milestone_reason: str,
    milestone_files: list[str],
    acceptance_criteria: list[str],
) -> FirstRunAssessment:
    current_state = [
        f"Repository path: {facts.repo_path}",
        f"Package manifests: {len(facts.package_manifests)}",
        f"Test-related files: {len(facts.test_files)}",
        f"Potential entry points: {len(facts.entry_points)}",
    ]

    architecture_map = [
        f"Entry points: {', '.join(facts.entry_points[:8]) or 'None detected'}",
        f"Manifests: {', '.join(facts.package_manifests[:10]) or 'None detected'}",
        f"Planner-related files: {', '.join(facts.planner_files[:10]) or 'None detected'}",
        f"Lifecycle/state files: {', '.join(facts.lifecycle_files[:10]) or 'None detected'}",
        f"Safety/invariant files: {', '.join(facts.safety_files[:10]) or 'None detected'}",
    ]

    working_capabilities = [
        "Repository discovery and file classification available",
        "TODO/FIXME marker extraction available",
        "Baseline verification discovery available",
    ]

    incomplete_capabilities = [
        "Autonomous code execution loop beyond first-run assessment",
        "Task graph persistence and dependency scheduling",
        "Evidence-driven repair and completion gate orchestration",
    ]

    risks = []
    if not facts.test_files:
        risks.append("Low confidence: no test files detected.")
    if facts.todo_markers:
        risks.append(f"Technical debt markers found in {len(facts.todo_markers)} files.")
    if not risks:
        risks.append("No critical risks detected from static first-run inspection.")

    return FirstRunAssessment(
        current_state=current_state,
        architecture_map=architecture_map,
        working_capabilities=working_capabilities,
        incomplete_capabilities=incomplete_capabilities,
        risks=risks,
        test_baseline=baseline_lines,
        recommended_milestone=MilestoneRecommendation(
            title=milestone_title,
            reason=milestone_reason,
            acceptance_criteria=acceptance_criteria,
            likely_files=milestone_files,
        ),
    )


def render_assessment_markdown(assessment: FirstRunAssessment, todo_files: list[str]) -> str:
    lines: list[str] = []
    lines.append("## CURRENT STATE")
    lines.extend(f"- {line}" for line in assessment.current_state)

    lines.append("")
    lines.append("## ARCHITECTURE MAP")
    lines.extend(f"- {line}" for line in assessment.architecture_map)

    lines.append("")
    lines.append("## WORKING CAPABILITIES")
    lines.extend(f"- {line}" for line in assessment.working_capabilities)

    lines.append("")
    lines.append("## INCOMPLETE CAPABILITIES")
    lines.extend(f"- {line}" for line in assessment.incomplete_capabilities)

    lines.append("")
    lines.append("## RISKS / TECHNICAL DEBT")
    lines.extend(f"- {line}" for line in assessment.risks)
    if todo_files:
        lines.append(f"- TODO/FIXME files: {', '.join(todo_files[:20])}")

    lines.append("")
    lines.append("## TEST BASELINE")
    lines.extend(f"- {line}" for line in assessment.test_baseline)

    lines.append("")
    lines.append("## RECOMMENDED NEXT MILESTONE")
    rm = assessment.recommended_milestone
    lines.append(f"- {rm.title}")
    lines.append(f"- Reason: {rm.reason}")

    lines.append("")
    lines.append("## FILES LIKELY TO CHANGE")
    lines.extend(f"- {line}" for line in rm.likely_files)

    lines.append("")
    lines.append("## ACCEPTANCE CRITERIA")
    lines.extend(f"- {line}" for line in rm.acceptance_criteria)

    return "\n".join(lines)


def render_task_execution_report(
    plan_file: Path,
    max_repair_attempts_per_task: int,
    results: list[TaskExecutionResult],
    validation_result: ValidationPipelineResult | None = None,
    audit_log_path: Path | None = None,
) -> str:
    lines: list[str] = []
    lines.append("## EXECUTION SUMMARY")
    lines.append(f"- Plan file: {plan_file}")
    lines.append(f"- Repair budget per task: {max_repair_attempts_per_task}")
    lines.append(f"- Total tasks processed: {len(results)}")

    completed = sum(1 for item in results if item.status == TaskStatus.COMPLETED)
    failed = sum(1 for item in results if item.status == TaskStatus.FAILED)
    blocked = sum(1 for item in results if item.status == TaskStatus.BLOCKED)
    lines.append(f"- Completed: {completed}")
    lines.append(f"- Failed: {failed}")
    lines.append(f"- Blocked: {blocked}")

    lines.append("")
    lines.append("## TASK RESULTS")
    for item in results:
        lines.append(
            f"- {item.task_id}: {item.status.value} | attempts={item.attempts} | repairs={item.repair_attempts}"
        )
        if item.duration_ms is not None:
            lines.append(f"  - Duration: {item.duration_ms} ms")
        if item.failure_type:
            lines.append(f"  - Failure type: {item.failure_type.value}")
        if item.message:
            lines.append(f"  - Message: {item.message}")

    overall_status = "PASS" if failed == 0 and blocked == 0 else "BLOCKED"

    if validation_result is not None:
        lines.append("")
        lines.append("## STAGED VALIDATION")
        lines.append(f"- Overall passed: {validation_result.overall_passed}")
        for stage in validation_result.stages:
            if stage.skipped:
                lines.append(f"- {stage.stage}: SKIPPED ({stage.skip_reason})")
            else:
                stage_status = "PASS" if stage.passed else "FAIL"
                lines.append(
                    f"- {stage.stage}: {stage_status} | attempts={stage.attempts} | exit={stage.exit_code}"
                )

    if audit_log_path is not None:
        lines.append("")
        lines.append("## APPROVAL / AUDIT")
        lines.append(f"- Audit log: {audit_log_path}")

    lines.append("")
    lines.append("## COMPLETION GATE")
    lines.append(f"- Status: {overall_status}")

    return "\n".join(lines)


def render_resume_dry_run_report(
    run_id: str,
    plan_file: Path,
    completed: list[str],
    to_retry: list[dict[str, str | int]],
    resume_max_risk: int,
    blocked_by_risk: list[dict[str, str | int]],
) -> str:
    lines: list[str] = []
    lines.append("## RESUME DRY RUN PREVIEW")
    lines.append(f"- Run ID: {run_id}")
    lines.append(f"- Plan file: {plan_file}")
    lines.append(f"- Completed tasks: {len(completed)}")
    lines.append(f"- Tasks to retry: {len(to_retry)}")
    lines.append(f"- Resume max risk policy: {resume_max_risk}")
    lines.append(f"- Above-threshold tasks: {len(blocked_by_risk)}")

    lines.append("")
    lines.append("## COMPLETED TASKS")
    if completed:
        lines.extend(f"- {task_id}" for task_id in completed)
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## RETRY QUEUE")
    if to_retry:
        for item in to_retry:
            lines.append(
                f"- {item['task_id']} | risk={item['risk_level']} ({item['risk_score']}/5)"
            )
            lines.append(f"  - Reason: {item['reason']}")
            lines.append(f"  - Recommendation: {item['recommendation']}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## POLICY PREVIEW")
    if blocked_by_risk:
        lines.append("- Resume execution would be blocked by --resume-max-risk for:")
        lines.extend(f"  - {item['task_id']} (risk {item['risk_score']}/5)" for item in blocked_by_risk)
    else:
        lines.append("- No retry task exceeds the configured risk threshold.")

    lines.append("")
    lines.append("## NEXT ACTION")
    lines.append("- Re-run without --resume-dry-run to continue execution from this checkpoint.")

    return "\n".join(lines)


def render_integrity_forensics_report(
    run_id: str,
    plan_file: Path,
    envelope_type: str,
    algorithm: str,
    signature_version: str,
    key_id: str,
    resolved_key_id: str,
    active_key_id: str,
    expected_hash: str,
    actual_hash: str,
    expected_signature: str,
    actual_signature: str,
    task_count: int,
    task_ids: list[str],
) -> str:
    lines: list[str] = []
    lines.append("## CHECKPOINT INTEGRITY FORENSICS")
    lines.append(f"- Run ID: {run_id}")
    lines.append(f"- Plan file: {plan_file}")
    lines.append("- Integrity status: FAILED")
    lines.append(f"- Envelope type: {envelope_type or 'unknown'}")
    lines.append(f"- Algorithm: {algorithm or 'unknown'}")
    lines.append(f"- Signature version: {signature_version or 'unknown'}")
    lines.append(f"- Envelope key ID: {key_id or 'missing'}")
    lines.append(f"- Resolved key ID: {resolved_key_id or 'unresolved'}")
    lines.append(f"- Active key ID: {active_key_id or 'missing'}")
    lines.append(f"- Expected hash: {expected_hash or 'missing'}")
    lines.append(f"- Actual hash: {actual_hash or 'missing'}")
    lines.append(f"- Expected signature: {expected_signature or 'missing'}")
    lines.append(f"- Actual signature: {actual_signature or 'missing'}")
    lines.append(f"- Checkpoint task count: {task_count}")

    lines.append("")
    lines.append("## CHECKPOINT TASK IDS")
    if task_ids:
        lines.extend(f"- {task_id}" for task_id in task_ids)
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## NEXT ACTION")
    lines.append("- Do not resume this run until state integrity is restored.")
    lines.append("- Recreate checkpoint by starting a new run-plan execution if needed.")

    return "\n".join(lines)


def render_resume_policy_block_report(
    run_id: str,
    plan_file: Path,
    resume_max_risk: int,
    blocked_items: list[dict[str, str | int]],
) -> str:
    lines: list[str] = []
    lines.append("## RESUME POLICY BLOCK")
    lines.append(f"- Run ID: {run_id}")
    lines.append(f"- Plan file: {plan_file}")
    lines.append(f"- Configured max risk: {resume_max_risk}")
    lines.append(f"- Blocked retry tasks: {len(blocked_items)}")

    lines.append("")
    lines.append("## BLOCKED TASKS")
    for item in blocked_items:
        lines.append(f"- {item['task_id']} | risk={item['risk_level']} ({item['risk_score']}/5)")
        lines.append(f"  - Reason: {item['reason']}")
        lines.append(f"  - Recommendation: {item['recommendation']}")

    lines.append("")
    lines.append("## NEXT ACTION")
    lines.append("- Increase --resume-max-risk or remediate risky tasks manually before resume.")

    return "\n".join(lines)
