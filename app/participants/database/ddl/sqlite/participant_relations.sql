--drop table participant_relations;

create table participant_relations
(
    id               INTEGER                            not null
        primary key,
    pati1_id         INTEGER                            not null,
    pati2_id         INTEGER                            not null,
    relation_type    VARCHAR(16)                        not null,
    created_by       VARCHAR(30)                        not null,
    created_datetime DATETIME default CURRENT_TIMESTAMP not null,
    constraint participant_relations_ak1
        unique (pati1_id, pati2_id, relation_type),
    constraint participants_chk1
        check (relation_type in ('GRANT', 'MEMBER OF', 'PROXY OF'))
);

create index participant_relations_fk2
    on participant_relations (pati2_id);

--drop view participant_relations_v;

create view participant_relations_v as
select r.id, p1.id p1_id, coalesce(p1.state,'ACTIVE') as p1_state, p1.name as p1_name, p1.display_name as p1_display_name,
p1.participant_type as p1_pati_type,  r.relation_type,
p2.name as p2_name, p2.display_name as p2_display_name, p2.id p2_id, p2.participant_type as p2_pati_type,
coalesce(p2.state,'ACTIVE') as p2_state, r.created_by,
r.created_datetime
from participant_relations r
inner join participants p1 on (r.pati1_id = p1.id)
inner join participants p2 on (r.pati2_id = p2.id)
;
