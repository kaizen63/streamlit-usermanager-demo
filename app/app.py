import logging
import os
from typing import Any, Iterable, Literal, Optional, TypeAlias
from sqlmodel import Session, select
import streamlit as st
from streamlit.connections import SQLConnection
from common import (
    check_access,
    compute_effective_app_roles,
    dequote,
    get_policy_enforcer,
    get_st_current_user,
    is_administrator,
    user_is_manager,
    CurrentUser,
)
from config import settings
from dotenv import find_dotenv, load_dotenv
from main_menu import render_main_menu
from participants import (
    Participant,
    ParticipantRepository,
    ParticipantType,
    ParticipantUpdate,
    ParticipantModel,
)

from setup_logging import (
    set_log_level_from_env,
    setup_logging,
    get_level,
    LogLevelInvalidError,
)

from streamlit_ldap_authenticator import Authenticate, Connection, UserInfos
from streamlit_rsa_auth_ui import SignoutEvent
from users import render_self_registration_form
from db import (
    get_engine,
    create_db_and_tables,
    create_db_engine,
    get_url,
    get_db,
)
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from initialize_tables import initialize_tables


# from streamlit_extras.bottom_container import bottom
logger = logging.getLogger(settings.LOGGER_NAME)

LayoutType: TypeAlias = Literal["centered", "wide"]


def get_role_manager():
    """Returns the role manager from the policy enforcer"""
    return get_policy_enforcer().get_role_manager()


def roles_of_role(role: str, role_manager) -> list[str]:
    """Returns the roles of a role. Assigned in the policy.csv"""
    return role_manager.get_roles(role)


def get_all_roles(role: str, seen: set[str], role_manager) -> None:
    """Get all roles of a role recursive. Drill down into each role to find other role to tole assignments"""
    if role in seen:
        return
    seen.add(role)
    for sub_role in roles_of_role(role, role_manager):
        get_all_roles(sub_role, seen, role_manager)


def get_all_roles_of_roles(roles: set[str]) -> set[str]:
    """Get all roles of a role. Drill down into each role to find other role to tole assignments"""
    role_manager = (
        get_role_manager()
    )  # Retrieve role manager once to avoid redundant calls
    all_roles: set[str] = set()
    for role in roles:
        get_all_roles(role, all_roles, role_manager)
    return all_roles


