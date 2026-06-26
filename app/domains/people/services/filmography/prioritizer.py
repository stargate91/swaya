from typing import List

class CreditsPrioritizer:
    @staticmethod
    def prioritize_person_credits(items: List[dict], known_for_items: List[dict]) -> List[dict]:
        if not items:
            return []
        
        known_for_keys = {}
        for index, entry in enumerate(known_for_items or []):
            tid = entry.get("tmdb_id")
            mtype = entry.get("media_type") or entry.get("type")
            if tid:
                known_for_keys[(tid, mtype)] = index

        prioritized = []
        for entry in items:
            tid = entry.get("tmdb_id")
            mtype = entry.get("media_type") or entry.get("type")
            rank = known_for_keys.get((tid, mtype))
            is_known = rank is not None
            prioritized.append({
                **entry,
                "is_known_for": is_known,
                "known_for_rank": rank if is_known else 10**9
            })

        prioritized.sort(
            key=lambda entry: (
                0 if entry.get("is_known_for") else 1,
                entry.get("known_for_rank", 10**9),
                0 if entry.get("in_library") else 1,
                -(int(entry.get("year") or 0))
            )
        )
        return prioritized
