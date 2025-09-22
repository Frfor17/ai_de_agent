from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, Iterable, List, Optional, Sequence, Tuple

from dotenv import load_dotenv
from psycopg import Connection, connect
from psycopg.rows import dict_row
from psycopg import sql


@dataclass
class DatabaseConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    sslmode: Optional[str] = None


def load_config_from_env() -> DatabaseConfig:
    load_dotenv(override=False)

    host = os.getenv("DB_HOST", "localhost")
    port_str = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "postgres")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")
    sslmode = os.getenv("DB_SSLMODE")

    try:
        port = int(port_str)
    except ValueError as exc:
        raise ValueError(f"DB_PORT must be an integer, got: {port_str}") from exc

    return DatabaseConfig(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        sslmode=sslmode,
    )


@contextmanager
def db_connection(config: Optional[DatabaseConfig] = None) -> Generator[Connection, None, None]:
    configuration = config or load_config_from_env()
    kwargs = dict(
        host=configuration.host,
        port=configuration.port,
        dbname=configuration.dbname,
        user=configuration.user,
        password=configuration.password,
        row_factory=dict_row,
    )
    if configuration.sslmode:
        kwargs["sslmode"] = configuration.sslmode

    connection: Connection = connect(**kwargs)
    try:
        yield connection
    finally:
        connection.close()


def test_connection() -> Tuple[bool, str]:
    try:
        with db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 as ok")
                row = cur.fetchone()
                if row and row.get("ok") == 1:
                    return True, "Connection successful"
                return False, "Connection established, but unexpected response"
    except Exception as exc:  # noqa: BLE001
        return False, f"Connection failed: {exc}"


def list_tables(include_system: bool = False, schema: Optional[str] = None) -> List[Tuple[str, str]]:
    schema_filter = ""
    params: List[str] = []
    if schema is not None:
        schema_filter = "and t.table_schema = %s"
        params.append(schema)
    elif not include_system:
        schema_filter = "and t.table_schema not in ('pg_catalog', 'information_schema')"

    query = f"""
        select t.table_schema, t.table_name
        from information_schema.tables t
        where t.table_type = 'BASE TABLE' {schema_filter}
        order by t.table_schema, t.table_name
    """

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            result = cur.fetchall()
            return [(r["table_schema"], r["table_name"]) for r in result]


def fetch_head(table: str, schema: Optional[str] = None, limit: int = 10) -> Tuple[Sequence[str], List[Sequence[object]]]:
    if limit <= 0:
        raise ValueError("limit must be positive")

    schema_name = schema or "public"

    with db_connection() as conn:
        with conn.cursor() as cur:
            composed = sql.SQL("select * from {}.{} limit {};").format(
                sql.Identifier(schema_name),
                sql.Identifier(table),
                sql.Literal(limit),
            )
            cur.execute(composed)
            column_names = [col.name for col in cur.description] if cur.description else []
            rows = cur.fetchall()
            values = [tuple(row.values()) for row in rows]
            return column_names, values


def run_query(query: str, limit: Optional[int] = None) -> Tuple[Sequence[str], List[Sequence[object]]]:
    text = query.strip().rstrip(";")
    if limit is not None and limit > 0:
        text = f"select * from ({text}) as subquery limit {int(limit)}"

    with db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(text)
            column_names = [col.name for col in cur.description] if cur.description else []
            rows = cur.fetchall()
            values = [tuple(row.values()) for row in rows]
            return column_names, values
