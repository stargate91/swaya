import re

class QuerySanitizer:
    def sanitize_query(self, query: str) -> str:
        """Removes common patterns left behind by text parsing."""
        if not query:
            return ""
        
        clean_query = query
        # Remove season ranges (e.g. 1-4, Seasons 1-4, S1-S4)
        clean_query = re.sub(r'(?i)\b(?:seasons?|s)?\s*\d+\s*[-–]\s*(?:seasons?|s)?\s*\d+\b', "", clean_query)
        # Remove specific words
        for word in ["Mini", "Complete", "Season"]:
            clean_query = re.sub(rf"\b{word}\b", "", clean_query, flags=re.IGNORECASE)
            
        return " ".join(clean_query.split()).strip()
