from dataclasses import replace
import pytest
from src import azure_key_vault_receipt_signing as m
from tests.test_azure_key_vault_receipt_signing import fixture, attestor_pin, Credential

READ_PRINCIPAL='32613b5f-a574-4e9c-b2af-b1e961c7240c'
WRITE_PRINCIPAL='289079d5-f779-4560-ad80-e0532ce91c17'
WRITE_CLIENT='ef81284d-d1d2-4ee3-b623-002b5ceec8fc'

@pytest.mark.parametrize('kind,principal,client',[
 ('',READ_PRINCIPAL,None), ('auto',READ_PRINCIPAL,None),
 ('user_assigned',WRITE_PRINCIPAL,None), ('user_assigned',WRITE_PRINCIPAL,''),
 ('user_assigned',WRITE_PRINCIPAL,'not-a-guid'),
 ('system_assigned',READ_PRINCIPAL,WRITE_CLIENT),
 ('system_assigned',None,None), ('system_assigned','',None),
 ('system_assigned','not-a-guid',None),
 ('system_assigned','00000000-0000-0000-0000-000000000000',None),
 ('system_assigned',READ_PRINCIPAL.upper(),None),
 ('user_assigned',WRITE_PRINCIPAL,WRITE_CLIENT.upper()),
])
def test_ambiguous_or_invalid_identity_is_rejected(kind,principal,client):
    with pytest.raises(ValueError):m.ReceiptManagedIdentity(kind,principal,client)

def test_missing_selector_is_not_implicit_system_identity():
    a,_,_=fixture()
    with pytest.raises(ValueError):replace(a.pin,managed_identity=None)
    with pytest.raises(ValueError):replace(a.pin,managed_identity=WRITE_CLIENT)

def test_system_and_user_assigned_factory_selection(monkeypatch):
    a,_,_=fixture();seen=[]
    def credential(**kwargs):seen.append(kwargs);return Credential()
    monkeypatch.setattr(m,'ManagedIdentityCredential',credential)
    monkeypatch.setattr(m.httpx,'HTTPTransport',lambda **kwargs:object())
    monkeypatch.setattr(m.httpx,'Client',lambda **kwargs:object())
    identities=[m.ReceiptManagedIdentity('system_assigned',READ_PRINCIPAL),
                m.ReceiptManagedIdentity('user_assigned',WRITE_PRINCIPAL,WRITE_CLIENT)]
    for identity in identities:m.build_managed_identity_sign_attempt(replace(a.pin,managed_identity=identity))
    assert seen==[{'retry_total':0},{'client_id':WRITE_CLIENT,'retry_total':0}]

def test_same_principal_is_rejected_even_with_different_selectors():
    a,_,_=fixture();other=attestor_pin(a.pin)
    backend=replace(a.pin,managed_identity=m.ReceiptManagedIdentity('system_assigned',READ_PRINCIPAL))
    attestor=replace(other,managed_identity=m.ReceiptManagedIdentity('user_assigned',READ_PRINCIPAL,WRITE_CLIENT))
    with pytest.raises(ValueError):m.validate_independent_receipt_pins(backend,attestor)

def test_same_client_is_rejected_even_if_principal_metadata_differs():
    a,_,_=fixture();other=attestor_pin(a.pin)
    backend=replace(a.pin,managed_identity=m.ReceiptManagedIdentity('user_assigned',READ_PRINCIPAL,WRITE_CLIENT))
    attestor=replace(other,managed_identity=m.ReceiptManagedIdentity('user_assigned',WRITE_PRINCIPAL,WRITE_CLIENT))
    with pytest.raises(ValueError):m.validate_independent_receipt_pins(backend,attestor)

def test_two_explicit_system_identities_are_distinguished_by_principal():
    a,_,_=fixture();other=attestor_pin(a.pin)
    backend=replace(a.pin,managed_identity=m.ReceiptManagedIdentity('system_assigned',READ_PRINCIPAL))
    attestor=replace(other,managed_identity=m.ReceiptManagedIdentity('system_assigned',WRITE_PRINCIPAL))
    m.validate_independent_receipt_pins(backend,attestor)

def test_different_keys_do_not_override_same_identity_rejection():
    a,_,_=fixture();other=attestor_pin(a.pin)
    with pytest.raises(ValueError):m.validate_independent_receipt_pins(a.pin,replace(other,managed_identity=a.pin.managed_identity))
