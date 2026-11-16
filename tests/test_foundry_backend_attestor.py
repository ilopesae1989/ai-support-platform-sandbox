"""Offline flow with real ES256, synthetic Foundry/KV and in-memory stores."""
import base64
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils

from src.attestation.foundry_backend_attestor import (
    AttestationJob, AttestationStopped, FoundryBackendAttestor, KINDS, LINK_DOMAIN, WIRE_FIELD,
)
from src.agents.foundry_native_receipt_source import FoundryNativeReceiptSource, NativeReceiptReadbackPin
from src.azure_key_vault_receipt_signing import ReceiptManagedIdentity, KeyVaultReceiptPin, KeyVaultReceiptSignAttempt
from src.persistence.receipt_custody import ReceiptCustodian, IndexOutcome, CustodyOutcome
from src.workflows.incident_resolution.mcp_receipt_trust import IndependentReceiptVerifier, canonical_subject_v1

spec = importlib.util.spec_from_file_location("attestor_crypto", Path(__file__).parent /
    "workflows/incident_resolution/test_mcp_authenticated_backend_bridge.py")
crypto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crypto)


class Journal:
    def __init__(self):
        self.claims, self.stages, self.writes, self.reads = {}, {}, [], []
        self.fail_stage = None
    def reserve(self, keys, owner, record):
        self.writes.append(tuple(keys))
        if any(k in self.claims for k in keys): return False
        self.claims.update({k: (owner, record) for k in keys})
        return True
    def put(self, owner, stage, raw):
        self.writes.append(stage)
        if stage == self.fail_stage or (owner, stage) in self.stages: return False
        self.stages[owner, stage] = raw
        return True
    def get(self, owner, stage):
        self.reads.append(stage)
        return self.stages.get((owner, stage))
    def read_claim(self, owner):
        self.reads.append("claim")
        return self.claims.get(owner, (None, None))[1]


class Objects:
    def __init__(self): self.rows, self.puts = {}, []
    def create_and_verify(self, name, data):
        self.puts.append(name)
        assert name not in self.rows
        self.rows[name] = data
        return self.read_and_verify(name, data)
    def read_and_verify(self, name, data):
        assert self.rows[name] == data
        return dict(name=name, sha256=hashlib.sha256(data).hexdigest(), uri="https://synthetic/"+name)


class Index:
    def __init__(self): self.rows, self.puts = {}, []
    def insert_once(self, logical, raw):
        self.puts.append(logical)
        assert logical not in self.rows
        self.rows[logical] = raw
        return IndexOutcome.COMMITTED
    def read(self, logical, raw):
        return IndexOutcome.PRESENT if self.rows.get(logical) == raw else IndexOutcome.ABSENT


