"""Initial expediente backend schema."""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    expediente_status = sa.Enum("open", "in_progress", "stayed", "closed", "archived", name="expediente_status")
    party_role = sa.Enum(
        "actor",
        "demandado",
        "quejoso",
        "autoridad_responsable",
        "tercero",
        "imputado",
        "victima",
        "defensor",
        "apoderado",
        "other",
        name="party_role",
    )
    document_type = sa.Enum(
        "notificacion",
        "emplazamiento",
        "acuerdo",
        "sentencia",
        "demanda",
        "escrito",
        "oficio",
        "constancia",
        "anexo",
        "prueba",
        "otro",
        name="document_type",
    )
    document_status = sa.Enum("draft", "active", "superseded", "void", "archived", name="document_status")
    version_source_kind = sa.Enum("generated", "uploaded", "imported", "ocr", "system", name="version_source_kind")
    event_type = sa.Enum("actuacion", "notificacion", "audiencia", "presentacion", "resolucion", "other", name="event_type")
    deadline_status = sa.Enum("open", "satisfied", "missed", "cancelled", name="deadline_status")
    release_verdict = sa.Enum("approved", "blocked", "bypass", name="release_verdict")

    bind = op.get_bind()
    expediente_status.create(bind, checkfirst=True)
    party_role.create(bind, checkfirst=True)
    document_type.create(bind, checkfirst=True)
    document_status.create(bind, checkfirst=True)
    version_source_kind.create(bind, checkfirst=True)
    event_type.create(bind, checkfirst=True)
    deadline_status.create(bind, checkfirst=True)
    release_verdict.create(bind, checkfirst=True)

    op.create_table(
        "expedientes",
        sa.Column("expediente_number", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("matter_type", sa.String(length=80), nullable=False),
        sa.Column("jurisdiction_level", sa.String(length=32), nullable=True),
        sa.Column("jurisdiction_detail", sa.String(length=255), nullable=True),
        sa.Column("forum_or_recipient", sa.String(length=255), nullable=True),
        sa.Column("court_or_authority", sa.String(length=255), nullable=True),
        sa.Column("procedural_stage", sa.String(length=128), nullable=True),
        sa.Column("requested_outcome", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("opened_on", sa.Date(), nullable=True),
        sa.Column("closed_on", sa.Date(), nullable=True),
        sa.Column("status", expediente_status, nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expedientes")),
    )
    op.create_index(op.f("ix_expedientes_expediente_number"), "expedientes", ["expediente_number"], unique=False)
    op.create_index(op.f("ix_expedientes_matter_type"), "expedientes", ["matter_type"], unique=False)
    op.create_index(op.f("ix_expedientes_jurisdiction_level"), "expedientes", ["jurisdiction_level"], unique=False)

    op.create_table(
        "expediente_parties",
        sa.Column("expediente_id", sa.Uuid(), nullable=False),
        sa.Column("role", party_role, nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("identifier", sa.String(length=128), nullable=True),
        sa.Column("contact_data", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["expediente_id"], ["expedientes.id"], name=op.f("fk_expediente_parties_expediente_id_expedientes"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expediente_parties")),
    )

    op.create_table(
        "expediente_documents",
        sa.Column("expediente_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", document_status, nullable=False),
        sa.Column("issuing_authority", sa.String(length=255), nullable=True),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("served_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_version_id", sa.Uuid(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["expediente_id"], ["expedientes.id"], name=op.f("fk_expediente_documents_expediente_id_expedientes"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expediente_documents")),
    )
    op.create_index(op.f("ix_expediente_documents_document_type"), "expediente_documents", ["document_type"], unique=False)
    op.create_index(op.f("ix_expediente_documents_event_date"), "expediente_documents", ["event_date"], unique=False)

    op.create_table(
        "document_versions",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_kind", version_source_kind, nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["expediente_documents.id"], name=op.f("fk_document_versions_document_id_expediente_documents"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_versions")),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_versions_doc_version"),
        sa.UniqueConstraint("storage_key", name=op.f("uq_document_versions_storage_key")),
    )

    op.create_foreign_key(
        op.f("fk_expediente_documents_current_version_id_document_versions"),
        "expediente_documents",
        "document_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "expediente_events",
        sa.Column("expediente_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", event_type, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["expediente_documents.id"], name=op.f("fk_expediente_events_document_id_expediente_documents"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["expediente_id"], ["expedientes.id"], name=op.f("fk_expediente_events_expediente_id_expedientes"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expediente_events")),
    )
    op.create_index(op.f("ix_expediente_events_event_date"), "expediente_events", ["event_date"], unique=False)

    op.create_table(
        "expediente_deadlines",
        sa.Column("expediente_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", deadline_status, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["expediente_documents.id"], name=op.f("fk_expediente_deadlines_document_id_expediente_documents"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["expediente_id"], ["expedientes.id"], name=op.f("fk_expediente_deadlines_expediente_id_expedientes"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expediente_deadlines")),
    )
    op.create_index(op.f("ix_expediente_deadlines_due_at"), "expediente_deadlines", ["due_at"], unique=False)

    op.create_table(
        "release_receipts",
        sa.Column("expediente_id", sa.Uuid(), nullable=True),
        sa.Column("document_version_id", sa.Uuid(), nullable=True),
        sa.Column("verdict", release_verdict, nullable=False),
        sa.Column("response_type", sa.String(length=64), nullable=True),
        sa.Column("policy_id", sa.String(length=128), nullable=True),
        sa.Column("bundle_path", sa.String(length=512), nullable=True),
        sa.Column("artifact_path", sa.String(length=512), nullable=True),
        sa.Column("bundle_sha256", sa.String(length=64), nullable=True),
        sa.Column("gate_summary", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_version_id"], ["document_versions.id"], name=op.f("fk_release_receipts_document_version_id_document_versions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["expediente_id"], ["expedientes.id"], name=op.f("fk_release_receipts_expediente_id_expedientes"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_release_receipts")),
    )


def downgrade() -> None:
    op.drop_table("release_receipts")
    op.drop_index(op.f("ix_expediente_deadlines_due_at"), table_name="expediente_deadlines")
    op.drop_table("expediente_deadlines")
    op.drop_index(op.f("ix_expediente_events_event_date"), table_name="expediente_events")
    op.drop_table("expediente_events")
    op.drop_table("document_versions")
    op.drop_index(op.f("ix_expediente_documents_event_date"), table_name="expediente_documents")
    op.drop_index(op.f("ix_expediente_documents_document_type"), table_name="expediente_documents")
    op.drop_table("expediente_documents")
    op.drop_table("expediente_parties")
    op.drop_index(op.f("ix_expedientes_jurisdiction_level"), table_name="expedientes")
    op.drop_index(op.f("ix_expedientes_matter_type"), table_name="expedientes")
    op.drop_index(op.f("ix_expedientes_expediente_number"), table_name="expedientes")
    op.drop_table("expedientes")

    bind = op.get_bind()
    sa.Enum(name="release_verdict").drop(bind, checkfirst=True)
    sa.Enum(name="deadline_status").drop(bind, checkfirst=True)
    sa.Enum(name="event_type").drop(bind, checkfirst=True)
    sa.Enum(name="version_source_kind").drop(bind, checkfirst=True)
    sa.Enum(name="document_status").drop(bind, checkfirst=True)
    sa.Enum(name="document_type").drop(bind, checkfirst=True)
    sa.Enum(name="party_role").drop(bind, checkfirst=True)
    sa.Enum(name="expediente_status").drop(bind, checkfirst=True)
