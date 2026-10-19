"""Permit unknown deal/property types for channel imports without guessing.

Revision ID: 20261019_0008
Revises: 20261019_0007
"""
from alembic import op

revision = "20261019_0008"
down_revision = "20261019_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_listings_deal_type", "listings", type_="check")
    op.drop_constraint("ck_listings_property_type", "listings", type_="check")
    op.create_check_constraint(
        "ck_listings_deal_type", "listings",
        "deal_type IN ('rent', 'sale', 'daily', 'unknown')",
    )
    op.create_check_constraint(
        "ck_listings_property_type", "listings",
        "property_type IN ('apartment', 'household', 'house', 'dormitory', 'unknown')",
    )


def downgrade() -> None:
    raise RuntimeError("Production downgrade is disabled to protect listing data.")
