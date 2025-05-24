"""
Participant repositories package.

This package provides repository classes for managing participants and their relationships
in the application. It exports repository classes for participants and participant relations,
along with their associated exceptions.

Exported classes:
    - ParticipantRepository: Repository for managing participant entities
    - ParticipantRelationRepository: Repository for managing relationships between participants

Exported exceptions:
    - ParticipantNotFoundError: Raised when a participant is not found in the database
    - ParticipantRelationNotFoundError: Raised when a participant relation is not found
    - IntegrityError: SQLAlchemy exception for database integrity violations
"""

from sqlalchemy.exc import IntegrityError

from .participant import ParticipantNotFoundError, ParticipantRepository
from .participant_relation import (
    ParticipantRelationNotFoundError,
    ParticipantRelationRepository,
)

__all__ = [
    "IntegrityError",
    "ParticipantNotFoundError",
    "ParticipantRelationNotFoundError",
    "ParticipantRelationRepository",
    "ParticipantRepository",
]
