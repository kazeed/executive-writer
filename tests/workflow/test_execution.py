import asyncio
from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from executive_writer.workflow.errors import ErrorCode, PlanErrorCode
from executive_writer.workflow.executor import WorkflowExecutor
from executive_writer.workflow.failures import ComponentFailure, WorkflowCancelled
from executive_writer.workflow.fakes import FakePlanner, FakeStages
from executive_writer.workflow.models import (
    AnalysisResult,
    AttemptOutcome,
    Citation,
    DocumentBrief,
    DocumentConstraints,
    DocumentOutline,
    ExecutionResult,
    Lifecycle,
    OutlineSection,
    ReviewDecision,
    SourceReference,
)
from executive_writer.workflow.policies import ExecutionLimits, ExecutionPolicy, Permissions
from executive_writer.workflow.reporting import ModelUsage
from executive_writer.workflow.repository import InMemoryArtifactRepository
from executive_writer.workflow.stages import Stage


@pytest.fixture
def brief():
    return DocumentBrief(objective="Rewrite the supplied memo", document_type="memo")


@pytest.fixture
def policy():
    return ExecutionPolicy(
        permissions=Permissions(external_research=True),
        limits=ExecutionLimits(
            max_planning_corrections=1,
            max_revision_cycles=2,
            max_research_rounds=1,
            max_attempts_per_stage=2,
            max_duration_seconds=10,
            max_model_calls=20,
            max_tokens=200,
        ),
    )


def execute(brief, policy, planner=None, stages=None, components=None):
    return asyncio.run(
        WorkflowExecutor(
            planner or FakePlanner(),
            components or (stages or FakeStages()).components(),
        ).execute(brief, policy)
    )


def test_minimal_rewrite(brief, policy):
    result = execute(brief, policy)
    assert result.status == Lifecycle.COMPLETED
    assert result.mandatory_checks_passed
    assert result.latest_draft is not None
    assert [attempt.stage for attempt in result.attempts] == [
        Stage.UNDERSTAND,
        Stage.PLAN,
        Stage.VALIDATE,
        Stage.DRAFT,
        Stage.REVIEW,
    ]
    assert [record.payload.kind for record in result.artifacts] == [
        "document_draft",
        "review_result",
    ]
    assert result.usage.model_calls == 3
    assert result.usage.tokens == 30
    assert result.usage.contains_synthetic_usage
    assert result.usage.reporting_complete
    assert result.usage.revision_cycles == result.usage.research_rounds == 0
    assert result.lifecycle_history == (
        Lifecycle.CREATED,
        Lifecycle.PLANNING,
        Lifecycle.EXECUTING,
        Lifecycle.REVIEWING,
        Lifecycle.COMPLETED,
    )
    assert result.attempts[0].usage.model_calls == result.attempts[2].usage.model_calls == 0
    assert ExecutionResult.model_validate_json(result.model_dump_json()) == result


def test_analysis_only_optional_inputs(brief, policy):
    received = []

    class Observed(FakeStages):
        async def analyze(self, brief, evidence):
            assert evidence is None
            return await super().analyze(brief, evidence)

        async def draft(self, brief, evidence, analysis, outline):
            received.append((evidence, analysis, outline))
            return await super().draft(brief, evidence, analysis, outline)

    result = execute(brief, policy, FakePlanner(("ANALYZE",)), Observed())
    assert result.status == Lifecycle.COMPLETED
    assert received[0][0] is received[0][2] is None
    assert isinstance(received[0][1], AnalysisResult)
    assert [record.payload.kind for record in result.artifacts] == [
        "analysis_result",
        "document_draft",
        "review_result",
    ]