def update_user_record(
    pati_repo: ParticipantRepository, pati: Participant, user: UserInfos
) -> Participant:
    """Compares user infos with db and updates the db if they are not equal.
    Returns the (modified) participant
    """

    user_changes: dict[str, str | None] = {
        "display_name": (
            user["displayName"]
            if pati.display_name != user["displayName"]
            else None
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
    else:
        pati_repo.commit()
        return updated_participant if updated_participant else pati


def add_roles_to_policy_enforcer(username, roles: Iterable[str]) -> None:
    """Adds the (effective) roles to cabin"""
    enforcer = st.session_state["policy_enforcer"]
    if not enforcer:
        return
    for r in roles:
        logger.debug(f"{username=}: Add role {r} to policy enforcer")
        enforcer.add_role_for_user(username, r)


def update_user_session_state(
    pati_repo: ParticipantRepository, pati: Participant, user: UserInfos
) -> None:
    """Clears the cache and sets the following variables in st.session_state:
    current_user
    username
    user_display_name
    """
    st.cache_data.clear()
    current_user: dict[str, Any] = {
        "username": pati.name,
        "display_name": pati.display_name,
        "email": pati.email or user["email"],
    }
    if pati.roles or pati.org_units or pati.proxy_of:
        logger.debug(
            f"update_user_session_state: compute effective roles for: {pati.name}"
        )
        # roles directly assigned or via org
        current_user["roles"] = pati_repo.compute_effective_roles(pati)
        current_user["effective_roles"] = get_all_roles_of_roles(
            current_user["roles"]
        )
    else:
        current_user["effective_roles"] = set()
        current_user["roles"] = set()

    if pati.org_units:
        current_user["org_units"] = set([ou.name for ou in pati.org_units])
    st_current_user: CurrentUser = CurrentUser(**current_user)
    st_current_user.update_session_state()
    st.session_state["username"] = pati.name
    st.session_state["user_display_name"] = pati.display_name
    st.session_state["user_email"] = pati.email
    current_user["title"] = user.get("title") or "unknown"


def check_user(conn: Optional[Connection], user: UserInfos) -> bool | str:
    """Validate if the AD user is our list of participants

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
    if is_administrator(username):
        if "user" in st.query_params:
            username = st.query_params["user"].upper()
        if "title" in st.query_params:
            user["title"] = st.query_params["title"]

    # logger.debug(f"Checking user {username}")

    current_user = CurrentUser.get_from_session_state()
    if current_user and username == current_user.username:
        return True

    with ParticipantRepository(get_db()) as pati_repo:
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
            current_user = CurrentUser.get_from_session_state()
            if current_user.username == user["uid"].upper():
                pati = update_user_record(pati_repo, pati, user)

            logger.info(
                f"User {current_user.display_name} ({current_user.username}) logged in."
            )
            st_effective_roles = current_user.effective_roles

            logger.debug(
                f"Participant {pati.name} has these effective roles in the session state: {', '.join(st_effective_roles)}"
            )
            add_roles_to_policy_enforcer(
                pati.name,
                st_effective_roles,
            )
            return True
        else:
            # Not a user in the database. Check the job title
            logger.debug(
                f"check_user: {username=} not known. Checking job title"
            )
            if user_is_manager(user):
                initialize_manager_user(user, username)
                return True
            else:
                clear_user_session()
                return "You are not authorized to login"


def initialize_manager_user(user: UserInfos, username: str) -> None:
    """Initialize a manager user session with limited roles."""
    current_user: CurrentUser = CurrentUser(
        username=username,
        display_name=user["displayName"],
        email=user["email"],
        roles=set(),
        effective_roles={
            "PUBLIC",
        },
        title=user.get("title", ""),
    )
    current_user.update_session_state()
    st.session_state.username = username
    st.session_state["must_register"] = True
    logger.info(
        f"User {current_user.display_name!a} ({current_user.username}) logged in."
    )


def clear_user_session() -> None:
    """Clear user session for unauthorized users."""
    st.session_state["current_user"] = {}
    st.session_state.username = ""
    st.session_state["user_email"] = ""
    st.session_state["user_display_name"] = ""


def role_checkbox_callback(role, key) -> None:
    # logger.debug(f"Callback: {role=}, {key=}")
    if key not in st.session_state:
        return
    # To for check_access to reread.
    check_access.clear()
    if not (current_user := CurrentUser.get_from_session_state()):
        return
    enforcer = get_policy_enforcer()
    if st.session_state[key] is True:
        current_user.effective_roles.add(role)
        enforcer.add_role_for_user(current_user.username, role)
    else:
        current_user.effective_roles.discard(role)
        enforcer.delete_role_for_user(current_user.username, role)
    return


def render_user_roles(
    title: str, all_roles: list[str], users_effective_roles: set[str]
) -> None:
    """Render the tickboxes with user roles on the sidebar"""
    st.write(title)
    if "PUBLIC" in all_roles:
        all_roles.remove("PUBLIC")
    for i, role in enumerate(all_roles):
        key = f"sidebar_roles_{i}"
        value = role in users_effective_roles
        st.checkbox(
            role,
            value=value,
            disabled=False,
            on_change=role_checkbox_callback,
            args=(role, key),
            key=key,
        )


def render_sidebar(auth: Authenticate, user: dict[str, Any]) -> None:
    """Render the sidebar"""

    def render_logout_form(user: str):
        """Renders the logout form"""
        (
            auth.createLogoutForm(
                config={
                    "message": "",
                    "title": {
                        "text": f"Welcome {user}",
                        "size": "small",
                    },
                },
                callback=signout_callback,
            )
            if auth
            else st.write(f"Welcome {user}")
        )

    current_user = CurrentUser.get_from_session_state()
    if not current_user:
        return
    with st.sidebar:
        # st.sidebar.title(f"Welcome {user['displayName']}")
        # display_user = get_st_current_user()
        st.write("### Welcome: " + get_st_current_user().display_name)
        # render_logout_form()
        st.divider()

        # Use a new policy enforcer, so the files are read again. We need to know
        # when a policy has changed. e.g. when the SUPERADMIN is granted and revoked
        if is_administrator(current_user.username):
            user_roles: list[str] = sorted(
                list(get_all_roles_of_roles(current_user.roles))
            )
            effective_roles = current_user.effective_roles

            render_user_roles("Your roles:", user_roles, effective_roles)

            st.divider()
            # because I am too lazy to type the param in the url. Added this shortcut
            if st.checkbox(
                "Debug Menu", value=st.query_params.get("debug", "0") == "1"
            ):
                st.query_params["debug"] = "1"
            else:
                if st.query_params.get("debug"):
                    del st.query_params["debug"]

            if is_administrator(st.session_state.username):
                if st.button("Clear caches"):
                    logger.info(
                        "Clear caches was requested via user interface."
                    )
                    st.cache_data.clear()


def init_session_state() -> None:
    pass


def signout_callback(event: SignoutEvent) -> Literal["cancel", None]:
    if event.event == "signout":
        logger.info(
            f"User {st.session_state.get('user_display_name', '?')} ({st.session_state.get('username', '?')}) logged out."
        )
        st.session_state["username"] = ""
        st.session_state["user_display_name"] = ""
        st.session_state["current_user"] = dict()
        st.session_state["must_register"] = False
        st.session_state["policy_enforcer"] = None

        connection: SQLConnection | None = st.session_state.get(
            "db_connection"
        )
        if connection:
            connection.engine.dispose()
            st.session_state["db_connection"] = None

        st.cache_data.clear()
        for key in st.session_state.keys():
            del st.session_state[key]
    return None  # return "cancel" on error


def render_login_screen(auth: Authenticate) -> dict[str, Any]:
    # col1, col2, col3 = st.columns(3)
    # with col2:
    # The standard login function adds \\ in front of the username, becuse
    # it thinks it is an active directory ldap

    # user = auth.login(
    #    check_user,
    #    config={"align": "center"},
    #    getLoginUserName=lambda u: u,
    # )
    user: dict[str, Any] = dict()
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


def put_settings_into_session_state() -> None:
    """Puts settings and env into session state without showing the secrets"""
    s = settings.model_dump()
    s["DB_PASSWORD"] = "*****"
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
    page_icon: str = ":robot:"
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

    put_settings_into_session_state()
    get_policy_enforcer()
    # We disconnect after the script run thru, because we don't want to have long running sessions in the database.
    # But: Callbacks need to reconnect to the database.
    #
    engine = get_engine()
    with Session(engine) as db:

        logger.debug("Connected to database")

        auth = get_authenticator()
        user = render_login_screen(auth)
        if not user:
            return

        init_session_state()
        render_sidebar(auth, user)

        if st.session_state.get("must_register", False) and user_is_manager():
            render_self_registration_form("## Self Registration")
        else:
            render_main_menu()

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
