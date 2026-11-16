import base64
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from src import azure_key_vault_receipt_signing as m
from src.workflows.incident_resolution.mcp_receipt_trust import IndependentReceiptVerifier, TrustedPublicKey, signature_preimage_v1

KEY='https://kv-icenter-sbx-neu.vault.azure.net/keys/synthetic-test-only/'+'1'*32
MI='11111111-1111-4111-8111-111111111111'
PRINCIPAL='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
IDENTITY=m.ReceiptManagedIdentity('user_assigned',PRINCIPAL,MI)
SCOPE='tenant:test/project:test/f27'
DOMAIN='backend_provenance'
SUBJECT=b'{"backend_request_id":"request-test","verified":true}'

class Credential:
    def __init__(self): self.scopes=[]
    def get_token(self,scope): self.scopes.append(scope);return SimpleNamespace(token='SYNTHETIC_SECRET')
    def close(self):pass

def fixture(*,reply=None):
    private=ec.generate_private_key(ec.SECP256R1())
    public=TrustedPublicKey('mcp_backend',private.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo),frozenset({DOMAIN}))
    pin=m.KeyVaultReceiptPin(KEY,IDENTITY,SCOPE,public);calls=[];credential=Credential()
    def handler(request):
        calls.append(request)
        assert request.method=='POST' and str(request.url)==KEY+'/sign?api-version=2025-07-01'
        assert request.headers['authorization']=='Bearer SYNTHETIC_SECRET'
        body=json.loads(request.content);assert body['alg']=='ES256'
        digest=base64.urlsafe_b64decode(body['value']+'=')
        assert digest==hashlib.sha256(signature_preimage_v1(scope=SCOPE,issuer='mcp_backend',domain=DOMAIN,kid=public.kid,subject=json.loads(SUBJECT))).digest()
        der=private.sign(digest,ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        r,s=utils.decode_dss_signature(der)
        value=base64.urlsafe_b64encode(r.to_bytes(32,'big')+s.to_bytes(32,'big')).rstrip(b'=').decode()
        obj={'kid':KEY,'value':value}
        return reply(request,obj) if reply else httpx.Response(200,json=obj)
    client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False,follow_redirects=False)
    return m.KeyVaultReceiptSignAttempt(pin=pin,credential=credential,client=client),calls,credential

def test_signs_one_sha256_digest_and_existing_verifier_accepts():
    attempt,calls,credential=fixture();out=attempt.sign(subject_json=SUBJECT,domain=DOMAIN)
    verifier=IndependentReceiptVerifier(scope=SCOPE,keys=(attempt.pin.public_key,))
    assert verifier(out.receipt,subject_kind=DOMAIN,subject=json.loads(out.canonical_subject))
    assert not verifier(out.receipt,subject_kind=DOMAIN,subject={'backend_request_id':'other','verified':True})
    assert out.key_version_id==KEY and len(calls)==1 and credential.scopes==['https://vault.azure.net/.default']
    with pytest.raises(m.ReceiptSigningUnavailable,match='ALREADY_CONSUMED'):attempt.sign(subject_json=SUBJECT,domain=DOMAIN)
    assert len(calls)==1

@pytest.mark.parametrize('status',[301,302,307,401,403,429,500,503])
def test_failure_never_retries_or_follows_redirect(status):
    attempt,calls,_=fixture(reply=lambda req,obj:httpx.Response(status,headers={'Location':'https://evil.invalid'},text='PRIVATE_ERROR'))
    with pytest.raises(m.ReceiptSigningUnavailable,match='UNUSABLE') as err:attempt.sign(subject_json=SUBJECT,domain=DOMAIN)
    assert 'PRIVATE' not in str(err.value) and 'SYNTHETIC_SECRET' not in str(err.value)
    with pytest.raises(m.ReceiptSigningUnavailable,match='ALREADY_CONSUMED'):attempt.sign(subject_json=SUBJECT,domain=DOMAIN)
    assert len(calls)==1

@pytest.mark.parametrize('kind',['duplicate','wrong_version','extra','invalid_signature','padding','oversize','non_json'])
def test_unusable_replies_do_not_produce_a_receipt(kind):
    def response(req,obj):
        if kind=='duplicate': return httpx.Response(200,content=b'{"kid":"x","kid":"y","value":"z"}')
        if kind=='wrong_version': obj['kid']=KEY[:-1]+'2'
        if kind=='extra':obj['untrusted_public_key']='do-not-trust'
        if kind=='invalid_signature':obj['value']='A'*86
        if kind=='padding':obj['value']+='=='
        if kind=='oversize':return httpx.Response(200,content=b'x'*16385)
        if kind=='non_json':return httpx.Response(200,content=b'PRIVATE')
        return httpx.Response(200,json=obj)
    attempt,calls,_=fixture(reply=response)
    with pytest.raises(m.ReceiptSigningUnavailable,match='UNUSABLE'):attempt.sign(subject_json=SUBJECT,domain=DOMAIN)
    assert len(calls)==1

