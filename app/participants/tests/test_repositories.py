from typing import Literal, Optional, cast, Generator

# import os
import pytest
from sqlmodel import Session, delete
import os

from app.participants import (
    Participant,
    ParticipantCreate,
    ParticipantRelationCreate,
    ParticipantRelationRepository,
    ParticipantRelationType,
    ParticipantRepository,
    ParticipantState,
    ParticipantType,
    ParticipantUpdate,
    ParticipantRelation,
    IntegrityError,
)
from sqlalchemy import Engine
from sqlalchemy.exc import PendingRollbackError
from ..models import ParticipantModel, ParticipantRelationModel
from .db import get_url, create_db_engine, is_sqlite, create_db_and_tables


db_engine: str = os.getenv("DB_ENGINE")
db_url = get_url(db_engine)

engine: Engine = create_db_engine(db_url)


def get_session_generator(engine: Engine) -> Generator:
    session = Session(bind=engine)
    try:
        _ = session.connection()
    except PendingRollbackError:
        session.rollback()
    yield session
    session.close()


def get_session(engine: Engine) -> Session:
    """to be used with:
    with get_session(engine) as session:
     ...
    """
    return next(get_session_generator(engine))


def delete_test_data():
    global engine
    with get_session(engine) as session:
        if is_sqlite(engine):
            statement = delete(ParticipantRelationModel)
            session.exec(statement)
            statement = delete(ParticipantModel)
            session.exec(statement)

        else:
            statement = delete(ParticipantRelationModel).where(
                ParticipantRelationModel.created_by == "UNITTEST"
            )
            session.exec(statement)
            statement = delete(ParticipantModel).where(
                ParticipantModel.created_by == "UNITTEST"
            )
            session.exec(statement)
        session.commit()
        session.flush()


@pytest.fixture(autouse=True, scope="module")
def setup_module() -> None:
    global engine
    if is_sqlite(engine):
        create_db_and_tables(engine)
    # delete leftovers from prev tests, if any
    delete_test_data()


def create_test_data(session: Session):
    global engine

    system2 = ParticipantModel(
        name="SYSTEM2",
        display_name="SYSTEM2",
        participant_type="SYSTEM",
        created_by="UNITTEST",
    )

    if is_sqlite(engine):
        system = ParticipantModel(
            name="SYSTEM",
            display_name="SYSTEM",
            participant_type="SYSTEM",
            created_by="UNITTEST",
        )
        session.add(system)

    user_1 = ParticipantModel(
        name="POITSCHKKA02",
        display_name="Poitschke, Kai2",
        participant_type="HUMAN",
        created_by="UNITTEST",
    )

    user_2 = ParticipantModel(
        name="SHULZJOE01",
        display_name="Schulz, Joerg",
        participant_type="HUMAN",
        created_by="UNITTEST",
    )
    user_3 = ParticipantModel(
        name="FUNKEVO01",
        display_name="Funke, Volker",
        participant_type="HUMAN",
        created_by="UNITTEST",
    )

    role_1 = ParticipantModel(
        name="ADMINISTRATOR2",
        display_name="Administrator2",
        participant_type="ROLE",
        created_by="UNITTEST",
    )

    public_role = ParticipantModel(
        name="EDITOR",
        display_name="EDITOR",
        participant_type="ROLE",
        created_by="UNITTEST",
    )

    org_unit_1 = ParticipantModel(
        name="ACME",
        display_name="A company making everything",
        participant_type="ORG_UNIT",
        created_by="UNITTEST",
    )

    try:
        for pati in [
            system2,
            user_1,
            user_2,
            user_3,
            role_1,
            public_role,
            org_unit_1,
        ]:
            session.add(pati)
        session.flush()
        rela_1 = ParticipantRelationModel(
            pati1_id=user_1.id,
            pati2_id=org_unit_1.id,
            relation_type="MEMBER OF",
            created_by="UNITTEST",
        )
        session.add(rela_1)

        rela_2 = ParticipantRelationModel(
            pati1_id=role_1.id,
            pati2_id=user_2.id,
            relation_type="GRANT",
            created_by="UNITTEST",
        )
        session.add(rela_2)

        rela_4 = ParticipantRelationModel(
            pati1_id=user_2.id,
            pati2_id=user_1.id,
            relation_type="PROXY OF",
            created_by="UNITTEST",
        )
        session.add(rela_4)

        for u in [user_1, user_2, user_3]:
            rela = ParticipantRelationModel(
                pati1_id=u.id,
                pati2_id=public_role.id,
                relation_type="GRANT",
                created_by="UNITTEST",
            )
            session.add(rela)
        session.flush()
    except Exception as e:
        print(e)
        session.rollback()
        raise


