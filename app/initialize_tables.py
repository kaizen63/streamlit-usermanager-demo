import logging
import os

from config import settings
from participants import (
    ParticipantCreate,
    ParticipantRelationType,
    ParticipantRepository,
    ParticipantType,
)
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlmodel import Session

schema = os.getenv("DB_SCHEMA")
schema_prefix = schema + "." if schema else ""


logger = logging.getLogger(settings.LOGGER_NAME)


def create_participants(session: Session) -> None:
    logger.debug("Create participant records")
    with ParticipantRepository(session) as repo:
        created_by = "SYSTEM"
        system = ParticipantCreate(
            name="SYSTEM",
            display_name="SYSTEM",
            participant_type=ParticipantType.SYSTEM,
            created_by=created_by,
        )
        repo.create(system)

        public_role = repo.add_role(
            "PUBLIC",
            "PUBLIC",
            created_by=created_by,
            description="The PUBLIC role.",
        )

        admin_role = repo.add_role(
            "ADMINISTRATOR",
            "Administrator",
            created_by=created_by,
            description="Can add users, orgs and roles",
        )
        user_admin_role = repo.add_role(
            "USER_ADMINISTRATOR",
            "User Administrator",
            description="Can add users, orgs and roles",
            created_by=created_by,
        )
        app_roles: list[ParticipantCreate] = [
            ParticipantCreate(
                name="USER_READ",
                display_name="User Read",
                description="Can read users",
                participant_type=ParticipantType.ROLE,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="USER_WRITE",
                display_name="User Write",
                description="Can edit user information",
                participant_type=ParticipantType.ROLE,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="ROLE_READ",
                display_name="Role Read",
                description="Can read roles",
                participant_type=ParticipantType.ROLE,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="ROLE_WRITE",
                display_name="Role Write",
                description="Can edit role information",
                participant_type=ParticipantType.ROLE,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="ORG_UNIT_READ",
                display_name="Org Unit Read",
                description="Can read org units",
                participant_type=ParticipantType.ROLE,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="ORG_UNIT_WRITE",
                display_name="Org Unit Write",
                description="Can edit org unit information",
                participant_type=ParticipantType.ROLE,
                created_by=created_by,
            ),
        ]
        # app roles:
        for app_role in app_roles:
            _ = repo.create(app_role)

        # Org Units from ldap.forumsys.com
        org_units: list[ParticipantCreate] = [
            ParticipantCreate(
                name="MATHEMATICIANS",
                display_name="Mathematicians",
                participant_type=ParticipantType.ORG_UNIT,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="SCIENTISTS",
                display_name="Scientists",
                participant_type=ParticipantType.ORG_UNIT,
                created_by=created_by,
            ),
        ]
        org_unit_lookup = {}
        for org_unit in org_units:
            pati = repo.create(org_unit)
            org_unit_lookup[org_unit.name] = pati.id

        scientists: list[ParticipantCreate] = [
            ParticipantCreate(
                name="einstein",
                display_name="Einstein, Albert",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="galileo",
                display_name="Galilei, Galileo",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="tesla",
                display_name="Tesla, Nicola",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
        ]
        # Create scientists and add them to the org unit scientists
        for s in scientists:
            scientist = repo.create(s)
            repo.add_relation(
                scientist,
                org_unit_lookup["SCIENTISTS"],
                ParticipantRelationType.MEMBER_OF,
                created_by=created_by,
            )
            repo.add_relation(
                scientist,
                public_role.id,
                ParticipantRelationType.GRANT,
                created_by=created_by,
            )
            if scientist.name == "EINSTEIN":
                repo.add_relation(
                    scientist,
                    admin_role.id,
                    ParticipantRelationType.GRANT,
                    created_by=created_by,
                )
                repo.add_relation(
                    scientist,
                    user_admin_role.id,
                    ParticipantRelationType.GRANT,
                    created_by=created_by,
                )

        mathematicians: list[ParticipantCreate] = [
            ParticipantCreate(
                name="newton",
                display_name="Newton, Isaac",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="riemann",
                display_name="Riemann, Bernhard",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="gauss",
                display_name="Gauss, Carl Friedrich",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="euler",
                display_name="Euler, Leonhard",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="euclid",
                display_name="Euclid",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
        ]
        # Create mathematicians and add them to ou mathematicians
        for m in mathematicians:
            mathematician = repo.create(m)
            repo.add_relation(
                mathematician,
                public_role.id,
                ParticipantRelationType.GRANT,
                created_by=created_by,
            )
            repo.add_relation(
                mathematician,
                org_unit_lookup["MATHEMATICIANS"],
                ParticipantRelationType.MEMBER_OF,
                created_by=created_by,
            )


def initialize_tables(engine: Engine) -> None:
    """Load some bootstrap data into the database, so we can work with"""
    logger.info("Initialize database")
    with Session(engine) as session:
        create_participants(session)
        session.commit()
        session.flush()


def execute_sql(
    connection: Connection, sql_text: str, _raise_on_error: bool = False
) -> None:
    try:
        connection.execute(text(sql_text))
    except Exception:
        logger.exception(f"Failed to execute statement: {sql_text} ")
    else:
        pass


def grant_participant_permissions(connection: Connection) -> None:
    """Grants all permissions on participant related objects". Ignores all errors"""
    grants_sql: list[str] = [
        f"""grant select, insert, update on {schema_prefix}participants to some_role""",
        f"""grant select, insert, update, delete on {schema_prefix}participant_relations to some_role""",
        f"""grant select on {schema_prefix}participant_relations_v to public""",
    ]
    for grant in grants_sql:
        execute_sql(connection, grant)


def grant_permissions(engine: Engine) -> None:
    """Grants the permissions to the tables and views"""
    with engine.connect() as connection:
        grant_participant_permissions(connection)
        connection.commit()
