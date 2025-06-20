import logging
import os
from collections.abc import Iterable
from typing import Any, Literal, TypeAlias

import streamlit as st
from common import (
    dequote,
)
from config import settings
from db import (
    create_db_and_tables,
    create_db_engine,
    get_engine,
    get_session,
    get_url,
    log_session_pool_statistics,
)
from dotenv import find_dotenv, load_dotenv
from initialize_tables import initialize_tables
from main_menu import render_main_menu
from participants import (
    Participant,
    ParticipantModel,
    ParticipantRepository,
    ParticipantType,
    ParticipantUpdate,
)
from session_user import SessionUser, get_session_user
from setup_logging import (
    LogLevelInvalidError,
    get_level,
    set_log_level_from_env,
    setup_logging,
)
from sidebar import render_sidebar
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, select
from streamlit_ldap_authenticator import Authenticate, Connection, UserInfos
from user_permissions import (
    get_all_roles_of_roles,
    get_policy_enforcer,
    get_user_permissions,
    user_is_administrator,
    user_is_manager,
)
from users import render_self_registration_form

# from streamlit_extras.bottom_container import bottom
logger = logging.getLogger(settings.LOGGER_NAME)

LayoutType: TypeAlias = Literal["centered", "wide"]


def update_user_record(
    pati_repo: ParticipantRepository, pati: Participant, user: UserInfos
) -> Participant:
    """
    Compares user infos with db and updates the db if they are not equal.

    Returns the (modified) participant
    """
    user_changes: dict[str, str | None] = {
        "display_name": (
            user["displayName"] if pati.display_name != user["displayName"] else None
        ),
        "email": (user["email"] if pati.email != user["email"] else None),
    }
    user_changes = {k: v for k, v in user_changes.items() if v}
    if not user_changes:
        return pati

    logger.info(f"Updating user {user['displayName']} with data from ldap.")
    user_changes["updated_by"] = "SYSTEM"
    try:
        update = ParticipantUpdate.model_validate(user_changes)
        updated_participant = pati_repo.update(pati.id, update)
    except Exception as e:
        pati_repo.rollback()
        logger.exception(
            f"Cannot update userid: {pati.id=}, {pati.name=}, {pati.display_name=} {pati.participant_type=} {e=}"
        )
        raise

    pati_repo.commit()
    return updated_participant if updated_participant else pati


def add_roles_to_policy_enforcer(username: str, roles: Iterable[str]) -> None:
    """Adds the (effective) roles to cabin"""
    enforcer = get_policy_enforcer()
    for r in roles:
        logger.debug(f"{username=}: Add role {r} to policy enforcer")
        enforcer.add_role_for_user(username, r)


def update_user_session_state(
    pati_repo: ParticipantRepository, pati: Participant, user: UserInfos
) -> None:
    """
    Clears the cache.

    Sets the following variables in st.session_state:
    session_user
    username
    user_display_name
    """
    st.cache_data.clear()
    session_user: SessionUser = SessionUser(
        username=pati.name,
        display_name=pati.display_name,
        email=pati.email or user["email"],
    )
    if pati.roles or pati.org_units or pati.proxy_of:
        logger.debug(
            f"update_user_session_state: compute effective roles for: {pati.name}"
        )
        # roles directly assigned or via org
        session_user.roles = pati_repo.compute_effective_roles(pati)
        session_user.effective_roles = get_all_roles_of_roles(session_user.roles)
        add_roles_to_policy_enforcer(pati.name, session_user.effective_roles)

    else:
        session_user.effective_roles = set()
        session_user.roles = set()

    if pati.org_units:
        session_user.org_units = {ou.name for ou in pati.org_units}

    session_user.permissions = get_user_permissions(pati.name)
    session_user.title = user.get("title") or "unknown"
    session_user.casbin_roles = get_policy_enforcer().get_roles_for_user(pati.name)
    session_user.update_session_state()

    st.session_state["username"] = pati.name
    st.session_state["user_display_name"] = pati.display_name
    st.session_state["user_email"] = pati.email


