from pathlib import Path
from threading import RLock

from fastapi import WebSocket

from shared.schemas import PairingCode, Policy

current_pairing_code : PairingCode | None = None

#Bộ nhớ trên Server
device_tokens : dict[str , str] = {}
device_states : dict[str , dict] = {}
policies_store : dict[str , Policy] = {}
active_ws_connections : dict[str , WebSocket] = {}

device_quota_store : dict[str , float] = {}
device_used_store : dict[str , float] = {}
device_quota_date_store : dict[str , str] = {}
device_policy_store : dict[str , str] = {}
app_bonus_store : dict[str , dict[str , int]] = {}
web_bonus_store : dict[str , dict[str , int]] = {}
QUOTA_STATE_FILE = Path("quota_state.json")
command_sessions : dict[str , dict] = {}
command_lock = RLock()
