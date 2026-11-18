"""Diagnostic projection of persisted evidence for a trusted installation."""
from collections import Counter
from dataclasses import dataclass, field
from uuid import UUID

from src.runtime.execution_affinity import AFFINITY_STATE_KEY, ExecutionAffinity, require_digest, require_identifier
from src.runtime.incident_execution import EXECUTION_ID_STATE_KEY, MANUAL_ANALYSIS_REASON_KEY
from src.runtime.procedure.models import WorkflowStatus


@dataclass(frozen=True)
class CheckpointEvidence:
    checkpoint_id: str
    parent: str | None
    signature: str
    requests: frozenset[str]
    messages: bool
    workflow_status: str | None
    manual_reason: str | None = None


@dataclass
class ExecutionEvidence:
    execution_id: str
    affinity: ExecutionAffinity
    checkpoints: dict[str, CheckpointEvidence] = field(default_factory=dict)
    # request_id -> (checkpoint_id, consumption status)
    approvals: dict[str, tuple[str, str]] = field(default_factory=dict)
    jobs: list[tuple[str, str]] = field(default_factory=list)
    issues: set[str] = field(default_factory=set)

    rejection_receipt: dict[str, str] = field(default_factory=lambda: {'status': 'unavailable'})

    resolution_receipt: dict[str, str] = field(default_factory=lambda: {'status': 'unavailable'})

    def observe_checkpoint(self, doc, stored_id):
        state = doc['state']
        runtime = state.get('procedure_runtime_state', {})
        if (doc['version'] != '1.0' or doc['checkpoint_id'] != stored_id
                or state[EXECUTION_ID_STATE_KEY] != self.execution_id
                or state.get(AFFINITY_STATE_KEY) != self.affinity.to_document()
                or not isinstance(runtime, dict)
                or (runtime and runtime.get('workflow_id') != self.execution_id)):
            self.issues.add('checkpoint_identity_conflict')
            return
        requests, messages = doc['pending_request_info_events'], doc['messages']
        if not isinstance(requests, dict) or not isinstance(messages, dict):
            self.issues.add('invalid_checkpoint')
            return
        parent, signature = doc['previous_checkpoint_id'], doc['graph_signature_hash']
        require_identifier(stored_id, 'checkpoint_id')
        if parent is not None:
            require_identifier(parent, 'previous_checkpoint_id')
        require_digest(signature, 'graph_signature_hash')
        reason = state.get(MANUAL_ANALYSIS_REASON_KEY)
        if MANUAL_ANALYSIS_REASON_KEY in state and (
                reason not in ("no_procedure", "human_escalation_required") or runtime or requests or messages):
            self.issues.add("manual_analysis_checkpoint_conflict")
            return
        cp = CheckpointEvidence(stored_id, parent, signature,
                                frozenset(requests), bool(messages), runtime.get('workflow_status'), reason)
        if stored_id in self.checkpoints:
            self.issues.add('duplicate_checkpoint')
        self.checkpoints[stored_id] = cp

    def verify_entry(self, lookup):
        """MAF's entry predates assignment to state. Follow the persisted parent reference."""
        for cp in self.checkpoints.values():
            if cp.parent in self.checkpoints:
                continue
            root = lookup(cp.parent) if cp.parent else None
            marker = f'internal:classification-affinity-{self.affinity.fingerprint}-admitted-v1'
            if (not root or root.get('checkpoint_id') != cp.parent
                    or root.get('previous_checkpoint_id') is not None
                    or root.get('workflow_name') != 'incident-resolution'
                    or root.get('version') != '1.0'
                    or root.get('graph_signature_hash') != cp.signature
                    or EXECUTION_ID_STATE_KEY in root['state']
                    or AFFINITY_STATE_KEY in root['state'] or set(root['messages']) != {marker}):
                self.issues.add('entry_checkpoint_unconfirmed')

    def _head(self):
        if not self.checkpoints:
            return None
        parents = {cp.parent for cp in self.checkpoints.values()}
        heads = self.checkpoints.keys() - parents
        if len(heads) == 1:
            head = self.checkpoints[next(iter(heads))]
            current = head
            visited = set()
            while current is not None and current.checkpoint_id not in visited:
                if current.signature != head.signature:
                    break
                visited.add(current.checkpoint_id)
                current = self.checkpoints.get(current.parent)
            if current is None and len(visited) == len(self.checkpoints):
                return head
        self.issues.add('ambiguous_checkpoint_history')
        return None

    def describe(self, consumer):
        head = self._head()
        for request_id, (checkpoint_id, _) in self.approvals.items():
            checkpoint = self.checkpoints.get(checkpoint_id)
            if checkpoint is None or request_id not in checkpoint.requests:
                self.issues.add('approval_checkpoint_unconfirmed')
        phase = 'start_unconfirmed' if not self.approvals and not self.jobs else 'unknown'
        if head:
            phase = 'in_progress'
            if head.requests:
                if head.workflow_status == WorkflowStatus.WAITING_HUMAN and head.requests <= self.approvals.keys():
                    phase = 'hitl_checkpoint'
                elif (head.workflow_status == WorkflowStatus.WAITING_VALIDATION
                      and all(_wait_request(req) for req in head.requests)):
                    phase = 'wait_checkpoint'
                elif head.workflow_status == WorkflowStatus.WAITING_HUMAN:
                    phase = 'hitl_registration_unconfirmed'
                else:
                    phase = 'pending_request_unidentified'
            elif not head.messages:
                terminal = {WorkflowStatus.RESOLVED, WorkflowStatus.BLOCKED,
                            WorkflowStatus.FAILED, WorkflowStatus.ESCALATION_REQUIRED}
                phase = 'terminal_checkpoint' if head.workflow_status in terminal else 'end_unconfirmed'
        if phase == 'terminal_checkpoint':
            if (any(status != 'completed' for _, status in self.approvals.values())
                    or any(status != 'completed' for _, status in self.jobs)):
                self.issues.add('terminal_with_unfinished_work')
        if any(cp.manual_reason is not None and cp != head for cp in self.checkpoints.values()):
            self.issues.add("manual_analysis_checkpoint_conflict")
        if head and head.manual_reason:
            if self.approvals or self.jobs:
                self.issues.add("manual_analysis_checkpoint_conflict")
            else:
                phase = "manual_analysis_requested"
        if self.issues:
            phase = 'unresolved'
        return {
            'execution_id': self.execution_id, 'release_id': self.affinity.release.release_id,
            'affinity_sha256': self.affinity.fingerprint, 'compatible': consumer == self.affinity,
            'observed_state': phase, 'checkpoint_count': len(self.checkpoints),
            'approvals': _counts(status for _, status in self.approvals.values()),
            'candidate_jobs': _counts(s for q, s in self.jobs if q == 'candidate'),
            'legacy_jobs': _counts(s for q, s in self.jobs if q == 'legacy'),
            'issues': sorted(self.issues), 'rejection_receipt': self.rejection_receipt,
            'manual_analysis_reason': head.manual_reason if phase == "manual_analysis_requested" else None,
            'resolution_receipt': self.resolution_receipt,
        }


