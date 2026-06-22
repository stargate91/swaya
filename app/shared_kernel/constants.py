from app.shared_kernel.enums import ExtraSubtype

# API URLs and Base Endpoints
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/"
TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_MOVIE_APPEND_PARTS = ["credits", "external_ids", "translations", "videos", "keywords"]
TMDB_TV_APPEND_PARTS = ["credits", "aggregate_credits", "external_ids", "translations", "videos", "keywords"]
STASHDB_DEFAULT_ENDPOINT = "https://stashdb.org/graphql"
FANSDB_DEFAULT_ENDPOINT = "https://fansdb.cc/graphql"
PORNDB_DEFAULT_ENDPOINT = "https://theporndb.net/graphql"
PORNDB_API_BASE = "https://api.theporndb.net"
OMDB_DEFAULT_ENDPOINT = "http://www.omdbapi.com/"
YOUTUBE_WATCH_BASE = "https://www.youtube.com/watch?v="

# Default Fallback Language
DEFAULT_FALLBACK_LANGUAGE = "en"

# Cache Expiry TTLs (in seconds)
DEFAULT_TTLS = {
    "static": None,      # Never expires automatically (movies, tv shows, performers detail details)
    "dynamic": 86400,    # 1 day: Popularity, ratings, recommendations, credits
    "search": 604800,    # 7 days: Search query results
    "failed": 604800,    # 7 days: Negative caching (404, empty/failed queries)
}

# Image Processing Specifications
MIN_CACHED_IMAGE_BYTES = 512
MEDIA_IMAGE_SUBFOLDERS = ["posters", "backdrops", "logos", "stills", "scene_stills", "people", "avatars"]

TMDB_DOWNLOAD_SIZES = {
    "posters": "w780",
    "backdrops": "original",
    "logos": "original",
    "stills": "500",
    "people": "632",
    "avatars": "w500"
}

MEDIA_IMAGE_LIMITS = {
    "backdrops": {"max_width": 3840},     # 4K limit
    "posters": {"max_width": 780},        # 780 width limit
    "people": {"max_height": 632},    # h632 height limit
    "stills": {"max_width": 500},         # 500 width limit for episode/tv screenshots
    "scene_stills": {"max_width": 3840},   # 3840 width limit (used as backdrops for adult scenes)
    "logos": None,                        # Keep original, no resize
    "avatars": {"max_width": 500}
}

# Image Selection and Download Settings
LOGO_MAX_DARK_PIXELS_RATIO = 0.2
LOGO_MIN_LUMINANCE_RATIO = 0.32
BACKDROP_BRIGHTNESS_THRESHOLD = 0.84
BACKDROP_MAX_BRIGHT_PIXELS_RATIO = 0.58
BACKDROP_ULTRA_HD_WIDTH = 2560
BACKDROP_DEFAULT_MIN_WIDTH = 1920
IMAGE_DOWNLOAD_TIMEOUT = (3, 10)

# Background Worker Thread Settings
DEFAULT_MAX_WORKERS = 6

# Network, Database, and Worker Timeout Settings
SCRAPER_REQUEST_TIMEOUT = 15
OMDB_REQUEST_TIMEOUT = 10
HEAVY_IMAGE_DOWNLOAD_TIMEOUT = (5, 30)
PLAYBACK_CHECK_TIMEOUT = 1.5
DATABASE_TIMEOUT_SECONDS = 30

# Scanner File Extension Specifications
DEFAULT_VIDEO_EXTS = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.mpg', '.mpeg'}
DEFAULT_SUBTITLE_EXTS = {'.srt', '.sub', '.ass', '.ssa', '.idx', '.vtt'}
DEFAULT_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
DEFAULT_AUDIO_EXTS = {'.ac3', '.dts', '.flac', '.mp3', '.aac', '.m4a'}
DEFAULT_META_EXTS = {'.nfo', '.xml', '.json', '.txt'}

CATEGORIZER_VIDEO_EXTS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.m4v'}
CATEGORIZER_SUBTITLE_EXTS = {'.srt', '.sub', '.ass', '.ssa', '.vtt'}
CATEGORIZER_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
CATEGORIZER_AUDIO_EXTS = {'.mka', '.ac3', '.dts', '.mp3', '.flac', '.wav', '.m4a'}
CATEGORIZER_META_EXTS = {'.nfo', '.xml', '.txt'}

# Keyword mapping for automated subtype detection
SCANNER_SUBTYPE_MAP = {
    'trailer': ExtraSubtype.TRAILER,
    'teaser': ExtraSubtype.TRAILER,
    'sample': ExtraSubtype.SAMPLE,
    'minta': ExtraSubtype.SAMPLE, # Hungarian for 'sample'
    'behind': ExtraSubtype.BEHIND_THE_SCENES,
    'making': ExtraSubtype.BEHIND_THE_SCENES,
    'featurette': ExtraSubtype.FEATURETTE,
    'deleted': ExtraSubtype.DELETED_SCENES,
    'kimaradt': ExtraSubtype.DELETED_SCENES, # Hungarian for 'deleted/omitted'
    'interview': ExtraSubtype.INTERVIEW,
    'riport': ExtraSubtype.INTERVIEW, # Hungarian for 'report/interview'
    'short': ExtraSubtype.SHORT,
    'promo': ExtraSubtype.PROMO,
    'clip': ExtraSubtype.CLIP,
    # Images
    'poster': ExtraSubtype.POSTER,
    'poszter': ExtraSubtype.POSTER, # Hungarian for 'poster'
    'fanart': ExtraSubtype.FANART,
    'backdrop': ExtraSubtype.BACKDROP,
    'hatter': ExtraSubtype.BACKDROP, # Hungarian for 'background'
    'banner': ExtraSubtype.BANNER,
    'thumb': ExtraSubtype.THUMBNAIL,
    'logo': ExtraSubtype.LOGO,
    'clearlogo': ExtraSubtype.CLEARLOGO,
    'disc': ExtraSubtype.DISC,
    'lemez': ExtraSubtype.DISC, # Hungarian for 'disc'
    # Subtitles
    'forced': ExtraSubtype.FORCED,
    'kenyszeritett': ExtraSubtype.FORCED, # Hungarian for 'forced'
    'sdh': ExtraSubtype.SDH,
    'commentary': ExtraSubtype.COMMENTARY_SUB,
    'full': ExtraSubtype.FULL,
    # Audio
    'dub': ExtraSubtype.DUBBED,
    'szinkron': ExtraSubtype.DUBBED, # Hungarian for 'dubbed/sync'
    'original': ExtraSubtype.ORIGINAL,
    'score': ExtraSubtype.ISOLATED_SCORE,
}
