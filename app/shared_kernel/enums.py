import enum

class Provider(enum.Enum):
    """Supported metadata and content providers."""
    TMDB = "tmdb"
    OMDB = "omdb"
    STASHDB = "stashdb"
    PORNDB = "porndb"
    FANSDB = "fansdb"
    MANUAL = "manual"

class ScanMode(enum.Enum):
    """Explicit metadata strategy for a scan run."""
    MOVIES_TV = "movies_tv"
    SCENES = "scenes"
    JAV = "jav"

    @property
    def uses_scene_pipeline(self) -> bool:
        return self in (ScanMode.SCENES, ScanMode.JAV)

    @property
    def requires_adult_access(self) -> bool:
        return self in (ScanMode.SCENES, ScanMode.JAV)

    @property
    def is_jav(self) -> bool:
        return self == ScanMode.JAV

class MediaType(enum.Enum):
    """Types of media content supported by the application."""
    MOVIE = "movie"
    TV = "tv"
    SEASON = "season"
    EPISODE = "episode"
    SCENE = "scene"
    JAV = "jav"
    PERSON = "person"
    VIDEO = "video"
    COLLECTION = "collection"

class ItemStatus(enum.Enum):
    """Indexing and matching status of a media item on disk."""
    NEW = "new"
    NO_MATCH = "no_match"
    UNCERTAIN = "uncertain"
    MULTIPLE = "multiple"
    MATCHED = "matched"
    ORGANIZED = "organized"
    RENAMED = "renamed"
    ERROR = "error"
    IGNORED = "ignored"
    MISSING = "missing"

class RoleType(enum.Enum):
    """Credits role types for cast and crew."""
    ACTOR = "actor"
    DIRECTOR = "director"
    WRITER = "writer"
    PRODUCER = "producer"
    CREATOR = "creator"

class TaskStatus(enum.Enum):
    """Current execution state of background tasks."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"

class TaskErrorCode(enum.Enum):
    """Categorized error codes for background task failures."""
    RATE_LIMIT = "rate_limit"
    API_KEY_MISSING = "api_key_missing"
    NETWORK_ERROR = "network_error"
    DATABASE_LOCK = "database_lock"
    NO_MATCH = "no_match"
    UNKNOWN = "unknown"

class AssetStatus(enum.Enum):
    """Status of downloading associated media assets (covers, posters, etc.)."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"

class CacheStatus(enum.Enum):
    """Status/Lifecycle of API cache records."""
    VALID = "valid"
    PARTIAL = "partial"
    EXPIRED = "expired"
    FAILED = "failed"
    NOT_FOUND = "not_found"

class MovieEdition(enum.Enum):
    """Special editions or cuts of movies."""
    NONE = "none"
    THEATRICAL = "theatrical"
    DIRECTORS_CUT = "directors_cut"
    EXTENDED = "extended"
    UNRATED = "unrated"
    REMASTERED = "remastered"
    SPECIAL = "special"
    ULTIMATE = "ultimate"
    COLLECTORS_EDITION = "collectors_edition"
    FAN_EDIT = "fan_edit"

class MediaSource(enum.Enum):
    """Source medium of the media file."""
    NONE = "none"
    BLURAY = "bluray"
    WEB = "web"
    DVD = "dvd"
    TV = "tv"
    CAM = "cam"

class MediaAudioType(enum.Enum):
    """Audio configuration of the media file."""
    NONE = "none"
    MONO = "mono"
    STEREO = "stereo"
    SURROUND = "surround"
    DUAL_AUDIO = "dual_audio"
    MULTI_AUDIO = "multi_audio"

class ActionType(enum.Enum):
    """File or metadata operations logged in action batches."""
    RENAME = "rename"
    MOVE = "move"
    COPY = "copy"
    DELETE = "delete"
    METADATA_UPDATE = "metadata_update"
    IDENTIFY = "identify"

class ActionStatus(enum.Enum):
    """Status of a logged file operation batch."""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    UNDONE = "undone"

class ExtraCategory(enum.Enum):
    """General category of associated extra files."""
    VIDEO = "video"
    IMAGE = "image"
    METADATA = "metadata"
    SUBTITLE = "subtitle"
    AUDIO = "audio"

class ExtraSubtype(enum.Enum):
    """Specific subtype of associated extra files."""
    TRAILER = "trailer"
    SAMPLE = "sample"
    BEHIND_THE_SCENES = "behind_the_scenes"
    FEATURETTE = "featurette"
    DELETED_SCENES = "deleted_scenes"
    INTERVIEW = "interview"
    SCENE_COMPARISON = "scene_comparison"
    SHORT = "short"
    PROMO = "promo"
    CLIP = "clip"
    POSTER = "poster"
    FANART = "fanart"
    DISC = "disc"
    BACKDROP = "backdrop"
    BANNER = "banner"
    THUMBNAIL = "thumbnail"
    LOGO = "logo"
    CLEARLOGO = "clearlogo"
    CHARACTER_ART = "character_art"
    FULL = "full"
    FORCED = "forced"
    SDH = "sdh"
    HEARING_IMPAIRED = "hearing_impaired"
    COMMENTARY_SUB = "commentary_sub"
    LYRICS = "lyrics"
    DUBBED = "dubbed"
    ORIGINAL = "original"
    COMMENTARY_AUDIO = "commentary_audio"
    DESCRIPTIVE = "descriptive"
    ISOLATED_SCORE = "isolated_score"
    NFO = "nfo"
    XML = "xml"
    JSON = "json"
    TXT = "txt"
    URL = "url"
    OTHER = "other"


class CustomListType(enum.Enum):
    """Types of items allowed in a custom user list to prevent mixing."""
    MEDIA = "media"
    MATCH = "match"
    PERSON = "person"
    STUDIO = "studio"
    COLLECTION = "collection"