def test_transport_failure_consumes_attempt_without_error_leak():
    def fail(*a):raise httpx.ReadTimeout('PRIVATE_TOKEN')
    attempt,calls,_=fixture(reply=fail)
    with pytest.raises(m.ReceiptSigningUnavailable,match='UNUSABLE') as err:attempt.sign(subject_json=SUBJECT,domain=DOMAIN)
    assert str(err.value)=='SIGN_RESULT_UNUSABLE_NO_RETRY'
    with pytest.raises(m.ReceiptSigningUnavailable,match='ALREADY_CONSUMED'):attempt.sign(subject_json=SUBJECT,domain=DOMAIN)
    assert len(calls)==1

@pytest.mark.parametrize('raw',[b'{"a":1,"a":2}',b'{"a":1.5}',b'{"a":NaN}',b'{"a":"\\u00f1"}'])
def test_invalid_subject_rejected_before_credentials_or_http(raw):
    attempt,calls,credential=fixture()
    with pytest.raises(ValueError):attempt.sign(subject_json=raw,domain=DOMAIN)
    assert calls==[] and credential.scopes==[]

def test_unregistered_domain_fails_before_credential():
    attempt,calls,credential=fixture()
    with pytest.raises(ValueError):attempt.sign(subject_json=SUBJECT,domain='other')
    assert calls==[] and credential.scopes==[]

@pytest.mark.parametrize('key',[KEY.replace('https:','http:'),KEY.replace('.vault.azure.net','.evil.invalid'),KEY.rsplit('/',1)[0],KEY+'?api-version=latest',KEY+'#x',KEY.replace('vault.azure.net','vault.azure.net:443'),KEY.replace('/keys/','/secrets/')])
def test_key_pin_rejects_unversioned_or_different_authority(key):
    attempt,_,_=fixture()
    with pytest.raises(ValueError):replace(attempt.pin,key_id=key)

def attestor_pin(backend):
    private=ec.generate_private_key(ec.SECP256R1())
    public=TrustedPublicKey('correlation_attestor',private.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo),frozenset({'correlation:authenticated_backend_request'}))
    return m.KeyVaultReceiptPin(KEY.replace('synthetic-test-only','synthetic-attestor'), m.ReceiptManagedIdentity('user_assigned','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','22222222-2222-4222-8222-222222222222'),SCOPE,public)

def test_static_independent_signer_configuration():
    attempt,_,_=fixture();a=attestor_pin(attempt.pin)
    m.validate_independent_receipt_pins(attempt.pin,a)
    with pytest.raises(ValueError):m.validate_independent_receipt_pins(attempt.pin,replace(a,managed_identity=IDENTITY))
    with pytest.raises(ValueError):m.validate_independent_receipt_pins(attempt.pin,replace(a,key_id=KEY))
    shared=TrustedPublicKey('correlation_attestor',attempt.pin.public_key.spki_der,a.public_key.domains)
    with pytest.raises(ValueError):m.validate_independent_receipt_pins(attempt.pin,replace(a,public_key=shared))
    with pytest.raises(ValueError):m.validate_independent_receipt_pins(attempt.pin,replace(a,scope='tenant:other'))

def test_factory_has_no_default_credential_proxy_redirect_or_retry(monkeypatch):
    attempt,_,_=fixture();seen={}
    def credential(**kwargs):seen['credential']=kwargs;return Credential()
    def transport(**kwargs):seen['transport']=kwargs;return object()
    def client(**kwargs):seen['client']=kwargs;return object()
    monkeypatch.setattr(m,'ManagedIdentityCredential',credential)
    monkeypatch.setattr(m.httpx,'HTTPTransport',transport)
    monkeypatch.setattr(m.httpx,'Client',client)
    m.build_managed_identity_sign_attempt(attempt.pin)
    assert seen['credential']=={'client_id':MI,'retry_total':0}
    assert seen['transport']=={'retries':0}
    assert seen['client']['trust_env'] is False and seen['client']['follow_redirects'] is False
