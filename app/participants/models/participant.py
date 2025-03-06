import re
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal, Optional, TypeAlias

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
    """

    HUMAN = "HUMAN"
    ROLE = "ROLE"
    ORG_UNIT = "ORG_UNIT"
    SYSTEM = "SYSTEM"


ParticipantTypeLiteral: TypeAlias = Literal[
    "HUMAN",
    "ROLE",
    "ORG_UNIT",
    "SYSTEM",
]


class ParticipantState(StrEnum):
    """
    Enum for the participant state.
    """

    ACTIVE = "ACTIVE"
    TERMINATED = "TERMINATED"


ParticipantStateLiteral: TypeAlias = Literal["ACTIVE", "TERMINATED"]
# ParticipantState.ACTIVE, ParticipantState.TERMINATED
# ]


def is_valid_name(name: str) -> bool:
    """
    Checks if a name is valid.
    A valid name must:
    - Start with a letter (uppercase or lowercase)
    - Contain only letters (uppercase or lowercase), digits, underscores and hyphens
    - Be between 2 and 20 characters long
    """
    pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{1,30}$")
    return bool(pattern.match(name))


class ParticipantBase(SQLModel):
    """Participant Base Model is used to read data from the database"""

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "from_attributes": True,
    }

    name: str = Field(..., max_length=30)
    display_name: str = Field(..., max_length=60)
    description: Optional[str] = Field(default=None, max_length=500)
    email: Optional[str] = Field(default=None, max_length=200)
    participant_type: ParticipantTypeLiteral = Field(..., max_length=30)

    state: Optional[ParticipantStateLiteral] = Field(
        default=None, max_length=20, description="ACTIVE or TERMINATED"
    )
    external_reference: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reference to an external system, e.g. active directory",
    )
    hashed_password: Optional[str] = Field(
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
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def get_field_names(cls, alias: bool = False) -> list[str]:
        properties = cls.model_json_schema(alias).get("properties", {})
        return list(properties.keys())

    @field_validator("state", "participant_type", mode="before")
    @classmethod
    def enum_to_string(cls, v: str, info: ValidationInfo) -> Optional[str]:
        if info.field_name == "state" and v is None:
            return "ACTIVE"
        return str(v) if isinstance(v, StrEnum) else v

    @field_validator(
        "email",
    )
    @classmethod
    def check_valid_email(
        cls, v: str | None, info: ValidationInfo
    ) -> str | None:
        """Checks the email"""
        if v and not validate_email(v):
            raise ValueError(
                f"Invalid email address: {v!a} in {info.field_name}"
            )
        return v

    @field_validator("name", "created_by")
    @classmethod
    def to_uppercase(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Uppercases a field"""
        return v.upper() if v else v


class ParticipantModel(ParticipantBase, table=True):
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
                "extend_existing": True,  # This should fix the error when rerun streamlit that the model exists
            }
            if schema
            else {"extend_existing": True}
        ),
    )
    id: int | None = Field(default=None, primary_key=True)
    # redefine participant_type and state to strings to make the model work
    participant_type: str = Field(..., max_length=30)

    state: str | None = Field(
        default=None, max_length=20, description="ACTIVE or TERMINATED"
    )

    updated_by: str | None = Field(default=None, max_length=30)
    updated_timestamp: datetime | None = Field(default=None)


class Participant(ParticipantBase):
    """Schema class for participants"""

    id: int = Field(...)
    created_by: str = Field(..., max_length=30)
    created_timestamp: datetime = Field(
        ..., default_factory=lambda: datetime.now(timezone.utc)
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
        return "ACTIVE" if not v else v

    @staticmethod
    def find_by_id(
        participants: list["Participant"], participant_id: int
    ) -> Optional["Participant"]:
        """Get a participant by his id"""
        return next((p for p in participants if p.id == participant_id), None)

    @staticmethod
    def find_by_name(
        participants: list["Participant"], name: str, participant_type: str
    ) -> Optional["Participant"]:
        """Get a participant by his name and participant_type"""
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
        """Get a participant by his display name and participant_type"""
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

    @field_validator("name")
    @classmethod
    def validate_name(
        cls, v: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        if v and not is_valid_name(v):
            raise ValueError(f"Invalid name: {v}")
        return v.upper() if v else v


class ParticipantUpdate(SQLModel):
    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "from_attributes": True,
    }
    """Class to update a participant. All changed fields will be updated"""
    name: Optional[str] = Field(default=None)
    display_name: Optional[str] = Field(default=None, max_length=60)
    description: Optional[str] = Field(default=None, max_length=500)
    email: Optional[EmailStr] = Field(default=None, max_length=200)
    state: Optional[Literal["ACTIVE", "TERMINATED"]] = Field(
        default=None,
        description="For HUMANs: ACTIVE or TERMINATED",
        max_length=20,
    )
    external_reference: Optional[str] = Field(
        default=None,
        description="Reference to an external system, e.g. active directory",
        max_length=500,
    )
    hashed_password: Optional[str] = Field(
        default=None,
        description="Hashed password of HUMANS if local authentication is implemented",
        max_length=100,
    )
    update_count: Optional[int] = Field(
        default=None,
        description="""Field to detect if a record was updated in the background.
    Use this before storing back the record. Must be used in combination with a row lock""",
    )
    updated_by: str = Field(..., max_length=30)
    updated_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Information about the relationships
    org_units: Optional[list[Participant]] = Field(default=None)
    roles: Optional[list[Participant]] = Field(default=None)
    proxy_of: Optional[list[Participant]] = Field(default=None)

    @classmethod
    def get_field_names(cls, alias: bool = False) -> list[str]:
        properties = cls.model_json_schema(alias).get("properties", {})
        return list(properties.keys())

    @field_validator("name", "updated_by")
    @classmethod
    def to_uppercase(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Uppercases a field"""
        return v.upper() if v else v


class RelatedParticipant(SQLModel):
    """Class to store the participants I am related with"""

    relation_type: ParticipantRelationTypeLiteral
    participant: Participant
