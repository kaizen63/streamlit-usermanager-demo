from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ..models import (  # noqa: TID252
    Participant,
    ParticipantCreate,
    ParticipantState,
    ParticipantType,
    ParticipantUpdate,
    is_valid_name,
)


def test_participant_model() -> None:
    now = datetime.now(UTC)
    p = Participant.model_validate(
        {
            "id": 1,
            "name": "test",
            "display_name": " Display, Name ",  # whitespaces added intentionally
            "email": "efpyi@example.com",
            "participant_type": ParticipantType.HUMAN,
            "state": ParticipantState.ACTIVE,
            "created_by": "admin",
            "created_timestamp": now,
            "external_reference": None,
        }
    )
    assert p.id == 1
    assert p.name == "TEST"
    assert p.display_name == "Display, Name"
    assert p.email == "efpyi@example.com"
    assert p.participant_type == ParticipantType.HUMAN
    assert p.state == "ACTIVE"
    assert p.created_by == "ADMIN"
    assert p.created_timestamp == now
    assert p.external_reference is None
    assert p.updated_by is None
    assert p.updated_timestamp is None


def test_participant_model_wrong_name_start() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        _ = ParticipantCreate.model_validate(
            {
                "id": 1,
                "name": "0abc",
                "display_name": "Display, Name",
                "email": "efpyi@example.com",
                "participant_type": ParticipantType.HUMAN,
                "state": "ACTIVE",
                "created_by": "admin",
                "created_timestamp": now,
                "external_reference": None,
            }
        )
    with pytest.raises(ValidationError):
        _ = ParticipantUpdate.model_validate(
            {
                "name": "0abc",
            }
        )


def test_participant_model_wrong_name_length() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        _ = ParticipantCreate.model_validate(
            {
                "id": 1,
                "name": "a123456789012345678901234567890",
                "display_name": "Display, Name",
                "email": "efpyi@example.com",
                "participant_type": ParticipantType.HUMAN,
                "state": "ACTIVE",
                "created_by": "admin",
                "created_timestamp": now,
                "external_reference": None,
            }
        )

    with pytest.raises(ValidationError):
        _ = ParticipantUpdate.model_validate(
            {
                "name": "a123456789012345678901234567890",
            }
        )


def test_participant_model_wrong_email() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        _ = Participant.model_validate(
            {
                "id": 1,
                "name": "test",
                "display_name": "Display, Name",
                "email": "efpyi_example.com",
                "participant_type": ParticipantType.HUMAN,
                "state": "ACTIVE",
                "created_by": "admin",
                "created_timestamp": now,
                "external_reference": None,
            }
        )


def test_participant_model_missing_fields() -> None:
    with pytest.raises(ValidationError):
        _ = Participant.model_validate(
            {
                "id": 1,
                "display_name": "Display, Name",
                "email": "efpyi@example.com",
                "participant_type": ParticipantType.HUMAN,
                "state": "ACTIVE",
                "external_reference": None,
            }
        )


def test_participant_create() -> None:
    now = datetime.now(UTC)
    p = ParticipantCreate.model_validate(
        {
            "name": "test",
            "display_name": "Display, Name",
            "email": "efpyi@example.com",
            "participant_type": "HUMAN",
            "state": "ACTIVE",
            "created_by": "admin",
            "created_timestamp": now,
            "external_reference": None,
        }
    )
    assert p.name == "TEST"
    assert p.display_name == "Display, Name"
    assert p.email == "efpyi@example.com"
    # assert p.participant_type == ParticipantType.HUMAN
    assert p.state == "ACTIVE"
    assert p.created_by == "ADMIN"
    assert p.created_timestamp == now
    assert p.external_reference is None

    p2 = ParticipantCreate.model_validate(
        {
            "name": "test",
            "display_name": "Display, Name",
            "email": "efpyi@example.com",
            "participant_type": ParticipantType.ROLE,
            "created_by": "admin",
            "created_timestamp": now,
        }
    )
    assert p2.name == "TEST"
    assert p2.display_name == "Display, Name"
    assert p2.email == "efpyi@example.com"
    assert p2.participant_type == ParticipantType.ROLE
    assert p2.state is None
    assert p2.created_by == "ADMIN"
    assert p2.created_timestamp == now
    assert p2.external_reference is None

    p3 = ParticipantCreate.model_validate(
        {
            "name": "test",
            "display_name": "Display, Name",
            "email": "efpyi@example.com",
            "participant_type": ParticipantType.ORG_UNIT,
            "created_by": "admin",
            "created_timestamp": now,
        }
    )
    assert p3.name == "TEST"
    assert p3.display_name == "Display, Name"
    assert p3.email == "efpyi@example.com"
    assert p3.participant_type == ParticipantType.ORG_UNIT
    assert p3.state is None
    assert p3.created_by == "ADMIN"
    assert p3.created_timestamp == now
    assert p3.external_reference is None

    # quick check on the repr
    r = repr(p3)
    assert len(r) > 0


def test_participant_create_wrong_ptype() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        _ = ParticipantCreate.model_validate(
            {
                "name": "test",
                "display_name": "Display, Name",
                "email": "efpyi@example.com",
                "participant_type": "WOMAN",
                "state": "ACTIVE",
                "created_by": "admin",
                "created_timestamp": now,
                "external_reference": None,
            }
        )


