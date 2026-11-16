from shared import clock

from . import state


def getDeviceBaseQuota(device_id : str , policy_id : str | None = None) -> int :
    #Lấy hạn mức ngày của thiết bị.
    now_dt = clock.getVnNow()
    is_weekend = now_dt.weekday() >= 5
    effective_policy_id = policy_id or state.device_policy_store.get(device_id)
    if not effective_policy_id and device_id.startswith("di_") :
        effective_policy_id = f"plcid_{device_id[3:]}"
    policy = state.policies_store.get(effective_policy_id) if effective_policy_id else None
    if policy is None and len(state.policies_store) == 1 :
        policy = next(iter(state.policies_store.values()))
    if policy is not None :
        return policy.weekend_quota if is_weekend else policy.weekday_quota
    return 7200 if is_weekend else 5400


def ensureDeviceDailyQuota(device_id : str , policy_id : str | None = None) -> bool :
    #Khởi tạo hoặc cấp lại hạn mức thiết bị khi sang ngày mới.
    if device_id in state.command_sessions :
        from .commands import refreshDeviceQuota
        return refreshDeviceQuota(device_id , policy_id)
    today_str = clock.getVnNow().strftime("%Y-%m-%d")
    policy_changed = bool(policy_id and state.device_policy_store.get(device_id) != policy_id)
    if policy_id :
        state.device_policy_store[device_id] = policy_id
    saved_date = state.device_quota_date_store.get(device_id)
    if device_id in state.device_quota_store :
        if saved_date is not None and today_str <= saved_date :
            return policy_changed
        if saved_date is None :
            state.device_quota_date_store[device_id] = today_str
            return True
    state.device_quota_store[device_id] = getDeviceBaseQuota(device_id , policy_id)
    state.device_used_store[device_id] = 0
    state.device_quota_date_store[device_id] = today_str
    return True
