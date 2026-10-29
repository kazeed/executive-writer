"""Deterministic plan validation. This module authorizes but never executes work."""

from dataclasses import dataclass

from pydantic import ValidationError

from executive_writer.workflow.errors import PlanErrorCode, PlanIssue, ValidationLayer
from executive_writer.workflow.models import DocumentBrief
from executive_writer.workflow.planning import (
    PlanSnapshot,
    ProposedPlan,
)
from executive_writer.workflow.policies import ExecutionPolicy, Permissions
from executive_writer.workflow.stages import FINAL_STAGES, INITIAL_STAGES, OPTIONAL_STAGES, Stage


@dataclass(frozen=True, slots=True, init=False)
class ApprovedPlan:
    """Only issued by validation. A snapshot/proposal is never an approval.

    This boundary prevents accidental construction, not malicious Python code
    executing inside the application process.
    """

    snapshot: PlanSnapshot

    def __new__(cls) -> "ApprovedPlan":
        raise TypeError("Use PlanValidator.validate to obtain an ApprovedPlan")


def _issue_approval(snapshot: PlanSnapshot) -> "ApprovedPlan":
    approved = object.__new__(ApprovedPlan)
    object.__setattr__(approved, "snapshot", snapshot)
    return approved


@dataclass(frozen=True, slots=True)
class PlanValidationResult:
    approved_plan: ApprovedPlan | None
    issues: tuple[PlanIssue, ...]


class PlanValidator:
    def validate_json(
        self, proposal_json: str, brief: DocumentBrief, policy: ExecutionPolicy
    ) -> PlanValidationResult:
        try:
            proposal = ProposedPlan.model_validate_json(proposal_json)
        except ValidationError as error:
            return self._schema_failure(error)
        return self.validate(proposal, brief, policy)

    def validate(
        self, proposal: object, brief: DocumentBrief, policy: ExecutionPolicy
    ) -> PlanValidationResult:
        # Revalidate even typed input: Pydantic's unchecked copy/construct APIs do
        # not establish trust. Trusted brief/policy are validated separately.
        brief = DocumentBrief.model_validate(brief)
        policy = ExecutionPolicy.model_validate(policy)
        try:
            parsed = ProposedPlan.model_validate(proposal)
        except ValidationError as error:
            return self._schema_failure(error)

        issues: list[PlanIssue] = []

        def reject(layer: ValidationLayer, code: PlanErrorCode, field: str, reason: str) -> None:
            issues.append(PlanIssue(layer=layer, code=code, field=field, reason=reason))

        selected: list[Stage] = []
        for index, name in enumerate(parsed.optional_stages):
            field = f"optional_stages.{index}"
            try:
                stage = Stage(name)
            except ValueError:
                reject(
                    ValidationLayer.SEMANTIC,
                    PlanErrorCode.UNKNOWN_STAGE,
                    field,
                    "Select a stage from RESEARCH, ANALYZE, OUTLINE.",
                )
                continue
            if stage not in OPTIONAL_STAGES:
                reject(
                    ValidationLayer.SEMANTIC,
                    PlanErrorCode.INVALID_SELECTION,
                    field,
                    "Only optional stages may be proposed; revision is review-controlled.",
                )
            if stage in selected:
                reject(
                    ValidationLayer.SEMANTIC,
                    PlanErrorCode.DUPLICATE_STAGE,
                    field,
                    "Select each optional stage at most once.",
                )
            selected.append(stage)

        optional = tuple(stage for stage in selected if stage in OPTIONAL_STAGES)
        canonical = tuple(stage for stage in OPTIONAL_STAGES if stage in optional)
        if optional != canonical:
            reject(
                ValidationLayer.SEMANTIC,
                PlanErrorCode.INVALID_ORDER,
                "optional_stages",
                "Order optional stages as RESEARCH, ANALYZE, OUTLINE without duplicates.",
            )

        stages = INITIAL_STAGES + canonical + FINAL_STAGES
        for index, dependency in enumerate(parsed.dependencies):
            if (
                dependency.stage not in stages
                or dependency.requires not in stages
                or stages.index(dependency.requires) >= stages.index(dependency.stage)
            ):
                reject(
                    ValidationLayer.SEMANTIC,
                    PlanErrorCode.INVALID_DEPENDENCY,
                    f"dependencies.{index}",
                    "A dependency must be an included stage preceding its consumer.",
                )

        if Stage.RESEARCH in selected:
            if not (brief.permissions.external_research and policy.permissions.external_research):
                reject(
                    ValidationLayer.AUTHORIZATION,
                    PlanErrorCode.RESEARCH_FORBIDDEN,
                    "optional_stages",
                    "Research requires both brief and policy permission.",
                )
            if policy.limits.max_research_rounds == 0:
                reject(
                    ValidationLayer.AUTHORIZATION,
                    PlanErrorCode.LIMIT_EXCEEDED,
                    "optional_stages",
                    "Research requires at least one permitted research round.",
                )
            if parsed.research_plan is None or not parsed.research_plan.questions:
                reject(
                    ValidationLayer.SEMANTIC,
                    PlanErrorCode.INVALID_DEPENDENCY,
                    "research_plan",
                    "Selected research requires a plan with research questions.",
                )

        if parsed.requested_limits is not None:
            for field in type(policy.limits).model_fields:
                if field == "schema_version":
                    continue
                requested: object = getattr(parsed.requested_limits, field)
                maximum: object = getattr(policy.limits, field)
                if isinstance(requested, int) and isinstance(maximum, int) and requested > maximum:
                    reject(
                        ValidationLayer.AUTHORIZATION,
                        PlanErrorCode.LIMIT_EXCEEDED,
                        f"requested_limits.{field}",
                        "Requested limit exceeds trusted policy.",
                    )

        if issues:
            return PlanValidationResult(None, tuple(issues))
        # Smaller requested ceilings constrain this approval; no output can raise
        # the trusted ceilings or change the supplied brief.
        effective_policy = ExecutionPolicy(
            permissions=Permissions(
                external_research=(
                    brief.permissions.external_research and policy.permissions.external_research
                )
            ),
            limits=parsed.requested_limits or policy.limits,
        )
        if Stage.RESEARCH in canonical and effective_policy.limits.max_research_rounds == 0:
            return PlanValidationResult(
                None,
                (
                    PlanIssue(
                        layer=ValidationLayer.AUTHORIZATION,
                        code=PlanErrorCode.LIMIT_EXCEEDED,
                        field="requested_limits.max_research_rounds",
                        reason="Selected research requires at least one permitted research round.",
                    ),
                ),
            )
        snapshot = PlanSnapshot(
            brief=brief, policy=effective_policy, proposal=parsed, stages=stages
        )
        return PlanValidationResult(_issue_approval(snapshot), ())

    @staticmethod
    def _schema_failure(error: ValidationError) -> PlanValidationResult:
        # Never echo planner content, unknown field names, or custom exception
        # messages into feedback. Locations use only known fields and indices.
        known_fields = set(ProposedPlan.model_fields)
        issues = tuple(
            PlanIssue(
                layer=ValidationLayer.SCHEMA,
                code=PlanErrorCode.INVALID_SCHEMA,
                field=".".join(
                    str(part) if isinstance(part, int) or part in known_fields else "field"
                    for part in detail["loc"]
                )
                or "proposal",
                reason="Invalid proposal schema; use declared fields and bounded strict types.",
            )
            for detail in error.errors(include_input=False, include_context=False)
        )
        return PlanValidationResult(None, issues)
