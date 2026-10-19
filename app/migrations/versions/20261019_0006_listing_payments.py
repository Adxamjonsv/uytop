"""Add listing payment verification and separate moderation approval.

Revision ID: 20261019_0006
Revises: 20261019_0005
"""
from alembic import op
import sqlalchemy as sa

revision = "20261019_0006"
down_revision = "20261019_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("payment_status", sa.String(length=16), nullable=False, server_default="unpaid"))
    op.add_column("listings", sa.Column("payment_reference", sa.String(length=160), nullable=True))
    op.add_column("listings", sa.Column("payment_proof_file_id", sa.String(length=255), nullable=True))
    op.add_column("listings", sa.Column("payment_verified_by", sa.BigInteger(), nullable=True))
    op.add_column("listings", sa.Column("admin_approved", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_check_constraint("ck_listings_payment_status", "listings", "payment_status IN ('unpaid', 'submitted', 'paid')")
    op.create_foreign_key("fk_listings_payment_verified_by_admins", "listings", "admins", ["payment_verified_by"], ["id"], ondelete="SET NULL")
    op.execute("UPDATE listings SET payment_status = 'paid', admin_approved = true WHERE status = 'active'")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrades are disabled. Apply a reviewed forward migration instead.")