def test_participant_create_wrong_state() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        _ = ParticipantCreate.model_validate(
            {
                "name": "test",
                "display_name": "Display, Name",
                "email": "efpyi@example.com",
                "participant_type": ParticipantType.HUMAN,
                "state": "SICK",
                "created_by": "admin",
                "created_timestamp": now,
                "external_reference": None,
            }
        )


def test_participant_update() -> None:
    now = datetime.now(UTC)
    p = ParticipantUpdate.model_validate(
        {
            "name": "test1",
            "display_name": "Display, Name",
            "email": "efpyi@example.com",
            "state": "ACTIVE",
            "external_reference": None,
            "updated_by": "admin",
            "updated_timestamp": now,
        }
    )
    assert p.name == "TEST1"
    assert p.display_name == "Display, Name"
    assert p.email == "efpyi@example.com"
    assert p.state == "ACTIVE"
    assert p.updated_by == "ADMIN"
    assert p.updated_timestamp == now
    assert p.external_reference is None

    # updated_by must be set automatically
    p2 = ParticipantUpdate.model_validate(
        {
            "name": "test2",
            "display_name": "Display, Name",
            "email": "efpyi@example.com",
            "state": "ACTIVE",
            "external_reference": None,
            "updated_by": "admin",
        }
    )
    assert p2.name == "TEST2"
    assert p2.display_name == "Display, Name"
    assert p2.email == "efpyi@example.com"
    assert p2.state == "ACTIVE"
    assert p2.updated_by == "ADMIN"
    assert p.updated_timestamp is not None
    assert p.external_reference is None


def test_participant_update_ptype() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        _ = ParticipantUpdate.model_validate(
            {
                "name": "test3",
                "display_name": "Display, Name",
                "email": "efpyi@example.com",
                "participant_type": "HUMAN",
                "state": "ACTIVE",
                "external_reference": None,
                "updated_by": "admin",
                "updated_timestamp": now,
            }
        )


def test_participant_update_wrong_state() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        _ = ParticipantUpdate.model_validate(
            {
                "name": "test4",
                "display_name": "Display, Name",
                "email": "efpyi@example.com",
                "state": "SICK",
                "external_reference": None,
                "updated_by": "admin",
                "updated_timestamp": now,
            }
        )


def test_participant_update_wrong_name() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        _ = ParticipantUpdate.model_validate(
            {
                "name": "0a",
                "display_name": "Display, Name",
                "email": "efpyi@example.com",
                "state": "TERMINATED",
                "external_reference": None,
                "updated_by": "admin",
                "updated_timestamp": now,
            }
        )


def test_participant_update_wrong_email() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        _ = ParticipantUpdate.model_validate(
            {
                "name": "test5",
                "display_name": "Display, Name",
                "email": "efpyi_example.com",
                "external_reference": None,
                "updated_by": "admin",
                "updated_timestamp": now,
            }
        )


def test_participant_wrong_name() -> None:
    with pytest.raises(ValidationError):  # noqa: PT012
        _ = ParticipantCreate.model_validate(
            {
                "id": 1,
                "name": "1234",
                "display_name": "Display, Name",
                "participant_type": ParticipantType.HUMAN,
                "state": ParticipantState.ACTIVE,
                "created_by": "admin",
            }
        )
        _ = ParticipantCreate.model_validate(
            {
                "id": 1,
                "name": "ABC?",
                "display_name": "Display, Name",
                "participant_type": ParticipantType.HUMAN,
                "state": ParticipantState.ACTIVE,
                "created_by": "admin",
            }
        )
        _ = ParticipantCreate.model_validate(
            {
                "id": 1,
                "name": "ABC-def",
                "display_name": "Display, Name",
                "participant_type": ParticipantType.HUMAN,
                "state": ParticipantState.ACTIVE,
                "created_by": "admin",
            }
        )


@pytest.mark.parametrize(
    ("name", "display_name", "participant_type", "created_by", "expected_result"),
    [
        (
            "test-user",
            "User, Test",
            ParticipantType.HUMAN,
            "user1",
            "TEST-USER",
        ),
        (
            "test-role",
            "Role, Test",
            ParticipantType.ROLE,
            "user2T",
            "TEST-ROLE",
        ),
        (
            "test-org",
            "Org, Test",
            ParticipantType.ORG_UNIT,
            "user3",
            "TEST-ORG",
        ),
    ],
)
def test_pati_model_create(
    name: str,
    display_name: str,
    participant_type: str,
    created_by: str,
    expected_result: str,
) -> None:
    create = ParticipantCreate(
        name=name,
        display_name=display_name,
        participant_type=participant_type,
        created_by=created_by,
    )
    assert create.created_timestamp is not None
    assert create.name == name.upper()
    assert create.display_name == display_name
    assert create.participant_type == participant_type
    assert create.created_by == created_by.upper()
    assert create.name == expected_result


@pytest.mark.parametrize(
    ("name", "expected_result"),
    [
        (None, False),
        ("", False),
        ("_abcdefg", False),
        ("0abcdefg", False),
        ("a", False),
        ("ab", True),
        ("poitsch", True),
        ("ab_cde-fgh", True),
        ("ab_cde-fgh?", False),
        ("a12345678901234567890123456789", True),
        ("a123456789012345678901234567890", False),
    ],
)
def test_is_valid_name(name: str, expected_result: bool) -> None:
    assert is_valid_name(name) == expected_result