def test_pati_repository_get_by_name() -> None:
    global engine
    with ParticipantRepository(get_session(engine)) as repository:
        create_test_data(repository.session)
        system: Optional[Participant] = repository.get_by_name(
            name="SYSTEM2", participant_type=ParticipantType.SYSTEM
        )
        assert system is not None
        assert system.name == "SYSTEM2"
        assert system.participant_type == "SYSTEM"

        administrator: Optional[Participant] = repository.get_by_name(
            name="ADMINISTRATOR2", participant_type=ParticipantType.ROLE
        )
        assert administrator is not None
        assert administrator.id > 1
        assert administrator.name == "ADMINISTRATOR2"
        assert administrator.participant_type == "ROLE"

        role_public: Optional[Participant] = repository.get_by_name(
            name="EDITOR", participant_type=ParticipantType.ROLE
        )
        assert role_public is not None
        assert role_public.id > 1
        assert role_public.name == "EDITOR"
        assert role_public.participant_type == "ROLE"

        user_1: Optional[Participant] = repository.get_by_name(
            name="POITSCHKKA02",
            participant_type=ParticipantType.HUMAN,
            include_relations=True,
            include_proxies=True,
        )
        assert user_1 is not None
        assert user_1.id > 1
        assert user_1.name == "POITSCHKKA02"
        assert user_1.display_name == "Poitschke, Kai2"
        assert user_1.participant_type == "HUMAN"
        repository.rollback()


def test_pati_repository_get_by_name_exc() -> None:
    with ParticipantRepository(get_session(engine)) as repository:
        with pytest.raises(ValueError):
            _ = repository.get_by_name(
                name="ADMINISTRATOR2", participant_type="TOTALLY WRONG"
            )


def test_pati_repository_get_by_name_not_found() -> None:
    with ParticipantRepository(session=get_session(engine)) as repository:
        result: Optional[Participant] = repository.get_by_name(
            name="KAI",
            participant_type=ParticipantType.HUMAN,
            raise_error_if_not_found=False,
        )
        assert result is None


def test_pati_repository_get_by_id_not_found() -> None:
    with ParticipantRepository(session=get_session(engine)) as repository:
        result: Optional[Participant] = repository.get_by_id(-1)
        assert result is None


def test_pati_exists() -> None:
    global engine
    with ParticipantRepository(session=get_session(engine)) as repo:
        create_test_data(repo.session)
        system: Optional[Participant] = repo.get_by_name(
            name="SYSTEM2", participant_type=ParticipantType.SYSTEM
        )
        assert system is not None
        exists = repo.exists("id", system.id, ParticipantType.SYSTEM)
        assert exists == "ACTIVE"

        exists = repo.exists("name", "EDITOR", ParticipantType.ROLE)
        assert exists == "ACTIVE"

        exists = repo.exists("name", "POITSCHKKA02", ParticipantType.HUMAN)
        assert exists == "ACTIVE"

        not_exists = repo.exists("id", -1, ParticipantType.HUMAN)
        assert not_exists is False

        not_exists = repo.exists("name", "ladkjflaskfm", ParticipantType.HUMAN)
        assert not_exists is False

        not_exists = repo.exists(
            "display_name", "ladkjflaskfm", ParticipantType.HUMAN
        )
        assert not_exists is False
        repo.rollback()


