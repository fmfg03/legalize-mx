"""Add OAuth identity bindings, gate evidence and transactional release outbox.

Legacy receipts retain execution_id=NULL; they cannot act as gate execution evidence.
No users or bindings are provisioned by this migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261013_0003"
down_revision = "20260405_0002"
branch_labels = None
depends_on = None

SQLITE_ENUM_COLUMNS = (
    ("app_users", "role"), ("expedientes", "status"), ("expediente_parties", "role"),
    ("expediente_documents", "document_type"), ("expediente_documents", "status"),
    ("document_versions", "source_kind"), ("expediente_events", "event_type"),
    ("expediente_deadlines", "status"), ("release_receipts", "verdict"),
)


def timestamps():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade():
    # The previous ORM stored enum member names in SQLite, while PostgreSQL
    # migrations define enum values. Normalize the fallback database on upgrade.
    if op.get_bind().dialect.name == "sqlite":
        for table, column in SQLITE_ENUM_COLUMNS:
            target = sa.table(table, sa.column(column))
            op.get_bind().execute(target.update().values({column: sa.func.lower(target.c[column])}))
    if op.get_bind().dialect.name == "postgresql":
        for table, column in (("app_users", "email"), ("api_keys", "key_prefix")):
            op.drop_constraint(f"uq_{table}_{column}", table, type_="unique")
            op.drop_index(f"ix_{table}_{column}", table_name=table)
            op.create_index(f"ix_{table}_{column}", table, [column], unique=True)
    op.create_table("oauth_bindings",
        *timestamps(),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_oauth_bindings_issuer_subject"),
    )
    op.create_table("gate_executions",
        *timestamps(),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("app_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expediente_id", sa.Uuid(), sa.ForeignKey("expedientes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), sa.ForeignKey("document_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("bundle", sa.JSON(), nullable=False),
        sa.Column("bundle_sha256", sa.String(64), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("policy_hashes", sa.JSON(), nullable=False),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
    )
    with op.batch_alter_table("release_receipts") as batch:
        batch.add_column(sa.Column("execution_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_release_receipts_execution_id_gate_executions", "gate_executions", ["execution_id"], ["id"], ondelete="RESTRICT")
        batch.create_unique_constraint("uq_release_receipts_execution_id", ["execution_id"])
    op.create_table("release_outbox",
        *timestamps(),
        sa.Column("receipt_id", sa.Uuid(), sa.ForeignKey("release_receipts.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )


def downgrade():
    # Avoid silently discarding security evidence on an accidental downgrade.
    for table in ("gate_executions", "oauth_bindings", "release_outbox"):
        if op.get_bind().scalar(sa.select(sa.func.count()).select_from(sa.table(table))):
            raise RuntimeError("Cannot downgrade while security evidence or bindings exist")
    op.drop_table("release_outbox")
    with op.batch_alter_table("release_receipts") as batch:
        batch.drop_constraint("uq_release_receipts_execution_id", type_="unique")
        batch.drop_constraint("fk_release_receipts_execution_id_gate_executions", type_="foreignkey")
        batch.drop_column("execution_id")
    op.drop_table("gate_executions")
    op.drop_table("oauth_bindings")
    if op.get_bind().dialect.name == "sqlite":
        for table, column in SQLITE_ENUM_COLUMNS:
            target = sa.table(table, sa.column(column))
            op.get_bind().execute(target.update().values({column: sa.func.upper(target.c[column])}))
    if op.get_bind().dialect.name == "postgresql":
        for table, column in (("app_users", "email"), ("api_keys", "key_prefix")):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
            op.create_unique_constraint(f"uq_{table}_{column}", table, [column])
            op.create_index(f"ix_{table}_{column}", table, [column], unique=False)