def check_user(_conn: Connection | None, user: UserInfos) -> bool | str:
    """
    Validate if the AD user is our list of participants

    UserInfos fields (from Active Directory):
    sAMAccountName : Username
    displayName: Last Name, First Name
    userPrincipalName: Email address of the user
    givenName: First Name
    distinguishedName: Name with LDAP fields: "CN=Poitschke, Kai,OU=Engineering,OU=Europe,OU=Accounts,DC=example,DC=com"
    title: Job title
    manager: Job manager in format like distinguishedName
    """
    # for testing
    # st.session_state["must_register"] = True
    username = user["uid"].upper()
    logger.debug(f"check_user starts for uid: {username}")
    # We can fake our userid and title if we are admin
    if user_is_administrator(username):
        if "user" in st.query_params:
            username = st.query_params["user"].upper()
        if "title" in st.query_params:
            user["title"] = st.query_params["title"]

    # logger.debug(f"Checking user {username}")

    session_user: SessionUser = get_session_user()
    if session_user and username == session_user.username:
        return True

    with get_session() as session, ParticipantRepository(session) as pati_repo:
        pati = pati_repo.get_by_name(
            username,
            participant_type=ParticipantType.HUMAN,
            include_relations=True,
        )
        if pati is not None:
            logger.debug(
                f"check_user: {username} has {len(pati.roles)} roles and {len(pati.org_units)} org_units"
            )
            update_user_session_state(pati_repo, pati, user)
            # We update the database with email, display_name and distinguishedName with the LDAP values
            # if they are different and we did not fake our userid
            if session_user.username == user["uid"].upper():
                pati = update_user_record(pati_repo, pati, user)

            logger.info(
                f"User {session_user.display_name} ({session_user.username}) logged in."
            )
            st_effective_roles = session_user.effective_roles

            logger.debug(
                f"Participant {pati.name} has these effective roles in the session state: {', '.join(st_effective_roles)}"
            )
            add_roles_to_policy_enforcer(
                pati.name,
                st_effective_roles,
            )
            return True
        # Not a user in the database. Check the job title
        logger.debug(f"check_user: {username=} not known. Checking job title")
        if user_is_manager(user):
            initialize_manager_user(user, username)
            return True
        clear_user_session()
        return "You are not authorized to login"


def initialize_manager_user(user: UserInfos, username: str) -> None:
    """Initialize a manager user session with limited roles."""
    session_user: SessionUser = SessionUser(
        username=username,
        display_name=user["displayName"],
        email=user["email"],
        roles=set(),
        effective_roles={
            "PUBLIC",
        },
        title=user.get("title", ""),
    )
    session_user.update_session_state()
    st.session_state.username = username
    st.session_state["must_register"] = True
    logger.info(
        f"User {session_user.display_name!a} ({session_user.username}) logged in."
    )


def clear_user_session() -> None:
    """Clear user session for unauthorized users."""
    st.session_state["session_user"] = {}
    st.session_state.username = ""
    st.session_state["user_email"] = ""
    st.session_state["user_display_name"] = ""


def render_login_screen(_auth: Authenticate) -> dict[str, Any]:
    # col1, col2, col3 = st.columns(3)
    # with col2:
    # The standard login function adds \\ in front of the username, becuse
    # it thinks it is an active directory ldap

    # user = auth.login(
    #    check_user,
    #    config={"align": "center"},
    #    getLoginUserName=lambda u: u,
    # )
    user: dict[str, Any] = {}
    if not user:
        user = {
            "uid": "einstein",
            "email": "albert.einstein@princeton.edu",
            "displayName": "Einstein, Albert",
            "title": "Nobel Price Winner",
        }
        check_user(
            None,
            user=user,
        )
    return user


def save_settings_into_session_state() -> None:
    """Puts settings and env into session state without showing the secrets"""
    s = settings.model_dump()
    s["DB_PASSWORD"] = "*****"  # noqa: S105
    s["settings"] = s


def set_log_level() -> None:
    """Sets the loglevel either from query_param or settings.LOGGING_LOG_LEVEL"""
    set_log_level_from_env(settings.LOGGER_NAME)
    if "loglevel" in st.query_params:
        log_level = st.query_params["loglevel"].upper()
    else:
        log_level = settings.LOGGING_LOG_LEVEL

    try:
        level_code = get_level(log_level)
    except LogLevelInvalidError:
        logger.error(f"Unknown loglevel: {log_level}")
        st.exception(ValueError(f"Unknown loglevel: {log_level}"))
        st.stop()
    else:
        if level_code != logger.level:
            logger.info(f"Set loglevel to {log_level}")
            logger.setLevel(level_code)
            if logger.root:
                logger.root.setLevel(level_code)
                logging.root.setLevel(level_code)


