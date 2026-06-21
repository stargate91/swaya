import logging
import requests
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.infrastructure.cache.cache_service import CacheService
from app.shared_kernel.enums import Provider

logger = logging.getLogger(__name__)

class BaseScraper:
    """
    Base scraper class containing database sessions, cache services,
    reusable request sessions, configuration helpers, and unified DB persistence.
    """

    def __init__(self, db_session: Session, cache_service: Optional[CacheService] = None, provider: Optional[Provider] = None):
        self.db = db_session
        self.cache = cache_service or CacheService()
        self.session = requests.Session()
        
        # Configure retry logic for rate limits and server errors
        from urllib3.util import Retry
        from requests.adapters import HTTPAdapter
        
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.provider = provider

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Helper to get a setting from user/system settings, falling back to environment."""
        import os
        from app.domains.settings.models import SystemSetting, UserSetting
        try:
            setting = self.db.query(UserSetting).filter(
                UserSetting.user_id == 1,
                UserSetting.key == key,
            ).first()
            if not setting:
                setting = self.db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if setting and setting.value:
                return str(setting.value)
        except Exception as e:
            logger.debug(f"Failed to query setting {key} from DB: {e}")
        
        # Fallback to env variables (uppercase)
        env_val = os.getenv(key.upper())
        if env_val:
            return env_val
        return default

    def execute_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Executes a GraphQL query against the provider's endpoint."""
        if not self.provider:
            return None

        # Resolve endpoint and API keys
        pref = self.provider.value  # e.g. 'stashdb', 'fansdb', 'porndb'
        endpoint = self.get_setting(f"{pref}_endpoint")
        api_key = self.get_setting(f"{pref}_api_key") or self.get_setting(f"{pref}_api_token")

        if not endpoint:
            if pref == "stashdb":
                endpoint = "https://stashdb.org/graphql"
            elif pref == "fansdb":
                endpoint = "https://fansdb.cc/graphql"
            elif pref == "porndb":
                endpoint = "https://theporndb.net/graphql"

        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            # StashDB and FansDB use ApiKey header, PornDB uses Authorization Bearer
            if pref in ("stashdb", "fansdb"):
                headers["ApiKey"] = api_key
            else:
                headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = self.session.post(
                endpoint,
                json={"query": query, "variables": variables or {}},
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            res_data = response.json()
            if "errors" in res_data:
                logger.error(f"GraphQL errors from {pref}: {res_data['errors']}")
                return None
            return res_data.get("data")
        except Exception as e:
            logger.error(f"Error querying {pref} GraphQL API: {e}")
            return None

    def search_performers(self, query_str: str) -> List[Dict[str, Any]]:
        """Search performers using GraphQL."""
        gql_query = """
        query SearchPerformers($name: String!) {
          searchPerformer(term: $name) {
            id
            name
            gender
            scene_count
            images {
              url
            }
          }
        }
        """
        data = self.execute_query(gql_query, {"name": query_str})
        if not data or "searchPerformer" not in data:
            return []
        return data["searchPerformer"] or []

    def get_performer_details(self, performer_id: str) -> Optional[Dict[str, Any]]:
        """Gets detailed performer metadata using GraphQL."""
        gql_query = """
        query GetPerformer($id: ID!) {
          findPerformer(id: $id) {
            id
            name
            gender
            scene_count
            birth_date
            ethnicity
            eye_color
            hair_color
            height
            measurements {
              cup_size
              band_size
              waist
              hip
            }
            images {
              url
            }
          }
        }
        """
        data = self.execute_query(gql_query, {"id": performer_id})
        if not data or "findPerformer" not in data:
            return None
        return data["findPerformer"]



    def log_search(self, task_id: Optional[int], media_item_id: Optional[int], search_query: str, result_count: int, details: Dict[str, Any]) -> None:
        """Saves a structured search log for scraper resolution auditing."""
        from app.domains.tasks.models import ScraperLog
        try:
            log_entry = ScraperLog(
                task_id=task_id,
                media_item_id=media_item_id,
                provider=self.provider,
                search_query=search_query,
                result_count=result_count,
                details=details
            )
            self.db.add(log_entry)
            self.db.flush()
        except Exception as e:
            logger.warning(f"Failed to save structured scraper search log: {e}")
