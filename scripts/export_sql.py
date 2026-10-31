"""Export the StudyShare database to SQLite and MySQL SQL files.

Usage:
    python scripts/export_sql.py

Outputs:
    SQL/studyshare_schema.sql        SQLite schema + data
    SQL/studyshare_schema_mysql.sql  MySQL/MariaDB schema + data

The export contains the StudyShare tables plus ``auth_user``. Django's
internal tables (sessions, migrations, permissions, content types) are
omitted so the files stay readable and easy to import for demos.

Run ``python manage.py migrate`` for the database Django actually uses;
these dumps are for documentation, submission, or phpMyAdmin import.
"""

import os
import re
import sqlite3
import sys
from datetime import date, datetime, time
from pathlib import Path
from uuid import UUID

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db.models import UniqueConstraint  # noqa: E402

SQL_DIR = BASE_DIR / 'SQL'
SQLITE_DB = SQL_DIR / 'db.sqlite3'
SQLITE_DB_LABEL = SQLITE_DB.relative_to(BASE_DIR).as_posix()

BLOCKED_TABLES = {
    'auth_group',
    'auth_group_permissions',
    'auth_permission',
    'auth_user_groups',
    'auth_user_user_permissions',
    'django_admin_log',
    'django_content_type',
    'django_migrations',
    'django_session',
}

MODEL_ORDER = [
    ('auth', 'User'),
    ('users', 'Profile'),
    ('notes', 'Note'),
    ('notes', 'QuizSet'),
    ('notes', 'Question'),
    ('notes', 'QuizAttempt'),
    ('chat', 'Conversation'),
    ('chat', 'Message'),
    ('chat', 'MessageAttachment'),
    ('chat', 'ChatQuizAttempt'),
]

MYSQL_TYPE_OVERRIDES = {
    'AutoField': 'int',
    'BigAutoField': 'bigint',
    'SmallAutoField': 'smallint',
    'CharField': None,
    'TextField': 'longtext',
    'EmailField': 'varchar(254)',
    'BooleanField': 'tinyint(1)',
    'IntegerField': 'int',
    'BigIntegerField': 'bigint',
    'SmallIntegerField': 'smallint',
    'PositiveIntegerField': 'int unsigned',
    'PositiveBigIntegerField': 'bigint unsigned',
    'PositiveSmallIntegerField': 'smallint unsigned',
    'FloatField': 'double',
    'DecimalField': None,
    'DateTimeField': 'datetime(6)',
    'DateField': 'date',
    'TimeField': 'time(6)',
    'JSONField': 'json',
    'UUIDField': 'char(32)',
    'FileField': 'varchar(100)',
    'ImageField': 'varchar(100)',
}

ON_DELETE_SQL = {
    'CASCADE': 'CASCADE',
    'SET_NULL': 'SET NULL',
    'PROTECT': 'RESTRICT',
    'SET_DEFAULT': 'SET DEFAULT',
}


def study_models():
    models = []
    for app_label, model_name in MODEL_ORDER:
        if app_label == 'auth' and model_name == 'User':
            models.append(get_user_model())
        else:
            models.append(apps.get_model(app_label, model_name))
    return models


def mysql_type(field):
    internal = field.get_internal_type()
    if internal in {'ForeignKey', 'OneToOneField'}:
        return mysql_type(field.target_field)
    if internal in MYSQL_TYPE_OVERRIDES:
        mapped = MYSQL_TYPE_OVERRIDES[internal]
        if mapped is not None:
            return mapped
    if internal == 'CharField':
        return f'varchar({field.max_length})'
    if internal == 'DecimalField':
        return f'decimal({field.max_digits},{field.decimal_places})'
    raise ValueError(f'Unsupported field type for MySQL export: {internal}')


def mysql_literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, UUID):
        return f"'{value.hex}'"
    if isinstance(value, (datetime, date, time)):
        text = value.isoformat(sep=' ') if isinstance(value, datetime) else value.isoformat()
        return f"'{text}'"
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    text = str(value)
    text = (
        text.replace('\\', '\\\\')
        .replace("'", "''")
        .replace('\0', '\\0')
        .replace('\n', '\\n')
        .replace('\r', '\\r')
        .replace('\x1a', '\\Z')
    )
    return f"'{text}'"


def column_definition(field):
    name = f'`{field.column}`'
    definition = mysql_type(field)
    if field.primary_key:
        return f'{name} {definition} NOT NULL AUTO_INCREMENT PRIMARY KEY'
    parts = [name, definition, 'NULL' if field.null else 'NOT NULL']
    if field.unique:
        parts.append('UNIQUE')
    return ' '.join(parts)


def table_indexes(model):
    lines = []
    for field in model._meta.local_fields:
        if field.db_index and not field.unique and not field.primary_key:
            lines.append(
                f'  KEY `{model._meta.db_table}_{field.column}` (`{field.column}`)'
            )
    for index in model._meta.indexes:
        if not index.fields or index.contains_expressions:
            continue
        columns = ', '.join(
            f'`{model._meta.get_field(name).column}`' for name in index.fields
        )
        lines.append(f'  KEY `{index.name}` ({columns})')
    for constraint in model._meta.constraints:
        if isinstance(constraint, UniqueConstraint) and constraint.fields:
            columns = ', '.join(
                f'`{model._meta.get_field(name).column}`'
                for name in constraint.fields
            )
            lines.append(f'  UNIQUE KEY `{constraint.name}` ({columns})')
    return lines


