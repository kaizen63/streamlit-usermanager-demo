--
-- Table participants
-- Short Name pati
--

--drop table participants;

create table participants
(
  id                 int identity(1000,1) not null,
  name               nvarchar(30)     not null,
  display_name       nvarchar(60)    not null,
  description        nvarchar(500)    null, -- Optional description
  participant_type   nvarchar(30)     not null,
  email              nvarchar(200)    null,
  state              nvarchar(20)     null,
  external_reference nvarchar(500)    null,
  hashed_password    nvarchar(100)    null, -- for HUMAN and local authorization. Use bcrypt to hash it
  -- maintenance columns
  update_count       int default 0 not null, -- Incremented by every update to let the frontend know something has changed in the db.
  created_by                     nvarchar(30) not null,
  created_datetime               datetime default current_timestamp not null,
  updated_by                     nvarchar(30)      null,
  updated_datetime               datetime
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
  constraint participants_pk
  primary key clustered (id)
  ;

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

