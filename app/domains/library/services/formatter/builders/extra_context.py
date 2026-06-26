from typing import Dict, Any

def build_extra_context(extra: Any, parent_formatted_name: str, config: Any) -> Dict[str, Any]:
    """Builds context variables for Extra files."""
    sub_cat = extra.subtype.value.replace("_", " ").title() if getattr(extra, "subtype", None) else ""
    category = extra.category.value if hasattr(extra.category, "value") else str(extra.category or "")
    if category.lower() == "metadata" and sub_cat.lower() == (extra.extension or "").lower().strip("."):
        sub_cat = ""

    return {
        "ParentName": parent_formatted_name,
        "Category": category,
        "category": category,
        "SubCategory": sub_cat,
        "sub_category": sub_cat,
        "Language": extra.language.upper() if getattr(extra, "language", None) else "",
        "language": extra.language.upper() if getattr(extra, "language", None) else "",
        "ext": extra.extension or "",
        "custom": config.custom_text
    }