def test_research_path_provenance_and_immutability(brief, policy):
    brief = brief.model_copy(update={"permissions": Permissions(external_research=True)})
    result = execute(brief, policy, FakePlanner(("RESEARCH", "ANALYZE", "OUTLINE")))
    assert result.status == Lifecycle.COMPLETED
    assert result.usage.model_calls == 6
    assert result.usage.research_rounds == 1
    assert [attempt.stage for attempt in result.attempts] == [
        Stage.UNDERSTAND,
        Stage.PLAN,
        Stage.VALIDATE,
        Stage.RESEARCH,
        Stage.ANALYZE,
        Stage.OUTLINE,
        Stage.DRAFT,
        Stage.REVIEW,
    ]
    seen = set()
    for record in result.artifacts:
        assert record.payload.artifact_id not in seen
        assert record.payload.version == 1
        assert set(record.consumed_artifact_ids) <= seen
        seen.add(record.payload.artifact_id)
        producing = next(
            attempt
            for attempt in result.attempts
            if (attempt.stage, attempt.attempt_number)
            == (record.producer.stage, record.producer.attempt_number)
        )
        assert record.payload.artifact_id in producing.produced_artifact_ids
        assert producing.source_artifact_ids == record.consumed_artifact_ids
        with pytest.raises(ValidationError):
            record.payload.version = 99
    evidence = result.artifacts[1].payload.evidence
    assert all(item.source.kind == "synthetic" for item in evidence)
    assert any("synthetic" in limitation for limitation in result.limitations)


def test_forbidden_research_no_fallback(brief, policy):
    result = execute(brief, policy, FakePlanner(("RESEARCH",)))
    assert result.status == Lifecycle.FAILED
    assert result.error.code == ErrorCode.PLAN_VALIDATION_FAILED
    assert PlanErrorCode.RESEARCH_FORBIDDEN in {
        issue.code for issue in result.error.planning_issues
    }
    assert result.artifacts == ()
    assert result.usage.planning_corrections == 1
    assert [attempt.stage for attempt in result.attempts].count(Stage.PLAN) == 2
    assert not any(attempt.stage == Stage.DRAFT for attempt in result.attempts)


def test_plan_correction_receives_typed_feedback(brief, policy):
    feedbacks = []

    class Repairing(FakePlanner):
        async def propose(self, brief, policy, feedback=()):
            feedbacks.append(feedback)
            return await FakePlanner(() if feedback else ("REVISE",)).propose(
                brief, policy, feedback
            )

    result = execute(brief, policy, Repairing())
    assert result.status == Lifecycle.COMPLETED
    assert feedbacks[0] == ()
    assert feedbacks[1][0].code == PlanErrorCode.INVALID_SELECTION
    assert result.usage.model_calls == 4
    assert result.usage.planning_corrections == 1
    assert result.usage.operational_retries == 0
    assert [
        attempt.attempt_number for attempt in result.attempts if attempt.stage == Stage.PLAN
    ] == [1, 2]


def test_malformed_proposal_can_be_corrected(brief, policy):
    class Repairing(FakePlanner):
        async def propose(self, brief, policy, feedback=()):
            response = await super().propose(brief, policy, feedback)
            if not feedback:
                return response.model_copy(
                    update={"value": {"rationale": "Test", "tools": ["exec"]}}
                )
            return response

    assert execute(brief, policy, Repairing()).status == Lifecycle.COMPLETED


@pytest.mark.parametrize("allowed", [0, 1, 2])
def test_exact_correction_allowance(brief, policy, allowed):
    policy = policy.model_copy(
        update={
            "limits": policy.limits.model_copy(
                update={
                    "max_planning_corrections": allowed,
                }
            )
        }
    )
    result = execute(brief, policy, FakePlanner(("UNKNOWN",)))
    assert result.status == Lifecycle.FAILED
    assert result.error.code == ErrorCode.PLAN_VALIDATION_FAILED
    assert result.usage.planning_corrections == allowed
    assert result.usage.model_calls == allowed + 1


def test_rejected_review_is_incomplete_without_routing(brief, policy):
    result = execute(brief, policy, stages=FakeStages(decision=ReviewDecision.CHANGES_REQUIRED))
    assert result.status == Lifecycle.INCOMPLETE
    assert result.latest_draft is not None
    assert result.review.findings[0].severity == "CRITICAL"
    assert result.usage.revision_cycles == result.usage.research_rounds == 0
    assert not any(attempt.stage == Stage.REVISE for attempt in result.attempts)
    assert [attempt.stage for attempt in result.attempts].count(Stage.REVIEW) == 1


