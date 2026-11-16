"""Synthetic HTTP evidence only; no Foundry call or attestor accreditation."""
from dataclasses import replace
from types import SimpleNamespace
import copy
import json

import httpx
import pytest

from src.agents import foundry_native_receipt_source as m
from src.azure_key_vault_receipt_signing import ReceiptManagedIdentity

ENDPOINT = 'https://aif-icenter-sbx-eus2.services.ai.azure.com/api/projects/aifproj-icenter-sbx'
IDENTITY = ReceiptManagedIdentity('user_assigned',
    '4d52408c-005e-41ec-8c6e-6a4a665b8afb', 'e089e1ed-e5e2-48e6-a8e5-706daa0a6975')


def pin(**changes):
    fields = dict(project_endpoint=ENDPOINT, identity=IDENTITY,
        approval_prompt_response_id='resp-pause', execution_response_id='resp-exec',
        approval_request_id='mcpr-001', server_label='azure-mcp-rglist-read',
        tool_name='group_list', expected_arguments_json=b'{"subscription":"sandbox"}')
    fields.update(changes)
    return m.NativeReceiptReadbackPin(**fields)


def replies():
    approval = dict(id='resp-pause', object='response', status='completed', error=None,
        output=[dict(id='mcpr-001', type='mcp_approval_request',
            server_label='azure-mcp-rglist-read', name='group_list',
            arguments='{"subscription":"sandbox"}')])
    execution = dict(id='resp-exec', object='response', status='completed', error=None,
        previous_response_id='resp-pause', output=[dict(id='mcpt-001', type='mcp_call',
            server_label='azure-mcp-rglist-read', name='group_list',
            arguments='{"subscription":"sandbox"}', approval_request_id='mcpr-001',
            output='sensitive synthetic output', error=None, status='completed')])
    inputs = dict(object='list', has_more=False, data=[dict(id='mcpa-001',
        type='mcp_approval_response', approval_request_id='mcpr-001', approve=True)])
    return [approval, execution, inputs]


class Credential:
    def __init__(self, token='synthetic-opaque-token'):
        self.token, self.scopes, self.closed = token, [], False
    def get_token(self, scope):
        self.scopes.append(scope)
        return SimpleNamespace(token=self.token)
    def close(self): self.closed = True


def source(data=None, *, fail_at=None, status=None, token='synthetic-opaque-token'):
    data = replies() if data is None else data
    requests = []
    credential = Credential(token)
    def handler(request):
        i = len(requests)
        requests.append(request)
        if i == fail_at:
            raise httpx.ReadTimeout('private response body must not escape')
        body = data[i]
        if isinstance(body, bytes): return httpx.Response(status or 200, content=body)
        return httpx.Response(status or 200, json=body)
    client = httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)
    return m.FoundryNativeReceiptSource(pin=pin(), credential=credential, client=client), requests, credential


def test_three_exact_gets_and_no_write_or_authority():
    reader, requests, credential = source()
    result = reader.read_once()
    assert [r.method for r in requests] == ['GET'] * 3
    assert [str(r.url) for r in requests] == [ENDPOINT + '/openai/v1/responses/' + x for x in (
        'resp-pause', 'resp-exec', 'resp-exec/input_items?limit=100&order=asc')]
    assert all(r.content == b'' for r in requests)
    assert credential.scopes == ['https://ai.azure.com/.default']
    assert result.mcp_call_id == 'mcpt-001'
    assert result.provider_output == 'sensitive synthetic output'
    assert len(set(result.source_sha256)) == 3
    assert not hasattr(result, 'dispatch_authorized')
    assert not hasattr(result, 'technical_success')
    assert 'sensitive' not in repr(result)
    assert 'sandbox' not in repr(pin())
    with pytest.raises(m.NativeReceiptUnavailable, match='ALREADY_CONSUMED'): reader.read_once()
    assert len(requests) == 3
    reader.close()
    assert credential.closed


@pytest.mark.parametrize('url',[
    'http://aif-icenter-sbx-eus2.services.ai.azure.com/api/projects/aifproj-icenter-sbx',
    ENDPOINT+'/', ENDPOINT+'?api-version=preview', ENDPOINT+'#x',
    ENDPOINT.replace('services.ai.azure.com','services.ai.azure.com.evil.test'),
    ENDPOINT.replace('https://','https://user@'),
    ENDPOINT.replace('services.ai.azure.com','services.ai.azure.com:443'),
    ENDPOINT.replace('aifproj-icenter-sbx','../another-project'), None,
])
def test_endpoint_cannot_escape_pinned_project(url):
    with pytest.raises(m.NativeReceiptUnavailable): pin(project_endpoint=url)


@pytest.mark.parametrize('field,value',[
    ('execution_response_id','resp-pause'), ('execution_response_id','../secrets'),
    ('approval_request_id','x?y'), ('server_label','x/y'), ('tool_name','group_list\n'),
    ('identity',None), ('expected_arguments_json',b'{"a":1,"a":2}'),
    ('expected_arguments_json',b'{"a":1.0000000000000001}'),
    ('expected_arguments_json',b'[]'),
])
def test_invalid_governor_pins_are_rejected_before_io(field,value):
    with pytest.raises((m.NativeReceiptUnavailable, ValueError)):
        pin(**{field:value})


