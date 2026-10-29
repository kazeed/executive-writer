"""Sequential, execution-local orchestration with deterministic Python control."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from executive_writer.workflow.components import WorkflowComponents
from executive_writer.workflow.errors import ErrorCode, ExecutionError, PlanIssue
from executive_writer.workflow.failures import ComponentFailure, ExecutionStopped, WorkflowCancelled
from executive_writer.workflow.models import (
    AnalysisResult,
    Artifact,
    ArtifactPayload,
    ArtifactRecord,
    AttemptOutcome,
    AttemptReference,
    DocumentBrief,
    DocumentDraft,
    DocumentOutline,
    EvidenceSet,
    ExecutionResult,
    Lifecycle,
    ResearchPlan,
    ReviewDecision,
    ReviewResult,
    StageAttempt,
    Usage,
)
from executive_writer.workflow.planning import Planner
from executive_writer.workflow.policies import ExecutionPolicy
from executive_writer.workflow.quality import check_draft
from executive_writer.workflow.reporting import ComponentResult, ModelUsage, ResourceBudget
from executive_writer.workflow.repository import (
    ArtifactConflict,
    ArtifactRepository,
    InMemoryArtifactRepository,
)
from executive_writer.workflow.stages import INITIAL_STAGES, Stage
from executive_writer.workflow.validation import ApprovedPlan, PlanValidator


class WorkflowExecutor:
    def __init__(
        self,
        planner: Planner,
        components: WorkflowComponents,
        repository_factory: Callable[[], ArtifactRepository] = InMemoryArtifactRepository,
    ) -> None:
        self._planner = planner
        self._components = components
        self._repository_factory = repository_factory

    async def execute(self, brief: DocumentBrief, policy: ExecutionPolicy) -> ExecutionResult:
        run = _Execution(
            DocumentBrief.model_validate(brief),
            ExecutionPolicy.model_validate(policy),
            self._planner,
            self._components,
            self._repository_factory(),
        )
        return await run.execute()


class _Execution:
    def __init__(
        self,
        brief: DocumentBrief,
        policy: ExecutionPolicy,
        planner: Planner,
        components: WorkflowComponents,
        repository: ArtifactRepository,
    ) -> None:
        if repository.records():
            raise ValueError("An execution requires an empty artifact repository")
        self.brief = brief
        self.policy = policy
        self.planner = planner
        self.components = components
        self.repository = repository
        self.started = asyncio.get_running_loop().time()
        self.history = [Lifecycle.CREATED]
        self.attempts: list[StageAttempt] = []
        self.usage = Usage()
        self.issues: tuple[PlanIssue, ...] = ()
        self.draft: DocumentDraft | None = None
        self.review: ReviewResult | None = None
        self.evidence: EvidenceSet | None = None
        self.analysis: AnalysisResult | None = None
        self.outline: DocumentOutline | None = None
        self.approved: ApprovedPlan | None = None

    @property
    def deadline(self) -> float:
        return self.started + self.policy.limits.max_duration_seconds

    def _check_limits(self) -> None:
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            raise asyncio.CancelledError
        if asyncio.get_running_loop().time() >= self.deadline:
            raise ExecutionStopped(ErrorCode.DEADLINE_EXCEEDED)
        limits = self.policy.limits
        if (
            self.usage.model_calls > limits.max_model_calls
            or self.usage.tokens > limits.max_tokens
            or self.usage.planning_corrections > limits.max_planning_corrections
            or self.usage.research_rounds > limits.max_research_rounds
        ):
            raise ExecutionStopped(ErrorCode.BUDGET_EXHAUSTED)

    def _charge(self, reported: ModelUsage, budget: ResourceBudget) -> None:
        report = ModelUsage.model_validate(reported)
        self.usage = self.usage.model_copy(
            update={
                "model_calls": self.usage.model_calls + report.model_calls,
                "tokens": self.usage.tokens + report.tokens,
                "contains_synthetic_usage": self.usage.contains_synthetic_usage or report.synthetic,
            }
        )
        if report.model_calls > budget.model_calls or report.tokens > budget.tokens:
            raise ExecutionStopped(ErrorCode.BUDGET_EXHAUSTED)
        self._check_limits()

    def _next_attempt(self, stage: Stage) -> AttemptReference:
        return AttemptReference(
            stage=stage, attempt_number=1 + sum(item.stage == stage for item in self.attempts)
        )

    def _record(
        self,
        reference: AttemptReference,
        started: datetime,
        outcome: AttemptOutcome,
        sources: tuple[UUID, ...] = (),
        produced: tuple[UUID, ...] = (),
        usage: Usage | None = None,
        error: ErrorCode | None = None,
    ) -> None:
        self.attempts.append(
            StageAttempt(
                stage=reference.stage,
                attempt_number=reference.attempt_number,
                started_at=started,
                ended_at=max(started, datetime.now(UTC)),
                outcome=outcome,
                source_artifact_ids=sources,
                produced_artifact_ids=produced,
                usage=usage or Usage(),
                error=ExecutionError(code=error) if error else None,
            )
        )

    def _control(self, stage: Stage, failed: bool = False, produced: tuple[UUID, ...] = ()) -> None:
        self._check_limits()
        self._record(
            self._next_attempt(stage),
            datetime.now(UTC),
            AttemptOutcome.FAILED if failed else AttemptOutcome.SUCCEEDED,
            produced=produced,
            error=ErrorCode.PLAN_VALIDATION_FAILED if failed else None,
        )

    def _store[T: ArtifactPayload](
        self,
        value: object,
        expected: type[T],
        producer: AttemptReference,
        consumed: tuple[Artifact, ...],
    ) -> T:
        payload = expected.model_validate(value)
        available: set[str] = (
            {item.evidence_id for item in self.evidence.evidence} if self.evidence else set()
        )
        if isinstance(payload, AnalysisResult) and not set(payload.evidence_ids) <= available:
            raise ArtifactConflict("Analysis references unavailable evidence")
        if isinstance(payload, DocumentOutline) and any(
            not set(section.evidence_ids) <= available for section in payload.sections
        ):
            raise ArtifactConflict("Outline references unavailable evidence")
        if isinstance(payload, DocumentDraft) and not payload.body.strip():
            raise ArtifactConflict("Draft must contain usable text")
        if isinstance(payload, ReviewResult) and (
            self.draft is None or payload.draft_id != self.draft.artifact_id
        ):
            raise ArtifactConflict("Review must reference the current draft")
        if isinstance(payload, EvidenceSet):
            sources = {source.source_id: source for source in self.brief.supplied_content}
            seen = {}
            for item in payload.evidence:
                if (
                    item.source.kind == "supplied"
                    and sources.get(item.source.source_id) != item.source
                ):
                    raise ArtifactConflict("Unknown supplied source")
                if item.source.source_id in seen and seen[item.source.source_id] != item.source:
                    raise ArtifactConflict("Source IDs must have consistent provenance")
                seen[item.source.source_id] = item.source
        self.repository.append(
            ArtifactRecord(
                payload=payload,
                producer=producer,
                consumed_artifact_ids=tuple(item.artifact_id for item in consumed),
                created_at=datetime.now(UTC),
            )
        )
        return payload

    async def _invoke[T](
        self,
        stage: Stage,
        budget: ResourceBudget,
        call: Callable[[], Awaitable[object]],
        accept: Callable[[object, AttemptReference], T],
        sources: tuple[Artifact, ...] = (),
        *,
        correction: bool = False,
    ) -> T:
        budget = ResourceBudget.model_validate(budget)
        for retry in range(self.policy.limits.max_attempts_per_stage):
            self._check_limits()
            if (
                self.usage.model_calls + budget.model_calls > self.policy.limits.max_model_calls
                or self.usage.tokens + budget.tokens > self.policy.limits.max_tokens
            ):
                raise ExecutionStopped(ErrorCode.BUDGET_EXHAUSTED)
            if not retry and stage == Stage.RESEARCH:
                if self.usage.research_rounds >= self.policy.limits.max_research_rounds:
                    raise ExecutionStopped(ErrorCode.BUDGET_EXHAUSTED)
                self.usage = self.usage.model_copy(
                    update={
                        "research_rounds": self.usage.research_rounds + 1,
                    }
                )
            if not retry and correction:
                self.usage = self.usage.model_copy(
                    update={
                        "planning_corrections": self.usage.planning_corrections + 1,
                    }
                )
                self._check_limits()
            if retry:
                self.usage = self.usage.model_copy(
                    update={
                        "operational_retries": self.usage.operational_retries + 1,
                    }
                )
            reference = self._next_attempt(stage)
            started = datetime.now(UTC)
            before = self.usage
            outcome = AttemptOutcome.FAILED
            failure: ErrorCode | None = None
            produced: tuple[UUID, ...] = ()
            complete_report = False
            synthetic_report = False
            try:
                async with asyncio.timeout_at(self.deadline):
                    response = ComponentResult[object].model_validate(await call())
                # A component may suppress cancellation; never continue in that case.
                task = asyncio.current_task()
                if task is not None and task.cancelling():
                    raise asyncio.CancelledError
                complete_report = True
                synthetic_report = response.usage.synthetic
                self._charge(response.usage, budget)
                accepted = accept(response.value, reference)
                produced = tuple(
                    item.payload.artifact_id
                    for item in self.repository.records()
                    if item.producer == reference
                )
                outcome = AttemptOutcome.SUCCEEDED
                return accepted
            except ComponentFailure as error:
                try:
                    report = ModelUsage.model_validate(error.usage)
                    complete_report = True
                    synthetic_report = report.synthetic
                    self._charge(report, budget)
                except (ValidationError, ExecutionStopped) as charge_error:
                    failure = (
                        charge_error.code
                        if isinstance(charge_error, ExecutionStopped)
                        else ErrorCode.INVALID_STAGE_OUTPUT
                    )
                    raise ExecutionStopped(failure) from charge_error
                failure = ErrorCode.STAGE_FAILED
                if not error.transient or retry + 1 == self.policy.limits.max_attempts_per_stage:
                    raise ExecutionStopped(failure) from error
            except asyncio.CancelledError:
                outcome = AttemptOutcome.CANCELLED
                failure = ErrorCode.CANCELLED
                raise
            except TimeoutError as error:
                outcome = AttemptOutcome.TIMED_OUT
                failure = ErrorCode.DEADLINE_EXCEEDED
                raise ExecutionStopped(failure) from error
            except ExecutionStopped as error:
                failure = error.code
                if failure == ErrorCode.DEADLINE_EXCEEDED:
                    outcome = AttemptOutcome.TIMED_OUT
                raise
            except (ValidationError, ArtifactConflict) as error:
                failure = ErrorCode.INVALID_STAGE_OUTPUT
                raise ExecutionStopped(failure) from error
            except Exception as error:
                # Component boundary: preserve the cause for internal debugging;
                # terminal diagnostics contain only a safe code, never its text.
                failure = ErrorCode.STAGE_FAILED
                raise ExecutionStopped(failure) from error
            finally:
                task = asyncio.current_task()
                cancellation_pending = task is not None and task.cancelling() > 0
                if cancellation_pending:
                    outcome = AttemptOutcome.CANCELLED
                    failure = ErrorCode.CANCELLED
                if not complete_report:
                    self.usage = self.usage.model_copy(update={"reporting_complete": False})
                delta = Usage(
                    model_calls=self.usage.model_calls - before.model_calls,
                    tokens=self.usage.tokens - before.tokens,
                    contains_synthetic_usage=synthetic_report,
                    reporting_complete=complete_report,
                )
                self._record(
                    reference,
                    started,
                    outcome,
                    tuple(item.artifact_id for item in sources),
                    produced,
                    delta,
                    failure,
                )
                if cancellation_pending:
                    raise asyncio.CancelledError
        raise AssertionError("Positive attempt limit guarantees an invocation")

    async def _plan(self) -> ApprovedPlan:
        self.history.append(Lifecycle.PLANNING)
        self._control(Stage.UNDERSTAND)
        validator = PlanValidator()
        for correction in range(self.policy.limits.max_planning_corrections + 1):
            proposal = await self._invoke(
                Stage.PLAN,
                self.planner.budget,
                lambda: self.planner.propose(self.brief, self.policy, self.issues),
                lambda value, _: value,
                correction=correction > 0,
            )
            validation = validator.validate(proposal, self.brief, self.policy)
            self.issues = validation.issues
            approved = validation.approved_plan
            if approved is not None:
                return self._accept_plan(approved)
            self._control(Stage.VALIDATE, failed=True)
        raise ExecutionStopped(ErrorCode.PLAN_VALIDATION_FAILED)

    def _accept_plan(self, approved: ApprovedPlan) -> ApprovedPlan:
        reference = self._next_attempt(Stage.VALIDATE)
        started = datetime.now(UTC)
        produced: tuple[UUID, ...] = ()
        failure: ErrorCode | None = None
        try:
            self.policy = approved.snapshot.policy
            self._check_limits()
            research_plan = approved.snapshot.proposal.research_plan
            if research_plan is not None:
                stored = self._store(research_plan, ResearchPlan, reference, ())
                produced = (stored.artifact_id,)
            return approved
        except (ValidationError, ArtifactConflict) as error:
            failure = ErrorCode.INVALID_STAGE_OUTPUT
            raise ExecutionStopped(failure) from error
        except ExecutionStopped as error:
            failure = error.code
            raise
        finally:
            self._record(
                reference,
                started,
                AttemptOutcome.FAILED if failure else AttemptOutcome.SUCCEEDED,
                produced=produced,
                error=failure,
            )

    async def _execute_stage(self, stage: Stage, plan: ApprovedPlan) -> None:
        components = self.components
        if stage == Stage.RESEARCH:
            researcher = components.researcher
            research_plan = plan.snapshot.proposal.research_plan
            if researcher is None or research_plan is None:
                raise ExecutionStopped(ErrorCode.STAGE_FAILED)
            self.evidence = await self._invoke(
                stage,
                researcher.budget,
                lambda: researcher.research(self.brief, research_plan),
                lambda value, ref: self._store(value, EvidenceSet, ref, (research_plan,)),
                (research_plan,),
            )
        elif stage == Stage.ANALYZE:
            analyst = components.analyst
            if analyst is None:
                raise ExecutionStopped(ErrorCode.STAGE_FAILED)
            sources = (self.evidence,) if self.evidence else ()
            self.analysis = await self._invoke(
                stage,
                analyst.budget,
                lambda: analyst.analyze(self.brief, self.evidence),
                lambda value, ref: self._store(value, AnalysisResult, ref, sources),
                sources,
            )
        elif stage == Stage.OUTLINE:
            outliner = components.outliner
            if outliner is None:
                raise ExecutionStopped(ErrorCode.STAGE_FAILED)
            sources = tuple(item for item in (self.evidence, self.analysis) if item is not None)
            self.outline = await self._invoke(
                stage,
                outliner.budget,
                lambda: outliner.outline(self.brief, self.evidence, self.analysis),
                lambda value, ref: self._store(value, DocumentOutline, ref, sources),
                sources,
            )
        elif stage == Stage.DRAFT:
            sources = tuple(
                item for item in (self.evidence, self.analysis, self.outline) if item is not None
            )
            self.draft = await self._invoke(
                stage,
                components.drafter.budget,
                lambda: components.drafter.draft(
                    self.brief, self.evidence, self.analysis, self.outline
                ),
                lambda value, ref: self._store(value, DocumentDraft, ref, sources),
                sources,
            )
        elif stage == Stage.REVIEW:
            self.history.append(Lifecycle.REVIEWING)
            draft = self.draft
            if draft is None:
                raise ExecutionStopped(ErrorCode.INVALID_STAGE_OUTPUT)
            sources = (draft, self.evidence) if self.evidence else (draft,)
            self.review = await self._invoke(
                stage,
                components.reviewer.budget,
                lambda: components.reviewer.review(self.brief, draft, self.evidence),
                lambda value, ref: self._store(value, ReviewResult, ref, sources),
                sources,
            )
        else:
            raise ExecutionStopped(ErrorCode.INVALID_STAGE_OUTPUT)

    def _result(
        self,
        status: Literal[
            Lifecycle.COMPLETED, Lifecycle.INCOMPLETE, Lifecycle.FAILED, Lifecycle.CANCELLED
        ],
        error: ErrorCode | None = None,
    ) -> ExecutionResult:
        checks = check_draft(self.brief, self.draft, self.evidence) if self.draft else ()
        limitations = list(checks)
        if self.evidence and any(
            item.source.kind == "synthetic" for item in self.evidence.evidence
        ):
            limitations.append("Evidence is synthetic; no external facts have been verified.")
        if self.draft and self.review is None:
            limitations.append("Draft has no completed review.")
        if self.review and self.review.decision != ReviewDecision.ACCEPTED:
            limitations.append("Review requires changes; P2 does not perform revision.")
        if self.evidence is not None and not self.evidence.evidence:
            limitations.append("Research returned no evidence; factual support is not verified.")
        if self.approved:
            limitations.extend(self.approved.snapshot.proposal.identified_gaps)
        if self.analysis:
            limitations.extend(self.analysis.unresolved_gaps)
        unique_limitations = tuple(dict.fromkeys(limitations))
        if len(unique_limitations) > 100:
            unique_limitations = unique_limitations[:99] + (
                "Additional limitations are retained in the plan and analysis artifacts.",
            )
        self.history.append(status)
        return ExecutionResult(
            status=status,
            latest_draft=self.draft,
            review=self.review,
            mandatory_checks_passed=self.draft is not None and not checks,
            limitations=unique_limitations,
            artifacts=self.repository.records(),
            attempts=tuple(self.attempts),
            usage=self.usage,
            error=ExecutionError(code=error, planning_issues=self.issues) if error else None,
            lifecycle_history=tuple(self.history),
        )

    async def execute(self) -> ExecutionResult:
        try:
            self.approved = await self._plan()
            self.history.append(Lifecycle.EXECUTING)
            for stage in self.approved.snapshot.stages:
                if stage not in INITIAL_STAGES:
                    await self._execute_stage(stage, self.approved)
            self._check_limits()
            accepted = (
                self.draft is not None
                and self.review is not None
                and self.review.decision == ReviewDecision.ACCEPTED
                and not check_draft(self.brief, self.draft, self.evidence)
            )
            return self._result(Lifecycle.COMPLETED if accepted else Lifecycle.INCOMPLETE)
        except asyncio.CancelledError as error:
            raise WorkflowCancelled(
                self._result(Lifecycle.CANCELLED, ErrorCode.CANCELLED)
            ) from error
        except ExecutionStopped as error:
            return self._result(
                Lifecycle.INCOMPLETE if self.draft else Lifecycle.FAILED, error.code
            )
