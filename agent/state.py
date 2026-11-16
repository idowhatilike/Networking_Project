from pathlib import Path
from threading import RLock

from shared.schemas import BlockReason, CmdAck, EventRecord, Policy

AGENT_STATE_FILE = Path("agent_quota_state.json")
IDLE_THRESHOLD_SEC = 300
CLOCK_TAMPER_THRESHOLD_SEC = 30

device_id = None
access_token = None
refresh_token = None
policy_id = None

dev_status_cur = "active"
device_quota : float = 0.0
device_used : float = 0.0
device_quota_date : str = "" #Ngày áp dụng hạn mức thiết bị.
quota_used : dict[str , int] = {}
app_bonus_time : dict[str , int] = {}
web_bonus_time : dict[str , int] = {}

last_mono_ts : float | None = None
last_wall_ts : float | None = None
last_input_mono : float | None = None
_last_win_input_tick : int | None = None
event_buffer : list[EventRecord] = []

is_manual_locked : bool = False
manual_locked_apps : set[str] = set()
manual_locked_domains : set[str] = set()
device_block_reason : BlockReason = BlockReason.NONE
app_block_reasons : dict[str , BlockReason] = {}
domain_block_reasons : dict[str , BlockReason] = {}
cur_policy : Policy | None = None
blocked_domains : set[str] = set()
command_seq : int = 0 #Mã lệnh đã xử lý.
last_cmd_ack : CmdAck | None = None
needs_sync : bool = True
online : bool = False
storage_loaded : bool = False
control_lock = RLock()
