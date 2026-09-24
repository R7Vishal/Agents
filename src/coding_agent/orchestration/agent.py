from __future__ import annotations

import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..execution.executor import execute_task_graph
from ..execution.command_runner import SandboxPolicy
from ..execution.task_graph import (
    apply_task_graph_checkpoint,
    extract_checkpoint_data,
    load_task_graph,
    snapshot_task_graph,
    validate_task_graph,
)
from ..execution.validation_pipeline import ValidationPipelineResult, run_staged_validation
from ..governance.approval import ApprovalPolicy
from ..execution.verifier import run_baseline_checks
from ..governance.integrity import (
    checkpoint_forensics,
    get_active_signing_key,
    load_or_create_hmac_keyring,
    rotate_hmac_key,
    verify_checkpoint_payload,
    wrap_checkpoint_payload,
)
from ..models import AgentRunRecord, FailureType, LifecycleState, TaskExecutionResult, TaskStatus
from ..observability import JsonlLogger
from ..planner import recommend_next_milestone
from ..repo_intel import discover_repository
from ..reporting import (
    build_assessment,
    render_assessment_markdown,
    render_integrity_forensics_report,
    render_resume_dry_run_report,
    render_resume_policy_block_report,
    render_task_execution_report,
)
from ..state_store import StateStore


