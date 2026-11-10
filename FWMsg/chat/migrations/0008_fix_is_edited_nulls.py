# Recovery migration for production DBs where 0007 left NULL is_edited values
# on historical tables (PostgreSQL NOT NULL constraint violation).

from django.db import migrations, models


def _column_exists(connection, table, column):
    with connection.cursor() as cursor:
        if connection.vendor == 'postgresql':
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                [table, column],
            )
            return cursor.fetchone() is not None
        if connection.vendor == 'sqlite':
            cursor.execute(f'PRAGMA table_info("{table}")')
            return any(row[1] == column for row in cursor.fetchall())
    return False


def ensure_is_edited_defaults(apps, schema_editor):
    tables = (
        'chat_chatmessagedirect',
        'chat_chatmessagegroup',
        'chat_historicalchatmessagedirect',
        'chat_historicalchatmessagegroup',
    )
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        for table in tables:
            if not _column_exists(connection, table, 'is_edited'):
                continue

            quoted = schema_editor.quote_name(table)
            cursor.execute(
                f'UPDATE {quoted} SET is_edited = %s WHERE is_edited IS NULL',
                [False],
            )

            if connection.vendor == 'postgresql':
                cursor.execute(
                    f'ALTER TABLE {quoted} ALTER COLUMN is_edited SET DEFAULT false'
                )
                cursor.execute(
                    f'ALTER TABLE {quoted} ALTER COLUMN is_edited SET NOT NULL'
                )


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0007_chatmessagedirect_is_edited_and_more'),
    ]

    operations = [
        migrations.RunPython(ensure_is_edited_defaults, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='chatmessagedirect',
            name='is_edited',
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AlterField(
            model_name='chatmessagegroup',
            name='is_edited',
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AlterField(
            model_name='historicalchatmessagedirect',
            name='is_edited',
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AlterField(
            model_name='historicalchatmessagegroup',
            name='is_edited',
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]
