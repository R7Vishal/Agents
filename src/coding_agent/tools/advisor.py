from __future__ import annotations

from typing import Any

from .capabilities import CapabilityManager


class SelfImprovementAdvisor:
    def __init__(self, capability_manager: CapabilityManager) -> None:
        self.capability_manager = capability_manager

    def analyze(self) -> dict[str, Any]:
        capabilities = self.capability_manager.as_dict()

        missing: list[str] = []
        for section, entries in capabilities.items():
            for entry in entries:
                if not entry["available"]:
                    missing.append(f"{section}:{entry['name']}")

        recommendations = [
            {
                "priority": "High",
                "area": "LLM",
                "benefit": "Natural language planning/execution quality",
                "action": "Configure and tune provider-backed reasoning gateway using environment policy and telemetry",
            },
            {
                "priority": "High",
                "area": "Memory",
                "benefit": "Better multi-session continuity",
                "action": "Extend persistent semantic index into richer project memory with summaries and embeddings",
            },
            {
                "priority": "Medium",
                "area": "UI",
                "benefit": "Better transparency",
                "action": "Show step-level tool call payloads and per-step validation in activity panel",
            },
            {
                "priority": "Medium",
                "area": "Security",
                "benefit": "Safer automation",
                "action": "Add explicit approval tokens for destructive git and delete operations",
            },
        ]

        return {
            "current_capabilities": capabilities,
            "missing_capabilities": missing,
            "potential_bottlenecks": [
                "Provider-backed LLM is policy-driven and may be disabled in current environment",
                "Autonomous repair currently applies bounded heuristics and command retries",
                "UI timeline/validation views are concise and can be extended with richer step telemetry",
            ],
            "recommended_improvements": recommendations,
        }

    def render_markdown(self) -> str:
        report = self.analyze()
        lines: list[str] = ["AGENT IMPROVEMENT ADVISOR", ""]
        lines.append("Current capabilities are derived from registered tools.")
        lines.append(f"Missing capabilities detected: {len(report['missing_capabilities'])}")
        lines.append("")
        lines.append("Potential bottlenecks")
        for item in report["potential_bottlenecks"]:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Recommended improvements")
        for item in report["recommended_improvements"]:
            lines.append(f"- [{item['priority']}] {item['area']}: {item['action']} (Benefit: {item['benefit']})")
        lines.append("")
        lines.append("Note: Advisor does not auto-modify the agent; it only recommends next actions.")
        return "\n".join(lines)
