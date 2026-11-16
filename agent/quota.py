import time
import uuid

import psutil

from shared import clock
from shared.schemas import (
    BlockReason,
    Cmd,
    EventRecord,
    EventType,
)

from . import state
from .helpers import input as user_input


def applyPolicy() :
    with state.control_lock :
        return evaluatePolicy()


def evaluatePolicy() :
    #Áp dụng khóa, hạn mức và cập nhật trạng thái thiết bị.
    #Xét khóa và hạn mức website.
    state.blocked_domains = set(state.manual_locked_domains)
    state.domain_block_reasons = {domain : BlockReason.POLICY for domain in state.manual_locked_domains}
    for rule in state.cur_policy.domain_rules if state.cur_policy is not None else [] :
        domain = rule.domain.lower().strip()
        if not rule.allowed or domain in state.manual_locked_domains :
            state.domain_block_reasons[domain] = BlockReason.POLICY
            state.blocked_domains.add(domain)
        elif rule.quota > 0 :
            remaining = max(0 , rule.quota + state.web_bonus_time.get(domain , 0) - state.quota_used.get(domain , 0))
            if remaining == 0 :
                state.domain_block_reasons[domain] = BlockReason.WEB_QUOTA
                state.blocked_domains.add(domain)
            else :
                state.domain_block_reasons[domain] = BlockReason.NONE
        else :
            state.domain_block_reasons[domain] = BlockReason.NONE

    #Xét khóa và hạn mức ứng dụng.
    blocked_process_names = set(state.manual_locked_apps)
    state.app_block_reasons = {name : BlockReason.POLICY for name in state.manual_locked_apps}
    for rule in state.cur_policy.app_rules if state.cur_policy is not None else [] :
        process_name = rule.exe_name.lower().strip()
        if not rule.allowed or process_name in state.manual_locked_apps :
            state.app_block_reasons[process_name] = BlockReason.POLICY
            blocked_process_names.add(process_name)
        elif rule.quota > 0 :
            remaining = max(0 , rule.quota + state.app_bonus_time.get(process_name , 0) - state.quota_used.get(process_name , 0))
            if remaining == 0 :
                state.app_block_reasons[process_name] = BlockReason.APP_QUOTA
                blocked_process_names.add(process_name)
            else :
                state.app_block_reasons[process_name] = BlockReason.NONE
        else :
            state.app_block_reasons[process_name] = BlockReason.NONE

    #Tắt các ứng dụng bị chặn.
    if blocked_process_names :
        for proc in psutil.process_iter(["name"]) :
            try :
                process_name = (proc.info["name"] or "").lower()
                if process_name in blocked_process_names :
                    proc.kill()
            except Exception :
                continue

    #Chưa có Policy: xét khóa thủ công và Idle, giữ khóa do lịch/hết giờ đã biết.
    if state.cur_policy is None :
        if state.is_manual_locked :
            state.device_block_reason = BlockReason.POLICY
            state.dev_status_cur = "locked"
        elif state.device_block_reason in (BlockReason.NONE , BlockReason.POLICY) :
            state.device_block_reason = BlockReason.NONE
            state.dev_status_cur = "idle" if user_input.getIdleSeconds() >= state.IDLE_THRESHOLD_SEC else "active"
        return

    #Đo thời gian đã trôi qua từ lần tính trước.
    now_mono = time.monotonic()
    if state.last_mono_ts is None or now_mono < state.last_mono_ts :
        mono_delta = 0.0
    else :
        mono_delta = now_mono - state.last_mono_ts
    #Lấy ngày và khung giờ để xét lịch sử dụng.
    now_dt = clock.getVnNow()
    day_idx = now_dt.weekday()
    slot_idx = now_dt.hour * 2 + (now_dt.minute // 30)
    limit_sec = state.cur_policy.weekend_quota if day_idx >= 5 else state.cur_policy.weekday_quota
    today_str = now_dt.strftime("%Y-%m-%d")

    #Chỉ cấp lại hạn mức khi ngày tăng.
    if state.device_quota_date == "" :
        state.device_quota_date = today_str
    elif today_str > state.device_quota_date and not state.online :
        state.device_quota = float(limit_sec)
        state.device_used = 0.0
        state.device_quota_date = today_str
        mono_delta = 0.0

    #Chỉ tính thời gian sử dụng khi thiết bị Active và không bị khóa.
    is_idle_now = user_input.getIdleSeconds(now_mono) >= state.IDLE_THRESHOLD_SEC
    is_schedule_locked = not state.cur_policy.schedule_7x48[day_idx][slot_idx]
    remaining = max(0.0 , state.device_quota - state.device_used)
    was_locked = (state.dev_status_cur == "locked") or state.is_manual_locked or is_schedule_locked or (remaining <= 0)

    if not was_locked and not is_idle_now and state.dev_status_cur == "active" and mono_delta > 0 :
        consumed = min(remaining , mono_delta)
        state.device_used += consumed

    remaining = max(0.0 , state.device_quota - state.device_used)

    #Chọn trạng thái: khóa thủ công → lịch cấm → hết giờ → Idle/Active.
    if state.is_manual_locked :
        state.dev_status_cur = "locked"
        state.device_block_reason = BlockReason.POLICY
    elif is_schedule_locked :
        state.dev_status_cur = "locked"
        state.device_block_reason = BlockReason.SCHEDULE
    elif remaining <= 0 :
        state.dev_status_cur = "locked"
        state.device_block_reason = BlockReason.DEVICE_QUOTA
    else :
        state.device_block_reason = BlockReason.NONE
        state.dev_status_cur = "idle" if is_idle_now else "active"

    #Đối chiếu giờ máy với thời gian đo; ghi nhận lệch tiến/lùi quá 30 giây.
    now_wall = time.time()
    if state.last_wall_ts is not None and state.last_mono_ts is not None and now_mono >= state.last_mono_ts :
        wall_elapsed_sec = now_wall - state.last_wall_ts
        measured_elapsed_sec = now_mono - state.last_mono_ts
        clock_offset_sec = wall_elapsed_sec - measured_elapsed_sec
        if abs(clock_offset_sec) > state.CLOCK_TAMPER_THRESHOLD_SEC :
            state.event_buffer.append(EventRecord(
                idempotency_key = str(uuid.uuid4()) ,
                ts = int(now_wall) ,
                device_id = state.device_id or "unknown_device" ,
                child_id = "child_default" ,
                type = EventType.QUOTA_WARNING ,
                subject = "Giờ hệ thống lệch tiến" if clock_offset_sec > 0 else "Giờ hệ thống lệch lùi" ,
                duration_sec = int(abs(clock_offset_sec)) ,
                policy_id = state.cur_policy.policy_id
            ))

    #Giữ hai mốc đo cho lần tính tiếp theo.
    state.last_mono_ts = now_mono
    state.last_wall_ts = now_wall


def execCmd(cmd : Cmd) :
    #Thực thi lệnh cho thiết bị, ứng dụng hoặc website.
    from .commands import applyCommand
    return applyCommand(cmd)
