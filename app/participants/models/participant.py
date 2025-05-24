"""
Participant Model Module.

This module defines the data models and related functionality for participants in the system.
It includes models for different types of participants (HUMAN, ROLE, ORG_UNIT, SYSTEM),
their relationships, and operations for creating, updating, and querying participants.
The module uses SQLModel for ORM functionality and Pydantic for validation.
"""

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Optional

from pydantic import (
    EmailStr,
    ValidationInfo,
    field_validator,
)
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel
from validate_email import validate_email

from .db_schema import schema
from .participant_relation import (
    ParticipantRelationTypeLiteral,
)


class ParticipantType(StrEnum):
    """
    Enum for the participant type.

    Defines the allowed types of participants in the system:
    - HUMAN: Individual user accounts
    - ROLE: Functional role that can be assigned to humans
    - ORG_UNIT: Organizational unit grouping
    - SYSTEM: System/service account
    """

    HUMAN = "HUMAN"
    ROLE = "ROLE"
    ORG_UNIT = "ORG_UNIT"
    SYSTEM = "SYSTEM"


type ParticipantTypeLiteral = Literal[
    "HUMAN",
    "ROLE",
    "ORG_UNIT",
    "SYSTEM",
]


class ParticipantState(StrEnum):
    """
    Enum for the participant state.

    Defines the possible states a participant can be in:
    - ACTIVE: Participant is active and can interact with the system
    - TERMINATED: Participant has been deactivated
    """

    ACTIVE = "ACTIVE"
    TERMINATED = "TERMINATED"


type ParticipantStateLiteral = Literal["ACTIVE", "TERMINATED"]
# ParticipantState.ACTIVE, ParticipantState.TERMINATED
# ]

VALID_NAME_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_-]{1,29}$"


def is_valid_name(name: str | None) -> bool:
    """
    Checks if a name is valid.

    A valid name must:
    - Start with a letter (uppercase or lowercase)
    - Contain only letters (uppercase or lowercase), digits, underscores and hyphens
    - Be between 2 and 30 characters long

    Args:
        name: The name to validate

    Returns:
        bool: True if the name is valid, False otherwise

    """
    pattern = re.compile(VALID_NAME_PATTERN)
    return bool(pattern.match(name)) if name else False


class ParticipantBase(SQLModel):
    """
    Participant Base Model is used to read data from the database.

    This is the foundation model that defines common fields and validation
    for all participant-related models.
    """

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "from_attributes": True,
    }

    name: str = Field(..., max_length=30)
    display_name: str = Field(..., max_length=60)
    description: str | None = Field(default=None, max_length=500)
    email: str | None = Field(default=None, max_length=200)
    participant_type: ParticipantTypeLiteral = Field(..., max_length=30)

    state: ParticipantStateLiteral | None = Field(
        default=None,
        max_length=20,
        description="ACTIVE or TERMINATED",
    )
    external_reference: str | None = Field(
        default=None,
        max_length=500,
        description="Reference to an external system, e.g. active directory",
    )
    hashed_password: str | None = Field(
        default=None,
        max_length=100,
        description="Hashed password of HUMANS if local authentication is implemented",
    )
    update_count: int = Field(
        default=0,
        description="""Field to detect if a record was updated in the background.
Use this before storing back the record. Must be used in combination with a row lock""",
    )
    created_by: str = Field(..., max_length=30)
    created_timestamp: datetime | None = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @classmethod
    def get_field_names(cls, alias: bool = False) -> list[str]:
        """
        Return the list of field names of the class

        Args:
            alias: If True, return the aliased field names

        Returns:
            list[str]: List of field names

        """
        properties = cls.model_json_schema(alias).get("properties", {})
        return list(properties.keys())

    @field_validator("state", "participant_type", mode="before")
    @classmethod
    def enum_to_string(cls, v: str, info: ValidationInfo) -> str | None:
        """
        Converts enum values to strings and sets default state to ACTIVE

        Args:
            v: The value to convert
            info: Validation info containing field context

        Returns:
            str or None: The string representation of the enum value

        """
        if info.field_name == "state" and v is None:
            return "ACTIVE"
        return str(v) if isinstance(v, StrEnum) else v

    @field_validator(
        "email",
    )
    @classmethod
    def check_valid_email(cls, v: str | None, info: ValidationInfo) -> str | None:
        """
        Checks if an email address is valid

        Args:
            v: The email address to validate
            info: Validation info containing field context

        Returns:
            str or None: The validated email address

        Raises:
            ValueError: If the email address is invalid

        """
        if v and not validate_email(v):
            exc_msg = f"Invalid email address: {v!a} in {info.field_name}"
            raise ValueError(exc_msg)
        return v

    @field_validator("name", "created_by")
    @classmethod
    def to_uppercase(cls, v: str | None, _info: ValidationInfo) -> str | None:
        """
        Converts a field value to uppercase.

        Args:
            v: The value to convert
            _info: Validation info containing field context

        Returns:
            str or None: The uppercase value

        """
        return v.upper() if v else v


class ParticipantModel(ParticipantBase, table=True):
    """
    SQLModel representation of a participant for database storage.

    This model maps to the 'participants' table and includes constraints and
    database-specific configuration.
    """

    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint(
            "participant_type",
            "name",
            name="participants_ak1",
        ),
        UniqueConstraint(
            "participant_type",
            "display_name",
            name="participants_ak2",
        ),
        CheckConstraint(
            "participant_type in ('SYSTEM', 'HUMAN', 'ROLE', 'ORG_UNIT')",
            name="participants_chk1",
        ),
        CheckConstraint(
            "participant_type in (NULL, 'ACTIVE', 'TERMINATED')",
            name="participants_chk2",
        ),
        (
            {
                "schema": schema,
                "extend_existing": True,
                # This should fix the error when rerun streamlit that the model exists
            }
            if schema
            else {"extend_existing": True}
        ),
    )
    id: int | None = Field(default=None, primary_key=True)
    # redefine participant_type and state to strings to make the model work
    participant_type: str = Field(..., max_length=30)
    state: str | None = Field(
        default=None,
        max_length=20,
        description="ACTIVE or TERMINATED",
    )

    updated_by: str | None = Field(default=None, max_length=30)
    updated_timestamp: datetime | None = Field(default=None)