def test_pati_exists_exceptions() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        with pytest.raises(ValueError):
            _ = repo.exists("not_a_valid_column", 1, ParticipantType.SYSTEM)


@pytest.mark.parametrize(
    "name, display_name, participant_type, created_by, expected_result",
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
def test_pati_repo_create(
    name, display_name, participant_type, created_by, expected_result
) -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        create = ParticipantCreate(
            name=name,
            display_name=display_name,
            participant_type=participant_type,
            created_by=created_by,
        )
        pati: Participant = repo.create(create)
        # Read what's in the database
        new_pati: Participant | None = repo.get_by_id(pati.id)
        assert new_pati is not None
        assert new_pati.name == name.upper()
        assert new_pati.display_name == display_name
        assert new_pati.participant_type == participant_type
        assert new_pati.created_by == created_by.upper()
        assert new_pati.created_timestamp is not None
        assert new_pati.id == pati.id
        assert pati.name == expected_result
        repo.rollback()


def test_pati_repository_add_user() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        user = repo.add_user(
            name="poitschlena",
            display_name="Poitschke, Lena",
            created_by="UNITTEST",
            external_reference="not in ldap",
        )
        assert user is not None
        assert user.name == "POITSCHLENA"
        assert user.display_name == "Poitschke, Lena"
        assert user.participant_type == ParticipantType.HUMAN
        assert user.created_by == "UNITTEST"
        assert user.created_timestamp is not None
        assert user.id is not None
        assert user.email is None
        assert user.description is None
        assert user.effective_roles == set()
        assert user.external_reference == "not in ldap"
        assert user.hashed_password is None
        assert user.state == "ACTIVE"
        repo.rollback()


def test_pati_repository_add_org() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        user = repo.add_org(
            name="airbusltd",
            display_name="Airbus Ltd",
            created_by="UNITTEST",
            external_reference="NASDAQ=1234",
        )
        assert user is not None
        assert user.name == "AIRBUSLTD"
        assert user.display_name == "Airbus Ltd"
        assert user.participant_type == ParticipantType.ORG_UNIT
        assert user.created_by == "UNITTEST"
        assert user.created_timestamp is not None
        assert user.id is not None
        assert user.email is None
        assert user.description is None
        assert user.effective_roles == set()
        assert user.external_reference == "NASDAQ=1234"
        assert user.hashed_password is None
        assert user.state == "ACTIVE"
        repo.rollback()


def test_pati_repository_add_role() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        user = repo.add_role(
            name="unittestrole1",
            display_name="Unit Test Role 1",
            created_by="UNITTEST",
        )
        assert user is not None
        assert user.name == "UNITTESTROLE1"
        assert user.display_name == "Unit Test Role 1"
        assert user.participant_type == ParticipantType.ROLE
        assert user.created_by == "UNITTEST"
        assert user.created_timestamp is not None
        assert user.id is not None
        assert user.email is None
        assert user.description is None
        assert user.effective_roles == set()
        assert user.external_reference is None
        assert user.hashed_password is None
        assert user.state == ParticipantState.ACTIVE
        repo.rollback()


def test_pati_repository_get_with_rel() -> None:

    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="USER-1",
            display_name="USER-1",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST",
        )
        user: Participant = repo.create(user_create)

        org_create = ParticipantCreate(
            name="ORG-1",
            display_name="ORG-1",
            participant_type=ParticipantType.ORG_UNIT,
            created_by="UNITTEST1",
        )
        org1: Participant = repo.create(org_create)

        org_create = ParticipantCreate(
            name="ORG-2",
            display_name="ORG-2",
            participant_type=ParticipantType.ORG_UNIT,
            created_by="UNITTEST1",
        )
        org2: Participant = repo.create(org_create)

        rel_record: ParticipantRelation = repo.add_relation(
            user,
            org1.id,
            ParticipantRelationType.MEMBER_OF,
            created_by="UNITTEST",
        )
        assert rel_record is not None
        assert rel_record.pati1_id == user.id
        assert rel_record.pati2_id == org1.id
        assert rel_record.relation_type == ParticipantRelationType.MEMBER_OF
        assert rel_record.created_by == "UNITTEST"

        rel_record = repo.add_relation(
            user,
            org2.id,
            ParticipantRelationType.MEMBER_OF,
            created_by="UNITTEST",
        )
        assert rel_record is not None
        assert rel_record.pati1_id == user.id
        assert rel_record.pati2_id == org2.id
        assert rel_record.relation_type == ParticipantRelationType.MEMBER_OF
        assert rel_record.created_by == "UNITTEST"

        role_create = ParticipantCreate(
            name="ROLE-1",
            display_name="ROLE-1",
            participant_type=ParticipantType.ROLE,
            created_by="UNITTEST1",
        )
        role: Participant = repo.create(role_create)

        rel_record = repo.add_relation(
            user, role.id, ParticipantRelationType.GRANT, created_by="UNITTEST"
        )
        assert rel_record is not None
        assert rel_record.pati1_id == user.id
        assert rel_record.pati2_id == role.id
        assert rel_record.relation_type == ParticipantRelationType.GRANT
        assert rel_record.created_by == "UNITTEST"

        user_create = ParticipantCreate(
            name="USER-2",
            display_name="USER-2",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST",
        )
        user2: Participant = repo.create(user_create)

        rel_record = repo.add_relation(
            user,
            user2.id,
            ParticipantRelationType.PROXY_OF,
            created_by="UNITTEST",
        )
        assert rel_record is not None
        assert rel_record.pati1_id == user.id
        assert rel_record.pati2_id == user2.id
        assert rel_record.relation_type == ParticipantRelationType.PROXY_OF
        assert rel_record.created_by == "UNITTEST"

        pati = repo.get_by_id(
            user.id, include_relations=True, include_proxies=True
        )
        assert pati is not None
        assert pati.name == "USER-1"
        assert len(pati.roles) == 1
        assert len(pati.org_units) == 2
        assert len(pati.proxy_of) == 1

        repo.rollback()


