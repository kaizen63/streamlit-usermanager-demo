--
-- Create table participant_relations and view participant_relations_v


--
-- PARTICIPANT_RELATIONS  (Table)
--
-- drop view participant_relations_v;
-- drop table participant_relations;
create table participant_relations
(
  id                     int identity(1,1)   not null,
  pati1_id               integer             not null,
  pati2_id               integer             not null,
  relation_type          nvarchar(16)        not null,
  -- maintenance columns
  created_by                     nvarchar(30) not null,
  created_timestamp               datetime default current_timestamp not null,
;

--comment on table participant_relations is
--'Defines relationships between participants';

--comment on column participant_relations.relation_type is
--'Either "GRANT", "MEMBER OF" or "PROXY OF"';


--
-- PARE_PATI_ARG2_FK_I  (Index) 
--
alter table participant_relations add constraint participant_relations_pk primary key (id);

--
--
--
create index pare_pati_fk on participant_relations
(pati1_id)
;

-- 
-- Non Foreign Key Constraints for Table SRE_UI_PARTICIPANT_RELATIONS
-- 
alter table participant_relations add
  constraint participant_relations_ak
  unique (pati1_id, pati2_id, relation_type)
;


create index participant_relations_arg2_fk on participant_relations
(pati2_id)
;

-- 
-- Foreign Key Constraints for Table PARTICIPANT_RELATIONS
-- 
alter table participant_relations add
  constraint participant_relations_arg2_fk
  foreign key (pati2_id) 
  references participants (id)  on delete no action
  ;

alter table participant_relations add
  constraint participant_relations_arg1_fk
  foreign key (pati1_id) 
  references participants (id) on delete cascade
  ;

alter table participant_relations add
  constraint participant_relations_chk check ( relation_type in ('GRANT', 'MEMBER OF', 'PROXY OF') )
;

grant select, insert, update, delete on participant_relations to appuser;

drop view participant_relations_v;

create view  participant_relations_v as
select r.id, p1.id p1_id, coalesce(p1.state,'ACTIVE') as p1_state, p1.name as p1_name, p1.display_name as p1_display_name,
p1.participant_type as p1_pati_type,  r.relation_type,
p2.name as p2_name, p2.display_name as p2_display_name, p2.id p2_id, p2.participant_type as p2_pati_type,
coalesce(p2.state,'ACTIVE') as p2_state, r.created_by,
r.created_timestamp
from participant_relations r
inner join participants p1 on (r.pati1_id = p1.id)
inner join participants p2 on (r.pati2_id = p2.id)
;

grant select on participant_relations_v to public;

commit;
