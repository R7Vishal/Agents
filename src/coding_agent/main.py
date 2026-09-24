from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import CodingAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Autonomous Coding Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    first_run = sub.add_parser(
        "first-run",
        help="Repository discovery and baseline assessment only",
    )
    first_run.add_argument("--repo", required=True, help="Target repository path")
    first_run.add_argument(
        "--requirement",
        default="Perform first-run repository discovery and baseline assessment.",
        help="Requirement string for this run",
    )
    first_run.add_argument(
        "--requirement-file",
        default="",
        help="Path to a text file containing requirement/prompt content",
    )
    first_run.add_argument(
        "--run-baseline",
        action="store_true",
        help="Execute discovered baseline checks",
    )
    first_run.add_argument("--output", default="", help="Optional markdown output path")

    run_plan = sub.add_parser(
        "run-plan",
        help="Execute controlled task graph with validation and repair budget",
    )
    run_plan.add_argument("--repo", required=True, help="Target repository path")
    run_plan.add_argument("--plan-file", required=True, help="JSON task graph file")
    run_plan.add_argument(
        "--requirement",
        default="Execute controlled task plan.",
        help="Requirement string for this run",
    )
    run_plan.add_argument(
        "--requirement-file",
        default="",
        help="Path to a text file containing requirement/prompt content",
    )
    run_plan.add_argument(
        "--max-repair-attempts-per-task",
        type=int,
        default=2,
        help="Maximum repair attempts allowed for each task",
    )
    run_plan.add_argument(
        "--sandbox-profile",
        choices=["local", "container"],
        default="local",
        help="Execution profile for command sandboxing",
    )
    run_plan.add_argument(
        "--scoped-write-path",
        action="append",
        default=[],
        help="Allowed write root path (repeat flag for multiple paths)",
    )
    run_plan.add_argument(
        "--require-approval",
        action="store_true",
        help="Require explicit approval for high-impact actions",
    )
    run_plan.add_argument(
        "--approved-action",
        action="append",
        default=[],
        help="Approved high-impact action key (repeat flag for multiple values)",
    )
    run_plan.add_argument(
        "--disable-validation-pipeline",
        action="store_true",
        help="Disable staged post-execution validation gates",
    )
    run_plan.add_argument(
        "--validation-retries-per-stage",
        type=int,
        default=1,
        help="Retry count for transient staged validation failures",
    )
    run_plan.add_argument(
        "--resume-run-id",
        default="",
        help="Resume an existing run by run ID",
    )
    run_plan.add_argument(
        "--resume-latest",
        action="store_true",
        help="Resume the latest run from .agent_state",
    )
    run_plan.add_argument(
        "--resume-dry-run",
        action="store_true",
        help="Preview retry queue from checkpoint without executing tasks",
    )
    run_plan.add_argument(
        "--resume-max-risk",
        type=int,
        default=5,
        help="Maximum allowed retry risk score (1-5) during resume execution",
    )
    run_plan.add_argument("--output", default="", help="Optional markdown output path")

    rotate_key = sub.add_parser(
        "rotate-key",
        help="Rotate checkpoint signing key while preserving verification compatibility",
    )
    rotate_key.add_argument("--output", default="", help="Optional markdown output path")

    run_config = sub.add_parser(
        "run-config",
        help="Run agent using workspace JSON configuration (VS Code friendly)",
    )
    run_config.add_argument(
        "--config",
        default=".vscode/coding-agent.json",
        help="Path to configuration JSON file",
    )
    run_config.add_argument(
        "--mode",
        choices=["first-run", "run-plan", "rotate-key"],
        default="",
        help="Optional override for configured mode",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    agent = CodingAgent(project_root)

    if args.command == "first-run":
        requirement = _resolve_requirement(
            requirement=args.requirement,
            requirement_file=args.requirement_file,
            project_root=project_root,
        )
        report = agent.first_run_assessment(
            repo_path=Path(args.repo).resolve(),
            requirement=requirement,
            run_baseline=args.run_baseline,
        )
        _write_or_print_report(report=report, output=args.output, project_root=project_root)

    if args.command == "run-plan":
        requirement = _resolve_requirement(
            requirement=args.requirement,
            requirement_file=args.requirement_file,
            project_root=project_root,
        )
        report = agent.run_controlled_plan(
            repo_path=Path(args.repo).resolve(),
            requirement=requirement,
            plan_file=Path(args.plan_file).resolve(),
            max_repair_attempts_per_task=args.max_repair_attempts_per_task,
            sandbox_profile=args.sandbox_profile,
            scoped_write_paths=args.scoped_write_path,
            require_approval=args.require_approval,
            approved_actions=args.approved_action,
            run_validation_pipeline=not args.disable_validation_pipeline,
            validation_retries_per_stage=args.validation_retries_per_stage,
            resume_run_id=args.resume_run_id or None,
            resume_latest=args.resume_latest,
            resume_dry_run=args.resume_dry_run,
            resume_max_risk=args.resume_max_risk,
        )
        _write_or_print_report(report=report, output=args.output, project_root=project_root)

    if args.command == "rotate-key":
        result = agent.rotate_checkpoint_key()
        report = "\n".join(
            [
                "## KEY ROTATION",
                f"- New key ID: {result['new_key_id']}",
                f"- Total keys in keyring: {result['total_keys']}",
                "- Status: SUCCESS",
            ]
        )
        _write_or_print_report(report=report, output=args.output, project_root=project_root)

    if args.command == "run-config":
        config_path = Path(args.config)
        if not config_path.is_absolute():
            config_path = project_root / config_path
        config = json.loads(config_path.read_text(encoding="utf-8"))

        configured_mode = str(config.get("mode", "first-run")).strip()
        mode = args.mode or configured_mode

        if mode == "first-run":
            repo = Path(str(config.get("repo", "."))).resolve()
            requirement = _resolve_requirement(
                requirement=str(config.get("requirement", "Perform first-run repository discovery and baseline assessment.")),
                requirement_file=str(config.get("requirement_file", "")),
                project_root=project_root,
            )
            run_baseline = bool(config.get("run_baseline", False))
            output = str(config.get("output", ""))
            report = agent.first_run_assessment(
                repo_path=repo,
                requirement=requirement,
                run_baseline=run_baseline,
            )
            _write_or_print_report(report=report, output=output, project_root=project_root)

        if mode == "run-plan":
            repo = Path(str(config.get("repo", "."))).resolve()
            plan_file_value = str(config.get("plan_file", "")).strip()
            if not plan_file_value:
                raise ValueError("plan_file is required in config for run-plan mode")
            plan_file = Path(plan_file_value)
            if not plan_file.is_absolute():
                plan_file = (project_root / plan_file).resolve()

            requirement = _resolve_requirement(
                requirement=str(config.get("requirement", "Execute controlled task plan.")),
                requirement_file=str(config.get("requirement_file", "")),
                project_root=project_root,
            )

            report = agent.run_controlled_plan(
                repo_path=repo,
                requirement=requirement,
                plan_file=plan_file,
                max_repair_attempts_per_task=int(config.get("max_repair_attempts_per_task", 2) or 2),
                sandbox_profile=str(config.get("sandbox_profile", "local") or "local"),
                scoped_write_paths=list(config.get("scoped_write_paths", []) or []),
                require_approval=bool(config.get("require_approval", False)),
                approved_actions=list(config.get("approved_actions", []) or []),
                run_validation_pipeline=bool(config.get("run_validation_pipeline", False)),
                validation_retries_per_stage=int(config.get("validation_retries_per_stage", 1) or 1),
                resume_run_id=str(config.get("resume_run_id", "")).strip() or None,
                resume_latest=bool(config.get("resume_latest", False)),
                resume_dry_run=bool(config.get("resume_dry_run", False)),
                resume_max_risk=int(config.get("resume_max_risk", 5) or 5),
            )

            output = str(config.get("output", ""))
            _write_or_print_report(report=report, output=output, project_root=project_root)

        if mode not in {"first-run", "run-plan", "rotate-key"}:
            raise ValueError(f"Unsupported mode in config: {mode}")

        if mode == "rotate-key":
            result = agent.rotate_checkpoint_key()
            report = "\n".join(
                [
                    "## KEY ROTATION",
                    f"- New key ID: {result['new_key_id']}",
                    f"- Total keys in keyring: {result['total_keys']}",
                    "- Status: SUCCESS",
                ]
            )
            output = str(config.get("output", ""))
            _write_or_print_report(report=report, output=output, project_root=project_root)


def _write_or_print_report(report: str, output: str, project_root: Path) -> None:
    if output:
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = project_root / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report written to: {output_path}")
    else:
        print(report)


def _resolve_requirement(requirement: str, requirement_file: str, project_root: Path) -> str:
    if not requirement_file:
        return requirement
    requirement_path = Path(requirement_file)
    if not requirement_path.is_absolute():
        requirement_path = project_root / requirement_path
    return requirement_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    main()