def test_pati_model_add_relation_role() -> None:

    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1",
            display_name="User, 1",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        user: Participant = repo.create(user_create)

        role_create = ParticipantCreate(
            name="role1",
            display_name="Role, 1",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST2",
        )
        role: Participant = repo.create(role_create)

        with ParticipantRelationRepository(repo.session) as rel_repo:
            # Grant Role to user
            rel = repo.add_relation(
                user,
                role.id,
                ParticipantRelationType.GRANT,
                created_by="user1",
            )
            assert rel is not None

            # repo.commit()  # We have to commit here because get is not using the orm and the orm has not written it to db
            rel1 = rel_repo.get(user.id, ("GRANT",))
            assert len(rel1) == 1
            assert rel1[0].relation_type == "GRANT"
            assert rel1[0].participant.id == role.id
            assert rel1[0].participant.name == role.name.upper()
            assert rel1[0].participant.display_name == role.display_name
            assert (
                rel1[0].participant.participant_type == role.participant_type
            )
            assert rel1[0].participant.state == "ACTIVE"

        repo.rollback()


def test_pati_model_add_relation_org() -> None:

    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1o",
            display_name="User, 1o",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        user: Participant = repo.create(user_create)

        org_create = ParticipantCreate(
            name="org1o",
            display_name="Org, 1o",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        org: Participant = repo.create(org_create)

        with ParticipantRelationRepository(repo.session) as rel_repo:

            rel = repo.add_relation(
                user,
                org.id,
                ParticipantRelationType.MEMBER_OF,
                created_by="user1",
            )
            assert rel is not None

            rel2 = rel_repo.get(user.id, ("MEMBER OF",))
            assert len(rel2) == 1
            assert rel2[0].relation_type == "MEMBER OF"
            assert rel2[0].participant.id == org.id
            assert rel2[0].participant.name == org.name.upper()
            assert rel2[0].participant.display_name == org.display_name
            assert rel2[0].participant.participant_type == org.participant_type
            assert rel2[0].participant.state == "ACTIVE"

        with pytest.raises(ValueError):
            repo.add_relation(
                user,
                org.id,
                cast(
                    ParticipantRelationType, "invalid"
                ),  # cast to make mypy happy
                created_by="user2",
            )
        repo.rollback()


def test_pati_model_add_reverse_relation_org() -> None:

    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1p",
            display_name="User, 1p",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        user: Participant = repo.create(user_create)

        org_create = ParticipantCreate(
            name="org1p",
            display_name="Org, 1p",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        org: Participant = repo.create(org_create)

        with ParticipantRelationRepository(repo.session) as rel_repo:

            rel = repo.add_reverse_relation(
                org,
                user.id,
                ParticipantRelationType.MEMBER_OF,
                created_by="user1p",
            )
            assert rel is not None

            rel2 = rel_repo.get(user.id, ("MEMBER OF",))
            assert len(rel2) == 1
            assert rel2[0].relation_type == "MEMBER OF"
            assert rel2[0].participant.id == org.id
            assert rel2[0].participant.name == org.name.upper()
            assert rel2[0].participant.display_name == org.display_name
            assert rel2[0].participant.participant_type == org.participant_type
            assert rel2[0].participant.state == "ACTIVE"

        with pytest.raises(ValueError):
            repo.add_reverse_relation(
                org,
                user.id,
                cast(
                    ParticipantRelationType, "invalid"
                ),  # cast to make mypy happy
                created_by="user2",
            )
        repo.rollback()


def test_pati_model_delete_relation() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1a",
            display_name="User, 1a",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1a",
        )
        user: Participant = repo.create(user_create)

        role_create = ParticipantCreate(
            name="role1a",
            display_name="Role, 1a",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST2a",
        )
        role: Participant = repo.create(role_create)

        org_create = ParticipantCreate(
            name="org1a",
            display_name="Org, 1a",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST3a",
        )
        org: Participant = repo.create(org_create)

        # Grant Role to user
        rel1 = repo.add_relation(
            user, role.id, ParticipantRelationType.GRANT, created_by="user1"
        )
        # Make user member of
        rel2 = repo.add_relation(
            user, org.id, ParticipantRelationType.MEMBER_OF, created_by="user2"
        )
        repo.delete_relation(user, role.id, ParticipantRelationType.GRANT)

        repo.delete_relation(user, org.id, ParticipantRelationType.MEMBER_OF)

        with ParticipantRelationRepository(repo.session) as rel_repo:
            assert rel_repo.get(user.id, ("GRANT",)) == []
            assert rel_repo.get(user.id, ("MEMBER OF",)) == []
        repo.rollback()


def test_pati_model_delete_all_relations() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1d",
            display_name="User, 1d",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1d",
        )
        user: Participant = repo.create(user_create)

        role_create = ParticipantCreate(
            name="role1d",
            display_name="Role, 1d",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST2d",
        )
        role: Participant = repo.create(role_create)

        org_create = ParticipantCreate(
            name="org1d",
            display_name="Org, 1d",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST3d",
        )
        org: Participant = repo.create(org_create)

        # Grant Role to user
        rel1 = repo.add_relation(
            user, role.id, ParticipantRelationType.GRANT, created_by="user1"
        )
        # Make user member of
        rel2 = repo.add_relation(
            user, org.id, ParticipantRelationType.MEMBER_OF, created_by="user2"
        )
        repo.delete_all_participant_relations(user.id)

        with ParticipantRelationRepository(repo.session) as rel_repo:
            assert rel_repo.get(user.id, ("GRANT",)) == []
            assert rel_repo.get(user.id, ("MEMBER OF",)) == []
        repo.rollback()


