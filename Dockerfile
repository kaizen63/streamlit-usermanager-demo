FROM python:3.12
# Install Microsoft sqlserver odbc
# See: https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server?view=sql-server-ver16&tabs=debian18-install%2Calpine17-install%2Cdebian8-install%2Credhat7-13-install%2Crhel7-offline
#RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
#    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
#    apt-get update -y && \
#    ACCEPT_EULA=Y apt-get install -y msodbcsql18 procps net-tools tini
RUN apt-get update -y && apt-get install -y tini

# Remove after testing
#RUN apt-get install -y vim
#RUN alias ll='ls -l'


# https://docs.python.org/3/using/cmdline.html#envvar-PYTHONDONTWRITEBYTECODE
# Prevents Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE 1

# ensures that the python output is sent straight to terminal (e.g. your container log)
# without being first buffered and that you can see the output of your application (e.g. django logs)
# in real time. Equivalent to python -u: https://docs.python.org/3/using/cmdline.html#cmdoption-u
ENV PYTHONUNBUFFERED 1

# Install Poetry
# https://python-poetry.org/docs/#installing-with-the-official-installer
ENV POETRY_HOME=/opt/poetry
ENV PATH=$POETRY_HOME/bin:$PATH
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    poetry config virtualenvs.create false

ENV POETRY_ARGS_PROD="--no-ansi --no-root --without dev --no-interaction"
ENV POETRY_ARGS_DEV="--no-ansi --no-root --no-interaction"
ENV POETRY_ARGS=${POETRY_ARGS_PROD}
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV POETRY_VIRTUALENVS_OPTIONS_NO_SETUPTOOLS=true
ENV PIP_DEFAULT_TIMEOUT=100

WORKDIR /app
COPY ./pyproject.toml .
RUN poetry install -v ${POETRY_ARGS}

# Now copy the app
COPY ./app .
RUN cat <<____HERE > .streamlit/secrets.toml

[ldap]
# See https://www.forumsys.com/2022/05/10/online-ldap-test-server/
server_path = "ldap://ldap.forumsys.com:389"
domain = ""
search_base = "dc=example,dc=com"
# attributes: enterpriseid, canonical name, email, Name, manager, first name
# https://www.filestash.app/ldap-test-tool.html
#attributes = ["sAMAccountName", "distinguishedName", "userPrincipalName", "displayName", "manager", "title", "givenName"]
attributes = ["uid", "mail", "displayName", "title"]
use_ssl = true

[session_state_names]
user = "login_user"
remember_me = "login_remember_me"


[auth_cookie]
name = "stusermanagerdemo"
key = "hf9u9iXyZrUAUn4jue2!oDz_96dtAX*Q"
expiry_days = 1
auto_renewal = true
delay_sec = 0.1

[encryptor]
folderPath = ".rsa"
keyName = "authkey"

____HERE

RUN chmod +x run.sh \
    && rm -f poetry.lock \
    && rm -rf logs \
    && mkdir logs \
    && mkdir -p .rsa \
    && python3 generateKeys.py && chmod 0600 .rsa/authkey

RUN useradd --create-home appuser && chown -R appuser:appuser .
USER appuser

ENV PYTHONPATH=/app
ENV PYTHONFAULTHANDLER=1

EXPOSE 8501

HEALTHCHECK --interval=30s --start-period=5s --retries=3 --timeout=10s CMD ["curl", "--fail",  "http://localhost:8501/_stcore/health"]
ENTRYPOINT []
CMD ["tini", "-s", "-g", "--", "./run.sh"]
