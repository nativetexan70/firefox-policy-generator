"""Models describing the shape of Firefox policies, parsed from Mozilla's schema."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ValueType(str, Enum):
    BOOL = "boolean"
    STRING = "string"
    INT = "integer"
    ENUM = "enum"
    OBJECT = "object"
    ARRAY = "array"
    URL = "url"


class PolicyField(BaseModel):
    key: str
    type: ValueType
    description: str | None = None
    enum_values: list[str] | None = None
    default: Any | None = None
    required: bool = False
    children: list[PolicyField] = Field(default_factory=list)


PolicyField.model_rebuild()


class PolicyDefinition(BaseModel):
    name: str
    category: str = "Uncategorized"
    description: str | None = None
    min_firefox_version: int | None = None
    max_firefox_version: int | None = None
    root_field: PolicyField


class PolicySchema(BaseModel):
    source_version: str
    fetched_at: datetime
    policies: dict[str, PolicyDefinition] = Field(default_factory=dict)
