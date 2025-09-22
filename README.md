## Data Engineer Assistant CLI (PostgreSQL)

Minimal CLI to connect to PostgreSQL, list tables, preview rows, and run queries.

### Setup

1. Create a `.env` from the example and set your credentials:

```
cp .env.example .env
```

2. Install dependencies:

```
pip install -r requirements.txt
```

### Usage

Run the CLI:

```
python -m de_assistant --help
```

Test connection:

```
python -m de_assistant test-connection
```

List tables (optionally by schema):

```
python -m de_assistant tables --schema public
```

Preview table head:

```
python -m de_assistant head my_table --schema public --limit 10
```

Run a query (show first N rows):

```
python -m de_assistant query "select * from my_table" --limit 50
``;

Set env vars in `.env` or your shell. SSL mode can be `disable`, `prefer`, or `require`.
bla bla
