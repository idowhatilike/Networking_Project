import json
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
from websockets.sync.client import connect

import agent
from shared import clock
from shared.schemas import CmdRequest , CommandType , ControlState , HeartbeatResponse


def testRealHttpAndWsDrainNextCommand(tmp_path , monkeypatch) :
    projectPath = Path(__file__).resolve().parents[1]
    with socket.socket() as listener :
        listener.bind(("127.0.0.1" , 0))
        port = listener.getsockname()[1]
    bootstrap = (
        "import sys,os; sys.path.insert(0,sys.argv[1]); "
        "import server,uvicorn; from shared.schemas import Policy; "
        "os.environ['PARENT_TOKEN']='smoke-parent'; "
        "p=Policy(policy_id='smoke-policy',policy_version=1,weekday_quota=1800,"
        "weekend_quota=1800,schedule_7x48=[[True]*48 for _ in range(7)],signature='unsigned'); "
        "server.state.policies_store[p.policy_id]=p; "
        "server.state.device_tokens['smoke-device']='smoke-token'; "
        "server.ensureDeviceDailyQuota('smoke-device',p.policy_id); "
        "uvicorn.run(server.app,host='127.0.0.1',port=int(sys.argv[2]),log_level='error')"
    )
    with (tmp_path / "server.log").open("w+" , encoding = "utf-8") as log :
        process = subprocess.Popen(
            [sys.executable , "-c" , bootstrap , str(projectPath) , str(port)] ,
            cwd = tmp_path , stdout = log , stderr = subprocess.STDOUT
        )
        try :
            baseUrl = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 10
            while True :
                try :
                    response = httpx.get(baseUrl + "/openapi.json" , timeout = 0.5)
                    response.raise_for_status()
                    break
                except httpx.HTTPError :
                    if process.poll() is not None or time.monotonic() >= deadline :
                        log.seek(0)
                        raise AssertionError(log.read())
                    time.sleep(0.05)

            today = clock.getVnNow().strftime("%Y-%m-%d")
            policy = httpx.get(baseUrl + "/api/v1/policy" , params = {
                "device_id" : "smoke-device" , "access_token" : "smoke-token" ,
                "policy_id" : "smoke-policy"
            }).json()
            for name , value in ControlState(device_quota_date = today).model_dump().items() :
                monkeypatch.setattr(agent.state , name , value)
            from shared.schemas import Policy

            for name , value in {
                "device_id" : "smoke-device" , "access_token" : "smoke-token" ,
                "policy_id" : "smoke-policy" , "cur_policy" : Policy(**policy) ,
                "last_cmd_ack" : None , "needs_sync" : True , "online" : False ,
                "storage_loaded" : True , "last_mono_ts" : None , "last_wall_ts" : None ,
                "last_input_mono" : None , "_last_win_input_tick" : None ,
                "dev_status_cur" : "active" , "AGENT_STATE_FILE" : tmp_path / "agent.json"
            }.items() :
                monkeypatch.setattr(agent.state , name , value)
            monkeypatch.setattr(agent , "HEARTBEAT_URL" , baseUrl + "/api/v1/heartbeat")
            monkeypatch.setattr(agent , "_ACK_URL" , baseUrl + "/api/v1/command-ack")
            monkeypatch.setattr(agent , "POLICY_URL" , baseUrl + "/api/v1/policy")
            agent.drainResponses(agent.requestHeartbeat())
            assert agent.state.device_quota == 1800
            url = (
                f"ws://127.0.0.1:{port}/ws/urgent"
                "?device_id=smoke-device&access_token=smoke-token"
            )
            with connect(url , open_timeout = 3) as websocket :
                websocket.send(json.dumps({
                    "type" : "sync" , "data" : agent.getControlState().model_dump(mode = "json")
                }))
                HeartbeatResponse.model_validate_json(websocket.recv(timeout = 3))
                for kind in (CommandType.LOCK , CommandType.UNLOCK) :
                    response = httpx.post(
                        baseUrl + "/api/v1/urgent" , params = {"device_id" : "smoke-device"} ,
                        headers = {"X-Parent-Token" : "smoke-parent"} ,
                        json = CmdRequest(cmd_type = kind).model_dump(mode = "json") , timeout = 3
                    )
                    response.raise_for_status()
                first = HeartbeatResponse.model_validate_json(websocket.recv(timeout = 3))
                ack = agent.HeartbeatResponseHanlder(first)
                response = agent.requestCmdAck(ack)
                assert response.command.cmd_type == CommandType.UNLOCK
                assert response.command.command_seq == first.command.command_seq + 1
                for _ in range(4) :
                    pushed = HeartbeatResponse.model_validate_json(websocket.recv(timeout = 3))
                    if pushed.command.command_seq == response.command.command_seq :
                        break
                assert pushed.command == response.command
                nextAck = agent.HeartbeatResponseHanlder(response)
                websocket.send(json.dumps({"type" : "ack" ,
                                           "data" : nextAck.model_dump(mode = "json")}))
                final = HeartbeatResponse.model_validate_json(websocket.recv(timeout = 3))
                assert final.command is None
                assert not agent.state.is_manual_locked
                agent.drainResponses(agent.requestHeartbeat())
                assert agent.state.command_seq == 2
        finally :
            process.terminate()
            try :
                process.wait(timeout = 5)
            except subprocess.TimeoutExpired :
                process.kill()
                process.wait(timeout = 5)