@pytest.mark.parametrize(
    "body,constraints,reason",
    [
        ("Too many words in this draft", DocumentConstraints(max_words=2), "word limit"),
        (
            "Decision is mentioned in prose",
            DocumentConstraints(required_sections=("Decision",)),
            "headings",
        ),
    ],
)
def test_accepted_review_cannot_bypass_checks(brief, policy, body, constraints, reason):
    brief = brief.model_copy(update={"constraints": constraints})
    result = execute(brief, policy, stages=FakeStages(body=body))
    assert result.status == Lifecycle.INCOMPLETE
    assert result.review.decision == ReviewDecision.ACCEPTED
    assert not result.mandatory_checks_passed
    assert any(reason in limitation for limitation in result.limitations)


def test_required_sections_success(brief, policy):
    brief = brief.model_copy(
        update={"constraints": DocumentConstraints(required_sections=("Decision",))}
    )
    assert execute(brief, policy).status == Lifecycle.COMPLETED


def test_unsupported_citation_is_visible_and_retains_draft(brief, policy):
    class Unsupported(FakeStages):
        async def draft(self, brief, evidence, analysis, outline):
            response = await super().draft(brief, evidence, analysis, outline)
            return response.model_copy(
                update={
                    "value": response.value.model_copy(
                        update={
                            "citations": (
                                Citation(
                                    claim_reference="Unsupported claim", evidence_id="missing"
                                ),
                            ),
                        }
                    )
                }
            )

    result = execute(brief, policy, stages=Unsupported())
    assert result.status == Lifecycle.INCOMPLETE
    assert result.latest_draft is not None
    assert any("unavailable evidence" in limitation for limitation in result.limitations)


@pytest.mark.parametrize(
    "field,limit,expected_stages",
    [
        ("max_model_calls", 0, []),
        ("max_model_calls", 1, [Stage.PLAN]),
        ("max_model_calls", 2, [Stage.PLAN, Stage.DRAFT]),
        ("max_tokens", 9, []),
        ("max_tokens", 10, [Stage.PLAN]),
    ],
)
def test_budget_preflight_and_no_later_stage(brief, policy, field, limit, expected_stages):
    policy = policy.model_copy(update={"limits": policy.limits.model_copy(update={field: limit})})
    result = execute(brief, policy)
    assert result.error.code == ErrorCode.BUDGET_EXHAUSTED
    assert [
        attempt.stage
        for attempt in result.attempts
        if attempt.stage not in (Stage.UNDERSTAND, Stage.VALIDATE)
    ] == expected_stages
    assert result.status == (Lifecycle.INCOMPLETE if result.latest_draft else Lifecycle.FAILED)


def test_usage_overrun_terminates_before_next_stage(brief, policy):
    class Overrun(FakePlanner):
        async def propose(self, brief, policy, feedback=()):
            response = await super().propose(brief, policy, feedback)
            return response.model_copy(
                update={"usage": ModelUsage(model_calls=2, tokens=15, synthetic=True)}
            )

    result = execute(brief, policy, Overrun())
    assert result.status == Lifecycle.FAILED
    assert result.error.code == ErrorCode.BUDGET_EXHAUSTED
    assert result.usage.model_calls == 2
    assert result.usage.tokens == 15
    assert result.attempts[-1].usage.model_calls == 2
    assert result.attempts[-1].outcome == AttemptOutcome.FAILED
    assert result.artifacts == ()


@pytest.mark.parametrize("transient,expected_calls", [(True, 2), (False, 1)])
def test_explicit_failure_retry_classification(brief, policy, transient, expected_calls):
    calls = []

    class Failing(FakeStages):
        async def draft(self, brief, evidence, analysis, outline):
            calls.append(1)
            if len(calls) == 1:
                raise ComponentFailure(
                    transient=transient, usage=ModelUsage(model_calls=1, tokens=3, synthetic=True)
                )
            return await super().draft(brief, evidence, analysis, outline)

    result = execute(brief, policy, stages=Failing())
    assert len(calls) == expected_calls
    assert result.usage.operational_retries == expected_calls - 1
    assert result.usage.planning_corrections == result.usage.revision_cycles == 0
    if transient:
        assert result.status == Lifecycle.COMPLETED
        assert [attempt.outcome for attempt in result.attempts if attempt.stage == Stage.DRAFT] == [
            AttemptOutcome.FAILED,
            AttemptOutcome.SUCCEEDED,
        ]
        assert result.usage.tokens == 33
    else:
        assert result.status == Lifecycle.FAILED
        assert result.error.code == ErrorCode.STAGE_FAILED


