"""0012: publish_requests 部分唯一索引——每游戏至多一个待审核申请。

消除并发 submit 的 TOCTOU（两个请求同时读到 DRAFT 都插入 SUBMITTED 行）。
索引仅覆盖 submitted/reviewing；rejected/approved 不占名额，允许驳回后重提。

若现网已存在同 game 的多条 submitted/reviewing 脏数据，需先人工保留最新一条、
其余改判 rejected，再执行本迁移（本项目尚无生产数据，可直接建索引）。
"""

import sqlalchemy as sa

from alembic import op

revision = "0012_publish_active_unique"
down_revision = "0011_batch_bc_social"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_publish_active_per_game",
        "publish_requests",
        ["game_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('submitted', 'reviewing')"),
        sqlite_where=sa.text("status IN ('submitted', 'reviewing')"),
    )


def downgrade() -> None:
    op.drop_index("uq_publish_active_per_game", table_name="publish_requests")
