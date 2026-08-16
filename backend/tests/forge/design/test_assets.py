"""B9: built-in asset picker tests."""

from app.forge.assets.picker import asset_pick, format_assets_for_prompt


def test_asset_pick_returns_defaults() -> None:
    assets = asset_pick("generic arcade game")
    assert len(assets) >= 2
    assert all(a.data_uri.startswith("data:") for a in assets)


def test_asset_pick_keyword_match() -> None:
    assets = asset_pick("player blue enemy red background grid")
    ids = {a.asset_id for a in assets}
    assert "sprite_player_blue" in ids or "bg_grid_dark" in ids


def test_format_assets_for_prompt() -> None:
    assets = asset_pick("player")
    text = format_assets_for_prompt(assets)
    assert "data_uri" in text
    assert assets[0].asset_id in text
