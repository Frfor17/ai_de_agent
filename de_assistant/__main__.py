from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .db import fetch_head, list_tables, run_query, test_connection

app = typer.Typer(add_completion=False, help="Data Engineer Assistant CLI for PostgreSQL")
console = Console()


def _version_callback(ctx: typer.Context, param: typer.CallbackParam, value: Optional[bool]):
    if value:
        console.print(f"de-assistant {__version__}")
        raise typer.Exit()
    return value


@app.callback()
def main(version: Optional[bool] = typer.Option(None, "--version", "-v", is_eager=True, help="Show version and exit", callback=_version_callback)):
    pass


# Rely on Typer's built-in --help


@app.command("test-connection")
def cmd_test_connection():
    ok, message = test_connection()
    if ok:
        console.print(f"[green]{message}[/green]")
        raise typer.Exit(code=0)
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(code=1)


@app.command("tables")
def cmd_tables(schema: Optional[str] = typer.Option(None, "--schema", help="Schema name (default: all user schemas)"), include_system: bool = typer.Option(False, "--include-system", help="Include system schemas")):
    pairs = list_tables(include_system=include_system, schema=schema)
    table = Table("schema", "table")
    for sch, tbl in pairs:
        table.add_row(sch, tbl)
    console.print(table)


@app.command("head")
def cmd_head(table_name: str = typer.Argument(..., help="Table name"), schema: Optional[str] = typer.Option(None, "--schema", help="Schema name (default: public)"), limit: int = typer.Option(10, "--limit", min=1, help="Number of rows to show")):
    columns, rows = fetch_head(table=table_name, schema=schema, limit=limit)
    table = Table(*[str(c) for c in columns])
    for row in rows:
        table.add_row(*["" if v is None else str(v) for v in row])
    console.print(table)


@app.command("query")
def cmd_query(sql_text: str = typer.Argument(..., help="SQL query to run"), limit: Optional[int] = typer.Option(None, "--limit", min=1, help="Limit rows by wrapping the query")):
    columns, rows = run_query(sql_text, limit=limit)
    if not columns:
        console.print("[yellow]Query executed. No rows returned.[/yellow]")
        raise typer.Exit(code=0)
    table = Table(*[str(c) for c in columns])
    for row in rows:
        table.add_row(*["" if v is None else str(v) for v in row])
    console.print(table)


def _main():
    app()


if __name__ == "__main__":
    _main()