def create_table_sql(model):
    table = model._meta.db_table
    lines = [f'CREATE TABLE `{table}` (']
    body = [f'  {column_definition(field)}' for field in model._meta.local_fields]
    body.extend(table_indexes(model))
    for field in model._meta.local_fields:
        if not (field.is_relation and field.many_to_one):
            continue
        target = field.related_model._meta.db_table
        target_column = field.target_field.column
        on_delete = ON_DELETE_SQL.get(
            getattr(field.remote_field.on_delete, '__name__', '')
        )
        rule = f' ON DELETE {on_delete}' if on_delete else ''
        body.append(
            f'  CONSTRAINT `fk_{table}_{field.column}` '
            f'FOREIGN KEY (`{field.column}`) REFERENCES `{target}` '
            f'(`{target_column}`){rule}'
        )
    lines.append(',\n'.join(body))
    lines.append(') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;')
    return '\n'.join(lines)


def table_columns(model):
    return [field.column for field in model._meta.local_fields]


def fetch_rows(connection, model):
    table = model._meta.db_table
    columns = table_columns(model)
    quoted = ', '.join(f'"{column}"' for column in columns)
    order = ''
    if model._meta.pk is not None:
        order = f' ORDER BY "{model._meta.pk.column}"'
    cursor = connection.execute(f'SELECT {quoted} FROM "{table}"{order}')
    return columns, cursor.fetchall()


def export_mysql(connection, path):
    lines = [
        '-- =====================================================================',
        '-- StudyShare schema - MySQL / MariaDB dialect',
        f'-- Generated from {SQLITE_DB_LABEL} on {date.today().isoformat()}.',
        '-- Engine: InnoDB, charset: utf8mb4.',
        '-- How to use: create an empty database in phpMyAdmin, select it, then',
        '-- import this file. (SQLite version: studyshare_schema.sql)',
        '-- Django bookkeeping tables are omitted; create the runnable database',
        '-- with "python manage.py migrate".',
        '-- =====================================================================',
        '',
        'SET NAMES utf8mb4;',
        'SET FOREIGN_KEY_CHECKS = 0;',
        '',
    ]

    models = study_models()
    for model in models:
        table = model._meta.db_table
        lines.append('-- ---------------------------------------------------------------------')
        lines.append(f'-- Table structure for `{table}`')
        lines.append('-- ---------------------------------------------------------------------')
        lines.append(create_table_sql(model))
        lines.append('')

    for model in models:
        table = model._meta.db_table
        columns, rows = fetch_rows(connection, model)
        lines.append('-- ---------------------------------------------------------------------')
        lines.append(f'-- Data for `{table}` ({len(rows)} rows)')
        lines.append('-- ---------------------------------------------------------------------')
        column_sql = ', '.join(f'`{column}`' for column in columns)
        for row in rows:
            values = ', '.join(mysql_literal(value) for value in row)
            lines.append(f'INSERT INTO `{table}` ({column_sql}) VALUES ({values});')
        lines.append('')

    lines.extend(
        [
            'SET FOREIGN_KEY_CHECKS = 1;',
            '',
            '-- End of StudyShare MySQL schema.',
            '',
        ]
    )
    path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')


def statement_table(statement):
    patterns = [
        r'^CREATE TABLE\s+"([^"]+)"',
        r'^INSERT INTO\s+"([^"]+)"',
        r'^DELETE FROM\s+"([^"]+)"',
        r'^CREATE (?:UNIQUE )?INDEX\s+"[^"]+"\s+ON\s+"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.match(pattern, statement, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def is_blocked_sequence_row(statement):
    match = re.match(
        r'^INSERT INTO "sqlite_sequence" VALUES\(\'([^\']+)\'',
        statement,
        re.IGNORECASE,
    )
    return bool(match and match.group(1) in BLOCKED_TABLES)


def export_sqlite(connection, path):
    dumped = []
    for statement in connection.iterdump():
        table = statement_table(statement)
        if table and table in BLOCKED_TABLES:
            continue
        if is_blocked_sequence_row(statement):
            continue
        dumped.append(statement)

    header = [
        '-- =====================================================================',
        '-- StudyShare schema - SQLite dialect',
        f'-- Generated from {SQLITE_DB_LABEL} on {date.today().isoformat()}.',
        '-- Includes the StudyShare tables and auth_user.',
        '-- Django bookkeeping tables are omitted; recreate a working database',
        '-- with: python manage.py migrate',
        '-- (MySQL version: studyshare_schema_mysql.sql)',
        '-- =====================================================================',
        '',
    ]
    path.write_text('\n'.join(header + dumped) + '\n', encoding='utf-8', newline='\n')


def main():
    if not SQLITE_DB.exists():
        raise SystemExit(f'Database not found: {SQLITE_DB}')

    SQL_DIR.mkdir(exist_ok=True)
    connection = sqlite3.connect(SQLITE_DB)

    try:
        sqlite_path = SQL_DIR / 'studyshare_schema.sql'
        mysql_path = SQL_DIR / 'studyshare_schema_mysql.sql'
        export_sqlite(connection, sqlite_path)
        export_mysql(connection, mysql_path)
    finally:
        connection.close()

    print(f'Wrote {sqlite_path.relative_to(BASE_DIR)}')
    print(f'Wrote {mysql_path.relative_to(BASE_DIR)}')


if __name__ == '__main__':
    main()