def test_pati_model_delete_reverse_relation() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1drr",
            display_name="User, 1drr",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1drr",
        )
        user: Participant = repo.create(user_create)

        role_create = ParticipantCreate(
            name="role1rr",
            display_name="Role, 1drr",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1drr",
        )
        role: Participant = repo.create(role_create)

        # Grant Role to user
        rel1 = repo.add_relation(
            user, role.id, ParticipantRelationType.GRANT, created_by="user1"
        )

        rel2 = repo.delete_reverse_relation(
            role, user.id, ParticipantRelationType.GRANT
        )

        repo.rollback()


def test_pati_repository_set_state() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1b",
            display_name="User, 1b",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        pati: Participant = repo.create(user_create)
        assert pati is not None
        orig_state = pati.state
        if orig_state is None:
            orig_state = "ACTIVE"

        if orig_state == ParticipantState.ACTIVE:
            new_state: Literal["ACTIVE", "TERMINATED"] = "TERMINATED"
        else:
            new_state = "ACTIVE"

        repo.set_participant_state(pati, new_state)
        updated_pati: Optional[Participant] = repo.get_by_id(pati.id)
        assert updated_pati is not None
        assert updated_pati.state == new_state

        repo.set_participant_state(pati, orig_state)
        updated_pati2: Optional[Participant] = repo.get_by_id(pati.id)
        assert updated_pati2 is not None
        assert updated_pati2.state == orig_state

        repo.rollback()


