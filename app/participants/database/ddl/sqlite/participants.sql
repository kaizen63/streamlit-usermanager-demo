
-- drop table participants;

create table participants
(
    id                 INTEGER                            not null
        primary key,
    name               VARCHAR(30)                        not null,
    display_name       VARCHAR(60)                        not null,
    description        VARCHAR(500),
    participant_type   VARCHAR(30)                        not null,
    email              VARCHAR(200),
    state              VARCHAR(20),
    external_reference VARCHAR(500),
    hashed_password    VARCHAR(100),
    update_count       INTEGER  default 0                 not null,
    created_by         VARCHAR(30)                        not null,
    created_datetime   DATETIME default CURRENT_TIMESTAMP not null,
    updated_by         VARCHAR(30),
    updated_datetime   DATETIME,
    constraint participants_ak1
        unique (participant_type, name),
    constraint participants_ak2
        unique (participant_type, display_name),
    constraint participants_chk1
        check (participant_type in ('SYSTEM', 'HUMAN', 'ROLE', 'ORG_UNIT'))
);

create view participants_v
as select * from participants;
