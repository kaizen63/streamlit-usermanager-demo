"""Defines the view participant_relations_v"""

from datetime import datetime
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlmodel import SQLModel

from .db_schema import schema_prefix


class ParticipantRelationsView(SQLModel, table=False):
    """The model for the view participant_relations_v"""

    __table_name__ = "participant_relations_v"
    p1_id: int
    p1_state: str
    p1_name: str
    p1_display_name: str
    p1_pati_type: str
    relation_type: str
    p2_name: str
    p2_display_name: str
    p2_id: int
    p2_pati_type: str
    p2_state: str
    created_by: str
    created_timestamp: datetime


create_view_sql = f"""
create view if not exists {schema_prefix}participant_relations_v as
select r.id, p1.id p1_id, coalesce(p1.state,'ACTIVE') as p1_state, p1.name as p1_name, p1.display_name as p1_display_name,
p1.participant_type as p1_pati_type,  r.relation_type,
p2.name as p2_name, p2.display_name as p2_display_name, p2.id p2_id, p2.participant_type as p2_pati_type,
coalesce(p2.state,'ACTIVE') as p2_state, r.created_by,
r.created_timestamp
from {schema_prefix}participant_relations r
inner join {schema_prefix}participants p1 on (r.pati1_id = p1.id)
inner join {schema_prefix}participants p2 on (r.pati2_id = p2.id)

"""  # noqa: S608


@event.listens_for(SQLModel.metadata, "after_create")
def create_view(_target: Any, connection: Connection, **_kwargs: Any) -> None:  # noqa: ANN401
    """Creates the view participant_relations_v after the table creation"""
    connection.execute(text(create_view_sql))
