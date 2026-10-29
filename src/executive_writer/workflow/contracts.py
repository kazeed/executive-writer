"""Shared immutable, bounded serialization primitives."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

type Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
type Body = Annotated[str, StringConstraints(min_length=1, max_length=100_000)]
type Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
type Texts = Annotated[tuple[Text, ...], Field(max_length=100)]
type Identifiers = Annotated[tuple[Identifier, ...], Field(max_length=100)]
type Positive = Annotated[int, Field(strict=True, gt=0)]
type Count = Annotated[int, Field(strict=True, ge=0)]


class Contract(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        hide_input_in_errors=True,
        revalidate_instances="always",
    )
    schema_version: Literal[1] = 1
