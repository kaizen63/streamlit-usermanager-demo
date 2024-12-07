"""
Repositories for participants and participant relations
"""

import logging

from sqlmodel import Session, select, or_
from sqlalchemy.exc import NoResultFound, IntegrityError
from sqlalchemy.orm import aliased
from sqlalchemy import Select

# from sqlalchemy.dialects import sqlite

from ..models import (
    ParticipantModel,
    ParticipantRelationModel,
    RelatedParticipant,
    ParticipantRelation,
    ParticipantRelationCreate,
)
from .base_class import RepositoryBase

logger = logging.getLogger("participants")


class ParticipantRelationNotFoundError(Exception):
    pass


class ParticipantRelationRepository(RepositoryBase):
    """Repository to store participant relations"""

    def __init__(
        self,
        session: Session,
    ) -> None:
        super().__init__(session)

    def get(
        self,
        participant_id: int,
        relation_type: tuple[str, ...] = ("MEMBER OF", "GRANT", "PROXY OF"),
    ) -> list[RelatedParticipant]:
        """Returns all relationships for this participant.
        HUMAN: Where I am member of
        GRANT: Role granted to
        ORG UNIT: The Org units the pati belongs to.
        PROXY OF: Pati I am proxy of
        """
        # Define an aliases for the related table
        # DO NOT USE 2 ALIASES -> BUG IN SQLALCHEMY
        # ParticipantModel1 = aliased(ParticipantModel)
        ParticipantModel2 = aliased(ParticipantModel)
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

            results = self.session.exec(statement).all()
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
                    relation_type=rel.relation_type, participant=participant2
                )
                for rel, participant1, participant2 in results
            ]
            return retval

    def get_reverse(
        self,
        participant_id: int,
        relation_type: tuple[str, ...] = ("MEMBER OF", "GRANT", "PROXY OF"),
    ) -> list[RelatedParticipant]:
        """Returns all relationships this  participant belongs to
        GRANT: Who has this role granted
        ORG UNIT: who belongs to this org unit
        PROXY OF: The proxies of me
        """
        # ParticipantModel1 = aliased(ParticipantModel)
        ParticipantModel2 = aliased(ParticipantModel)
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

            results = self.session.exec(statement).all()
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
                    relation_type=rel.relation_type, participant=participant1
                )
                for rel, participant1, participant2 in results
            ]
            return retval

    def exists(
        self,
        pati_rel: ParticipantRelation,
    ) -> bool:
        """Returns True if a pati relation exists, else False"""
        try:
            statement: Select = select(ParticipantRelationModel).where(
                ParticipantRelationModel.pati1_id == pati_rel.pati1_id,
                ParticipantRelationModel.pati2_id == pati_rel.pati2_id,
                ParticipantRelationModel.relation_type
                == pati_rel.relation_type,
            )
            result: ParticipantRelationModel = self.session.exec(
                statement
            ).one()
        except NoResultFound:
            return False
        except Exception as e:
            logger.exception(f"exists: {id=} - {e}")
            raise
        else:
            if result:
                return True
            else:
                return False

    def create(
        self,
        participant_relation: ParticipantRelationCreate,
        raise_error_on_duplicate: bool = False,
    ) -> ParticipantRelation | None:
        """Adds a relation to another participant. Raises IntegrityError on duplicate record"""
        model: ParticipantRelationModel = ParticipantRelationModel(
            **participant_relation.model_dump()
        )
        try:
            self.session.add(model)
        except IntegrityError as e:
            if raise_error_on_duplicate:
                logger.exception(
                    f"Failed: when creating participant relation. Relation already exists - {e}"
                )
                raise
            else:
                logger.error(
                    f"Failed: when creating participant relation. Relation already exists - {e}"
                )
                return None

        except Exception as e:
            logger.exception(
                f"Failed: when creating participant relation. - {e}"
            )
            raise
        else:
            self.session.flush()
            self.session.refresh(model)

            return ParticipantRelation(**model.model_dump())
