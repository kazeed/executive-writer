"""Closed workflow stage catalog; revision is a review-controlled transition."""

from enum import StrEnum


class Stage(StrEnum):
    UNDERSTAND = "UNDERSTAND"
    PLAN = "PLAN"
    VALIDATE = "VALIDATE"
    RESEARCH = "RESEARCH"
    ANALYZE = "ANALYZE"
    OUTLINE = "OUTLINE"
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    REVISE = "REVISE"


OPTIONAL_STAGES = (Stage.RESEARCH, Stage.ANALYZE, Stage.OUTLINE)
INITIAL_STAGES = (Stage.UNDERSTAND, Stage.PLAN, Stage.VALIDATE)
FINAL_STAGES = (Stage.DRAFT, Stage.REVIEW)
