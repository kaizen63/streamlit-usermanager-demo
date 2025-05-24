FROM python:3.12-slim-bookworm
# Update package lists and install required tools
RUN <<EOF
apt-get -y update && \
apt-get -y install --no-install-recommends \
curl \
gnupg \
apt-transport-https \
net-tools \
tini && \

# Add Microsoft package repository and install ODBC 18
# https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server?view=sql-server-ver16&tabs=debian18-install%2Calpine17-install%2Cdebian8-install%2Credhat7-13-install%2Crhel7-offline
OS_VERSION=$(grep VERSION_ID /etc/os-release | cut -d '"' -f 2 | cut -d '.' -f 1) && \
#curl -sSL -O https://packages.microsoft.com/config/debian/${OS_VERSION}/packages-microsoft-prod.deb && \
#dpkg -i packages-microsoft-prod.deb && rm packages-microsoft-prod.deb && \
#apt-get update -y && \
#ACCEPT_EULA=Y apt-get install --no-install-recommends -y msodbcsql18 procps net-tools tini

apt-get clean && rm -rf /var/lib/apt/lists/*
EOF


# https://docs.python.org/3/using/cmdline.html#envvar-PYTHONDONTWRITEBYTECODE
# Prevents Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1

# ensures that the python output is sent straight to terminal (e.g. your container log)
# without being first buffered and that you can see the output of your application (e.g. django logs)
# in real time. Equivalent to python -u: https://docs.python.org/3/using/cmdline.html#cmdoption-u
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=100

# Install uv
ADD https://astral.sh/uv/install.sh /install.sh
RUN chmod 755 /install.sh && /install.sh && rm /install.sh

ENV PATH=/root/.local/bin:$PATH

WORKDIR /app
RUN useradd --no-create-home appuser && chown -R appuser:appuser /app

COPY ./pyproject.toml .
RUN uv pip install -r pyproject.toml --system

# Now copy the app
USER appuser
# Now copy the app
COPY --chown=appuser:appuser ./app .
RUN <<EOF
python -c "import uuid; print(uuid.uuid4())" > auth_cookie_key.uuid
cat <<____HERE > .streamlit/secrets.toml

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
key = "$(cat auth_cookie_key.uuid)"
expiry_days = 1
auto_renewal = true
delay_sec = 0.1

[encryptor]
folderPath = ".rsa"
keyName = "authkey"

____HERE

# if the grep fails, the file was not created correct. Run the job again
echo "If the following grep fails, the secrets.toml file was not created. Build the image again"
grep keyName .streamlit/secrets.toml || exit 1
chmod +x run.sh \
&& rm -f uv.lock \
&& rm -rf logs \
&& mkdir logs \
&& mkdir -p .rsa
EOF
ENV PYTHONPATH=/app
ENV PYTHONFAULTHANDLER=1

EXPOSE 8501

HEALTHCHECK --interval=30s --start-period=5s --retries=3 --timeout=10s CMD ["curl", "--fail",  "http://localhost:8501/_stcore/health"]
ENTRYPOINT []
CMD ["tini", "-s", "-g", "--", "./run.sh"]
