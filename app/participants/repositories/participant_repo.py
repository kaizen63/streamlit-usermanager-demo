"""
Repositories for participants

This module provides repository classes to handle participant management operations
including CRUD operations, relation management, and state transitions.
It serves as the data access layer for participant-related functionality.
"""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, TypeAlias, cast, get_args

from pydantic import ValidationError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.sql.selectable import Select
from sqlalchemy.sql.functions import coalesce
from sqlmodel import Session, delete, or_, select, update

from ..models import (  # noqa: TID252
    Participant,
    ParticipantCreate,
    ParticipantModel,
    ParticipantRelation,
    ParticipantRelationCreate,
    ParticipantRelationModel,
    ParticipantRelationType,
    ParticipantState,
    ParticipantStateLiteral,
    ParticipantType,
    ParticipantUpdate,
    RelatedParticipant,
)
from .base_class import LOGGER_NAME, RepositoryBase
from .participant_relation_repo import (
    ParticipantRelationNotFoundError,
    ParticipantRelationRepository,
)

logger = logging.getLogger(LOGGER_NAME)

KeyColumnLiteral: TypeAlias = Literal["id", "name", "display_name"]


class ParticipantNotFoundError(Exception):
    """Raised when a participant is not found."""


class ParticipantRepository(RepositoryBase):
    """
    The repository for participants

    Handles operations for creating, retrieving, updating, and managing
    participants and their relationships in the system.
    """

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
    ) -> Participant | None:
        """
        Get a participant by name and type.

        Retrieves a participant from the database based on the provided name and
        participant type. Optionally includes related entities and can raise an
        error if the participant is not found.

        Args:
            name: The unique name of the participant to retrieve (case-sensitive)
            participant_type: The type of participant (HUMAN, ROLE, ORG_UNIT, SYSTEM)
            include_relations: Whether to include related participants (roles, org_units, proxy_of).
                Defaults to False.
            include_proxies: Whether to include participants that have this participant
                as a proxy. Only relevant if include_relations is True. Defaults to False.
            raise_error_if_not_found: Whether to raise ParticipantNotFoundError if the
                participant doesn't exist. Defaults to False.

        Returns:
            Participant: The found participant object, or None if not found and
            raise_error_if_not_found is False.

        Raises:
            ValueError: If the participant_type is invalid
            ParticipantNotFoundError: If the participant doesn't exist and
                raise_error_if_not_found is True
            Exception: For any database errors

        """
        if participant_type not in [str(m) for m in ParticipantType]:
            exc_msg = f"Wrong participant_type: {participant_type}"
            raise ValueError(exc_msg)
        try:
            result: ParticipantModel | None = self.session.exec(
                select(ParticipantModel).where(
                    ParticipantModel.name == name,
                    ParticipantModel.participant_type == participant_type,
                ),
            ).one_or_none()
        except Exception as e:
            logger.exception(f"get_by_name: {participant_type=}, {name=} - {e}")
            raise
        else:
            if result is None:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError
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
    ) -> Participant | None:
        """
        Get a participant by display_name and type.

        Retrieves a participant from the database based on the provided display_name and
        participant type. Optionally includes related entities and can raise an
        error if the participant is not found.

        Args:
            display_name: The display name of the participant to retrieve
            participant_type: The type of participant (HUMAN, ROLE, ORG_UNIT, SYSTEM)
            include_relations: Whether to include related participants (roles, org_units, proxy_of).
                Defaults to False.
            include_proxies: Whether to include participants that have this participant
                as a proxy. Only relevant if include_relations is True. Defaults to False.
            raise_error_if_not_found: Whether to raise ParticipantNotFoundError if the
                participant doesn't exist. Defaults to False.

        Returns:
            Participant: The found participant object, or None if not found and
            raise_error_if_not_found is False.

        Raises:
            ValueError: If the participant_type is invalid
            ParticipantNotFoundError: If the participant doesn't exist and
                raise_error_if_not_found is True
            Exception: For any database errors

        """
        if participant_type not in [str(m) for m in ParticipantType]:
            exc_msg = f"Wrong participant_type: {participant_type}"
            raise ValueError(exc_msg)
        try:
            result: ParticipantModel | None = self.session.exec(
                select(ParticipantModel).where(
                    ParticipantModel.display_name == display_name,
                    ParticipantModel.participant_type == participant_type,
                ),
            ).one_or_none()
        except Exception as e:
            logger.exception(
                f"get_by_display_name: {participant_type=}, {display_name=} - {e}",
            )
            raise
        else:
            if result is None:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError
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
    ) -> Participant | None:
        """
        Get a participant by id.

        Retrieves a participant from the database based on the provided id.
        Optionally includes related entities and can raise an error if the
        participant is not found.

        Args:
            id_: The unique id of the participant to retrieve
            include_relations: Whether to include related participants. Defaults to False.
            include_proxies: Whether to include proxies. Only relevant if
                include_relations is True. Defaults to False.
            raise_error_if_not_found: Whether to raise ParticipantNotFoundError if the
                participant doesn't exist. Defaults to False.

        Returns:
            Participant: The found participant object, or None if not found and
            raise_error_if_not_found is False.

        Raises:
            ParticipantNotFoundError: If the participant doesn't exist and
                raise_error_if_not_found is True
            Exception: For any database errors

        """
        try:
            result: ParticipantModel | None = self.session.exec(
                select(ParticipantModel).where(ParticipantModel.id == id_),
            ).one_or_none()
        except Exception as e:
            logger.exception(f"get_by_id: {id=} - {e}")
            raise
        else:
            if result is None:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError
                return None
            pati = Participant(**result.model_dump())
            if include_relations:
                self.set_relations(pati, include_proxies)
            return pati

    def exists(
        self,
        column: KeyColumnLiteral,
        value: int | str,
        participant_type: ParticipantType,
    ) -> bool | str:
        """
        Query if the participant exists based on a key column.

        Checks if a participant exists in the database using the specified key column
        and value, along with the participant type.

        Args:
            column: The column to search by (id, name, or display_name)
            value: The value to search for (int for id, str for name/display_name)
            participant_type: The type of participant (HUMAN, ROLE, ORG_UNIT, SYSTEM)

        Returns:
            bool | str: False if the participant does not exist, or
                the state (ACTIVE or TERMINATED) if the participant exists

        Raises:
            ValueError: If an invalid column or participant_type is provided

        """
        if participant_type not in ParticipantType.__members__.values():
            exc_msg = f"Wrong participant_type: {participant_type}"
            raise ValueError(exc_msg)

        if column not in set(get_args(KeyColumnLiteral)):
            exc_msg = f"Wrong column {column!a} provided. Allowed values are: {get_args(KeyColumnLiteral)}"
            raise ValueError(exc_msg)

        # Define column to lookup method mapping
        lookup_methods: dict[str, Any] = {
            "name": self.get_by_name,
            "id": self.get_by_id,
            "display_name": self.get_by_display_name,
        }

        # Lookup the appropriate method based on column
        if column in lookup_methods:
            # Ensure `value` type matches expected type for the column
            if column == "id" and not isinstance(value, int):
                return False
            if column in ["name", "display_name"] and not isinstance(value, str):
                return False

            # Perform the lookup
            if column == "id":
                pati = lookup_methods[column](value, raise_error_if_not_found=False)
            else:
                pati = lookup_methods[column](
                    value,
                    participant_type,
                    raise_error_if_not_found=False,
                )

            return str(pati.state) if pati else False

        return False

    def get_all(
        self,
        participant_type: str,
        *,
        include_relations: bool = False,
        only_active: bool = False,
    ) -> list[Participant]:
        """
        Get all participants of a specified type.

        Retrieves all participants of the specified type from the database.
        Optionally filters to include only active participants and can
        include related entities.

        Args:
            participant_type: The type of participants to retrieve
            include_relations: Whether to include related participants for each
                participant. Defaults to False.
            only_active: Whether to include only active participants. Defaults to False.

        Returns:
            list[Participant]: A list of participant objects matching the criteria,
                or an empty list if none found.

        Raises:
            ValueError: If the participant_type is invalid
            Exception: For any database errors

        """
        if participant_type not in [str(m) for m in ParticipantType]:
            exc_msg = f"Wrong participant_type: {participant_type}"
            raise ValueError(exc_msg)
        active_state_filter = None if only_active else "ACTIVE"
        try:
            statement: Select = (
                select(ParticipantModel)
                .where(
                    ParticipantModel.participant_type == participant_type,
                    coalesce(active_state_filter, ParticipantModel.state, "ACTIVE")
                    == "ACTIVE",
                )
                .order_by(ParticipantModel.display_name)
            )
            result: Sequence[ParticipantModel] = self.session.exec(statement).all()
        except Exception as e:
            logger.exception(f"get_all: - {e}")
            raise
        else:
            participants = [Participant(**r.model_dump()) for r in result]

            if include_relations:
                [self.set_relations(p) for p in participants]
            return participants

    def set_relations(
        self,
        participant: Participant,
        set_proxies: bool = False,
    ) -> Participant:
        """
        Adds all relationships for a participant from the database to the object.

        Retrieves and adds role, org_unit, and proxy relationships to a participant
        object from the database.

        Args:
            participant: The participant to add the relations roles, org_units, proxy_of and proxies
            set_proxies: Whether to add proxies of this user or not. Defaults to False

        Returns:
            Participant: The passed participant with relations populated

        """
        with ParticipantRelationRepository(self.session) as rel_repository:
            relations: list[RelatedParticipant] = rel_repository.get(participant.id)
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

            if set_proxies is False:
                return participant

            proxies: list[RelatedParticipant] = rel_repository.get_reverse(
                participant.id,
                ("PROXY OF",),
            )
            if not proxies:
                return participant
            participant.proxies = participant.proxies = [
                r.participant
                for r in proxies
                if r.participant.state == ParticipantState.ACTIVE.value
            ]

        return participant

    def compute_effective_roles(self, participant: Participant) -> set[str]:
        """
        Computes effective roles for a participant.

        Determines the combined set of roles for a participant based on directly
        assigned roles, roles assigned to their organization units, and roles
        assigned to participants they are a proxy for.

        Args:
            participant: The participant to compute effective roles for

        Returns:
            set[str]: A set of role names that are effectively granted to the participant

        Notes:
            - Only goes one level deep into org_units or proxies
            - Updates the participant's effective_roles attribute

        """
        # Collect  roles assigned to this participant
        # we start with a list and turn it into a set at the end
        logger.debug(
            f"Participant: {participant.name}, num_roles: {len(participant.roles)}, "
            f"num_orgs: {len(participant.org_units)}, num_proxy_of: {len(participant.proxy_of)}",
        )
        effective_roles: set[str] = {role.name for role in participant.roles}
        with ParticipantRelationRepository(self.session) as rel_repository:

            def get_granted_roles(participants: list[Participant]) -> set[str]:
                """Helper function to get the roles of a participant"""
                roles: set[str] = set()
                for pati in participants:
                    relations = rel_repository.get(pati.id, relation_type=("GRANT",))
                    if relations:
                        roles.update(r.participant.name for r in relations)
                return roles

            # Add roles from org_units and proxies
            effective_roles.update(get_granted_roles(participant.org_units))
            effective_roles.update(get_granted_roles(participant.proxy_of))

        participant.effective_roles = effective_roles
        return participant.effective_roles

    def set_participant_state(
        self,
        participant: Participant,
        state: ParticipantStateLiteral | None,
        raise_error_if_not_found: bool = False,
    ) -> Participant:
        """
        Sets the status of the participant to the specified state.

        Updates the participant's state in the database. Cannot change the
        state of the SYSTEM user.

        Args:
            participant: The participant to update
            state: The new state to set (ACTIVE, TERMINATED, or None)
            raise_error_if_not_found: Whether to raise ParticipantNotFoundError if the
                participant doesn't exist. Defaults to False.

        Returns:
            Participant: The updated participant object

        Raises:
            ParticipantNotFoundError: If the participant doesn't exist and
                raise_error_if_not_found is True
            Exception: For any database errors

        Notes:
            - SYSTEM user's state cannot be modified

        """
        if participant.name == "SYSTEM":
            return participant

        try:
            now = datetime.now(UTC)
            result = self.session.exec(
                update(ParticipantModel)
                .where(ParticipantModel.id == participant.id)
                .values(state=state, updated_timestamp=now),
            )
            self.session.flush()
        except Exception as e:
            logger.exception(
                f"Failed to update state of {participant.id} to {state} - {e}",
            )
            raise
        else:
            if result.rowcount == 1:
                participant.state = state
            elif raise_error_if_not_found:
                raise ParticipantNotFoundError
            return participant

    def terminate_participant(
        self,
        participant: Participant,
        raise_error_if_not_found: bool = False,
    ) -> Participant:
        """
        Sets the status of the participant to TERMINATED.

        Convenience method to terminate a participant. Cannot terminate the SYSTEM user.

        Args:
            participant: The participant to terminate
            raise_error_if_not_found: Whether to raise ParticipantNotFoundError if the
                participant doesn't exist. Defaults to False.

        Returns:
            Participant: The updated participant object

        Raises:
            ParticipantNotFoundError: If the participant doesn't exist and
                raise_error_if_not_found is True

        """
        if participant.name == "SYSTEM":
            return participant
        return self.set_participant_state(
            participant,
            "TERMINATED",
            raise_error_if_not_found,
        )

    def activate_participant(
        self,
        participant: Participant,
        raise_error_if_not_found: bool = False,
    ) -> Participant:
        """
        Sets the status of the participant to ACTIVE.

        Convenience method to activate a participant. Cannot modify the SYSTEM user.

        Args:
            participant: The participant to activate
            raise_error_if_not_found: Whether to raise ParticipantNotFoundError if the
                participant doesn't exist. Defaults to False.

        Returns:
            Participant: The updated participant object

        Raises:
            ParticipantNotFoundError: If the participant doesn't exist and
                raise_error_if_not_found is True

        """
        if participant.name == "SYSTEM":
            return participant
        return self.set_participant_state(
            participant,
            "ACTIVE",
            raise_error_if_not_found,
        )

    def update(
        self,
        id_: int,
        pati_update: ParticipantUpdate,
        *,
        raise_error_if_not_found: bool = False,
    ) -> Participant | None:
        """
        Updates participant fields in the database.

        Updates a participant's information in the database based on the provided
        ParticipantUpdate object.

        Args:
            id_: The ID of the participant to update
            pati_update: The update data object containing fields to update
            raise_error_if_not_found: Whether to raise ParticipantNotFoundError if the
                participant doesn't exist. Defaults to False.

        Returns:
            Participant | None: The updated participant object, or None if not found and
                raise_error_if_not_found is False

        Raises:
            ParticipantNotFoundError: If the participant doesn't exist and
                raise_error_if_not_found is True
            Exception: For any database errors

        Notes:
            - Only fields that are explicitly set in pati_update will be updated
            - The updated_timestamp is automatically set to current time if not provided

        """
        # exclude_unset delivers only the fields present at creation time, not the ones
        # modified afterward. We use these to get the ones initialized with None,
        # which will be updated to NULL.
        modified_fields = pati_update.model_dump(
            exclude_unset=True,
        )  # was exclude_unset=True, exclude defaults gives us the updated_timestamp
        if "updated_timestamp" not in modified_fields:
            modified_fields["updated_timestamp"] = (
                pati_update.updated_timestamp or datetime.now(UTC)
            )

        try:
            pati = self.session.exec(
                select(ParticipantModel).where(ParticipantModel.id == id_),
            ).one_or_none()
            if pati is None:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError  # noqa: TRY301
                return None

            result = self.session.exec(
                update(ParticipantModel)
                .where(ParticipantModel.id == id_)
                .values(**modified_fields),
            )

        except Exception as e:
            logger.exception(f"Error updating metadata. Error: {e}")
            raise
        else:
            if result.rowcount == 0:
                if raise_error_if_not_found:
                    raise ParticipantNotFoundError
                return None
            self.session.refresh(pati)
            return Participant(**pati.model_dump())

    def create(self, create: ParticipantCreate) -> Participant:
        """
        Creates a new participant.

        Creates a new participant in the database based on the provided
        ParticipantCreate object.

        Args:
            create: The ParticipantCreate object containing the data for the new participant

        Returns:
            Participant: The newly created participant with ID

        Raises:
            ValidationError: If the created participant fails validation
            Exception: For any database errors

        Notes:
            - The name is automatically converted to uppercase

        """
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
            else:
                return pati

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
        """
        Creates a new human participant.

        Convenience method to create a new human participant (user) with
        the specified attributes.

        Args:
            name: The unique name for the user (will be converted to uppercase)
            display_name: The display name for the user
            created_by: The name of the user creating this participant
            email: Optional email address for the user
            description: Optional description of the user
            external_reference: Optional external reference ID
            hashed_password: Optional hashed password for authentication

        Returns:
            Participant: The newly created participant

        Raises:
            ValueError: If mandatory fields are missing
            Exception: For any database errors

        """
        for f in [name, display_name, created_by]:
            if f is None:
                exc_msg = f"add_user: Missing mandatory field: {f}"
                raise ValueError(exc_msg)

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
        """
        Creates a new role participant.

        Convenience method to create a new role participant with
        the specified attributes.

        Args:
            name: The unique name for the role (will be converted to uppercase)
            display_name: The display name for the role
            created_by: The name of the user creating this role
            description: Optional description of the role

        Returns:
            Participant: The newly created role participant

        Raises:
            ValueError: If mandatory fields are missing
            Exception: For any database errors

        """
        for f in [name, display_name, created_by]:
            if f is None:
                exc_msg = f"add_user: Missing mandatory field: {f}"
                raise ValueError(exc_msg)

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
        """
        Creates a new organizational unit participant.

        Convenience method to create a new organizational unit participant with
        the specified attributes.

        Args:
            name: The unique name for the org unit (will be converted to uppercase)
            display_name: The display name for the org unit
            created_by: The name of the user creating this org unit
            email: Optional email address for the org unit
            description: Optional description of the org unit
            external_reference: Optional external reference ID

        Returns:
            Participant: The newly created org unit participant

        Raises:
            ValueError: If mandatory fields are missing
            Exception: For any database errors

        """
        for f in [name, display_name, created_by]:
            if f is None:
                exc_msg = f"add_user: Missing mandatory field: {f}"
                raise ValueError(exc_msg)

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
        """
        Adds a relation from one participant to another.

        Creates a relationship between the given participant (as source)
        and another participant identified by pati2_id (as target).

        Args:
            participant: The source participant for the relation
            pati2_id: The ID of the target participant for the relation
            relation_type: The type of relation to create
            created_by: The name of the user creating this relation

        Returns:
            ParticipantRelation: The created relationship

        """
        with ParticipantRelationRepository(self.session) as rel_repo:
            create = ParticipantRelationCreate(
                pati1_id=participant.id,
                pati2_id=pati2_id,
                relation_type=relation_type,
                created_by=created_by,
            )
            if create.created_timestamp is None:
                create.created_timestamp = datetime.now(UTC)
            return cast("ParticipantRelation", rel_repo.create(create, True))

    def add_reverse_relation(
        self,
        participant: Participant,  # p2
        pati1_id: int,
        relation_type: ParticipantRelationType,
        created_by: str,
    ) -> ParticipantRelation:
        """
        Adds a relation to this participant from another participant.

        Creates a relationship to the given participant (as target)
        from another participant identified by pati1_id (as source).

        Args:
            participant: The target participant for the relation
            pati1_id: The ID of the source participant for the relation
            relation_type: The type of relation to create
            created_by: The name of the user creating this relation

        Returns:
            ParticipantRelation: The created relationship

        """
        with ParticipantRelationRepository(self.session) as rel_repo:
            create = ParticipantRelationCreate(
                pati1_id=pati1_id,
                pati2_id=participant.id,
                relation_type=relation_type,
                created_by=created_by,
            )
            if create.created_timestamp is None:
                create.created_timestamp = datetime.now(UTC)
            return cast("ParticipantRelation", rel_repo.create(create, True))

    def delete_relation(
        self,
        participant: Participant,
        pati2_id: int,
        relation_type: ParticipantRelationType,
        raise_error_if_not_found: bool = False,
    ) -> None:
        """
        Deletes a relation from a source participant to a target participant.

        Removes a relationship where the given participant is the source (pati1)
        and another participant identified by pati2_id is the target (pati2).

        Args:
            participant: The source participant of the relation to delete
            pati2_id: The ID of the target participant in the relation
            relation_type: The type of relation to delete (GRANT, MEMBER OF, PROXY OF)
            raise_error_if_not_found: Whether to raise an error if the relation
                doesn't exist. Defaults to False.

        Returns:
            None

        Raises:
            ValueError: If the relation_type is invalid
            ParticipantRelationNotFoundError: If the relation doesn't exist and
                raise_error_if_not_found is True
            Exception: For any database errors

        """
        if relation_type not in [str(pt) for pt in ParticipantRelationType]:
            exc_msg = f"Wrong relation_type: {relation_type=}"
            raise ValueError(exc_msg)

        try:
            result = self.session.exec(
                delete(ParticipantRelationModel).where(
                    ParticipantRelationModel.pati1_id == participant.id,
                    ParticipantRelationModel.pati2_id == pati2_id,
                    ParticipantRelationModel.relation_type == relation_type,
                ),
            )
            self.session.flush()
        except Exception as e:
            logger.exception(f"Error deleting relation of pati1 {participant.id=}: {e}")
            raise
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
        """
        Deletes a relation where the given participant is the target.

        Removes a relationship where the given participant is the target (pati2)
        and another participant identified by pati1_id is the source (pati1).

        Args:
            participant: The target participant of the relation to delete
            pati1_id: The ID of the source participant in the relation
            relation_type: The type of relation to delete (GRANT, MEMBER OF, PROXY OF)
            raise_error_if_not_found: Whether to raise an error if the relation
                doesn't exist. Defaults to False.

        Returns:
            int: Number of affected rows (0 or 1)

        Raises:
            ValueError: If the relation_type is invalid
            ParticipantRelationNotFoundError: If the relation doesn't exist and
                raise_error_if_not_found is True
            Exception: For any database errors

        """
        if relation_type not in [str(pt) for pt in ParticipantRelationType]:
            exc_msg = f"Wrong relation_type: {relation_type=}"
            raise ValueError(exc_msg)
        try:
            result = self.session.exec(
                delete(ParticipantRelationModel).where(
                    ParticipantRelationModel.pati2_id == participant.id,
                    ParticipantRelationModel.pati1_id == pati1_id,
                    ParticipantRelationModel.relation_type == relation_type,
                ),
            )
            self.session.flush()

        except Exception as e:
            logger.exception(
                f"Error deleting reverse relation of pati2 {participant.id=}: {e}",
            )
            raise
        else:
            if result.rowcount == 0 and raise_error_if_not_found:
                raise ParticipantRelationNotFoundError
            return result.rowcount

    def delete_all_participant_relations(
        self,
        participant_id: int,
    ) -> int:
        """
        Deletes all relations where the participant is either source or target.

        Removes all relationships where the specified participant is either
        the source (pati1) or target (pati2) of the relationship.

        Args:
            participant_id: The ID of the participant whose relations should be deleted

        Returns:
            int: Number of relations deleted

        Raises:
            Exception: For any database errors

        """
        try:
            result = self.session.exec(
                delete(ParticipantRelationModel).where(
                    or_(
                        ParticipantRelationModel.pati1_id == participant_id,
                        ParticipantRelationModel.pati2_id == participant_id,
                    ),
                ),
            )

        except Exception as e:
            logger.exception(
                f"Error deleting all relations of participant {participant_id=} {e}",
            )
            raise
        return result.rowcount
