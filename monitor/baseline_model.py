"""Agent 행동 패턴 Baseline 모델링"""
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import statistics
import time

BEHAVIOR_LOG = Path("monitor/behavior_log.jsonl")

class AgentBaseline:
    """각 agent의 행동 패턴 baseline 모델"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.action_counts = defaultdict(int)  # action별 횟수
        self.action_times = defaultdict(list)  # action별 시간대
        self.target_agents = defaultdict(int)  # 대상 agent별 통신 횟수
        self.avg_interval = 0.0  # 평균 행동 간격 (초)
        self.intervals = []  # 행동 간격 리스트
        self.last_action_time = None
        self.total_actions = 0
        
    def add_action(self, action: str, target_agent: Optional[str], timestamp: str):
        """행동 패턴에 추가"""
        self.action_counts[action] += 1
        self.total_actions += 1
        
        # 시간대 추출 (0-23시)
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            hour = dt.hour
            self.action_times[action].append(hour)
        except:
            pass
        
        if target_agent:
            self.target_agents[target_agent] += 1
        
        # 간격 계산
        try:
            current_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if self.last_action_time:
                interval = (current_time - self.last_action_time).total_seconds()
                if 0 < interval < 3600:  # 1시간 이내만 고려
                    self.intervals.append(interval)
            self.last_action_time = current_time
        except:
            pass
    
    def calculate_baseline(self):
        """Baseline 통계 계산"""
        baseline = {
            "agent_id": self.agent_id,
            "total_actions": self.total_actions,
            "action_distribution": dict(self.action_counts),
            "action_frequencies": {
                action: count / self.total_actions if self.total_actions > 0 else 0
                for action, count in self.action_counts.items()
            },
            "target_agent_distribution": dict(self.target_agents),
            "avg_interval_seconds": statistics.mean(self.intervals) if self.intervals else 0,
            "std_interval_seconds": statistics.stdev(self.intervals) if len(self.intervals) > 1 else 0,
            "action_time_patterns": {
                action: {
                    "avg_hour": statistics.mean(hours) if hours else 0,
                    "std_hour": statistics.stdev(hours) if len(hours) > 1 else 0,
                    "most_common_hour": max(set(hours), key=hours.count) if hours else 0
                }
                for action, hours in self.action_times.items()
            }
        }
        return baseline
    
    def detect_anomaly(self, action: str, target_agent: Optional[str], 
                      interval: Optional[float] = None) -> Dict:
        """이상 행동 탐지"""
        anomalies = []
        
        # 1. 희귀한 action 탐지
        if self.total_actions > 10:
            action_freq = self.action_counts.get(action, 0) / self.total_actions
            if action_freq < 0.01 and action not in ["ping", "get_status"]:  # 1% 미만
                anomalies.append({
                    "type": "rare_action",
                    "action": action,
                    "frequency": action_freq,
                    "severity": "medium"
                })
        
        # 2. 비정상적인 간격 탐지
        if interval and self.intervals:
            avg_interval = statistics.mean(self.intervals)
            std_interval = statistics.stdev(self.intervals) if len(self.intervals) > 1 else avg_interval * 0.5
            
            if interval > avg_interval + 3 * std_interval:
                anomalies.append({
                    "type": "unusual_interval",
                    "interval": interval,
                    "expected_avg": avg_interval,
                    "severity": "low"
                })
            elif interval < avg_interval - 3 * std_interval and interval > 0:
                anomalies.append({
                    "type": "rapid_actions",
                    "interval": interval,
                    "expected_avg": avg_interval,
                    "severity": "medium"
                })
        
        # 3. 비정상적인 대상 agent 탐지
        if target_agent and self.total_actions > 10:
            target_freq = self.target_agents.get(target_agent, 0) / self.total_actions
            if target_freq < 0.05:  # 5% 미만
                anomalies.append({
                    "type": "unusual_target",
                    "target_agent": target_agent,
                    "frequency": target_freq,
                    "severity": "low"
                })
        
        return {
            "has_anomaly": len(anomalies) > 0,
            "anomalies": anomalies
        }

class BaselineModel:
    """전체 agent baseline 모델 관리"""
    
    def __init__(self):
        self.baselines: Dict[str, AgentBaseline] = {}
        self.load_from_logs()
    
    def load_from_logs(self, limit: int = 10000):
        """behavior_log.jsonl에서 행동 패턴 로드"""
        if not BEHAVIOR_LOG.exists():
            return
        
        try:
            # 기존 baseline 유지하면서 새 데이터 추가
            with open(BEHAVIOR_LOG, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # 최근 limit개만 로드
                for line in lines[-limit:]:
                    try:
                        entry = json.loads(line.strip())
                        # sender_agent 또는 executor_agent 추출
                        agent_id = entry.get("sender_agent") or entry.get("executor_agent", "unknown")
                        if agent_id == "unknown":
                            continue
                        
                        if agent_id not in self.baselines:
                            self.baselines[agent_id] = AgentBaseline(agent_id)
                        
                        baseline = self.baselines[agent_id]
                        action = entry.get("action", "unknown")
                        target_agent = entry.get("recipient_agent") or entry.get("target_agent")
                        timestamp = entry.get("timestamp", datetime.utcnow().isoformat() + "Z")
                        
                        baseline.add_action(action, target_agent, timestamp)
                    except Exception as e:
                        continue
        except Exception as e:
            print(f"[Baseline] Error loading logs: {e}")
    
    def get_baseline(self, agent_id: str) -> Optional[Dict]:
        """Agent의 baseline 반환"""
        if agent_id not in self.baselines:
            return None
        return self.baselines[agent_id].calculate_baseline()
    
    def update_baseline(self, agent_id: str, action: str, target_agent: Optional[str], timestamp: str):
        """Baseline 업데이트"""
        if agent_id not in self.baselines:
            self.baselines[agent_id] = AgentBaseline(agent_id)
        
        self.baselines[agent_id].add_action(action, target_agent, timestamp)
    
    def detect_anomaly(self, agent_id: str, action: str, target_agent: Optional[str],
                      timestamp: str, last_action_time: Optional[datetime] = None) -> Dict:
        """이상 행동 탐지"""
        if agent_id not in self.baselines:
            return {"has_anomaly": False, "anomalies": [], "reason": "no_baseline"}
        
        baseline = self.baselines[agent_id]
        
        # 간격 계산
        interval = None
        if last_action_time:
            try:
                current_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                interval = (current_time - last_action_time).total_seconds()
            except:
                pass
        
        return baseline.detect_anomaly(action, target_agent, interval)
    
    def get_all_baselines(self) -> Dict[str, Dict]:
        """모든 agent의 baseline 반환"""
        return {
            agent_id: baseline.calculate_baseline()
            for agent_id, baseline in self.baselines.items()
        }

# 전역 baseline 모델 인스턴스
baseline_model = BaselineModel()