def test_pati_repository_update() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1b",
            display_name="User, 1b",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        pati: Participant = repo.create(user_create)
        assert pati is not None
        orig_state = pati.state
        if orig_state is None:
            orig_state = "ACTIVE"

        if orig_state == ParticipantState.ACTIVE:
            new_state: Literal["ACTIVE", "TERMINATED"] = "TERMINATED"
        else:
            new_state = "ACTIVE"
        update = ParticipantUpdate(state=new_state, updated_by="UNITTEST8")

        updated_pati: Optional[Participant] = repo.update(-1, update)
        assert updated_pati is None

        updated_pati = repo.update(pati.id, update)
        assert updated_pati is not None
        assert updated_pati.state == new_state
        assert updated_pati.updated_by == "UNITTEST8"

        update = ParticipantUpdate(state=orig_state, updated_by="UNITTEST8")
        updated_pati2 = repo.update(pati.id, update)
        assert updated_pati2 is not None
        assert updated_pati2.state == orig_state
        assert updated_pati.updated_by == "UNITTEST8"

        update = ParticipantUpdate(state=None, updated_by="UNITTEST8")
        updated_pati3 = repo.update(pati.id, update)
        assert updated_pati3 is not None
        assert updated_pati3.state == "ACTIVE"
        assert updated_pati3.updated_by == "UNITTEST8"

        repo.rollback()


def test_pati_terminate() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1b",
            display_name="User, 1b",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST",
        )
        pati: Participant = repo.create(user_create)
        assert pati is not None

        updated_user = repo.terminate_participant(pati, ParticipantType.HUMAN)
        assert updated_user is not None
        assert updated_user.state == "TERMINATED"
        repo.rollback()


def test_pati_activate() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1b",
            display_name="User, 1b",
            participant_type=ParticipantType.HUMAN,
            state=ParticipantState.TERMINATED,
            created_by="UNITTEST",
        )
        pati: Participant = repo.create(user_create)
        assert pati is not None

        updated_user = repo.activate_participant(pati, ParticipantType.HUMAN)
        assert updated_user is not None
        assert updated_user.state == "ACTIVE"
        repo.rollback()


