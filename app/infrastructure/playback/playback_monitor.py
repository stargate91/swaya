import time
import re
import requests
import logging
import subprocess
from app.shared_kernel.constants import PLAYBACK_CHECK_TIMEOUT

logger = logging.getLogger(__name__)

active_sessions = set()

def monitor_playback(item_id: int, player_type: str, proc: subprocess.Popen, port: int, user_id: int):
    logger.info(f"Started playback monitoring thread for item_id={item_id}, player={player_type}, port={port}, user_id={user_id}")
    active_sessions.add(item_id)
    last_saved_time = 0
    total_length = 0
    current_time = 0
    time.sleep(3)
    
    try:
        while proc.poll() is None:
            time.sleep(2)
            try:
                if player_type == "vlc":
                    r = requests.get(
                        f"http://127.0.0.1:{port}/requests/status.json", 
                        auth=("", "swaya"), 
                        timeout=PLAYBACK_CHECK_TIMEOUT
                    )
                    if r.status_code == 200:
                        data = r.json()
                        current_time = int(data.get("time", 0))
                        total_length = int(data.get("length", 0))
                elif player_type == "mpc":
                    r = requests.get(f"http://127.0.0.1:{port}/variables.html", timeout=PLAYBACK_CHECK_TIMEOUT)
                    if r.status_code == 200:
                        pos_match = re.search(r'id="position">(\d+)</p>', r.text)
                        dur_match = re.search(r'id="duration">(\d+)</p>', r.text)
                        if pos_match:
                            current_time = int(pos_match.group(1)) // 1000
                        if dur_match:
                            total_length = int(dur_match.group(1)) // 1000
                
                if current_time > 0 and abs(current_time - last_saved_time) >= 10:
                    last_saved_time = current_time
                    _save_position(item_id, current_time, total_length, user_id)
            except Exception as e:
                logger.debug(f"Polling failed: {e}")
    except Exception as e:
        logger.error(f"Error in monitoring: {e}")
    finally:
        active_sessions.discard(item_id)
        if current_time > 0 and current_time != last_saved_time:
            _save_position(item_id, current_time, total_length, user_id)


def _save_position(item_id: int, current_time: int, total_length: int, user_id: int):
    from app.shared_kernel.database import SessionLocal
    from app.infrastructure.media.db_media_resolver import DbMediaResolver
    
    db_session = SessionLocal()
    try:
        resolver = DbMediaResolver(db_session)
        resolver.save_playback_position(item_id, current_time, total_length, user_id)
        db_session.commit()
    except Exception as ex:
        db_session.rollback()
        logger.error(f"Failed to update position: {ex}")
    finally:
        db_session.close()
