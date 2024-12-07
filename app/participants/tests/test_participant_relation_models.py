from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ..models import (
    ParticipantRelation,
    ParticipantRelationCreate,
    ParticipantRelationType,
    ParticipantType,
)


def test_participant_relation_model() -> None:
    r = ParticipantRelation.model_validate(
        {
            "id": 1,
            "pati1_id": 20,
            "pati2_id": 30,
            "relation_type": ParticipantRelationType.MEMBER_OF,
            "created_by": "admin",
        }
    )
    assert r.id == 1
    assert r.pati1_id == 20
    assert r.pati2_id == 30
    assert r.relation_type == ParticipantRelationType.MEMBER_OF
    assert r.created_by == "ADMIN"
    assert r.created_timestamp is not None


def test_participant_relation_wrong_rel_type() -> None:
    with pytest.raises(ValidationError):
        _ = ParticipantRelation.model_validate(
            {
                "id": 1,
                "pati1_id": 20,
                "pati2_id": 30,
                "relation_type": "belongs to me",
                "created_by": "admin",
            }
        )


def test_participant_relation_missing_fields() -> None:
    with pytest.raises(ValidationError):
        _ = ParticipantRelation.model_validate(
            {
                "id": 1,
                "pati1_id": 10,
                "relation_type": ParticipantRelationType.GRANT,
                "created_by": "admin",
            }
        )


def test_participant_relation_create() -> None:
    r = ParticipantRelationCreate.model_validate(
        {
            "pati1_id": 10,
            "pati2_id": 20,
            "relation_type": ParticipantRelationType.GRANT,
            "created_by": "admin",
        }
    )
    assert r.pati1_id == 10
    assert r.pati2_id == 20
    assert r.relation_type == "GRANT"
    assert r.created_by == "ADMIN"
    assert r.created_timestamp is not None

    # quick check on the repr
    rpr = repr(r)
    assert len(rpr) > 0


def test_participant_relation_create_wrong_rel_type() -> None:
    with pytest.raises(ValidationError):
        _ = ParticipantRelationCreate.model_validate(
            {
                "pati1_id": 10,
                "pati2_id": 20,
                "relation_type": "xyuuy",
                "created_by": "admin",
            }
        )


def test_participant_relation_create_wrong_missing_field() -> None:
    with pytest.raises(ValidationError):
        _ = ParticipantRelationCreate.model_validate(
            {
                "pati2_id": 20,
                "relation_type": "xyuuy",
                "created_by": "admin",
            }
        )