def test_retry_exhaustion_and_preflight(brief, policy):
    class Failing(FakeStages):
        async def draft(self, brief, evidence, analysis, outline):
            raise ComponentFailure(
                transient=True, usage=ModelUsage(model_calls=1, tokens=10, synthetic=True)
            )

    result = execute(brief, policy, stages=Failing())
    assert result.error.code == ErrorCode.STAGE_FAILED
    assert [a.attempt_number for a in result.attempts if a.stage == Stage.DRAFT] == [1, 2]
    policy = policy.model_copy(
        update={"limits": policy.limits.model_copy(update={"max_model_calls": 2})}
    )
    result = execute(brief, policy, stages=Failing())
    assert result.error.code == ErrorCode.BUDGET_EXHAUSTED
    assert [a.attempt_number for a in result.attempts if a.stage == Stage.DRAFT] == [1]


def test_unexpected_exception_has_safe_diagnostics(brief, policy):
    class Broken(FakeStages):
        async def review(self, brief, draft, evidence):
            raise RuntimeError("CONFIDENTIAL_DIAGNOSTIC_MARKER")

    result = execute(brief, policy, stages=Broken())
    assert result.status == Lifecycle.INCOMPLETE
    assert result.latest_draft is not None
    assert result.error.code == ErrorCode.STAGE_FAILED
    assert "CONFIDENTIAL_DIAGNOSTIC_MARKER" not in result.model_dump_json()
    assert not result.usage.reporting_complete
    assert len([a for a in result.attempts if a.stage == Stage.REVIEW]) == 1


@pytest.mark.parametrize("mutation", ["wrong_type", "unchecked", "blank", "version", "reused_id"])
def test_invalid_draft_output(brief, policy, mutation):
    class Broken(FakeStages):
        async def draft(self, brief, evidence, analysis, outline):
            response = await super().draft(brief, evidence, analysis, outline)
            if mutation == "wrong_type":
                return response.model_copy(
                    update={"value": AnalysisResult(artifact_id=uuid4(), version=1)}
                )
            changes = {
                "unchecked": {"body": 42},
                "blank": {"body": "  "},
                "version": {"version": 2},
                "reused_id": {"artifact_id": analysis.artifact_id if analysis else uuid4()},
            }
            return response.model_copy(
                update={"value": response.value.model_copy(update=changes[mutation])}
            )

    result = execute(brief, policy, FakePlanner(("ANALYZE",)), Broken())
    assert result.status == Lifecycle.FAILED
    assert result.error.code == ErrorCode.INVALID_STAGE_OUTPUT
    assert not any(a.stage == Stage.REVIEW for a in result.attempts)
    assert result.latest_draft is None


def test_review_wrong_draft_is_invalid(brief, policy):
    class Broken(FakeStages):
        async def review(self, brief, draft, evidence):
            response = await super().review(brief, draft, evidence)
            return response.model_copy(
                update={"value": response.value.model_copy(update={"draft_id": uuid4()})}
            )

    result = execute(brief, policy, stages=Broken())
    assert result.status == Lifecycle.INCOMPLETE
    assert result.error.code == ErrorCode.INVALID_STAGE_OUTPUT
    assert result.review is None


def test_missing_selected_component_fails(brief, policy):
    components = replace(FakeStages().components(), analyst=None)
    result = execute(brief, policy, FakePlanner(("ANALYZE",)), components=components)
    assert result.status == Lifecycle.FAILED
    assert result.error.code == ErrorCode.STAGE_FAILED
    assert result.latest_draft is None


