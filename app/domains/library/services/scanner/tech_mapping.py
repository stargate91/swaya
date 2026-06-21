def map_resolution(width: int, height: int) -> str:
    """FFprobe width/height -> scene-standard resolution."""
    if not width or not height:
        return ""
    h = min(width, height)
    w = max(width, height)
    
    if w >= 7000: return "8K"
    if w >= 3500: return "2160p"
    if w >= 2500: return "1440p"
    if w >= 1800: return "1080p"
    if w >= 1200: return "720p"
    if w >= 700 and h >= 500: return "576p"
    if w >= 640: return "480p"
    return f"{h}p"

_VIDEO_CODEC_MAP = {
    "h264": "x264",
    "avc1": "x264",
    "hevc": "x265",
    "h265": "x265",
    "av1": "AV1",
    "vp9": "VP9",
    "vp8": "VP8",
    "mpeg2video": "MPEG2",
    "mpeg4": "MPEG4",
    "wmv3": "WMV",
    "vc1": "VC-1",
    "theora": "Theora",
}

def map_video_codec(codec_name: str) -> str:
    """FFprobe codec_name -> scene-standard video codec."""
    if not codec_name:
        return ""
    return _VIDEO_CODEC_MAP.get(codec_name.lower(), codec_name.upper())

_AUDIO_CODEC_MAP = {
    "aac": "AAC",
    "ac3": "DD",
    "eac3": "DD+",
    "dts": "DTS",
    "truehd": "TrueHD",
    "flac": "FLAC",
    "opus": "Opus",
    "vorbis": "Vorbis",
    "mp3": "MP3",
    "mp2": "MP2",
    "wmav2": "WMA",
}

_DTS_PROFILE_MAP = {
    "DTS-HD MA": "DTS-HD.MA",
    "DTS-HD HRA": "DTS-HD.HRA",
    "DTS Express": "DTS-Express",
    "DTS:X": "DTS-X",
}

def map_audio_codec(codec_name: str, profile: str = None) -> str:
    if not codec_name:
        return ""
    key = codec_name.lower()
    if key == "dts" and profile:
        return _DTS_PROFILE_MAP.get(profile, "DTS")
    if key.startswith("pcm_"):
        return "PCM"
    return _AUDIO_CODEC_MAP.get(key, codec_name.upper())

_CHANNEL_MAP = {
    1: "1.0",
    2: "2.0",
    3: "2.1",
    6: "5.1",
    7: "6.1",
    8: "7.1",
}

def map_audio_channels(channels: int) -> str:
    if not channels:
        return ""
    return _CHANNEL_MAP.get(channels, f"{channels}ch")
