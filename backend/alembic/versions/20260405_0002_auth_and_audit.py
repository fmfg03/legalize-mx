"""Add backend auth and audit tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0002"
down_revision = "20260405_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    user_role = sa.Enum("admin", "operator", "reviewer", "observer", name="user_role")
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)

    op.create_table(
        "app_users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_users")),
        sa.UniqueConstraint("email", name=op.f("uq_app_users_email")),
    )
    op.create_index(op.f("ix_app_users_email"), "app_users", ["email"], unique=False)
    op.create_index(op.f("ix_app_users_role"), "app_users", ["role"], unique=False)

    op.create_table(
        "api_keys",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("key_prefix", sa.String(length=24), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], name=op.f("fk_api_keys_user_id_app_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
        sa.UniqueConstraint("key_prefix", name=op.f("uq_api_keys_key_prefix")),
        sa.UniqueConstraint("secret_hash", name=op.f("uq_api_keys_secret_hash")),
    )
    op.create_index(op.f("ix_api_keys_key_prefix"), "api_keys", ["key_prefix"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("expediente_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("route", sa.String(length=255), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["app_users.id"], name=op.f("fk_audit_logs_actor_user_id_app_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_actor_user_id"), "audit_logs", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_type"), "audit_logs", ["entity_type"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_id"), "audit_logs", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_expediente_id"), "audit_logs", ["expediente_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_document_id"), "audit_logs", ["document_id"], unique=False)

    audit_actor_tables = [
        "expedientes",
        "expediente_parties",
        "expediente_documents",
        "expediente_events",
        "expediente_deadlines",
    ]
    for table_name in audit_actor_tables:
        op.add_column(table_name, sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
        op.add_column(table_name, sa.Column("updated_by_user_id", sa.Uuid(), nullable=True))
        op.create_index(op.f(f"ix_{table_name}_created_by_user_id"), table_name, ["created_by_user_id"], unique=False)
        op.create_index(op.f(f"ix_{table_name}_updated_by_user_id"), table_name, ["updated_by_user_id"], unique=False)
        op.create_foreign_key(
            op.f(f"fk_{table_name}_created_by_user_id_app_users"),
            table_name,
            "app_users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_foreign_key(
            op.f(f"fk_{table_name}_updated_by_user_id_app_users"),
            table_name,
            "app_users",
            ["updated_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    created_only_tables = ["document_versions", "release_receipts"]
    for table_name in created_only_tables:
        op.add_column(table_name, sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
        op.create_index(op.f(f"ix_{table_name}_created_by_user_id"), table_name, ["created_by_user_id"], unique=False)
        op.create_foreign_key(
            op.f(f"fk_{table_name}_created_by_user_id_app_users"),
            table_name,
            "app_users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    created_only_tables = ["release_receipts", "document_versions"]
    for table_name in created_only_tables:
        op.drop_constraint(op.f(f"fk_{table_name}_created_by_user_id_app_users"), table_name, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table_name}_created_by_user_id"), table_name=table_name)
        op.drop_column(table_name, "created_by_user_id")

    audit_actor_tables = [
        "expediente_deadlines",
        "expediente_events",
        "expediente_documents",
        "expediente_parties",
        "expedientes",
    ]
    for table_name in audit_actor_tables:
        op.drop_constraint(op.f(f"fk_{table_name}_updated_by_user_id_app_users"), table_name, type_="foreignkey")
        op.drop_constraint(op.f(f"fk_{table_name}_created_by_user_id_app_users"), table_name, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table_name}_updated_by_user_id"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_created_by_user_id"), table_name=table_name)
        op.drop_column(table_name, "updated_by_user_id")
        op.drop_column(table_name, "created_by_user_id")

    op.drop_index(op.f("ix_audit_logs_document_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_expediente_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_type"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_user_id"), table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(op.f("ix_api_keys_key_prefix"), table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index(op.f("ix_app_users_role"), table_name="app_users")
    op.drop_index(op.f("ix_app_users_email"), table_name="app_users")
    op.drop_table("app_users")

    sa.Enum(name="user_role").drop(op.get_bind(), checkfirst=True)
