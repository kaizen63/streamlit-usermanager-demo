from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal, Optional, TypeAlias

from pydantic import (
    ValidationInfo,
    field_validator,
)
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel
from sqlmodel._compat import SQLModelConfig

from .db_schema import schema, schema_prefix


class ParticipantRelationType(StrEnum):
    """
    Enum for the participant relation type.
    """

    GRANT = "GRANT"
    MEMBER_OF = "MEMBER OF"
    PROXY_OF = "PROXY OF"


ParticipantRelationTypeLiteral: TypeAlias = Literal[
    "GRANT",
    "MEMBER OF",
    "PROXY OF",
]


class ParticipantRelationBase(SQLModel):
    """The relationship between participants"""

    model_config = SQLModelConfig(
        extra="forbid", str_strip_whitespace=True, from_attributes=True
    )

    pati1_id: int = Field(...)
    pati2_id: int = Field(...)
    relation_type: ParticipantRelationTypeLiteral = Field(..., max_length=16)
    created_by: str = Field(...)
    created_timestamp: datetime = Field(
        ..., default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def get_field_names(cls, alias: bool = False) -> list[str]:
        properties = cls.model_json_schema(alias).get("properties", {})
        return list(properties.keys())

    @field_validator(
        "relation_type",
        mode="before",
    )
    @classmethod
    def enum_to_string(cls, v: str, info: ValidationInfo) -> Optional[str]:
        return str(v) if isinstance(v, StrEnum) else v

    @field_validator("created_by")
    @classmethod
    def to_uppercase(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Uppercase a field"""

        return v.upper() if v else v


class ParticipantRelationModel(ParticipantRelationBase, table=True):
    __tablename__ = "participant_relations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["pati1_id"],
            [f"{schema_prefix}participants.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["pati2_id"],
            [f"{schema_prefix}participants.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "pati1_id",
            "pati2_id",
            "relation_type",
            name="participant_relations_ak1",
        ),
        CheckConstraint(
            "relation_type in ('GRANT', 'MEMBER OF', 'PROXY OF')",
            name="participants_chk1",
        ),
        Index("participant_relations_fk2", "pati2_id"),
        (
            {"schema": schema, "extend_existing": True}
            if schema
            else {"extend_existing": True}
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    pati1_id: int = Field(..., foreign_key=f"{schema_prefix}participants.id")
    pati2_id: int = Field(..., foreign_key=f"{schema_prefix}participants.id")
    # redefine as str to make the model work
    relation_type: str = Field(..., max_length=16)  # type: ignore


class ParticipantRelationCreate(ParticipantRelationBase):
    """Create a relationship between participants"""

    pass


class ParticipantRelation(ParticipantRelationBase):
    id: int | None = Field(default=None)
