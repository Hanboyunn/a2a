import os, json
from datetime import datetime
import matplotlib
matplotlib.use("Agg")  # 서버/백그라운드 저장 모드
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
DATA_FILE   = os.path.join(HERE, "data.jsonl")
ALERTS_FILE = os.path.join(HERE, "alerts.jsonl")
PNG_FILE    = os.path.join(HERE, "trust_timeline.png")

def _first(v, *alts):
    """첫 번째로 값이 있는 항목 반환"""
    if v is not None:
        return v
    for a in alts:
        if a is not None:
            return a
    return None

def _parse_ts(s):
    if not s:
        return None
    try:
        # Z 포함/미포함 모두 처리
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def _extract(msg):
    """
    다양한 구조에서 (ts, trust, revoked, sig_valid, replay, sender) 추출
    - 루트/ message/ reason 3곳을 모두 뒤진다.
    """
    m = msg.get("message", {}) if isinstance(msg.get("message", {}), dict) else {}
    r = msg.get("reason", {}) if isinstance(msg.get("reason", {}), dict) else {}

    trust = _first(
        msg.get("_trust"),
        m.get("_trust"),
        r.get("trust")
    )

    ts = _first(
        msg.get("timestamp"),
        msg.get("ts"),
        m.get("timestamp"),
        m.get("ts")
    )
    ts = _parse_ts(ts)

    revoked   = bool(_first(msg.get("_revoked"), m.get("_revoked"), r.get("revoked"), False))
    sig_valid = bool(_first(msg.get("_signature_valid"), m.get("_signature_valid"), r.get("sig_valid"), True))
    replay    = bool(_first(msg.get("_replay"), m.get("_replay"), r.get("replay"), False))

    # sender
    sender = None
    s1 = msg.get("sender") or m.get("sender")
    if isinstance(s1, dict):
        sender = s1.get("agent_id")

    return ts, trust, revoked, sig_valid, replay, sender

def _read_lines(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                continue
    return rows

def plot_trust(agent_filter=None):
    data_rows   = _read_lines(DATA_FILE)
    alerts_rows = _read_lines(ALERTS_FILE)

    ts_list, trust_list = [], []
    alerts_pts = []

    revoked_spans = []
    rev_on = None

    last_t = None
    onboarding_spans = []
    ob_on = None

    for row in data_rows:
        ts, trust, revoked, sig_valid, replay, sender = _extract(row)
        if ts is None or trust is None:
            continue
        if agent_filter and sender and sender != agent_filter:
            continue

        ts_list.append(ts); trust_list.append(float(trust))

        # revoked zone
        if revoked and rev_on is None:
            rev_on = ts
        if (not revoked) and rev_on is not None:
            revoked_spans.append((rev_on, ts))
            rev_on = None

        # onboarding (trust 급상승 구간 간단 추정)
        if last_t is not None:
            delta = trust - last_t
            if delta >= 0.15 and ob_on is None:
                ob_on = ts
            elif delta < 0.05 and ob_on is not None:
                onboarding_spans.append((ob_on, ts))
                ob_on = None
        last_t = trust

    # 미종료 스팬 닫기
    if rev_on is not None and ts_list:
        revoked_spans.append((rev_on, ts_list[-1]))
    if ob_on is not None and ts_list:
        onboarding_spans.append((ob_on, ts_list[-1]))

    # alerts 점(리플레이/무효/폐기 등)
    for row in alerts_rows:
        ts = _parse_ts(_first(row.get("ts"), row.get("timestamp")))
        r  = row.get("reason", {})
        tr = r.get("trust")
        if ts is not None and tr is not None:
            alerts_pts.append((ts, float(tr)))

    # === 그리기 ===
    plt.figure(figsize=(10, 4))
    if ts_list:
        plt.plot(ts_list, trust_list, marker="o", color="#1f77b4", label="Trust")

    for s, e in revoked_spans:
        plt.axvspan(s, e, color="red", alpha=0.15, label="Revoked" if "Revoked" not in plt.gca().get_legend_handles_labels()[1] else "")
    for s, e in onboarding_spans:
        plt.axvspan(s, e, color="green", alpha=0.10, label="Onboarding" if "Onboarding" not in plt.gca().get_legend_handles_labels()[1] else "")

    if alerts_pts:
        plt.scatter([x for x,_ in alerts_pts], [y for _,y in alerts_pts], color="orange", zorder=5, label="Alerts")

    plt.axhline(0.3, color="orange", linestyle="--", label="Normal (0.3)")
    plt.axhline(0.8, color="red", linestyle="--", label="Privileged (0.8)")
    title = "Agent Trust Timeline" if ts_list else "Agent Trust Timeline (No Data)"
    plt.title(title)
    plt.xlabel("Time"); plt.ylabel("Trust Level")
    plt.ylim(-0.05, 1.05)
    plt.grid(True, ls="--", alpha=0.5)
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(PNG_FILE, dpi=300)
    plt.close()
    print(f"[plot_utils] saved → {PNG_FILE}")

if __name__ == "__main__":
    # 특정 에이전트만 보고 싶으면 예: plot_trust('agent-user-01')
    plot_trust()
