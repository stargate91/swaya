import os
import platform
import shutil
import subprocess
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

def find_media_player(db, settings_port) -> Tuple[Optional[str], Optional[str]]:
    from app.shared_kernel.user_context import get_current_user_id
    current_user_id = get_current_user_id()
    vlc_path = settings_port.get_setting("vlc_path", user_id=current_user_id)
    mpc_path = settings_port.get_setting("mpc_path", user_id=current_user_id)

    if isinstance(vlc_path, str):
        vlc_path = vlc_path.strip().strip('"').strip("'")
    if isinstance(mpc_path, str):
        mpc_path = mpc_path.strip().strip('"').strip("'")

    def save_setting(key, val):
        try:
            from app.domains.settings.models import UserSetting
            setting = db.query(UserSetting).filter(UserSetting.user_id == current_user_id, UserSetting.key == key).first()
            if setting:
                setting.value = val
            else:
                db.add(UserSetting(user_id=current_user_id, key=key, value=val))
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save player setting {key}: {e}")

    # Detect VLC
    vlc_valid = False
    if vlc_path and os.path.exists(vlc_path):
        vlc_valid = True
    else:
        which_vlc = shutil.which("vlc")
        if which_vlc:
            vlc_path = which_vlc
            vlc_valid = True
        elif platform.system() == "Windows":
            vlc_paths = [
                r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
            ]
            for p in vlc_paths:
                if os.path.exists(p):
                    vlc_path = p
                    vlc_valid = True
                    break
        if vlc_valid and vlc_path:
            save_setting("vlc_path", vlc_path)

    # Detect MPC-HC
    mpc_valid = False
    if mpc_path and os.path.exists(mpc_path):
        mpc_valid = True
    else:
        which_mpc = shutil.which("mpc-hc") or shutil.which("mpc-hc64")
        if which_mpc:
            mpc_path = which_mpc
            mpc_valid = True
        elif platform.system() == "Windows":
            mpc_paths = [
                r"C:\Program Files\MPC-HC\mpc-hc64.exe",
                r"C:\Program Files (x86)\MPC-HC\mpc-hc.exe"
            ]
            for p in mpc_paths:
                if os.path.exists(p):
                    mpc_path = p
                    mpc_valid = True
                    break
        if mpc_valid and mpc_path:
            save_setting("mpc_path", mpc_path)

    if vlc_valid and vlc_path:
        return vlc_path, "vlc"
    if mpc_valid and mpc_path:
        return mpc_path, "mpc"
    return None, None


def launch_media_file(file_path: str, db, settings_port, start_seconds: int = 0) -> dict:
    normalized_path = os.path.normpath(file_path)
    player_path, player_type = find_media_player(db, settings_port)

    if player_path and player_type:
        proc = None
        port = 8080 if player_type == "vlc" else 13579

        if player_type == "vlc":
            args = [player_path, normalized_path]
            if start_seconds > 10:
                args.append(f"--start-time={start_seconds}")
            args.extend(["--no-one-instance", "--extraintf=http", "--http-password=swaya", f"--http-port={port}", "--http-host=127.0.0.1"])
            proc = subprocess.Popen(args)
        elif player_type == "mpc":
            args = [player_path, normalized_path]
            if start_seconds > 10:
                h = start_seconds // 3600
                m = (start_seconds % 3600) // 60
                s = start_seconds % 60
                args.extend(["/startpos", f"{h:02d}:{m:02d}:{s:02d}"])
            proc = subprocess.Popen(args)

        if proc:
            return {
                "status": "success",
                "player_type": player_type,
                "process": proc,
                "port": port,
                "message": f"Launched {player_type.upper()} for {normalized_path}",
            }

    logger.info(f"VLC or MPC-HC not found. Falling back to default OS player for: {normalized_path}")
    if platform.system() == "Windows":
        os.startfile(normalized_path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", normalized_path])
    else:
        subprocess.Popen(["xdg-open", normalized_path])

    return {
        "status": "success",
        "player_type": "default",
        "process": None,
        "port": None,
        "message": f"Launched default player for {normalized_path}",
    }
