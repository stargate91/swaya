from typing import Protocol, Any, Dict, Optional

class SettingsPort(Protocol):
    def get_system_setting(self, key: str) -> Optional[Any]:
        """Gets system setting value by key."""
        ...

    def get_all_system_settings(self) -> Dict[str, Any]:
        """Gets all system settings as a dictionary of key-value pairs."""
        ...
