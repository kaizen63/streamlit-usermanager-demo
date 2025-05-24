"""
Participant Relation Module

This module defines the data models and functionality for relationships between participants.
It includes models for different types of relationships (GRANT, MEMBER OF, PROXY OF)
and provides functionality for creating and querying participant relationships.
The module uses SQLModel for ORM functionality and Pydantic for validation.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

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

from .db_schema import schema, schema_prefix


class ParticipantRelationType(StrEnum):
    """
    Enum for the participant relation type.

    Defines the allowed types of relationships between participants:
    - GRANT: Assigns a role/permission to a participant
    - MEMBER OF: Indicates membership in an organizational unit
    - PROXY OF: Indicates a proxy relationship where one participant can act on behalf of another
    """

    GRANT = "GRANT"
    MEMBER_OF = "MEMBER OF"
    PROXY_OF = "PROXY OF"


type ParticipantRelationTypeLiteral = Literal[
    "GRANT",
    "MEMBER OF",
    "PROXY OF",
]


class ParticipantRelationBase(SQLModel):
    """
    Base model for participant relationships.

    Defines the core fields and validation for relationships between participants,
    including the relationship type and metadata about creation.
    """

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "from_attributes": True,
    }

    pati1_id: int = Field(
        ...,
        description="ID of the first participant in the relationship",
    )
    pati2_id: int = Field(
        ...,
        description="ID of the second participant in the relationship",
    )
    relation_type: ParticipantRelationTypeLiteral = Field(..., max_length=16)
    created_by: str = Field(
        ...,
        description="Identifier of the participant who created this relationship",
    )
    created_timestamp: datetime = Field(
        ...,
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp when the relationship was created",
    )

    @classmethod
    def get_field_names(cls, alias: bool = False) -> list[str]:
        """
        Return the list of field names of the class.

        Args:
            alias: If True, return the aliased field names

        Returns:
            list[str]: List of field names

        """
        properties = cls.model_json_schema(alias).get("properties", {})
        return list(properties.keys())

    @field_validator(
        "relation_type",
        mode="before",
    )
    @classmethod
    def enum_to_string(cls, v: str, _info: ValidationInfo) -> str | None:
        """
        Converts enum values to strings.

        Args:
            v: The value to convert
            _info: Validation info containing field context

        Returns:
            str or None: The string representation of the enum value

        """
        return str(v) if isinstance(v, StrEnum) else v

    @field_validator("created_by")
    @classmethod
    def to_uppercase(cls, v: str | None, _info: ValidationInfo) -> str | None:
        """
        Converts field value to uppercase.

        Args:
            v: The value to convert
            _info: Validation info containing field context

        Returns:
            str or None: The uppercase value

        """
        return v.upper() if v else v


class ParticipantRelationModel(ParticipantRelationBase, table=True):
    """
    SQLModel representation of a participant relationship for database storage.

    This model maps to the 'participant_relations' table and includes constraints
    and database-specific configuration including foreign keys, unique constraints,
    and indexes for optimal performance.
    """

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

    id: int | None = Field(
        default=None,
        primary_key=True,
        description="Unique identifier for the relationship",
    )
    pati1_id: int = Field(..., foreign_key=f"{schema_prefix}participants.id")
    pati2_id: int = Field(..., foreign_key=f"{schema_prefix}participants.id")
    # redefine as str to make the model work
    relation_type: str = Field(..., max_length=16)


class ParticipantRelationCreate(ParticipantRelationBase):
    """
    Model for creating new participant relationships.

    Extends ParticipantRelationBase with validation specific to the creation process.
    This model is used when adding new relationships between participants.
    """


class ParticipantRelation(ParticipantRelationBase):
    """
    Schema class for participant relationships with ID field.

    This model extends ParticipantRelationBase with the ID field for use in
    API responses and application logic.
    """

    id: int | None = Field(
        default=None,
        description="Unique identifier for the relationship",
    )
