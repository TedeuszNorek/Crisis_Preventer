from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class SignalRule:
    operator: str
    enter_threshold: float
    exit_threshold: float

@dataclass
class SignalContractV1:
    signal_id: str
    intent: str
    inputs: List[str]
    compute: str
    rule: SignalRule
    anti_flapping: Dict[str, int]
    data_quality_gate: Dict[str, float]
    drift_hooks: Dict[str, Any]
    confidence: float
    severity: str
    evidence_pack: List[str]
    dedupe_key: str
    lifecycle: List[str]
    actions: List[str]
    owner: str
    tests: List[str]
