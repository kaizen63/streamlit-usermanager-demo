"""
Repositories for participants and participant relations.

This module contains repository classes for managing participant relationships
in the application. It provides functionality to create, retrieve, and check
existence of relationships between participants.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.sql.selectable import Select

from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import aliased
from sqlmodel import Session, or_, select

from ..models import (  # noqa: TID252
    ParticipantModel,
    ParticipantRelation,
    ParticipantRelationCreate,
    ParticipantRelationModel,
    RelatedParticipant,
)
from .base_class import LOGGER_NAME, RepositoryBase

if TYPE_CHECKING:
    ParticipantModel2 = ParticipantModel  # for mypy
else:
    ParticipantModel2 = aliased(ParticipantModel)  # for runtime use
# from sqlalchemy.dialects import sqlite


logger = logging.getLogger(LOGGER_NAME)


class ParticipantRelationNotFoundError(Exception):
    """Exception raised when a participant relation is not found in the database."""


class ParticipantRelationRepository(RepositoryBase):
    """
    Repository to store and retrieve participant relations.

    This class handles database operations for participant relationships,
    including creating new relationships, checking if relationships exist,
    and retrieving relationships for a given participant.

    Attributes:
        session: SQLAlchemy database session for performing database operations

    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        """
        Initialize the repository with a database session.

        Args:
            session: SQLAlchemy session for database operations

        """
        super().__init__(session)

    def get(
        self,
        participant_id: int,
        relation_type: tuple[str, ...] = ("MEMBER OF", "GRANT", "PROXY OF"),
    ) -> list[RelatedParticipant]:
        """
        Returns all outgoing relationships for a participant.

        This method retrieves all relationships where the given participant
        is the source participant (pati1).

        Relation types include:
            - MEMBER OF: Organizations the participant is a member of
            - GRANT: Roles granted to the participant
            - PROXY OF: Participants this participant is a proxy for

        Args:
            participant_id: The ID of the participant to find relationships for
            relation_type: Tuple of relation types to filter by

        Returns:
            List of RelatedParticipant objects representing the relationships

        Raises:
            Exception: If a database error occurs

        """
        # Define an aliases for the related table
        # DO NOT USE 2 ALIASES -> BUG IN SQLALCHEMY
        try:
            statement: Select = (
                select(
                    ParticipantRelationModel,
                    ParticipantModel,
                    ParticipantModel2,
                )
                .join(
                    ParticipantRelationModel,
                    ParticipantModel.id == ParticipantRelationModel.pati1_id,
                )
                .join(
                    ParticipantModel2,
                    ParticipantModel2.id == ParticipantRelationModel.pati2_id,
                )
                .where(
                    ParticipantRelationModel.pati1_id == participant_id,
                    ParticipantModel.id == participant_id,
                    ParticipantRelationModel.relation_type.in_(relation_type),
                    or_(
                        ParticipantModel.state.is_(None),
                        ParticipantModel.state == "ACTIVE",
                    ),
                )
            )
            # sql_text = str(statement.compile(dialect=sqlite.dialect()))

            results: Sequence[
                tuple[
                    ParticipantRelationModel,
                    ParticipantModel,
                    ParticipantModel,
                ]
            ] = self.session.exec(statement).all()
        except NoResultFound:
            return []

        except Exception as e:
            logger.exception(f"get: {participant_id=}, {relation_type=} {e}")
            raise
        else:
            if len(results) == 0:
                return []
            retval = [
                RelatedParticipant(
                    relation_type=rel.relation_type,
                    participant=participant2,
                )
                for rel, participant1, participant2 in results
            ]
            return retval

    def get_reverse(
        self,
        participant_id: int,
        relation_type: tuple[str, ...] = ("MEMBER OF", "GRANT", "PROXY OF"),
    ) -> list[RelatedParticipant]:
        """
        Returns all incoming relationships for a participant.

        This method retrieves all relationships where the given participant
        is the target participant (pati2).

        Relation types include:
            - MEMBER OF: Members that belong to this organization
            - GRANT: Participants who have been granted this role
            - PROXY OF: Proxies of this participant

        Args:
            participant_id: The ID of the participant to find relationships for
            relation_type: Tuple of relation types to filter by

        Returns:
            List of RelatedParticipant objects representing the relationships

        Raises:
            Exception: If a database error occurs

        """
        # ParticipantModel1 = aliased(ParticipantModel)
        ParticipantModel2 = aliased(ParticipantModel)  # noqa: N806
        try:
            statement: Select = (
                select(
                    ParticipantRelationModel,
                    ParticipantModel,
                    ParticipantModel2,
                )
                .join(
                    ParticipantRelationModel,
                    ParticipantModel.id == ParticipantRelationModel.pati1_id,
                )
                .join(
                    ParticipantModel2,
                    ParticipantModel2.id == ParticipantRelationModel.pati2_id,
                )
                .where(
                    ParticipantRelationModel.pati2_id == participant_id,
                    ParticipantRelationModel.relation_type.in_(relation_type),
                    or_(
                        ParticipantModel.state.is_(None),
                        ParticipantModel.state == "ACTIVE",
                    ),
                )
            )
            # sql_text = str(statement.compile(dialect=sqlite.dialect()))

            results: Sequence[
                tuple[ParticipantRelationModel, ParticipantModel, ParticipantModel]
            ] = self.session.exec(statement).all()
        except NoResultFound:
            return []

        except Exception as e:
            logger.exception(f"get: {participant_id=}, {relation_type=} {e}")
            raise
        else:
            if len(results) == 0:
                return []
            retval = [
                RelatedParticipant(
                    relation_type=rel.relation_type,
                    participant=participant1,
                )
                for rel, participant1, participant2 in results
            ]
            return retval

    def exists(
        self,
        pati_rel: ParticipantRelation,
    ) -> bool:
        """
        Checks if a participant relation exists in the database.

        Args:
            pati_rel: The participant relation to check for

        Returns:
            True if the relation exists, False otherwise

        Raises:
            Exception: If a database error occurs other than NoResultFound

        """
        try:
            statement: Select = select(ParticipantRelationModel).where(
                ParticipantRelationModel.pati1_id == pati_rel.pati1_id,
                ParticipantRelationModel.pati2_id == pati_rel.pati2_id,
                ParticipantRelationModel.relation_type == pati_rel.relation_type,
            )
            result: ParticipantRelationModel = self.session.exec(statement).one()
        except NoResultFound:
            return False
        except Exception as e:
            logger.exception(f"exists: {id=} - {e}")
            raise
        else:
            return bool(result)

    def create(
        self,
        participant_relation: ParticipantRelationCreate,
        raise_error_on_duplicate: bool = False,
    ) -> ParticipantRelation | None:
        """
        Creates a new participant relation in the database.

        Args:
            participant_relation: The participant relation to create
            raise_error_on_duplicate: If True, raises IntegrityError when
                                     attempting to create a duplicate relation.
                                     If False, returns None instead.

        Returns:
            The created ParticipantRelation object, or None if the relation
            already exists and raise_error_on_duplicate is False

        Raises:
            IntegrityError: If the relation already exists and raise_error_on_duplicate is True
            Exception: If any other database error occurs

        """
        model: ParticipantRelationModel = ParticipantRelationModel(
            **participant_relation.model_dump(),
        )
        try:
            self.session.add(model)
        except IntegrityError as e:
            if raise_error_on_duplicate:
                logger.exception(
                    f"Failed: when creating participant relation. Relation already exists - {e}",
                )
                raise
            logger.error(
                f"Failed: when creating participant relation. Relation already exists - {e}",
            )
            return None

        except Exception as e:
            logger.exception(f"Failed: when creating participant relation. - {e}")
            raise
        else:
            self.session.flush()
            self.session.refresh(model)

            return ParticipantRelation(**model.model_dump())
