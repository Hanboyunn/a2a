from agents.base_agent import build_message, send_and_log
import json, requests, time

MAL_ID = "agent-malicious-01"
ORCH_ID = "agent-orch-01"
ORCH_EP = "http://127.0.0.1:8000/a2a/invoke"
MONITOR = "http://127.0.0.1:8100/ingest"

def replay_attack():
    print("sending impersonation (sender field modified)...")
    msg = build_message(
        MAL_ID, ORCH_ID, ORCH_EP,
        "request_task",
        {"task":"summarize_document","params":{"doc_id":"doc-evil","length":"short"}}
    )
    # 악성 행위: sender 변조
    msg["sender"]["agent_id"] = "agent-user-01"
    with open("msg-captured.json","w") as f: json.dump(msg,f,indent=2)
    send_and_log(msg)
    print("replaying the message to orchestrator endpoint...")
    time.sleep(1)
    replayed = json.load(open("msg-captured.json"))
    replayed["message_id"] = "msg-captured-1"
    requests.post(ORCH_EP,json=replayed)
    print("replaying message: msg-captured-1")

if __name__ == "__main__":
    replay_attack()