def setup(*, journal=None, changed=None, fail_get=None, fail_sign=None, operation="operation-001",
          response="resp-exec", approval="mcpr-001", keys=None, finish="SUCCESS"):
    p = crypto._pinned(state="APPROVED", human="human-001", operation_id=operation,
        response_id=response, approval_request_id=approval, server_label="azure-mcp-rglist-read")
    if keys is None:
        bp, bk = crypto._key("mcp_backend", "event:"+KINDS[0])
        bk = replace(bk, domains=frozenset("event:"+k for k in KINDS))
        ap, ak = crypto._key("correlation_attestor", LINK_DOMAIN)
        keys = (bp,bk,ap,ak)
    bp,bk,ap,ak = keys
    backend = KeyVaultReceiptPin("https://f27synthetic.vault.azure.net/keys/backend/"+"a"*32,
        ReceiptManagedIdentity("system_assigned", "00000000-0000-0000-0000-000000000001"), p.trusted_scope, bk)
    attestor = KeyVaultReceiptPin("https://f27synthetic.vault.azure.net/keys/attestor/"+"b"*32,
        ReceiptManagedIdentity("user_assigned", "00000000-0000-0000-0000-000000000002",
                               "00000000-0000-0000-0000-000000000003"), p.trusted_scope, ak)
    native = NativeReceiptReadbackPin("https://synthetic.services.ai.azure.com/api/projects/sandbox",
        attestor.managed_identity,"resp-pause",response,approval,p.server_label,p.tool_name,b'{"subscription":"sandbox"}')
    job = AttestationJob(p,native,backend,attestor)
    events=[]
    for i,k in enumerate(KINDS):
        event = crypto._backend_body(p,k)
        event.update(event_id="backend-event-"+str(i),captured_at_utc=f"2026-10-28T10:00:0{i+1}Z",
                     ingested_at_utc=f"2026-10-28T10:00:0{i+2}Z")
        if i == 2: event["status"] = finish
        event["source_receipt"] = crypto._sign(bp,bk,"event:"+k,event)
        events.append(event)
    if changed: changed(events, bp, bk)
    replies = [dict(id="resp-pause",object="response",status="completed",error=None,
        output=[dict(id=approval,type="mcp_approval_request",server_label=p.server_label,
        name=p.tool_name,arguments=native.expected_arguments_json.decode())]),
        dict(id=response,object="response",status="completed",error=None,previous_response_id="resp-pause",
        output=[dict(id="mcpt-001",type="mcp_call",server_label=p.server_label,name=p.tool_name,
        arguments=native.expected_arguments_json.decode(),approval_request_id=approval,
        output=json.dumps({WIRE_FIELD:events,"result":{"private":"not public"}}),error=None,status="completed")]),
        dict(object="list",has_more=False,data=[dict(id="mcpa-001",type="mcp_approval_response",
             approval_request_id=approval,approve=True)])]
    requests, signs = [],[]
    credential = SimpleNamespace(get_token=lambda scope:SimpleNamespace(token="synthetic-token"),close=lambda:None)
    def get(request):
        index=len(requests);requests.append(request)
        if index == fail_get: raise httpx.ReadTimeout("private error")
        return httpx.Response(200,json=replies[index])
    source = FoundryNativeReceiptSource(pin=native,credential=credential,
        client=httpx.Client(transport=httpx.MockTransport(get)))
    def sign(request):
        signs.append(request)
        if len(signs)==fail_sign: raise httpx.ReadTimeout("private sign error")
        body=json.loads(request.content); digest=base64.urlsafe_b64decode(body["value"]+"=")
        der=ap.sign(digest,ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        r,s=utils.decode_dss_signature(der)
        return httpx.Response(200,json={"kid":attestor.key_id,"value":base64.urlsafe_b64encode(
            r.to_bytes(32,"big")+s.to_bytes(32,"big")).rstrip(b"=").decode()})
    def signer(pin):
        return KeyVaultReceiptSignAttempt(pin=pin,credential=credential,
            client=httpx.Client(transport=httpx.MockTransport(sign)))
    objects,index=Objects(),Index()
    custody=ReceiptCustodian(objects=objects,index=index,
        backend_verifier=IndependentReceiptVerifier(scope=p.trusted_scope,keys=(bk,)),
        bridge_verifier=IndependentReceiptVerifier(scope=p.trusted_scope,keys=(ak,)))
    journal=journal or Journal()
    worker=FoundryBackendAttestor(job=job,source=source,journal=journal,signer_factory=signer,
        custodian=custody,clock=lambda:"2026-10-28T10:00:04Z")
    return SimpleNamespace(worker=worker,job=job,events=events,replies=replies,requests=requests,
        signs=signs,journal=journal,objects=objects,index=index,custody=custody,keys=keys)


@pytest.mark.parametrize("finish",["SUCCESS","ERROR"])
def test_three_verified_pairs_and_read_only_recovery_never_grant_success(finish):
    f=setup(finish=finish);result=f.worker.run_once()
    assert result.outcome == "RECEIPTS_STORED_VERIFIED_NO_AUTHORITY"
    assert result.signed_pairs == result.stored_pairs == 3
    assert len(f.requests)==len(f.signs)==3 and len(f.objects.puts)==6 and len(f.index.puts)==3
    assert all(x.method=="GET" for x in f.requests)
    assert all(x.method=="POST" and "/sign?" in str(x.url) for x in f.signs)
    assert not hasattr(result,"technical_success") and not hasattr(result,"dispatch_allowed")
    before=(len(f.journal.writes),len(f.signs),len(f.objects.puts),len(f.index.puts),len(f.requests))
    assert f.worker.reconcile().outcome == "RECOVERY_READBACK_VERIFIED_NO_AUTHORITY"
    assert before==(len(f.journal.writes),len(f.signs),len(f.objects.puts),len(f.index.puts),len(f.requests))
    assert "not public" not in repr(result)


def test_fresh_worker_cannot_repeat_operation_or_native_approval():
    f=setup(); assert f.worker.run_once().stored_pairs==3
    for overrides in ({},{"operation":"other"},{"operation":"other","response":"resp-new"}):
        g=setup(journal=f.journal,keys=f.keys,**overrides)
        assert g.worker.run_once().stop_code == "OPERATION_CLAIM_UNAVAILABLE"
        assert not g.requests and not g.signs and not g.objects.puts


def test_backend_events_cannot_move_to_another_native_call():
    f=setup();assert f.worker.run_once().stored_pairs==3
    g=setup(journal=f.journal,keys=f.keys,operation="other",response="resp-new",approval="mcpr-new")
    assert g.worker.run_once().stop_code == "BACKEND_REPLAY_OR_UNKNOWN"
    assert len(g.requests)==3 and not g.signs and not g.objects.puts


def resign(events, bp, bk):
    for e in events:
        e["source_receipt"]=crypto._sign(bp,bk,"event:"+e["event_type"],
            {k:v for k,v in e.items() if k!="source_receipt"})


@pytest.mark.parametrize("index,field,value",[
    (0,"auth_result","DENY"),(0,"issuer_valid",False),(0,"tenant_valid",False),
    (0,"audience_valid",False),(0,"lifetime_valid",False),(0,"role_or_scope_valid",False),
    (1,"backend_request_id","another"),(2,"producer_instance_id","another"),
    (0,"tool_name","vm_start"),(1,"arguments_fingerprint","hmac:wrong"),
    (2,"backend_revision_fingerprint","hmac:other"),(1,"image_fingerprint","hmac:other"),
    (2,"event_id","backend-event-1"),(0,"captured_at_utc","2026-10-28T09:00:00Z"),
    (1,"captured_at_utc","2026-10-28T09:59:59Z"),
])
def test_even_validly_signed_mismatches_do_not_reach_attestor_signing(index,field,value):
    def changed(events,bp,bk):
        events[index][field]=value;resign(events,bp,bk)
    f=setup(changed=changed);result=f.worker.run_once()
    assert result.outcome=="ATTESTATION_STOP_NO_RETRY"
    assert not f.signs and not f.objects.puts and not f.index.puts


def test_invalid_backend_signature_is_rejected():
    def changed(events,bp,bk): events[1]["source_receipt"]["proof_id"]="es256:v1:"+bk.kid+":"+"A"*86
    f=setup(changed=changed)
    assert f.worker.run_once().stop_code=="BACKEND_SIGNATURE_INVALID"
    assert not f.signs


@pytest.mark.parametrize("payload",['{}','{"f27_backend_receipts_v1":[]}',
    '{"f27_backend_receipts_v1":[],"f27_backend_receipts_v1":[]}',
    '{"f27_backend_receipts_v1":NaN}','[1,2,3]'])
def test_missing_or_ambiguous_native_receipts_never_sign(payload):
    f=setup();f.replies[1]["output"][0]["output"]=payload
    assert f.worker.run_once().outcome=="ATTESTATION_STOP_NO_RETRY"
    assert not f.signs


@pytest.mark.parametrize("stage,signed,stored",[("NATIVE_APPROVAL",0,0),("NATIVE_EXECUTION",0,0),
    ("NATIVE_INPUT",0,0),("PAIR_0",1,0),("PAIR_1",2,1),("PAIR_2",3,2),("COMPLETE",3,3)])
def test_journal_failure_preserves_attempt_and_never_repeats(stage,signed,stored):
    f=setup();f.journal.fail_stage=stage;result=f.worker.run_once()
    assert result.outcome=="ATTESTATION_STOP_NO_RETRY"
    assert result.signed_pairs==signed and result.stored_pairs==stored
    with pytest.raises(AttestationStopped,match="WORKER_ALREADY_CONSUMED"):f.worker.run_once()
    g=setup(journal=f.journal,keys=f.keys)
    assert g.worker.run_once().stop_code=="OPERATION_CLAIM_UNAVAILABLE" and not g.requests


@pytest.mark.parametrize("number",[1,2,3])
def test_unknown_sign_result_never_retried(number):
    f=setup(fail_sign=number);r=f.worker.run_once()
    assert r.outcome=="ATTESTATION_STOP_NO_RETRY" and len(f.signs)==number
    before=len(f.signs)
    assert f.worker.reconcile().outcome=="RECOVERY_INCOMPLETE_NO_WRITES"
    assert len(f.signs)==before


@pytest.mark.parametrize("number",[0,1,2])
def test_failed_provider_read_keeps_claim_without_sign_or_retry(number):
    f=setup(fail_get=number);r=f.worker.run_once()
    assert r.outcome=="ATTESTATION_STOP_NO_RETRY" and not f.signs
    g=setup(journal=f.journal,keys=f.keys)
    assert g.worker.run_once().stop_code=="OPERATION_CLAIM_UNAVAILABLE" and not g.requests


def test_storage_unknown_stops_further_pairs_and_recovery_only_reads():
    f=setup();original=f.custody.store
    def uncertain(**kwargs):
        original(**kwargs)
        return SimpleNamespace(outcome=CustodyOutcome.INDEX_UNCERTAIN_NO_RETRY)
    f.custody.store=uncertain
    assert f.worker.run_once().stop_code=="PAIR_STORE_UNCERTAIN"
    assert len(f.signs)==1 and len(f.objects.puts)==2
    assert f.worker.reconcile().outcome=="RECOVERY_INCOMPLETE_NO_WRITES"
    assert len(f.signs)==1 and len(f.objects.puts)==2


def test_recovery_rejects_changed_governor_pins():
    f=setup();assert f.worker.run_once().stored_pairs==3
    g=setup(journal=f.journal,keys=f.keys)
    g.worker.job=replace(g.job,operation=replace(g.job.operation,agent_version="999"))
    assert g.worker.reconcile().stop_code=="RECOVERY_PIN_MISMATCH"
    assert not g.requests and not g.signs


@pytest.mark.parametrize("change",["scope","state","native","identity","key","domains"])
def test_job_configuration_rejects_inconsistent_or_non_independent_pins(change):
    f=setup();j=f.job
    with pytest.raises(ValueError if change in ("scope","key") else (ValueError,AttestationStopped)):
        if change=="scope":replace(j,backend=replace(j.backend,scope="tenant:another/f27"))
        elif change=="state":replace(j,operation=replace(j.operation,approval_state="DENIED",technical_approval=False))
        elif change=="native":replace(j,native=replace(j.native,execution_response_id="resp-other"))
        elif change=="identity":replace(j,native=replace(j.native,identity=j.backend.managed_identity))
        elif change=="key":replace(j,attestor=replace(j.attestor,managed_identity=j.backend.managed_identity))
        else:replace(j,backend=replace(j.backend,public_key=replace(j.backend.public_key,domains=frozenset({"event:"+KINDS[0]}))))