def configure_main_page() -> None:
    """Configures the main page. Must be the first call to streamlit"""
    # Page icons: https://www.webfx.com/tools/emoji-cheat-sheet/
    # https://streamlit-emoji-shortcodes-streamlit-app-gwckff.streamlit.app/
    page_icon: str = ":material/robot:"
    layout: LayoutType = "wide"
    page_title: str = "Streamlit UserManager Demo"
    st.set_page_config(
        page_title=page_title,
        layout=layout,
        initial_sidebar_state="expanded",
        page_icon=page_icon,
    )


def get_authenticator() -> Authenticate:
    """Gets the Authenticator instance"""
    ldap_config = dict(st.secrets["ldap"])
    ldap_config["server_path"] = settings.LDAP_SERVER or dequote(
        st.secrets["ldap"]["server_path"]
    )

    logger.debug(ldap_config)
    auth = Authenticate(
        ldap_config,
        st.secrets["session_state_names"],
        st.secrets["auth_cookie"],
        st.secrets["encryptor"],
    )
    return auth


def is_database_empty(engine: Engine) -> bool:
    """Checks whether we deal with an empty database"""
    with Session(engine) as session:
        result = session.exec(select(ParticipantModel).limit(1)).first()
        return result is None


def setup_database() -> None:
    """We create the tables in a sqlite database. Executed unless db_initialized is not present in st.session_state"""
    if not st.session_state.get("db_initialized"):
        db_name_env = os.getenv("DB_DATABASE")
        db_eng_env: str | None = os.getenv("DB_ENGINE")
        engine: Engine = create_db_engine(
            get_url(db_eng_env),
            db_schema=os.getenv("DB_SCHEMA"),
            echo=True,
            poolclass=StaticPool,
        )

        if db_eng_env == "sqlite":
            if db_name_env == ":memory:":
                engine = get_engine()
            create_db_and_tables(engine)
            # Check if the participant table is empty. If yes, its a new db and we add some records to start with.
            if is_database_empty(engine):
                initialize_tables(engine)
        elif db_eng_env == "mssql":
            pass
            # Throws only errors
            # grant_permissions(engine)
        # engine.dispose()
    st.session_state["db_initialized"] = True


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))
    # use LOG_CONFIG env variable to pass in the name of the file
    setup_logging(settings.LOGGING_CONFIG)
    set_log_level()

    configure_main_page()
    setup_database()

    save_settings_into_session_state()
    get_policy_enforcer()
    # We disconnect after the script run thru, because we don't want to have long running sessions in the database.
    # But: Callbacks need to reconnect to the database.
    #
    engine = get_engine()
    with Session(engine):
        logger.debug("Connected to database")

        auth = get_authenticator()
        user = render_login_screen(auth)
        if not user:
            return

        session_user = get_session_user()
        session_user.permissions = get_user_permissions(session_user.username)
        session_user.update_session_state()

        render_sidebar(auth)

        if st.session_state.get("must_register", False) and user_is_manager():
            render_self_registration_form("## Self Registration")
        else:
            render_main_menu()
    log_session_pool_statistics("app.main")

    # Now we are disconnected from the db. Callbacks need to reconnect


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(e)
        raise

    # For profiling:
    # See: https://docs.python.org/3/library/profile.html
    # Sort keys:
    # calls (call count)
    # cumulative (cumulative time)
    # cumtime (cumulative time)
    # file (file name)
    # filename (file name)
    # module (file name)
    # ncalls (call count)
    # pcalls (primitive call count)
    # line (line number)
    # name (function name)
    # nfl (name/file/line)
    # stdname (standard name)
    # time (internal time)
    # tottime (internal time)
    # import cProfile

    # cProfile.run("main()", sort="cumtime")
    # cProfile.run("main()", sort="tottime")
    # cProfile.run("main()", sort="ncalls")
    # cProfile.run("main()", sort="pcall")