@pytest.mark.parametrize('index,path,value',[
    (0,('id',),'resp-other'), (0,('status',),'in_progress'),
    (0,('output',0,'id'),'mcpr-other'),
    (0,('output',0,'arguments'),'{"subscription":"other"}'),
    (1,('id',),'resp-other'), (1,('previous_response_id',),'resp-other'),
    (1,('output',0,'approval_request_id'),'mcpr-other'),
    (1,('output',0,'server_label'),'other-server'),
    (1,('output',0,'name'),'vm_start'),
    (1,('output',0,'arguments'),'{"subscription":"other"}'),
    (1,('output',0,'arguments'),'{"subscription":"sandbox","subscription":"sandbox"}'),
    (1,('output',0,'status'),'failed'),
    (1,('output',0,'error'),{'message':'private failure'}),
    (1,('output',0,'output'),None),
    (2,('has_more',),True), (2,('has_more',),0),
    (2,('data',0,'approval_request_id'),'mcpr-other'),
    (2,('data',0,'approve'),False), (2,('data',0,'approve'),1),
])
def test_native_mismatches_and_denials_cannot_be_accepted(index,path,value):
    data = replies(); target = data[index]
    for key in path[:-1]: target = target[key]
    target[path[-1]] = value
    reader, requests, _ = source(data)
    with pytest.raises(m.NativeReceiptUnavailable): reader.read_once()
    count = len(requests)
    with pytest.raises(m.NativeReceiptUnavailable, match='ALREADY_CONSUMED'): reader.read_once()
    assert len(requests) == count


@pytest.mark.parametrize('index,field',[(0,'output'),(1,'output'),(2,'data')])
def test_duplicate_items_are_not_silently_selected(index,field):
    data = replies()
    data[index][field].append(copy.deepcopy(data[index][field][0]))
    reader, _, _ = source(data)
    with pytest.raises(m.NativeReceiptUnavailable): reader.read_once()


def test_two_distinct_native_calls_are_rejected():
    data=replies(); other=copy.deepcopy(data[1]['output'][0]);other['id']='mcpt-002'
    data[1]['output'].append(other)
    reader,_,_=source(data)
    with pytest.raises(m.NativeReceiptUnavailable,match='EXPECTED_ONE_MCP_CALL'):reader.read_once()


def test_input_call_or_message_does_not_replace_native_output():
    data = replies()
    data[2]['data'].append(data[1]['output'][0])
    data[1]['output']=[dict(id='msg-001',type='message',content=[{'text':'mcp_call approved'}])]
    reader, _, _ = source(data)
    with pytest.raises(m.NativeReceiptUnavailable,match='EXPECTED_ONE_MCP_CALL'): reader.read_once()


def test_call_observed_at_approval_pause_is_not_accepted_as_pause():
    data = replies();data[0]['output'].append(data[1]['output'][0])
    reader, _, _ = source(data)
    with pytest.raises(m.NativeReceiptUnavailable,match='CALL_PRESENT_AT_APPROVAL_PAUSE'):reader.read_once()


def test_conversation_continuation_still_requires_native_input_decision():
    data=replies();data[1]['previous_response_id']=None
    reader,requests,_=source(data)
    assert reader.read_once().approval_request_id=='mcpr-001'
    assert len(requests)==3
    data[2]['data']=[]
    reader,_,_=source(data)
    with pytest.raises(m.NativeReceiptUnavailable,match='EXPECTED_ONE_MCP_APPROVAL_RESPONSE'):reader.read_once()


@pytest.mark.parametrize('status',[301,302,307,308,401,403,404,429,500])
def test_http_failures_do_not_redirect_or_retry(status):
    reader,requests,_=source(status=status)
    with pytest.raises(m.NativeReceiptUnavailable,match='HTTP_STATUS'):reader.read_once()
    assert len(requests)==1


@pytest.mark.parametrize('index',[0,1,2])
def test_transport_failure_is_redacted_and_attempt_consumed(index):
    reader,requests,_=source(fail_at=index)
    with pytest.raises(m.NativeReceiptUnavailable) as error:reader.read_once()
    assert str(error.value)=='PROVIDER_READBACK_UNAVAILABLE_NO_RETRY'
    with pytest.raises(m.NativeReceiptUnavailable,match='ALREADY_CONSUMED'):reader.read_once()
    assert len(requests)==index+1


@pytest.mark.parametrize('raw',[b'{"id":"resp-pause","id":"resp-pause"}',b'{"x":NaN}',b'[]',b'bad-json',b'x'*(m._LIMIT+1)],
                         ids=['duplicate-json-key','nonfinite-json-number','json-array','invalid-json','over-limit-json'])
def test_invalid_or_oversized_provider_json_is_rejected(raw):
    data=replies();data[0]=raw
    reader,_,_=source(data)
    with pytest.raises(m.NativeReceiptUnavailable):reader.read_once()


@pytest.mark.parametrize('token',['','secret\r\nX-Header: injected','secret\x00','x'*65537],
                         ids=['empty-token','crlf-token','nul-token','over-limit-token'])
def test_invalid_token_never_reaches_http(token):
    reader,requests,_=source(token=token)
    with pytest.raises(m.NativeReceiptUnavailable,match='INVALID_ACCESS_TOKEN'):reader.read_once()
    assert requests==[]


def test_factory_has_explicit_identity_no_network_retry_proxy_or_redirect(monkeypatch):
    calls=[]
    monkeypatch.setattr(m,'ManagedIdentityCredential',lambda **kw:calls.append(('credential',kw)) or Credential())
    monkeypatch.setattr(m.httpx,'HTTPTransport',lambda **kw:calls.append(('transport',kw)) or object())
    class Client:
        def __init__(self,**kw):calls.append(('client',kw))
        def close(self):pass
    monkeypatch.setattr(m.httpx,'Client',Client)
    r=m.build_managed_identity_native_receipt_source(pin());r.close()
    assert calls[0]==('credential',{'retry_total':0,'client_id':IDENTITY.client_id})
    assert calls[1]==('transport',{'retries':0})
    assert calls[2][1]['trust_env'] is False
    assert calls[2][1]['follow_redirects'] is False
    assert calls[2][1]['timeout']==20.0
