# STREAMLIT USERMANAGER DEMO 

Streamlit user interface to maintain Users, Groups, Org Units.

## Status

[![Docker Image CI](https://github.com/kaizen63/streamlit-usermanager-demo/actions/workflows/docker-image.yml/badge.svg)](https://github.com/kaizen63/streamlit-usermanager-demo/actions/workflows/docker-image.yml)
[![Python application](https://github.com/kaizen63/streamlit-usermanager-demo/actions/workflows/python-app.yml/badge.svg)](https://github.com/kaizen63/streamlit-usermanager-demo/actions/workflows/python-app.yml)


## Quickstart using Docker

Requires Docker installed on your computer.

To run the application on a Mac, copy the code below into a terminal window and execute:

```bash
git clone git@github.com:kaizen63/streamlit-usermanager-demo.git
cd streamlit-usermanager-demo
chmod +x *.sh
./docker_run.sh
```

To stop and remove the container run:

```bash
docker compose down
```

## Authentication
**NOT IMPLEMENTED / WORKING**
Authentication is done via LDAP service. User has to enter his username and password.

## Authorization
Menus and functions are restricted to various roles. The roles are defined in the database and assigned there either to users or org units.
Authorization is done via the [casbin package](https://github.com/casbin/pycasbin).  

The UI is set up for role based access control in [model.conf](./app/casbin/model.conf). Don't touch it unless you know what you are doing.
The configuration of who can do what is managed in policies stored in the file [policy.csv](./app/casbin/policy.csv)


## Roles
Following application specific roles are defined in the system:

| Role                  | Description                                                        |
|-----------------------|--------------------------------------------------------------------|
| ADMINISTRATOR         | Can do everything                                                  |
| USER_ADMINISTRATOR    | Can create and edit users, roles and teams and their relationships |
| USER_READ             | Can read users                                                     |
| USER_WRITE            | Cand edit users                                                    |
| ROLE_READ             | Can read roles                                                     |
| ROLE_WRITE            | Can edit roles                                                     |
| ORG_UNIT_READ         | Can read Org Units                                                 |
| ORG_UNIT_WRITE        | Can edit Org Units                                                 |                                     
| PUBLIC                | Can only use the contact form                                      |
 

### Access to main menu

| Role               | Home  | Users | Roles | Orgs | 
|--------------------|-------|-------|-------|------|
| ADMINISTRATOR      | yes   | yes   | yes   | yes  |
| USER_ADMINISTRATOR | no    | yes   | yes   | yes  |
| USER_READ          | yes   | yes   | no    | no   |
| USER_WRITE         | yes   | yes   | no    | no   |
| ROLE_READ          | yes   | no    | yes   | no   |
| ROLE_WRITE         | yes   | no    | yes   | no   |
| ORG_UNIT_READ      | yes   | no    | no    | yes  |
| ORG_UNIT_WRITE     | yes   | no    | no    | yes  |
| PUBLIC             | no    | no    | no    | no   |


### Sidebar menu

In the sidebar menu is the *Sign-Out* button. If you are an ADMINISTRATOR you will find tickboxes to disable the effective
roles of your user. This is only used for validating the RBAC to the menus.

### Role Assignment - Best Practices

Reduce assigning roles directly to users to a minimum. Instead, create teams (org units) and grant the roles to the teams.
When moving a person from one team to another he will automatically get the right permissions of the new team.



## URL query parameters

Following query parameters are supported in the URL:

| Parameters | Purpose                                                                                                                         |
|------------|---------------------------------------------------------------------------------------------------------------------------------|
| menu       | Selected item in the main menu                                                                                                  |
| debug      | If set to 1, shows an additional Debug menu where you can see the session state variables                                       |
| loglevel  | Set to DEBUG to enable the loglevel DEBUG. Usefull if you want to debug something in prod, where the default loglevel is INFO  |


## RBAC Implementation

### Role Model
Roles are stored in the database table **participants** with a participant_type of *ROLE*
Users (participant_type *HUMAN* ) and Teams (participant_type *ORG_UNIT*) are stored in the same
table. Relationships between participants are defined in the table **participant_relations**
There are 3 different relation_ship_types:
* GRANT
* MEMBER OF
* PROXY OF

Roles can be granted to either Users (HUMAN) and Teams (ORG_UNIT)

```mermaid
erDiagram
    participants ||--o{ participant_relations: has
    participants {
        bigint id
        varchar(30) name
        varchar(60) display_name
        varchar(500) description
        varchar(30) participant_type
        varchar(200) email
        varchar(20) state
        varchar(500) external_reference
        varchar(100) hashed_password
        int update_count
        varchar(30) created_by
        timestamp created_datetime 
        varchar(30) updated_by
        timestamp updated_datetime
    }
    
    participant_relations {
        bigint id
        bigint pati1_id
        bigint pati2_id
        varchar(16) relation_type
        varchar(30) created_by
        timestamp created_timestamp
        
    }
  ```

[ER Diagram](images/particiapants_er_diagram.png)


To better illustrate the relationship the view [participants_relations](images/participant_relations_v.png) is available.

## Environment Variables

| Environment Variable                    | Purpose                                                                                              | Default                      | Example                                            |
|-----------------------------------------|------------------------------------------------------------------------------------------------------|------------------------------|----------------------------------------------------|
| DB_SERVER                               | The database server where the data is stored                                                         |                              |                                                    |
| DB_DATABASE                             | The database name                                                                                    |                              |                                                    |
| DB_PORT                                 | The database port                                                                                    |                              |                                                    |
| DB_USERNAME                             | The database username                                                                                |                              |                                                    |
| DB_PASSWORD                             | The password of the db user                                                                          |                              |                                                    |
| DB_SCHEMA                               | The schema where we find our tables. Empty for sqlite                                                |                              |                                                    |
| LDAP_SERVER                             | The ldap server we use for authentication                                                            |                              | ldap://ldap.forumsys.com                                                   |
| STREAMLIT_LOGGER_LEVEL                  | The loglevel for streamlit                                                                           | INFO                         | WARNING in prod                                    |
| STREAMLIT_LOGGER_MESSAGE_FORMAT         | The message format used by streamlit                                                                 |                              | %(asctime)s %(levelname)s [%(name)s] [%(process)d] - %(message)s |
| STREAMLIT_SERVER_FOLDER_WATCH_BLACKLIST | Folders to ignore when watching for changed files                                                    |                              | ["/app/logs", "./logs"]                            |
| STREAMLIT_BROWSER_GATHER_USAGE_STATS    | Enable usage stats gathering for streamlit                                                           | True                         | Set it to False in all envs                        |
| STREAMLIT_SERVER_FILE_WATCHER_TYPE      | Disable the filewatcher                                                                              |                              | none                                               |
| LOGGING_CONFIG                          | Log config for our app                                                                               | log-config/logging-conf.yaml | log-config/logging-conf.prod.yaml                  |
| LOGGING_LOG_LEVEL                       | The log level of our app                                                                             | INFO                         | DEBUG in dev                                       |
| LOGGER_SERVICE                          | The service tag in the json log                                                                      |                              |                                                    |
| POLICY_TTL                              | Set the TTL in seconds of the policy cache. For debugging Adminstrator special functions set it to 0 | 600                          | 0 in development                                   |



## Administrator view

Users with the role ADMINISTRATOR can simulate the behaviour of the application for different roles to test the application.

As Administrator you see the this [sidebar](images/administrator_sidebar.jpg)

Initially all roles are on. Switch off the tickboxes beside the role to remove the role from the current session.
You will notice how the main menu will change. 
Also in some dialogs fields will be disabled when you do not have the appropriate role.