def test_deadline_during_await(brief, policy):
    cleanup = []

    class Slow(FakeStages):
        async def draft(self, brief, evidence, analysis, outline):
            try:
                await asyncio.Event().wait()
            finally:
                cleanup.append(True)

    policy = policy.model_copy(
        update={"limits": policy.limits.model_copy(update={"max_duration_seconds": 1})}
    )
    result = execute(brief, policy, stages=Slow())
    assert cleanup == [True]
    assert result.error.code == ErrorCode.DEADLINE_EXCEEDED
    assert result.attempts[-1].outcome == AttemptOutcome.TIMED_OUT
    assert result.usage.reporting_complete is False
    assert result.latest_draft is None


@pytest.mark.parametrize("suppress", [False, True])
def test_mid_stage_cancellation_propagates_and_preserves_snapshot(brief, policy, suppress):
    cleanup = []

    async def scenario():
        entered = asyncio.Event()

        class Waiting(FakeStages):
            async def draft(self, brief, evidence, analysis, outline):
                entered.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    if not suppress:
                        raise
                    return await super().draft(brief, evidence, analysis, outline)
                finally:
                    cleanup.append(True)

        task = asyncio.create_task(
            WorkflowExecutor(FakePlanner(), Waiting().components()).execute(brief, policy)
        )
        await entered.wait()
        task.cancel()
        with pytest.raises(WorkflowCancelled) as caught:
            await task
        assert task.cancelled()
        return caught.value.result

    result = asyncio.run(scenario())
    assert cleanup == [True]
    assert result.status == Lifecycle.CANCELLED
    assert result.error.code == ErrorCode.CANCELLED
    assert result.attempts[-1].outcome == AttemptOutcome.CANCELLED
    assert not any(a.stage == Stage.REVIEW for a in result.attempts)


def test_concurrent_executions_have_isolated_history(brief, policy):
    async def scenario():
        executor = WorkflowExecutor(FakePlanner(), FakeStages().components())
        return await asyncio.gather(
            executor.execute(brief, policy), executor.execute(brief, policy)
        )

    first, second = asyncio.run(scenario())
    assert first.status == second.status == Lifecycle.COMPLETED
    assert len(first.artifacts) == len(second.artifacts) == 2
    assert {r.payload.artifact_id for r in first.artifacts}.isdisjoint(
        r.payload.artifact_id for r in second.artifacts
    )


def test_repository_factory_requires_execution_local_store(brief, policy):
    repository = InMemoryArtifactRepository()
    executor = WorkflowExecutor(FakePlanner(), FakeStages().components(), lambda: repository)
    asyncio.run(executor.execute(brief, policy))
    with pytest.raises(ValueError, match="empty"):
        asyncio.run(executor.execute(brief, policy))
    with pytest.raises(FrozenInstanceError):
        FakeStages().components().researcher = None


@pytest.mark.parametrize("stage", ["analysis", "outline"])
def test_optional_artifact_references_must_exist(brief, policy, stage):
    class Broken(FakeStages):
        async def analyze(self, brief, evidence):
            return self._reported(
                AnalysisResult(artifact_id=uuid4(), version=1, evidence_ids=("missing",))
            )

        async def outline(self, brief, evidence, analysis):
            return self._reported(
                DocumentOutline(
                    artifact_id=uuid4(),
                    version=1,
                    sections=(
                        OutlineSection(
                            title="Summary", key_argument="Test", evidence_ids=("missing",)
                        ),
                    ),
                )
            )

    selected = ("ANALYZE",) if stage == "analysis" else ("OUTLINE",)
    result = execute(brief, policy, FakePlanner(selected), Broken())
    assert result.status == Lifecycle.FAILED
    assert result.error.code == ErrorCode.INVALID_STAGE_OUTPUT


