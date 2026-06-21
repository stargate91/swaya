import re
from typing import Dict, Any, Optional
from .config import FormatterConfig, Casing

class TemplateRenderer:
    """
    Handles template rendering, string casing, separator replacement,
    number formatting, and path sanitization.
    """

    ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|]')
    MULTI_SPACE = re.compile(r'\s{2,}')
    TEMPLATE_VAR = re.compile(r'\{(\w+)\}')

    def __init__(self, config: FormatterConfig):
        self.config = config

    def render(self, template: str, context: Dict[str, Any], is_file: bool = True) -> str:
        """Renders the template and automatically appends the extension if it's a file."""
        if not template:
            return ""
            
        # 1. Substitution (Case and Underscore insensitive lookup)
        # Create a normalized mapping (lowercase, no underscores)
        norm_ctx = {k.lower().replace("_", ""): v for k, v in context.items()}
        result = self.TEMPLATE_VAR.sub(lambda m: str(norm_ctx.get(m.group(1).lower().replace("_", ""), "")), template)
        
        # 2. Clean up empty parentheses/residuals
        result = re.sub(r'\(\s*\)', '', result)
        result = re.sub(r'\[\s*\]', '', result)
        
        # Collapse multiple separators (e.g., " -  - " -> " - ")
        result = re.sub(r'\s*-\s*-\s*', ' - ', result)
        result = re.sub(r'\s{2,}', ' ', result)
        
        result = re.sub(r'\s*-\s*$', '', result)
        result = re.sub(r'^\s*-\s*', '', result)
        result = self.sanitize(result, is_file)

        # 3. Apply Casing and Separator (only to the name, not the extension!)
        result = self.apply_casing(result, context)
        result = self.apply_separator(result)

        # 4. Automatically add extension if it is a file
        if is_file:
            ext = context.get("ext", "")
            if ext:
                ext_lower = ext.lower()
                if not result.lower().endswith(ext_lower):
                    result = f"{result}{ext_lower}"

        return result.strip()

    def apply_casing(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
        if not text:
            return ""
        if self.config.casing == Casing.LOWER:
            return text.lower()
        if self.config.casing == Casing.UPPER:
            return text.upper()
        if self.config.casing == Casing.TITLE:
            title_text = text.title()
            # Force 'CD' to stay uppercase in title case
            title_text = re.sub(r'\bCd\b', 'CD', title_text)
            if context:
                # Protect special, standalone uppercase/original elements (e.g. language codes like HU)
                for key in ["language", "part", "custom"]:
                    val = context.get(key)
                    if isinstance(val, str) and val:
                        val_title = val.title()
                        if val != val_title and val_title in title_text:
                            title_text = re.sub(r'\b' + re.escape(val_title) + r'\b', val, title_text)
            return title_text
        return text

    def apply_separator(self, text: str) -> str:
        if not text:
            return ""
        sep = self.config.separator.value
        if sep != " ":
            text = text.replace("(", "").replace(")", "").replace("[", "").replace("]", "")
            text = text.replace(" - ", " ")
        normalized = self.MULTI_SPACE.sub(" ", text.strip())
        return normalized.replace(" ", sep) if sep != " " else normalized

    def format_number(self, num: Any, width: int = 2) -> str:
        if isinstance(num, (list, tuple)):
            return f"-E".join(str(n).zfill(width) for n in num)
            
        try: 
            n = int(num)
        except: 
            # If string and JSON list, try to parse it
            if isinstance(num, str) and num.startswith("["):
                 try:
                     import ast
                     parsed = ast.literal_eval(num)
                     if isinstance(parsed, list):
                         return self.format_number(parsed, width)
                 except: 
                     pass
            return str(num) if num else ""
            
        return str(n).zfill(width) if self.config.zero_pad else str(n)

    def sanitize(self, text: str, is_file: bool = True) -> str:
        if not text:
            return ""
        if is_file:
            return self.MULTI_SPACE.sub(" ", self.ILLEGAL_CHARS.sub("", text)).strip(". ")
        else:
            folder_illegal = re.compile(r'[:*?"<>|]')
            return self.MULTI_SPACE.sub(" ", folder_illegal.sub("", text)).strip(". ")