def test_pati_relation_repository_create() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:

        user_create = ParticipantCreate(
            name="user1r",
            display_name="User, 1r",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        user: Participant = repo.create(user_create)

        role_create = ParticipantCreate(
            name="role1r",
            display_name="Role, 1r",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST2",
        )
        role: Participant = repo.create(role_create)
        with ParticipantRelationRepository(repo.session) as rel_repo:
            # Grant Role to user
            create = ParticipantRelationCreate(
                pati1_id=user.id,
                pati2_id=role.id,
                relation_type="GRANT",
                created_by="UNITTEST1",
            )
            rel = rel_repo.create(create)
            assert rel is not None

            rel1 = rel_repo.get(user.id, ("GRANT",))
            assert len(rel1) == 1
            assert rel1[0].relation_type == "GRANT"
            assert rel1[0].participant.id == role.id
            assert rel1[0].participant.name == role.name.upper()
            assert rel1[0].participant.display_name == role.display_name
            assert (
                rel1[0].participant.participant_type == role.participant_type
            )
            assert rel1[0].participant.state == "ACTIVE"

            # Creating it a 2nd time should return 0
            with pytest.raises(IntegrityError):
                rel_repo.create(create, raise_error_on_duplicate=False)
            rel_repo.rollback()  # otherwise pending rollback error
        repo.rollback()


def test_pati_relation_repository_exists() -> None:
    with ParticipantRepository(session=get_session(engine)) as repo:

        user_create = ParticipantCreate(
            name="user1x",
            display_name="User, 1x",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        user: Participant = repo.create(user_create)

        role_create = ParticipantCreate(
            name="role1x",
            display_name="Role, 1x",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST2",
        )
        role: Participant = repo.create(role_create)

        with ParticipantRelationRepository(repo.session) as rel_repo:
            # Grant Role to user
            create = ParticipantRelationCreate(
                pati1_id=user.id,
                pati2_id=role.id,
                relation_type="GRANT",
                created_by="UNITTEST1",
            )
            rel = rel_repo.create(create)
            assert rel is not None

            exists = rel_repo.exists(
                ParticipantRelation(
                    pati1_id=user.id,
                    pati2_id=role.id,
                    relation_type="GRANT",
                    created_by="POITSCHKKA01",
                )
            )
            assert exists is True
            exists = rel_repo.exists(
                ParticipantRelation(
                    pati1_id=user.id,
                    pati2_id=role.id,
                    relation_type="MEMBER OF",
                    created_by="POITSCHKKA01",
                )
            )
            assert exists is False
        repo.rollback()


def test_pati_model_get_reverse_relation() -> None:

    with ParticipantRepository(session=get_session(engine)) as repo:
        user_create = ParticipantCreate(
            name="user1grr",
            display_name="User, 1grr",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        user: Participant = repo.create(user_create)

        org_create = ParticipantCreate(
            name="org1grr",
            display_name="Org, 1grr",
            participant_type=ParticipantType.HUMAN,
            created_by="UNITTEST1",
        )
        org: Participant = repo.create(org_create)

        with ParticipantRelationRepository(repo.session) as rel_repo:

            rel = repo.add_relation(
                user,
                org.id,
                ParticipantRelationType.MEMBER_OF,
                created_by="user1",
            )
            assert rel is not None

            # repo.commit()  # We have to commit here because get is not using the orm and the orm has not written it to db
            rel2 = rel_repo.get_reverse(org.id, ("MEMBER OF",))
            assert len(rel2) == 1
            assert rel2[0].relation_type == "MEMBER OF"
            assert rel2[0].participant.id == user.id
            assert rel2[0].participant.name == user.name.upper()
            assert rel2[0].participant.display_name == user.display_name
            assert (
                rel2[0].participant.participant_type == user.participant_type
            )
            assert rel2[0].participant.state == "ACTIVE"

        repo.rollback()
