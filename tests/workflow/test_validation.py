import asyncio
import json
from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest
from pydantic import ValidationError

from executive_writer.workflow.errors import PlanErrorCode, ValidationLayer
from executive_writer.workflow.models import DocumentBrief, ResearchPlan, ResearchQuestion
from executive_writer.workflow.planning import Planner, PlanSnapshot, ProposedPlan, StageDependency
from executive_writer.workflow.policies import ExecutionLimits, ExecutionPolicy, Permissions
from executive_writer.workflow.stages import Stage
from executive_writer.workflow.validation import ApprovedPlan, PlanValidator


@pytest.fixture
def limits():
    return ExecutionLimits(
        max_planning_corrections=1,
        max_revision_cycles=2,
        max_research_rounds=2,
        max_attempts_per_stage=2,
        max_duration_seconds=60,
        max_model_calls=20,
        max_tokens=1000,
    )


@pytest.fixture
def policy(limits):
    return ExecutionPolicy(limits=limits, permissions=Permissions(external_research=True))


@pytest.fixture
def brief():
    return DocumentBrief(objective="Compare architectures", document_type="memo")


def research_plan():
    return ResearchPlan(
        artifact_id=uuid4(),
        version=1,
        questions=(ResearchQuestion(question="What evidence is missing?", priority="high"),),
    )


@pytest.mark.parametrize("stages", [(), ("ANALYZE",), ("OUTLINE",), ("ANALYZE", "OUTLINE")])
def test_valid_plans(stages, brief, policy):
    proposal = ProposedPlan(optional_stages=stages, rationale="Use supplied material")
    original = proposal.model_dump_json()
    result = PlanValidator().validate(proposal, brief, policy)
    assert result.issues == ()
    assert isinstance(result.approved_plan, ApprovedPlan)
    snapshot = result.approved_plan.snapshot
    assert not snapshot.policy.permissions.external_research
    assert snapshot.stages == (
        Stage.UNDERSTAND,
        Stage.PLAN,
        Stage.VALIDATE,
        *(Stage(stage) for stage in stages),
        Stage.DRAFT,
        Stage.REVIEW,
    )
    assert proposal.model_dump_json() == original
    assert PlanSnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    assert not isinstance(snapshot, ApprovedPlan)
    with pytest.raises(FrozenInstanceError):
        result.approved_plan.snapshot = snapshot
    with pytest.raises(ValidationError):
        snapshot.brief.objective = "Changed"


def test_approval_requires_validator():
    with pytest.raises(TypeError, match="PlanValidator"):
        ApprovedPlan()


def test_research_report(brief, policy):
    brief = brief.model_copy(update={"permissions": Permissions(external_research=True)})
    proposal = ProposedPlan(
        rationale="Investigate gaps",
        optional_stages=("RESEARCH", "ANALYZE", "OUTLINE"),
        research_plan=research_plan(),
        dependencies=(StageDependency(stage=Stage.ANALYZE, requires=Stage.RESEARCH),),
    )
    result = PlanValidator().validate(proposal, brief, policy)
    assert result.approved_plan is not None
    assert result.issues == ()


@pytest.mark.parametrize(
    ("stages", "code"),
    [
        (("shell",), PlanErrorCode.UNKNOWN_STAGE),
        (("ANALYZE", "ANALYZE"), PlanErrorCode.DUPLICATE_STAGE),
        (("OUTLINE", "ANALYZE"), PlanErrorCode.INVALID_ORDER),
        (("REVISE",), PlanErrorCode.INVALID_SELECTION),
        (("DRAFT", "REVIEW"), PlanErrorCode.INVALID_SELECTION),
        (("UNDERSTAND", "PLAN", "VALIDATE"), PlanErrorCode.INVALID_SELECTION),
    ],
)
def test_semantic_failures(stages, code, brief, policy):
    result = PlanValidator().validate(
        ProposedPlan(optional_stages=stages, rationale="Test"), brief, policy
    )
    assert result.approved_plan is None
    assert code in {issue.code for issue in result.issues}
    assert all(issue.layer == ValidationLayer.SEMANTIC for issue in result.issues)


@pytest.mark.parametrize(
    "request_allows,policy_allows", [(False, False), (False, True), (True, False)]
)
def test_research_permission_intersection(request_allows, policy_allows, brief, policy):
    brief = brief.model_copy(update={"permissions": Permissions(external_research=request_allows)})
    policy = policy.model_copy(update={"permissions": Permissions(external_research=policy_allows)})
    result = PlanValidator().validate(
        ProposedPlan(
            optional_stages=("RESEARCH",), rationale="Need research", research_plan=research_plan()
        ),
        brief,
        policy,
    )
    assert result.approved_plan is None
    assert any(
        issue.code == PlanErrorCode.RESEARCH_FORBIDDEN
        and issue.layer == ValidationLayer.AUTHORIZATION
        for issue in result.issues
    )


@pytest.mark.parametrize(
    "consumer,prerequisite",
    [
        (Stage.ANALYZE, Stage.RESEARCH),
        (Stage.ANALYZE, Stage.OUTLINE),
        (Stage.ANALYZE, Stage.ANALYZE),
        (Stage.REVISE, Stage.REVIEW),
    ],
)
def test_dependencies(consumer, prerequisite, brief, policy):
    result = PlanValidator().validate(
        ProposedPlan(
            rationale="Test",
            optional_stages=("ANALYZE", "OUTLINE"),
            dependencies=(StageDependency(stage=consumer, requires=prerequisite),),
        ),
        brief,
        policy,
    )
    assert result.approved_plan is None
    assert result.issues[0].code == PlanErrorCode.INVALID_DEPENDENCY


