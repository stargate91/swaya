import subprocess
import json
import os
from typing import Dict, Any, Optional
from .tech_mapping import map_resolution

class TechnicalProber:
    """
    FFmpeg (ffprobe) based technical metadata extraction engine.
    Retrieves stream details, codecs, and container metadata.
    """

    def probe(self, file_path: str) -> Dict[str, Any]:
        """
        Executes ffprobe on the given file and returns the raw JSON output.
        """
        cmd = [
            'ffprobe', 
            '-v', 'quiet', 
            '-print_format', 'json', 
            '-probesize', '5000000',        # 5MB – sufficient for stream detection
            '-analyzeduration', '5000000',  # 5 seconds
            '-show_format', 
            '-show_streams', 
            file_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
            return json.loads(result.stdout)
        except Exception:
            return {}

    def extract_info(self, probe_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filters and structures essential data from the raw ffprobe JSON response.
        Extracts duration, size, resolution, codecs, bitrates, channels, HDR, framerate, etc.
        """
        info = {
            "duration": None,
            "size": None,
            "resolution": None,
            "video_codec": None,
            "video_bitrate": None,
            "audio_codec": None,
            "audio_channels": None,
            "audio_bitrate": None,
            "framerate": None,
            "bit_depth": None,
            "hdr_type": None,
            "internal_title": None,
            "video_stream": {},
            "audio_streams": [],
            "subtitle_streams": []
        }
        
        if not probe_data:
            return info

        # Container format data
        fmt = probe_data.get('format', {})
        info["duration"] = float(fmt.get('duration', 0)) if fmt.get('duration') else None
        info["size"] = int(fmt.get('size', 0)) if fmt.get('size') else None
        info["internal_title"] = fmt.get('tags', {}).get('title')

        # Individual stream data (Video/Audio/Subtitle)
        for stream in probe_data.get('streams', []):
            stype = stream.get('codec_type')
            
            if stype == 'video' and not info["resolution"]:
                info["video_codec"] = stream.get('codec_name')
                w = stream.get('width')
                h = stream.get('height')
                if w and h:
                    info["resolution"] = map_resolution(w, h)

                # Video bitrate
                vbr = stream.get('bit_rate')
                if vbr:
                    info["video_bitrate"] = int(vbr)

                # Framerate
                rfr = stream.get('r_frame_rate')
                if rfr and '/' in rfr:
                    try:
                        num, den = rfr.split('/')
                        fps = round(int(num) / int(den), 3)
                        info["framerate"] = str(fps)
                    except: pass
                elif rfr:
                    info["framerate"] = rfr

                # Bit depth
                bd = stream.get('bits_per_raw_sample')
                if bd:
                    try: info["bit_depth"] = int(bd)
                    except: pass
                if not info["bit_depth"]:
                    pix_fmt = stream.get('pix_fmt', '')
                    if '10le' in pix_fmt or '10be' in pix_fmt or 'p010' in pix_fmt:
                        info["bit_depth"] = 10
                    elif '12le' in pix_fmt or '12be' in pix_fmt:
                        info["bit_depth"] = 12
                    elif pix_fmt:
                        info["bit_depth"] = 8

                # HDR detection
                info["hdr_type"] = self._detect_hdr(stream)
                info["video_stream"] = stream
                
            elif stype == 'audio':
                a_codec = stream.get('codec_name')
                a_channels = stream.get('channels')
                a_bitrate = stream.get('bit_rate')
                a_lang = stream.get('tags', {}).get('language')
                a_title = stream.get('tags', {}).get('title')
                a_profile = stream.get('profile')

                info["audio_streams"].append({
                    "codec": a_codec,
                    "channels": a_channels,
                    "bitrate": int(a_bitrate) if a_bitrate else None,
                    "language": a_lang,
                    "title": a_title,
                    "profile": a_profile
                })
                if not info["audio_codec"]:
                    info["audio_codec"] = a_codec
                if not info["audio_channels"] and a_channels:
                    info["audio_channels"] = str(a_channels)
                if not info["audio_bitrate"] and a_bitrate:
                    info["audio_bitrate"] = int(a_bitrate)
            
            elif stype == 'subtitle':
                s_lang = stream.get('tags', {}).get('language')
                s_title = stream.get('tags', {}).get('title')
                info["subtitle_streams"].append({
                    "language": s_lang,
                    "title": s_title,
                    "codec": stream.get('codec_name')
                })

        return info

    def _detect_hdr(self, video_stream: Dict) -> Optional[str]:
        """Detects HDR type from video stream side_data and color metadata."""
        color_transfer = (video_stream.get('color_transfer') or '').lower()
        color_primaries = (video_stream.get('color_primaries') or '').lower()
        
        side_data_list = video_stream.get('side_data_list', [])
        has_dovi = any('dovi' in str(sd.get('side_data_type', '')).lower() for sd in side_data_list)
        has_hdr10_plus = any('hdr10+' in str(sd.get('side_data_type', '')).lower() or 
                             'dynamic' in str(sd.get('side_data_type', '')).lower() for sd in side_data_list)
        has_mastering = any('mastering' in str(sd.get('side_data_type', '')).lower() for sd in side_data_list)
        has_cll = any('content light' in str(sd.get('side_data_type', '')).lower() for sd in side_data_list)

        if has_dovi:
            if has_hdr10_plus:
                return "DV HDR10+"
            if has_mastering or has_cll:
                return "DV HDR10"
            return "DV"
        if has_hdr10_plus:
            return "HDR10+"
        if color_transfer == 'smpte2084':
            if has_mastering or has_cll:
                return "HDR10"
            return "PQ"
        if color_transfer == 'arib-std-b67':
            return "HLG"
        if color_primaries == 'bt2020':
            return "HDR"
        return None
