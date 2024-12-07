"""
Repositories for participants
"""

import logging
from datetime import datetime, timezone
from typing import Literal, Optional, cast

from pydantic import ValidationError
from sqlalchemy import Select
from sqlmodel import Session, select, or_, delete, update

from ..models import (
    ParticipantModel,
    ParticipantRelationModel,
    Participant,
    ParticipantCreate,
    ParticipantState,
    ParticipantStateLiteral,
    ParticipantType,
    ParticipantUpdate,
    RelatedParticipant,
    ParticipantRelation,
    ParticipantRelationCreate,
    ParticipantRelationType,
)


from .base_class import RepositoryBase
from .participant_relation import (
    ParticipantRelationRepository,
    ParticipantRelationNotFoundError,
)

logger = logging.getLogger("participants")


class ParticipantNotFoundError(Exception):
    """Raised when a participant is not found."""

    pass


class ParticipantRepository(RepositoryBase):
    """The repository for participants"""

    def __init__(
        self,
        session: Session,
    ) -> None:
        super().__init__(session)

    def get_by_name(
        self,
        name: str,
        participant_type: ParticipantType,
        *,
        include_relations: bool = False,
        include_proxies: bool = False,
        raise_error_if_not_found: bool = False,
    ) -> Optional[Participant]:
        """Get a participant by name and type.
        include_proxies is only relevant if include_relations is True
        Returns None if not found."""
        if participant_type not in [str(m) for m in ParticipantType]:
            raise ValueError("Wrong participant_type: {participant_type}")
        try:
            result: ParticipantModel | None = self.session.exec(
                select(ParticipantModel).where(
                    ParticipantModel.name == name,
                    ParticipantModel.participant_type == participant_type,
                )
            ).one_or_none()
        except Exception as e:
            logger.exception(
                f"get_by_name: {participant_type=}, {name=} - {e}"
            )
            raise
        else:
            if result is None:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError
                else:
                    return None

            pati = Participant(**result.model_dump())
            if include_relations:
                self.set_relations(pati, include_proxies)
            return pati
        finally:
            pass

    def get_by_display_name(
        self,
        display_name: str,
        participant_type: ParticipantType,
        *,
        include_relations: bool = False,
        include_proxies: bool = False,
        raise_error_if_not_found: bool = False,
    ) -> Optional[Participant]:
        """Get a participant by display_name and type.
        include_proxies is only relevant if include_relations is True
        Returns None if not found."""
        if participant_type not in [str(m) for m in ParticipantType]:
            raise ValueError("Wrong participant_type: {participant_type}")
        try:
            result: ParticipantModel | None = self.session.exec(
                select(ParticipantModel).where(
                    ParticipantModel.name == display_name,
                    ParticipantModel.participant_type == participant_type,
                )
            ).one_or_none()
        except Exception as e:
            logger.exception(
                f"get_by_display_name: {participant_type=}, {display_name=} - {e}"
            )
            raise
        else:
            if result is None:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError
                else:
                    return None

            pati = Participant(**result.model_dump())
            if include_relations:
                self.set_relations(pati, include_proxies)
            return pati
        finally:
            pass

    def get_by_id(
        self,
        id_: int,
        *,
        include_relations: bool = False,
        include_proxies: bool = False,
        raise_error_if_not_found: bool = False,
    ) -> Optional[Participant]:
        """Get a participant by id
        Returns None if not found."""
        try:
            result: ParticipantModel | None = self.session.exec(
                select(ParticipantModel).where(ParticipantModel.id == id_)
            ).one_or_none()
        except Exception as e:
            logger.exception(f"get_by_id: {id=} - {e}")
            raise
        else:
            if result is None:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError
                else:
                    return None
            pati = Participant(**result.model_dump())
            if include_relations:
                self.set_relations(pati, include_proxies)
            return pati

    def exists(
        self,
        column: Literal["id", "name", "display_name"],
        value: int | str,
        participant_type: ParticipantType,
    ) -> bool | str:
        """query if the participant exists. All AK fields are possible.
        Returns:
            False if the participant does not exists
            The state (ACTIVE or TERMINATED) if the user exists
        """
        if participant_type not in [str(m) for m in ParticipantType]:
            raise ValueError("Wrong participant_type: {participant_type}")

        if column.lower() not in {"id", "name", "display_name"}:
            raise ValueError(
                f"Wrong column {column!a} provided. Allowed values are: id, name, display_name"
            )

        if column.lower() == "name":
            pati: Participant | None = self.get_by_name(
                cast(str, value),
                participant_type,
                raise_error_if_not_found=False,
            )
            return str(pati.state) if pati else False
        elif column.lower() == "id":
            pati = self.get_by_id(
                cast(int, value), raise_error_if_not_found=False
            )
            return str(pati.state) if pati else False
        elif column.lower() == "name":
            pati = self.get_by_name(
                cast(str, value),
                participant_type,
                raise_error_if_not_found=False,
            )
            return str(pati.state) if pati else False
        elif column.lower() == "display_name":
            pati = self.get_by_display_name(
                cast(str, value),
                participant_type,
                raise_error_if_not_found=False,
            )
            return str(pati.state) if pati else False
        else:
            return False

    def get_all(
        self,
        participant_type: str,
        *,
        include_relations: bool = False,
        only_active: bool = False,
    ) -> list[Participant]:
        """Get all participants of a type
        Returns [] if not found."""
        if participant_type not in [str(m) for m in ParticipantType]:
            raise ValueError("Wrong participant_type: {participant_type}")
        #
        try:
            if only_active:
                statement: Select = (
                    select(ParticipantModel)
                    .where(
                        ParticipantModel.participant_type == participant_type
                    )
                    .where(
                        or_(
                            ParticipantModel.state.is_(None),
                            ParticipantModel.state == "ACTIVE",
                        )
                    )
                    .order_by(ParticipantModel.display_name)
                )
            else:
                statement = select(ParticipantModel).where(
                    ParticipantModel.participant_type == participant_type
                )

            result: list[ParticipantModel] = self.session.exec(statement).all()
        except Exception as e:
            logger.exception(f"get_all_id: {id=} - {e}")
            raise
        else:
            participants = [Participant(**r.model_dump()) for r in result]

            if include_relations:
                _ = [self.set_relations(p) for p in participants]
            return participants

    def set_relations(
        self, participant: Participant, set_proxies: bool = False
    ) -> Participant:
        """Adds all relationships for a participant from the database to the object

        Args:
            participant: The participant to add the relations roles, org_units, proxy_of and proxies
            set_proxies: Whether to add proxies of this user or not. Defaults to False

        Returns: The passed participant"""
        with ParticipantRelationRepository(self.session) as rel_repository:
            relations: list[RelatedParticipant] = rel_repository.get(
                participant.id
            )
            if not relations:
                return participant

            participant.roles = []
            participant.org_units = []
            participant.proxy_of = []

            for r in relations:
                # Add only relationships if the related participant is active
                if r.participant.state != ParticipantState.ACTIVE.value:
                    continue

                match r.relation_type:
                    case "GRANT":
                        participant.roles.append(r.participant)
                    case "MEMBER OF":
                        participant.org_units.append(r.participant)
                    case "PROXY OF":
                        participant.proxy_of.append(r.participant)
                    case _:
                        pass

            if set_proxies is True:
                proxies: list[RelatedParticipant] = rel_repository.get_reverse(
                    participant.id, ("PROXY OF",)
                )
                if not proxies:
                    return participant
                participant.proxies = []
                for r in proxies:
                    if r.participant.state == ParticipantState.ACTIVE.value:
                        participant.proxies.append(r.participant)
        return participant

    def compute_effective_roles(self, participant: Participant) -> set[str]:
        """Computes effective roles for this participant based on the assigned roles, the roles assigned to the
        related ORGs or PROXYs.
        We go only one level deep into an org_unit or a proxy
        """
        # Collect  roles assigned to this participant
        # we start with a list and turn it into a set at the end
        logger.debug(
            f"Participant: {participant.name}, num_roles: {len(participant.roles)}, num_orgs: {len(participant.org_units)}, num_proxy_of: {len(participant.proxy_of)}"
        )
        effective_roles: set[str] = set()
        with ParticipantRelationRepository(self.session) as rel_repository:
            for g in participant.roles:
                effective_roles.add(g.name)
            for ou in participant.org_units:
                relations: Optional[list[RelatedParticipant]] = (
                    rel_repository.get(ou.id, relation_type=("GRANT",))
                )
                if not relations:
                    continue
                for r in relations:
                    effective_roles.add(r.participant.name)
            for p in participant.proxy_of:
                # get the roles granted to this participant
                relations = rel_repository.get(p.id, relation_type=("GRANT",))
                if not relations:
                    continue
                for r in relations:
                    effective_roles.add(r.participant.name)
        participant.effective_roles = effective_roles
        return participant.effective_roles

    def set_participant_state(
        self,
        participant: Participant,
        state: Optional[ParticipantStateLiteral],
        raise_error_if_not_found: bool = False,
    ) -> Participant:
        """Sets the status of the participant to the state
        Status of SYSTEM user cannot be terminated.
        """
        if participant.name == "SYSTEM":
            return participant

        try:
            result = self.session.exec(
                update(ParticipantModel)
                .where(ParticipantModel.id == participant.id)
                .values(state=state)
            )
            self.session.flush()
        except Exception as e:
            logger.exception(
                f"Failed to update state of {participant.id} to {state} - {e}"
            )
            raise
        else:
            if result.rowcount == 1:
                participant.state = state
            else:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError
            return participant

    def terminate_participant(
        self, participant: Participant, raise_error_if_not_found: bool = False
    ) -> Participant:
        """Sets the status of the participant to TERMINATED. Cannot be done for SYSTEM user"""
        if participant.name == "SYSTEM":
            return participant
        return self.set_participant_state(
            participant,
            ParticipantState.TERMINATED.value,
            raise_error_if_not_found,
        )

    def activate_participant(
        self, participant: Participant, raise_error_if_not_found: bool = False
    ) -> Participant:
        """Sets the status of the participant to ACTIVE. Cannot be done for SYSTEM user"""
        if participant.name == "SYSTEM":
            return participant
        return self.set_participant_state(
            participant,
            ParticipantState.ACTIVE.value,
            raise_error_if_not_found,
        )

    def update(
        self,
        id_: int,
        pati_update: ParticipantUpdate,
        *,
        raise_error_if_not_found: bool = False,
    ) -> Participant | None:
        """Updates all None fields in the database. Make sure the object is created with all values"""
        # exclude_unset delivers only the fields present at creation time, not the ones
        # modified afterward. We use these to get the ones initialized with None,
        # which will be updated to NULL.
        modified_fields = pati_update.model_dump(
            exclude_unset=True
        )  # was exclude_unset=True, exclude defaults gives us the updated_timestamp
        if "updated_timestamp" not in modified_fields:
            modified_fields["updated_timestamp"] = (
                pati_update.updated_timestamp or datetime.now(timezone.utc)
            )

        try:
            pati = self.session.exec(
                select(ParticipantModel).where(ParticipantModel.id == id_)
            ).one_or_none()
            if pati is None:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError
                else:
                    return None

            result = self.session.exec(
                (
                    update(ParticipantModel)
                    .where(ParticipantModel.id == id_)
                    .values(**modified_fields)
                )
            )

        except Exception as e:
            logger.exception(f"Error updating metadata. Error: {e}")
            raise e
        else:
            if result.rowcount == 0:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError
                else:
                    return None
            self.session.refresh(pati)
            return Participant(**pati.model_dump())

    def create(self, create: ParticipantCreate) -> Participant:
        """Creates a new participant and returns the Participant model with the id"""
        create.name = create.name.upper()
        model = ParticipantModel(**create.model_dump())
        try:
            self.session.add(model)
        except Exception as e:
            logger.exception(f"Failed: when creating participant - {e}")
            raise
        else:
            self.session.flush()
            self.session.refresh(model)
            try:
                pati = Participant(**model.model_dump())
            except ValidationError as e:
                logger.exception(f"Validation error {e}")
                raise
            return pati
        finally:
            pass

    def add_user(
        self,
        name: str,
        display_name: str,
        *,
        created_by: str,
        email: str | None = None,
        description: str | None = None,
        external_reference: str | None = None,
        hashed_password: str | None = None,
    ) -> Participant:
        """Creates a new user
        Returns the new users object"""
        for f in [name, display_name, created_by]:
            if f is None:
                raise ValueError(f"add_user: Missing mandatory field: {f}")

        create = ParticipantCreate(
            name=name,
            display_name=display_name,
            email=email,
            description=description,
            state=None,
            participant_type=ParticipantType.HUMAN.value,
            external_reference=external_reference,
            hashed_password=hashed_password,
            created_by=created_by,
        )
        try:
            return self.create(create)
        except Exception as e:
            logger.exception(f"Failed: when creating participant - {e}")
            raise

    def add_role(
        self,
        name: str,
        display_name: str,
        *,
        created_by: str,
        description: str | None = None,
    ) -> Participant:
        """Creates a new role
        Returns the new roles object"""
        for f in [name, display_name, created_by]:
            if f is None:
                raise ValueError(f"add_user: Missing mandatory field: {f}")

        create = ParticipantCreate(
            name=name,
            display_name=display_name,
            description=description,
            state=None,
            participant_type=ParticipantType.ROLE.value,
            created_by=created_by,
        )
        try:
            return self.create(create)
        except Exception as e:
            logger.exception(f"Failed: when creating participant - {e}")
            raise

    def add_org(
        self,
        name: str,
        display_name: str,
        *,
        created_by: str,
        email: str | None = None,
        description: str | None = None,
        external_reference: str | None = None,
    ) -> Participant:
        """Creates a new org
        Returns the new orgs object"""
        for f in [name, display_name, created_by]:
            if f is None:
                raise ValueError(f"add_user: Missing mandatory field: {f}")

        create = ParticipantCreate(
            name=name,
            display_name=display_name,
            description=description,
            state=None,
            participant_type=ParticipantType.ORG_UNIT.value,
            external_reference=external_reference,
            created_by=created_by,
            email=email,
        )
        try:
            return self.create(create)
        except Exception as e:
            logger.exception(f"Failed: when creating participant - {e}")
            raise

    def add_relation(
        self,
        participant: Participant,
        pati2_id: int,
        relation_type: ParticipantRelationType,
        created_by: str,
    ) -> ParticipantRelation:
        """Adds a relation to another participant
        Returns the number of affected rows: 0 or 1
        """
        with ParticipantRelationRepository(self.session) as rel_repo:
            create = ParticipantRelationCreate(
                pati1_id=participant.id,
                pati2_id=pati2_id,
                relation_type=relation_type,
                created_by=created_by,
            )
            if create.created_timestamp is None:
                create.created_timestamp = datetime.now(timezone.utc)
            return cast(ParticipantRelation, rel_repo.create(create, True))

    def add_reverse_relation(
        self,
        participant: Participant,  # p2
        pati1_id: int,
        relation_type: ParticipantRelationType,
        created_by: str,
    ) -> ParticipantRelation:
        """Adds a relation to this participant
        Returns the number of created rows: 0 or 1
        """
        with ParticipantRelationRepository(self.session) as rel_repo:
            create = ParticipantRelationCreate(
                pati1_id=pati1_id,
                pati2_id=participant.id,
                relation_type=relation_type,
                created_by=created_by,
            )
            if create.created_timestamp is None:
                create.created_timestamp = datetime.now(timezone.utc)
            return cast(ParticipantRelation, rel_repo.create(create, True))

    def delete_relation(
        self,
        participant: Participant,
        pati2_id: int,
        relation_type: ParticipantRelationType,
        raise_error_if_not_found: bool = False,
    ) -> None:
        """Deletes a relation to another participant.

        Returns the number of affected rows ( 1 or 0)
        """
        if relation_type not in [str(pt) for pt in ParticipantRelationType]:
            raise ValueError(f"Wrong relation_type: {relation_type=}")

        try:
            result = self.session.exec(
                delete(ParticipantRelationModel).where(
                    ParticipantRelationModel.pati1_id == participant.id,
                    ParticipantRelationModel.pati2_id == pati2_id,
                    ParticipantRelationModel.relation_type == relation_type,
                )
            )
            self.session.flush()
        except Exception as e:
            logger.exception(
                f"Error deleting relation of pati1 {participant.id=}: {e}"
            )
            raise e
        else:
            if result.rowcount == 0 and raise_error_if_not_found:
                raise ParticipantRelationNotFoundError
            return

    def delete_reverse_relation(
        self,
        participant: Participant,
        pati1_id: int,
        relation_type: ParticipantRelationType,
        raise_error_if_not_found: bool = False,
    ) -> int:
        """Deletes a relation to this participant.
        Returns the number of affected rows ( 1 or 0)"""
        if relation_type not in [str(pt) for pt in ParticipantRelationType]:
            raise ValueError(f"Wrong relation_type: {relation_type=}")
        try:
            result = self.session.exec(
                delete(ParticipantRelationModel).where(
                    ParticipantRelationModel.pati2_id == participant.id,
                    ParticipantRelationModel.pati1_id == pati1_id,
                    ParticipantRelationModel.relation_type == relation_type,
                )
            )
            self.session.flush()

        except Exception as e:
            logger.exception(
                f"Error deleting reverse relation of pati2 {participant.id=}: {e}"
            )
            raise e
        else:
            if result.rowcount == 0 and raise_error_if_not_found:
                raise ParticipantRelationNotFoundError
            return result.rowcount

    def delete_all_participant_relations(
        self,
        participant_id: int,
    ) -> int:
        """Deletes all relations of this participant
        Returns the number of affected rows"""
        try:
            result = self.session.exec(
                delete(ParticipantRelationModel).where(
                    or_(
                        ParticipantRelationModel.pati1_id == participant_id,
                        ParticipantRelationModel.pati2_id == participant_id,
                    )
                )
            )

        except Exception as e:
            logger.exception(
                f"Error deleting all relations of participant {participant_id=} {e}"
            )
            raise e
        else:
            return result.rowcount
        finally:
            pass
