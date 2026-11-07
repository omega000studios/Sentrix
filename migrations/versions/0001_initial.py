"""Initial backend schema."""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("orders", sa.Column("id", sa.String(128), primary_key=True), sa.Column("capture_id", sa.String(128), nullable=False, unique=True), sa.Column("paypal_order_id", sa.String(128), nullable=False), sa.Column("amount", sa.Numeric(12, 2), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("paypal_address", sa.JSON(), nullable=False), sa.Column("seller_protection", sa.String(32), nullable=False), sa.Column("source", sa.String(16), nullable=False), sa.Column("state", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("messages", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_id", sa.String(128), sa.ForeignKey("orders.id"), nullable=False), sa.Column("external_id", sa.String(128), nullable=False), sa.Column("text", sa.String(10000), nullable=False), sa.Column("analysis", sa.JSON(), nullable=True), sa.UniqueConstraint("order_id", "external_id"))
    op.create_table("labels", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_id", sa.String(128), sa.ForeignKey("orders.id"), nullable=False), sa.Column("data", sa.JSON(), nullable=False))
    op.create_table("verdicts", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("order_id", sa.String(128), sa.ForeignKey("orders.id"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("rule_version", sa.String(32), nullable=False), sa.Column("inputs", sa.JSON(), nullable=False), sa.Column("result", sa.JSON(), nullable=False))


def downgrade():
    for table in ("verdicts", "labels", "messages", "orders"):
        op.drop_table(table)