class Participant(ParticipantBase):
    """
    Schema class for participants with extended functionality.

    This model extends ParticipantBase with additional fields and methods for
    working with participant relationships and effective roles.
    """

    id: int = Field(...)
    created_by: str = Field(..., max_length=30)
    created_timestamp: datetime = Field(
        ...,
        default_factory=lambda: datetime.now(UTC),
    )
    updated_timestamp: datetime | None = Field(default=None)
    updated_by: str | None = Field(default=None, max_length=30)

    # Information about the relationships
    org_units: list["Participant"] = Field(default=[])
    roles: list["Participant"] = Field(default=[])
    proxy_of: list["Participant"] = Field(default=[])
    proxies: list["Participant"] = Field(default=[])  # My proxies
    # The roles that are effective for this user.
    # Roles that are either directly assigned, assigned to the ORG_UNITs the user belongs to
    # or the roles inherited from the PROXY.
    effective_roles: set[str] = Field(default=set())

    @field_validator("state", mode="after")
    @classmethod
    def validate_state(cls, v: str | None) -> str | None:
        """
        Ensures state has a default value of ACTIVE if not specified.

        Args:
            v: The state value

        Returns:
            str or None: The validated state value

        """
        return v if v else "ACTIVE"

    @staticmethod
    def find_by_id(
        participants: list["Participant"],
        participant_id: int,
    ) -> Optional["Participant"]:
        """
        Get a participant by their ID.

        Args:
            participants: List of participants to search
            participant_id: ID of the participant to find

        Returns:
            Participant or None: The found participant or None if not found

        """
        return next((p for p in participants if p.id == participant_id), None)

    @staticmethod
    def find_by_name(
        participants: list["Participant"],
        name: str,
        participant_type: str,
    ) -> Optional["Participant"]:
        """
        Get a participant by their name and participant_type.

        Args:
            participants: List of participants to search
            name: Name of the participant to find
            participant_type: Type of the participant to find

        Returns:
            Participant or None: The found participant or None if not found

        """
        return next(
            (
                p
                for p in participants
                if p.name == name and p.participant_type == participant_type
            ),
            None,
        )

    @staticmethod
    def find_by_display_name(
        participants: list["Participant"],
        display_name: str,
        participant_type: str,
    ) -> Optional["Participant"]:
        """
        Get a participant by their display name and participant_type.

        Args:
            participants: List of participants to search
            display_name: Display name of the participant to find
            participant_type: Type of the participant to find

        Returns:
            Participant or None: The found participant or None if not found

        """
        return next(
            (
                p
                for p in participants
                if p.display_name == display_name
                and p.participant_type == participant_type
            ),
            None,
        )


class ParticipantCreate(ParticipantBase):
    """
    Model for creating new participants.

    Extends ParticipantBase with additional validation specifically for
    the creation process.
    """

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None, _info: ValidationInfo) -> str | None:
        """
        Validates that the name follows the required pattern and converts to uppercase.

        Args:
            v: The name to validate
            _info: Validation info containing field context

        Returns:
            str or None: The validated, uppercase name

        Raises:
            ValueError: If the name doesn't match the required pattern

        """
        if v and not is_valid_name(v):
            exc_msg = f"Invalid name: {v}"
            raise ValueError(exc_msg)
        return v.upper() if v else v


class ParticipantUpdate(SQLModel):
    """
    Model for updating existing participants.

    Contains optional fields that can be updated, with updated_by and
    updated_timestamp always required.
    """

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "from_attributes": True,
    }
    """Class to update a participant. All changed fields will be updated"""
    name: str | None = Field(
        default=None,
        max_length=30,
        schema_extra={"pattern": VALID_NAME_PATTERN},
    )
    display_name: str | None = Field(default=None, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    email: EmailStr | None = Field(default=None, max_length=200)
    state: Literal["ACTIVE", "TERMINATED"] | None = Field(
        default=None,
        description="For HUMANs: ACTIVE or TERMINATED",
        max_length=20,
    )
    external_reference: str | None = Field(
        default=None,
        description="Reference to an external system, e.g. active directory",
        max_length=500,
    )
    hashed_password: str | None = Field(
        default=None,
        description="Hashed password of HUMANS if local authentication is implemented",
        max_length=100,
    )
    update_count: int | None = Field(
        default=None,
        description="""Field to detect if a record was updated in the background.
    Use this before storing back the record. Must be used in combination with a row lock""",
    )
    updated_by: str = Field(..., max_length=30)
    updated_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    # Information about the relationships
    org_units: list[Participant] | None = Field(default=None)
    roles: list[Participant] | None = Field(default=None)
    proxy_of: list[Participant] | None = Field(default=None)

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

    @field_validator("name", "updated_by")
    @classmethod
    def to_uppercase(cls, v: str | None, _info: ValidationInfo) -> str | None:
        """
        Converts a field value to uppercase.

        Args:
            v: The value to convert
            _info: Validation info containing field context

        Returns:
            str or None: The uppercase value

        """
        return v.upper() if v else v


class RelatedParticipant(SQLModel):
    """
    Class to store information about participants that are related to another participant.

    Contains the relationship type and the related participant object.
    """

    relation_type: ParticipantRelationTypeLiteral
    participant: Participant
