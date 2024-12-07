from participants import ParticipantType, ParticipantRelationType
from participants import ParticipantCreate, ParticipantRepository
from sqlalchemy import Engine, text, Connection
from sqlmodel import Session
import logging
from config import settings
import os

schema = os.getenv("DB_SCHEMA")
if schema:
    schema_prefix = schema + "."
else:
    schema_prefix = ""


logger = logging.getLogger(settings.LOGGER_NAME)


def create_participants(session: Session):
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
            created_by=created_by,
            description="Can add users, orgs and roles",
        )
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
        org_unit_lookup = dict()
        for org_unit in org_units:
            pati = repo.create(org_unit)
            org_unit_lookup[org_unit.name] = pati.id

        scientists: list[ParticipantCreate] = [
            ParticipantCreate(
                name="einstein",
                display_name="Einstein",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="newton",
                display_name="Newton",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="galileo",
                display_name="Galileo",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="tesla",
                display_name="Tesla",
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
                name="riemann",
                display_name="Riemann",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="gauss",
                display_name="Gauss",
                participant_type=ParticipantType.HUMAN,
                created_by=created_by,
            ),
            ParticipantCreate(
                name="euler",
                display_name="Euler",
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


def initialize_tables(engine: Engine):
    """Load some bootstrap data into the database, so we can work with"""
    logger.info("Initialize database")
    with Session(engine) as session:
        create_participants(session)
        session.commit()
        session.flush()


def execute_sql(
    connection: Connection, sql_text: str, raise_on_error: bool = False
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
    return


def grant_permissions(engine: Engine):
    """Grants the permissions to the tables and views"""
    with engine.connect() as connection:
        grant_participant_permissions(connection)
        connection.commit()