@pytest.mark.parametrize("defect", ["unknown_supplied", "conflicting_source"])
def test_evidence_source_integrity(brief, policy, defect):
    class Broken(FakeStages):
        async def research(self, brief, plan):
            response = await super().research(brief, plan)
            first = response.value.evidence[0]
            supplied = SourceReference(
                source_id=first.source.source_id, kind="supplied", reference="Unknown"
            )
            second = first.model_copy(update={"evidence_id": "different", "source": supplied})
            if defect == "unknown_supplied":
                evidence = (second,)
            else:
                evidence = (
                    first,
                    second.model_copy(
                        update={"source": first.source.model_copy(update={"reference": "Changed"})}
                    ),
                )
            return response.model_copy(
                update={"value": response.value.model_copy(update={"evidence": evidence})}
            )

    brief = brief.model_copy(update={"permissions": Permissions(external_research=True)})
    result = execute(brief, policy, FakePlanner(("RESEARCH",)), Broken())
    assert result.error.code == ErrorCode.INVALID_STAGE_OUTPUT
    assert [r.payload.kind for r in result.artifacts] == ["research_plan"]


def test_known_supplied_evidence_and_gap_disclosure(brief, policy):
    supplied = SourceReference(
        source_id="supplied-1", kind="supplied", reference="Internal reference"
    )
    brief = brief.model_copy(
        update={"supplied_content": (supplied,), "permissions": Permissions(external_research=True)}
    )

    class Supplied(FakeStages):
        async def research(self, brief, plan):
            response = await super().research(brief, plan)
            item = response.value.evidence[0].model_copy(update={"source": supplied})
            return response.model_copy(
                update={"value": response.value.model_copy(update={"evidence": (item,)})}
            )

        async def analyze(self, brief, evidence):
            response = await super().analyze(brief, evidence)
            return response.model_copy(
                update={
                    "value": response.value.model_copy(
                        update={"unresolved_gaps": ("Disclosed gap",)}
                    )
                }
            )

    class Gaps(FakePlanner):
        async def propose(self, brief, policy, feedback=()):
            response = await super().propose(brief, policy, feedback)
            return response.model_copy(
                update={
                    "value": response.value.model_copy(
                        update={"identified_gaps": ("Planning uncertainty",)}
                    )
                }
            )

    result = execute(brief, policy, Gaps(("RESEARCH", "ANALYZE")), Supplied())
    assert result.status == Lifecycle.COMPLETED
    assert "Planning uncertainty" in result.limitations
    assert "Disclosed gap" in result.limitations


@pytest.mark.parametrize(
    "defect", ["usage_schema", "missing_envelope", "failure_usage", "failure_overrun"]
)
def test_invalid_or_excessive_usage_reports(brief, policy, defect):
    class Broken(FakePlanner):
        async def propose(self, brief, policy, feedback=()):
            response = await super().propose(brief, policy, feedback)
            invalid = ModelUsage(model_calls=1, tokens=1, synthetic=True).model_copy(
                update={"tokens": "bad"}
            )
            if defect == "failure_usage":
                raise ComponentFailure(transient=True, usage=invalid)
            if defect == "failure_overrun":
                raise ComponentFailure(
                    transient=True, usage=ModelUsage(model_calls=2, tokens=11, synthetic=True)
                )
            if defect == "missing_envelope":
                return response.value
            return response.model_copy(update={"usage": invalid})

    result = execute(brief, policy, Broken())
    expected = (
        ErrorCode.BUDGET_EXHAUSTED
        if defect == "failure_overrun"
        else ErrorCode.INVALID_STAGE_OUTPUT
    )
    assert result.error.code == expected
    assert len([a for a in result.attempts if a.stage == Stage.PLAN]) == 1


@pytest.mark.parametrize("kind", ["model", "duration", "corrections"])
def test_approved_lower_limits_include_resources_already_spent(brief, policy, kind):
    class Lower(FakePlanner):
        async def propose(self, brief, policy, feedback=()):
            response = await super().propose(brief, policy, feedback)
            changes = {"max_model_calls": 0} if kind == "model" else {"max_planning_corrections": 0}
            if kind == "duration":
                changes = {"max_duration_seconds": 1}
                await asyncio.sleep(1.01)
            if kind == "corrections" and not feedback:
                response = await FakePlanner(("REVISE",)).propose(brief, policy, feedback)
            else:
                response = response.model_copy(
                    update={
                        "value": response.value.model_copy(
                            update={
                                "requested_limits": policy.limits.model_copy(update=changes),
                            }
                        )
                    }
                )
            return response

    result = execute(brief, policy, Lower())
    assert result.status == Lifecycle.FAILED
    assert result.error.code == (
        ErrorCode.DEADLINE_EXCEEDED if kind == "duration" else ErrorCode.BUDGET_EXHAUSTED
    )
    assert not any(a.stage == Stage.DRAFT for a in result.attempts)


