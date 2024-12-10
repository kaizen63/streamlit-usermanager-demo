--
-- Table participants
-- Short Name pati
--
set search_path to unittest;

--drop table participants;

create table participants
(
  id bigint GENERATED ALWAYS AS IDENTITY (MINVALUE 1 START WITH 1 CACHE 10) PRIMARY key,
  name               varchar(30)     not null,
  display_name       varchar(60)     not null,
  description        varchar(500)    null, -- Optional description
  participant_type   varchar(30)     not null,
  email              varchar(200)    null,
  state              varchar(20)     null,
  external_reference varchar(500)    null,
  hashed_password    varchar(100)    null, -- for HUMAN and local authorization. Use bcrypt to hash it
  -- maintenance columns
  update_count       int default 0 not null, -- Incremented by every update to let the frontend know something has changed in the db.
  created_by                     varchar(30) not null,
  created_datetime               timestamp with time zone default current_timestamp not null,
  updated_by                     varchar(30)      null,
  updated_datetime               timestamp with time zone
);

--comment on table participants is
--'Stores participants of the system.';

--comment on column participants.state is 'ACTIVE (or null) or TERMINATED.';

--comment on column participants.participant_type is
--'ROLE, ORGANIZATIONAL_UNIT, HUMAN or SYSTEM. A process definition only contains ROLEs. The other participant types will be used later on';


--comment on column participants.email is
--'An email address of the participant, if applicable'
--;

--comment on column participants.external_reference is
--'An external key (id or name) used to sync with an external system';


alter table participants add
  constraint participants_ak1
  unique
  (participant_type, name)
  ;

alter table participants add
  constraint participants_ak2
  unique
  (participant_type, display_name)
  ;

alter table participants add
  constraint participants_chk1
  check
  (participant_type in ('ROLE', 'ORG_UNIT', 'HUMAN', 'SYSTEM'))
;

alter table participants add
  constraint participants_chk2
  check
  (state in (NULL, 'ACTIVE', 'TERMINATED'))
;

grant select, insert, update on participants to appuser;

commit;

