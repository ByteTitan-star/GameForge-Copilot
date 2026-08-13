"""0015: 游戏封面截图——Game.cover_path 与 GameVersion.thumbnail_path。"""

import sqlalchemy as sa

from alembic import op

revision = "0015_game_covers"
down_revision = "0014_forge_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 均 nullable、不回填：老游戏无封面，前端卡片回退 CSS 渐变。
    op.add_column(
        "games",
        sa.Column("cover_path", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "game_versions",
        sa.Column("thumbnail_path", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("game_versions", "thumbnail_path")
    op.drop_column("games", "cover_path")