def test_deadline_after_draft_retains_it(brief, policy):
    class SlowReview(FakeStages):
        async def review(self, brief, draft, evidence):
            await asyncio.Event().wait()

    policy = policy.model_copy(
        update={"limits": policy.limits.model_copy(update={"max_duration_seconds": 1})}
    )
    result = execute(brief, policy, stages=SlowReview())
    assert result.status == Lifecycle.INCOMPLETE
    assert result.latest_draft is not None
    assert result.error.code == ErrorCode.DEADLINE_EXCEEDED
    assert result.attempts[-1].outcome == AttemptOutcome.TIMED_OUT


@pytest.mark.parametrize("phase", ["planning", "review"])
def test_cancellation_in_other_awaited_phases(brief, policy, phase):
    async def scenario():
        entered = asyncio.Event()

        class WaitingPlanner(FakePlanner):
            async def propose(self, brief, policy, feedback=()):
                entered.set()
                await asyncio.Event().wait()

        class WaitingReviewer(FakeStages):
            async def review(self, brief, draft, evidence):
                entered.set()
                await asyncio.Event().wait()

        planner = WaitingPlanner() if phase == "planning" else FakePlanner()
        stages = WaitingReviewer() if phase == "review" else FakeStages()
        task = asyncio.create_task(
            WorkflowExecutor(planner, stages.components()).execute(brief, policy)
        )
        await entered.wait()
        task.cancel()
        with pytest.raises(WorkflowCancelled) as caught:
            await task
        return caught.value.result

    result = asyncio.run(scenario())
    assert result.status == Lifecycle.CANCELLED
    assert result.attempts[-1].stage == (Stage.PLAN if phase == "planning" else Stage.REVIEW)
    assert result.attempts[-1].outcome == AttemptOutcome.CANCELLED
    assert (result.latest_draft is not None) == (phase == "review")


def test_planner_transient_failure_is_not_a_plan_correction(brief, policy):
    calls = []

    class RetryPlanner(FakePlanner):
        async def propose(self, brief, policy, feedback=()):
            calls.append(1)
            if len(calls) == 1:
                raise ComponentFailure(
                    transient=True, usage=ModelUsage(model_calls=0, tokens=0, synthetic=True)
                )
            return await super().propose(brief, policy, feedback)

    result = execute(brief, policy, RetryPlanner())
    assert result.status == Lifecycle.COMPLETED
    assert result.usage.operational_retries == 1
    assert result.usage.planning_corrections == 0


@pytest.mark.parametrize("stage", ["RESEARCH", "OUTLINE"])
def test_other_missing_selected_components(brief, policy, stage):
    brief = brief.model_copy(update={"permissions": Permissions(external_research=True)})
    stages = FakeStages().components()
    components = (
        replace(stages, researcher=None) if stage == "RESEARCH" else replace(stages, outliner=None)
    )
    result = execute(brief, policy, FakePlanner((stage,)), components=components)
    assert result.status == Lifecycle.FAILED
    assert result.error.code == ErrorCode.STAGE_FAILED


@pytest.mark.parametrize(
    "body,completed",
    [
        ("```markdown\n## Decision\n```", False),
        ("~~~\n## Decision\n~~~", False),
        ("```\n```\n## Decision", True),
        ("    ## Decision", False),
        ("## decision ###\nText", True),
        ("## Decision#\nText", False),
        ("```\n~~~\n## Decision", False),
    ],
)
def test_required_headings_are_not_prose_or_code(brief, policy, body, completed):
    brief = brief.model_copy(
        update={"constraints": DocumentConstraints(required_sections=("Decision",))}
    )
    result = execute(brief, policy, stages=FakeStages(body=body))
    assert (result.status == Lifecycle.COMPLETED) == completed