def _wait_request(value):
    if not value.startswith('rchk-'):
        return False
    try:
        return str(UUID(value[5:])) == value[5:]
    except ValueError:
        return False


def _counts(values):
    return dict(sorted(Counter(values).items()))


def drain_reasons(row):
    """Explain outstanding work on one attributed execution in this inventory page."""
    reasons = list(row["issues"])
    phase = row["observed_state"]
    if phase == "manual_analysis_requested":
        reasons.append("manual_handoff_unconfirmed")
    elif phase != "terminal_checkpoint":
        reasons.append(phase)
    if any(status != "completed" for status in row["approvals"]):
        reasons.append("approval_unfinished")
    if any(status != "completed" for key in ("candidate_jobs", "legacy_jobs") for status in row[key]):
        reasons.append("continuation_unfinished")
    receipts = [row["resolution_receipt"], row["rejection_receipt"]]
    recorded = [receipt for receipt in receipts if receipt["status"] == "recorded"]
    if len(recorded) > 1:
        reasons.append("conflicting_terminal_receipts")
    if phase == "terminal_checkpoint" and not recorded:
        reasons.append("terminal_closure_unconfirmed")
    if recorded and any(r.get("notification_delivery") != "confirmed" for r in recorded):
        reasons.append("notification_delivery_unconfirmed")
    return reasons