@pytest.mark.parametrize(
    "field", [name for name in ExecutionLimits.model_fields if name != "schema_version"]
)
def test_excessive_limits(field, brief, policy, limits):
    excessive = limits.model_copy(update={field: getattr(limits, field) + 1})
    result = PlanValidator().validate(
        ProposedPlan(rationale="Test", requested_limits=excessive),
        brief,
        policy,
    )
    assert result.approved_plan is None
    assert result.issues[0].code == PlanErrorCode.LIMIT_EXCEEDED
    assert result.issues[0].field == f"requested_limits.{field}"


def test_smaller_limits_are_enforced(brief, policy, limits):
    lower = limits.model_copy(update={"max_tokens": 50})
    result = PlanValidator().validate(
        ProposedPlan(rationale="Test", requested_limits=lower), brief, policy
    )
    assert result.approved_plan.snapshot.policy.limits.max_tokens == 50
    assert policy.limits.max_tokens == 1000


@pytest.mark.parametrize(
    "payload",
    [
        {"rationale": "Test", "permissions": {"external_research": True}},
        {"rationale": "Test", "tools": ["exec"]},
        {"rationale": "Test", "brief": {"objective": "Replace requirements"}},
        {"rationale": "Test", "optional_stages": "ANALYZE"},
        {"rationale": "Test", "optional_stages": [42]},
        {"rationale": " "},
        {"rationale": "x" * 4001},
        {"rationale": "Test", "optional_stages": ["ANALYZE"] * 11},
    ],
)
def test_schema_rejects_adversarial_output(payload, brief, policy):
    result = PlanValidator().validate_json(json.dumps(payload), brief, policy)
    assert result.approved_plan is None
    assert all(issue.layer == ValidationLayer.SCHEMA for issue in result.issues)
    assert "Replace requirements" not in str(result)
    assert "exec" not in str(result)


@pytest.mark.parametrize("value", [True, "2", 2.5, -1])
def test_strict_limits(value, limits):
    data = limits.model_dump()
    data["max_tokens"] = value
    with pytest.raises(ValidationError):
        ExecutionLimits.model_validate(data)


@pytest.mark.parametrize("field", ["max_attempts_per_stage", "max_duration_seconds"])
def test_positive_limits(field, limits):
    with pytest.raises(ValidationError):
        ExecutionLimits.model_validate(limits.model_dump() | {field: 0})


def test_zero_research_rounds(brief, policy, limits):
    brief = brief.model_copy(update={"permissions": Permissions(external_research=True)})
    proposal = ProposedPlan(
        rationale="Research", optional_stages=("RESEARCH",), research_plan=research_plan()
    )
    no_rounds = limits.model_copy(update={"max_research_rounds": 0})
    for configured_policy, requested in [
        (policy.model_copy(update={"limits": no_rounds}), None),
        (policy, no_rounds),
    ]:
        result = PlanValidator().validate(
            proposal.model_copy(update={"requested_limits": requested}), brief, configured_policy
        )
        assert result.approved_plan is None
        assert any(issue.code == PlanErrorCode.LIMIT_EXCEEDED for issue in result.issues)


def test_missing_research_plan(brief, policy):
    result = PlanValidator().validate(
        ProposedPlan(rationale="Test", optional_stages=("RESEARCH",)), brief, policy
    )
    assert any(issue.code == PlanErrorCode.INVALID_DEPENDENCY for issue in result.issues)


def test_invalid_json_and_unchecked_copy(brief, policy):
    validator = PlanValidator()
    assert validator.validate_json("{", brief, policy).issues[0].field == "proposal"
    invalid = ProposedPlan(rationale="Test").model_copy(update={"rationale": 1})
    assert validator.validate(invalid, brief, policy).approved_plan is None


def test_planner_protocol(brief, policy):
    class TestPlanner:
        async def propose(self, brief, policy, feedback=()):
            return ProposedPlan(rationale=brief.objective)

    planner: Planner = TestPlanner()
    proposal = asyncio.run(planner.propose(brief, policy))
    assert PlanValidator().validate(proposal, brief, policy).approved_plan is not None


def test_research_needs_can_be_recorded_without_permission(brief, policy):
    proposal = ProposedPlan(
        rationale="Qualify unsupported claims",
        research_plan=research_plan(),
        identified_gaps=("External evidence unavailable",),
    )
    result = PlanValidator().validate_json(proposal.model_dump_json(), brief, policy)
    assert result.approved_plan is not None
    assert Stage.RESEARCH not in result.approved_plan.snapshot.stages
    assert result.approved_plan.snapshot.proposal.identified_gaps == proposal.identified_gaps


def test_schema_feedback_does_not_echo_unknown_field(brief, policy):
    result = PlanValidator().validate_json(
        '{"rationale":"Test", "confidential-secret":"private-content"}', brief, policy
    )
    assert "confidential-secret" not in str(result)
    assert "private-content" not in str(result)