@pytest.mark.parametrize("replacement", ["transient", "unexpected"])
def test_cancellation_cannot_be_replaced_with_an_error_or_retry(brief, policy, replacement):
    async def scenario():
        entered = asyncio.Event()

        class Replacing(FakeStages):
            async def draft(self, brief, evidence, analysis, outline):
                entered.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    if replacement == "transient":
                        raise ComponentFailure(
                            transient=True,
                            usage=ModelUsage(model_calls=0, tokens=0, synthetic=True),
                        ) from None
                    raise RuntimeError("Error after cancellation") from None

        task = asyncio.create_task(
            WorkflowExecutor(FakePlanner(), Replacing().components()).execute(brief, policy)
        )
        await entered.wait()
        task.cancel()
        with pytest.raises(WorkflowCancelled) as caught:
            await task
        assert task.cancelled()
        return caught.value.result

    result = asyncio.run(scenario())
    assert result.status == Lifecycle.CANCELLED
    assert result.attempts[-1].outcome == AttemptOutcome.CANCELLED
    assert result.usage.operational_retries == 0
    assert not any(a.stage == Stage.REVIEW for a in result.attempts)


def test_invalid_research_plan_version_records_validation_failure(brief, policy):
    class InvalidVersion(FakePlanner):
        async def propose(self, brief, policy, feedback=()):
            response = await super().propose(brief, policy, feedback)
            return response.model_copy(
                update={
                    "value": response.value.model_copy(
                        update={
                            "research_plan": response.value.research_plan.model_copy(
                                update={"version": 2}
                            ),
                        }
                    )
                }
            )

    brief = brief.model_copy(update={"permissions": Permissions(external_research=True)})
    result = execute(brief, policy, InvalidVersion(("RESEARCH",)))
    assert result.error.code == ErrorCode.INVALID_STAGE_OUTPUT
    assert result.attempts[-1].stage == Stage.VALIDATE
    assert result.attempts[-1].outcome == AttemptOutcome.FAILED
    assert result.artifacts == ()


@pytest.mark.parametrize("stages", [("RESEARCH",), ("REVISE",)])
def test_preflight_does_not_count_unstarted_research_or_corrections(brief, policy, stages):
    brief = brief.model_copy(update={"permissions": Permissions(external_research=True)})
    policy = policy.model_copy(
        update={"limits": policy.limits.model_copy(update={"max_model_calls": 1})}
    )
    result = execute(brief, policy, FakePlanner(stages))
    assert result.error.code == ErrorCode.BUDGET_EXHAUSTED
    assert result.usage.research_rounds == result.usage.planning_corrections == 0
    assert len([a for a in result.attempts if a.stage == Stage.PLAN]) == 1
    assert not any(a.stage == Stage.RESEARCH for a in result.attempts)


def test_empty_research_is_disclosed_without_inventing_evidence(brief, policy):
    class EmptyResearch(FakeStages):
        async def research(self, brief, plan):
            response = await super().research(brief, plan)
            return response.model_copy(
                update={"value": response.value.model_copy(update={"evidence": ()})}
            )

    brief = brief.model_copy(update={"permissions": Permissions(external_research=True)})
    result = execute(brief, policy, FakePlanner(("RESEARCH",)), EmptyResearch())
    assert result.status == Lifecycle.COMPLETED
    assert result.latest_draft.citations == ()
    assert any("returned no evidence" in limitation for limitation in result.limitations)


def test_limitation_bounds_preserve_synthetic_disclosure(brief, policy):
    class ManyGaps(FakePlanner):
        async def propose(self, brief, policy, feedback=()):
            response = await super().propose(brief, policy, feedback)
            return response.model_copy(
                update={
                    "value": response.value.model_copy(
                        update={
                            "identified_gaps": tuple(f"Gap {index}" for index in range(100)),
                        }
                    )
                }
            )

    brief = brief.model_copy(update={"permissions": Permissions(external_research=True)})
    result = execute(brief, policy, ManyGaps(("RESEARCH",)))
    assert result.status == Lifecycle.COMPLETED
    assert len(result.limitations) == 100
    assert any("synthetic" in limitation for limitation in result.limitations)
    assert result.limitations[-1].startswith("Additional limitations")