class CodingAgent:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.state_store = StateStore(workspace_root / ".agent_state")
        self.log_dir = workspace_root / ".agent_logs"
        self.checkpoint_keyring = load_or_create_hmac_keyring(self.state_store.state_dir)
        self.active_key_id, self.checkpoint_hmac_key = get_active_signing_key(self.checkpoint_keyring)

    def rotate_checkpoint_key(self) -> dict[str, Any]:
        rotation = rotate_hmac_key(self.state_store.state_dir)
        self.checkpoint_keyring = load_or_create_hmac_keyring(self.state_store.state_dir)
        self.active_key_id, self.checkpoint_hmac_key = get_active_signing_key(self.checkpoint_keyring)
        return rotation

    def first_run_assessment(
        self,
        repo_path: Path,
        requirement: str,
        run_baseline: bool,
    ) -> str:
        run_id = str(uuid.uuid4())
        record = AgentRunRecord(
            run_id=run_id,
            requirement=requirement,
            state=LifecycleState.ANALYZING,
            repo_path=str(repo_path),
            notes={},
        )
        self.state_store.save(record)
        logger = JsonlLogger(self.log_dir, run_id)
        logger.emit("run_started", mode="first-run", repo_path=str(repo_path))

        facts = discover_repository(repo_path)

        self.state_store.transition(record, LifecycleState.VALIDATING)
        logger.emit("state_transition", state=record.state.value)

        baseline_results = run_baseline_checks(repo_path=repo_path, execute=run_baseline)
        baseline_lines: list[str] = []
        for item in baseline_results:
            if item.executed:
                status = "PASS" if item.passed else "FAIL"
                baseline_lines.append(
                    f"{item.name}: executed ({item.command}) => {status} (exit={item.exit_code})"
                )
            elif item.available:
                baseline_lines.append(f"{item.name}: available but not executed ({item.command})")
            else:
                baseline_lines.append(f"{item.name}: not available in environment")

        self.state_store.transition(record, LifecycleState.PLANNING)
        logger.emit("state_transition", state=record.state.value)

        milestone = recommend_next_milestone(facts)

        assessment = build_assessment(
            facts=facts,
            baseline_lines=baseline_lines,
            milestone_title=milestone.title,
            milestone_reason=milestone.reason,
            milestone_files=milestone.likely_files,
            acceptance_criteria=milestone.acceptance_criteria,
        )

        self.state_store.transition(record, LifecycleState.COMPLETED)
        record.notes = {
            "assessment": asdict(assessment),
            "mode": "first-run",
        }
        self.state_store.save(record)
        logger.emit("run_completed", mode="first-run", state=record.state.value)

        return render_assessment_markdown(assessment, facts.todo_markers)

    def run_controlled_plan(
        self,
        repo_path: Path,
        requirement: str,
        plan_file: Path,
        max_repair_attempts_per_task: int,
        sandbox_profile: str = "local",
        scoped_write_paths: list[str] | None = None,
        require_approval: bool = False,
        approved_actions: list[str] | None = None,
        run_validation_pipeline: bool = False,
        validation_retries_per_stage: int = 1,
        resume_run_id: str | None = None,
        resume_latest: bool = False,
        resume_dry_run: bool = False,
        resume_max_risk: int = 5,
    ) -> str:
        if resume_dry_run and not (resume_run_id or resume_latest):
            raise ValueError("--resume-dry-run requires --resume-run-id or --resume-latest")
        if resume_max_risk < 1 or resume_max_risk > 5:
            raise ValueError("--resume-max-risk must be between 1 and 5")

        is_resume = bool(resume_run_id or resume_latest)

        record = self._resolve_run_record(
            repo_path=repo_path,
            requirement=requirement,
            plan_file=plan_file,
            max_repair_attempts_per_task=max_repair_attempts_per_task,
            resume_run_id=resume_run_id,
            resume_latest=resume_latest,
        )
        logger = JsonlLogger(self.log_dir, record.run_id)
        logger.emit(
            "run_started",
            mode="run-plan",
            repo_path=str(repo_path),
            plan_file=str(plan_file),
            resumed=bool(resume_run_id or resume_latest),
        )

        task_graph = load_task_graph(plan_file)
        validate_task_graph(task_graph)
        checkpoint_payload = record.notes.get("checkpoint") or {}
        if checkpoint_payload:
            if isinstance(checkpoint_payload, dict) and (
                "signature" in checkpoint_payload or "hash" in checkpoint_payload
            ):
                if not verify_checkpoint_payload(checkpoint_payload, keyring=self.checkpoint_keyring):
                    forensic = checkpoint_forensics(checkpoint_payload, keyring=self.checkpoint_keyring)
                    logger.emit(
                        "checkpoint_integrity_failed",
                        expected_hash=forensic.get("expected_hash", ""),
                        actual_hash=forensic.get("actual_hash", ""),
                        expected_signature=forensic.get("expected_signature", ""),
                        actual_signature=forensic.get("actual_signature", ""),
                    )
                    self.state_store.transition(record, LifecycleState.BLOCKED)
                    record.notes["integrity_forensics"] = forensic
                    self.state_store.save(record)
                    return render_integrity_forensics_report(
                        run_id=record.run_id,
                        plan_file=plan_file,
                        envelope_type=str(forensic.get("envelope_type", "")),
                        algorithm=str(forensic.get("algorithm", "")),
                        signature_version=str(forensic.get("signature_version", "")),
                        key_id=str(forensic.get("key_id", "")),
                        resolved_key_id=str(forensic.get("resolved_key_id", "")),
                        active_key_id=str(forensic.get("active_key_id", "")),
                        expected_hash=str(forensic.get("expected_hash", "")),
                        actual_hash=str(forensic.get("actual_hash", "")),
                        expected_signature=str(forensic.get("expected_signature", "")),
                        actual_signature=str(forensic.get("actual_signature", "")),
                        task_count=int(forensic.get("task_count", 0) or 0),
                        task_ids=list(forensic.get("task_ids", [])),
                    )
                checkpoint_data = extract_checkpoint_data(checkpoint_payload)
            else:
                checkpoint_data = checkpoint_payload

            apply_task_graph_checkpoint(task_graph, checkpoint_data)
            logger.emit(
                "checkpoint_loaded",
                completed=sum(1 for t in task_graph.tasks if t.status == TaskStatus.COMPLETED),
                integrity="verified"
                if isinstance(checkpoint_payload, dict)
                and ("signature" in checkpoint_payload or "hash" in checkpoint_payload)
                else "legacy",
            )

        retry_candidates = [
            self._build_retry_risk(task)
            for task in task_graph.tasks
            if task.status != TaskStatus.COMPLETED
        ]

        blocked_by_risk = [item for item in retry_candidates if int(item["risk_score"]) > resume_max_risk]

        if resume_dry_run:
            logger.emit("resume_dry_run", run_id=record.run_id)
            return render_resume_dry_run_report(
                run_id=record.run_id,
                plan_file=plan_file,
                completed=[task.task_id for task in task_graph.tasks if task.status == TaskStatus.COMPLETED],
                to_retry=retry_candidates,
                resume_max_risk=resume_max_risk,
                blocked_by_risk=blocked_by_risk,
            )

        if is_resume and blocked_by_risk:
            logger.emit("resume_policy_blocked", run_id=record.run_id, resume_max_risk=resume_max_risk, blocked=len(blocked_by_risk))
            self.state_store.transition(record, LifecycleState.BLOCKED)
            record.notes["resume_policy_block"] = {
                "resume_max_risk": resume_max_risk,
                "blocked": blocked_by_risk,
            }
            self.state_store.save(record)
            return render_resume_policy_block_report(
                run_id=record.run_id,
                plan_file=plan_file,
                resume_max_risk=resume_max_risk,
                blocked_items=blocked_by_risk,
            )

        self.state_store.transition(record, LifecycleState.EXECUTING)
        logger.emit("state_transition", state=record.state.value)

        approval_policy = ApprovalPolicy(
            require_approval=require_approval,
            approved_actions=set(approved_actions or []),
            audit_path=self.log_dir / f"{record.run_id}.audit.jsonl",
        )
        write_scope_roots = [Path(path).resolve() for path in (scoped_write_paths or [str(repo_path)])]
        sandbox_policy = SandboxPolicy(
            profile=sandbox_profile,
            require_allowlist=True,
            scoped_write_paths=write_scope_roots,
            approval_policy=approval_policy,
        )

        def _on_event(payload: dict[str, Any]) -> None:
            logger.emit("task_event", **payload)
            record.notes["checkpoint"] = wrap_checkpoint_payload(
                snapshot_task_graph(task_graph),
                key=self.checkpoint_hmac_key,
                key_id=self.active_key_id,
                signature_version="v2",
            )
            self.state_store.save(record)

        execution_results = execute_task_graph(
            graph=task_graph,
            repo_path=repo_path,
            max_repair_attempts_per_task=max_repair_attempts_per_task,
            sandbox_policy=sandbox_policy,
            on_event=_on_event,
        )

        if not execution_results:
            execution_results = [
                self._final_result_from_task(task)
                for task in task_graph.tasks
                if task.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.BLOCKED}
            ]

        any_failed = any(item.status in {TaskStatus.FAILED, TaskStatus.BLOCKED} for item in execution_results)
        validation_result: ValidationPipelineResult | None = None
        if run_validation_pipeline and not any_failed:
            self.state_store.transition(record, LifecycleState.VALIDATING)
            logger.emit("state_transition", state=record.state.value)
            validation_result = run_staged_validation(
                repo_path=repo_path,
                policy=sandbox_policy,
                max_retries_per_stage=validation_retries_per_stage,
            )
            logger.emit(
                "validation_completed",
                overall_passed=validation_result.overall_passed,
                stages=[
                    {
                        "stage": stage.stage,
                        "passed": stage.passed,
                        "attempts": stage.attempts,
                        "skipped": stage.skipped,
                    }
                    for stage in validation_result.stages
                ],
            )
            if not validation_result.overall_passed:
                any_failed = True

        target_state = LifecycleState.BLOCKED if any_failed else LifecycleState.COMPLETED
        self.state_store.transition(record, target_state)
        record.notes = {
            "mode": "run-plan",
            "plan_file": str(plan_file),
            "max_repair_attempts_per_task": max_repair_attempts_per_task,
            "sandbox_profile": sandbox_profile,
            "scoped_write_paths": [str(path) for path in write_scope_roots],
            "require_approval": require_approval,
            "approved_actions": sorted(list(approval_policy.approved_actions)),
            "run_validation_pipeline": run_validation_pipeline,
            "validation_retries_per_stage": validation_retries_per_stage,
            "validation": [
                {
                    "stage": stage.stage,
                    "command": stage.command,
                    "passed": stage.passed,
                    "attempts": stage.attempts,
                    "exit_code": stage.exit_code,
                    "skipped": stage.skipped,
                    "skip_reason": stage.skip_reason,
                }
                for stage in (validation_result.stages if validation_result else [])
            ],
            "results": [asdict(item) for item in execution_results],
            "checkpoint": wrap_checkpoint_payload(
                snapshot_task_graph(task_graph),
                key=self.checkpoint_hmac_key,
                key_id=self.active_key_id,
                signature_version="v2",
            ),
        }
        self.state_store.save(record)
        logger.emit("run_completed", mode="run-plan", state=record.state.value)

        return render_task_execution_report(
            plan_file=plan_file,
            max_repair_attempts_per_task=max_repair_attempts_per_task,
            results=execution_results,
            validation_result=validation_result,
            audit_log_path=self.log_dir / f"{record.run_id}.audit.jsonl",
        )

    def _resolve_run_record(
        self,
        repo_path: Path,
        requirement: str,
        plan_file: Path,
        max_repair_attempts_per_task: int,
        resume_run_id: str | None,
        resume_latest: bool,
    ) -> AgentRunRecord:
        if resume_run_id or resume_latest:
            record = self.state_store.load(resume_run_id) if resume_run_id else self.state_store.latest_run()
            if record is None:
                raise ValueError("No previous run found to resume")
            if Path(record.repo_path).resolve() != repo_path.resolve():
                raise ValueError("Resume run repo path does not match current --repo")
            if str(record.notes.get("plan_file", "")) != str(plan_file):
                raise ValueError("Resume run plan file does not match current --plan-file")
            if record.state == LifecycleState.COMPLETED:
                raise ValueError("Run is already COMPLETED and cannot be resumed")
            return record

        run_id = str(uuid.uuid4())
        record = AgentRunRecord(
            run_id=run_id,
            requirement=requirement,
            state=LifecycleState.PLANNING,
            repo_path=str(repo_path),
            notes={
                "mode": "run-plan",
                "plan_file": str(plan_file),
                "max_repair_attempts_per_task": max_repair_attempts_per_task,
                "checkpoint": wrap_checkpoint_payload(
                    {},
                    key=self.checkpoint_hmac_key,
                    key_id=self.active_key_id,
                    signature_version="v2",
                ),
            },
        )
        self.state_store.save(record)
        return record

    def _final_result_from_task(self, task) -> TaskExecutionResult:
        return TaskExecutionResult(
            task_id=task.task_id,
            status=task.status,
            attempts=task.attempts,
            repair_attempts=task.repair_attempts,
            failure_type=task.failure_type,
            message="Recovered from checkpoint",
        )

    def _build_retry_risk(self, task) -> dict[str, str | int]:
        score = 1
        reasons: list[str] = ["Pending retry"]

        if task.failure_type is not None:
            score += 2
            reasons.append(f"Previous failure: {task.failure_type.value}")
        if task.attempts > 0:
            score += 1
            reasons.append(f"Prior attempts: {task.attempts}")
        if task.repair_attempts > 0:
            score += 1
            reasons.append(f"Repair attempts: {task.repair_attempts}")
        if task.dependencies:
            score += 1
            reasons.append(f"Depends on {len(task.dependencies)} task(s)")

        if score > 5:
            score = 5

        if score <= 2:
            level = "LOW"
        elif score <= 4:
            level = "MEDIUM"
        else:
            level = "HIGH"

        return {
            "task_id": task.task_id,
            "risk_score": score,
            "risk_level": level,
            "reason": "; ".join(reasons),
            "recommendation": self._suggest_repair_class(task),
        }

    def _suggest_repair_class(self, task) -> str:
        if task.failure_type == FailureType.SYNTAX_ERROR:
            return "Syntax fix class: run formatter/linter and patch compile errors"
        if task.failure_type == FailureType.IMPORT_ERROR:
            return "Import fix class: validate module path and package installation"
        if task.failure_type == FailureType.DEPENDENCY_ERROR:
            return "Dependency fix class: install/restore dependencies and lock versions"
        if task.failure_type == FailureType.TYPE_ERROR:
            return "Type fix class: run type checker and resolve mismatched signatures"
        if task.failure_type == FailureType.TEST_FAILURE:
            return "Test fix class: run failing tests only and patch assertion/root cause"
        if task.failure_type == FailureType.BUILD_FAILURE:
            return "Build fix class: run clean build and resolve compiler/build output"
        if task.failure_type == FailureType.CONFIGURATION_ERROR:
            return "Config fix class: validate env vars, secrets, and runtime config"
        if task.failure_type == FailureType.ENVIRONMENT_ERROR:
            return "Environment fix class: verify interpreter/tool availability and PATH"
        if task.failure_type == FailureType.TIMEOUT:
            return "Timeout fix class: increase timeout or split/batch heavy operations"

        command = (task.command or "").lower()
        if "pytest" in command:
            return "Test fix class: inspect failing tests and rerun targeted test cases"
        if "mvn" in command or "gradle" in command:
            return "Build fix class: run clean build lifecycle and inspect dependency tree"
        if "npm" in command or "yarn" in command:
            return "Node fix class: reinstall dependencies and rerun with verbose output"
        if "python" in command:
            return "Python fix class: rerun with verbose traceback and apply minimal patch"
        return "Generic fix class: rerun with verbose logging and apply minimal root-cause repair"
