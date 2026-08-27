"""Knowledge Metadata  taxonomy 与校验（ADR-14 §3.2–§3.3）。"""

from __future__ import annotations

DOMAIN_CATEGORIES: dict[str, frozenset[str]] = {
    "design": frozenset(
        {
            "gameplay_mechanic",
            "game_genre",
            "design_principle",
            "numeric_design",
            "level_design",
            "progression",
            "economy",
            "difficulty",
        }
    ),
    "example": frozenset(
        {
            "historical_game",
            "gameplay_case",
            "prototype_case",
            "ui_case",
            "mechanic_case",
        }
    ),
    "art": frozenset(
        {
            "art_direction",
            "ui_style",
            "ui_case",
            "color",
            "visual_reference",
            "asset_rule",
        }
    ),
    "platform": frozenset(
        {
            "engine_constraint",
            "output_contract",
            "coding_rule",
            "platform_capability",
            "security_rule",
        }
    ),
    "ops": frozenset({"connectivity_probe"}),
}

VALID_DOMAINS = frozenset(DOMAIN_CATEGORIES)
VALID_ACL = frozenset({"public", "internal", "restricted"})
VALID_QUALITY_TIERS = frozenset({"gold", "silver", "bronze"})


def metadata_validation_error(
    *,
    domain: str,
    category: str,
    acl: str,
    quality_tier: str = "silver",
) -> str | None:
    """返回首条校验错误；合法则 None。"""
    d = domain.strip()
    c = category.strip()
    a = acl.strip()
    tier = quality_tier.strip()
    if d not in VALID_DOMAINS:
        return f"invalid domain: {d!r}"
    allowed = DOMAIN_CATEGORIES.get(d, frozenset())
    if c not in allowed:
        return f"invalid category {c!r} for domain {d!r}"
    if a not in VALID_ACL:
        return f"invalid acl: {a!r}"
    if tier not in VALID_QUALITY_TIERS:
        return f"invalid quality_tier: {tier!r}"
    return None
