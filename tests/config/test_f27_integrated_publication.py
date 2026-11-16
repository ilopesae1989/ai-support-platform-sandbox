import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from src.config.foundry_capability_bindings import build_capability_foundry_agent_binding_registry, RESOURCE_GROUP_LIST_ISOLATED_PROFILE, SANDBOX_PROJECT_ENDPOINT
from src.config.procedure_configuration import build_procedure_configuration
from src.workflows.incident_resolution.executors.azure_operations import AzureOperationsExecutor
from src.workflows.incident_resolution.azure_read_tool_authority import build_default_azure_read_tool_authority_registry
from tests.test_production_capability_foundry_agent_wiring import rig

def read_env(version='3'):
    # Synthetic explicit publication value; no assertion that 3 is the live version.
    return {'FOUNDRY_PROJECT_ENDPOINT':SANDBOX_PROJECT_ENDPOINT,
            'FOUNDRY_CAPABILITY_BINDING_PROFILE':RESOURCE_GROUP_LIST_ISOLATED_PROFILE,
            'FOUNDRY_RG_LIST_AGENT_VERSION':version}

def test_read_selector_and_approval_authority_share_publication():
    registry=build_capability_foundry_agent_binding_registry(read_env())
    executor=AzureOperationsExecutor(agents=SimpleNamespace(),capability_foundry_agent_binding_registry=registry)
    authority=executor._azure_read_tool_authority_registry.get('azure.resource_group.list')
    binding=registry.get('azure.resource_group.list')
    assert authority is binding.read_tool_authority
    assert authority.server_label=='azure-mcp-rglist-read'
    assert binding.resolve(capability=binding.capability,read_tool_authority=authority).version=='3'
    assert binding.require_approval=='always'

@pytest.mark.parametrize('version',[None,'','1','2','latest','@latest','03',3,'3 '])
def test_read_rejects_unknown_or_excluded_publication(version):
    with pytest.raises(ValueError):build_capability_foundry_agent_binding_registry(read_env(version))

def test_explicit_independent_authority_does_not_get_silently_overwritten():
    registry=build_capability_foundry_agent_binding_registry(read_env())
    explicit=build_default_azure_read_tool_authority_registry()
    executor=AzureOperationsExecutor(agents=SimpleNamespace(),azure_read_tool_authority_registry=explicit,capability_foundry_agent_binding_registry=registry)
    assert executor._azure_read_tool_authority_registry is explicit
    binding=registry.get('azure.resource_group.list')
    with pytest.raises(ValueError):binding.resolve(capability=binding.capability,read_tool_authority=explicit.get('azure.resource_group.list'))

def bundle(tmp_path, approved=False):
    root=Path(__file__).resolve().parents[2]/'src/workflows/incident_resolution'
    catalog=json.loads((root/'procedure_catalog.v1.json').read_text())
    catalog['procedures'].append({'procedure_id':'AI-SUPPORT-SBX-AZ-RG-LIST-001','procedure_version':'1.0','procedure_name':'Inventario gobernado de grupos de recursos Azure','lifecycle':'published','step_ids':['1']})
    bindings=json.loads((root/'procedure_capability_bindings.v1.json').read_text())
    bindings['bindings'].append({'procedure_id':'AI-SUPPORT-SBX-AZ-RG-LIST-001','procedure_version':'1.0','step_id':'1','capability_id':'azure.resource_group.list','applicability':{'allowed_environments':['sandbox'],'allowed_incident_origins':['observed']}})
    governance={'schema_version':'1.0','procedures':[{'procedure_id':'AI-SUPPORT-SBX-AZ-RG-LIST-001','procedure_version':'1.0','owner':'synthetic-test-owner','governance_approval_status':'approved' if approved else 'pending','governance_approval_reference':'synthetic-test-approval' if approved else None,'compatible_previous_versions':[],'rollback_version':None}]}
    manifest={'schema_version':'1.0','files':{}}
    for kind, payload in [('catalog',catalog),('bindings',bindings),('governance',governance)]:
        path=tmp_path/(kind+'.json');path.write_text(json.dumps(payload))
        manifest['files'][kind]={'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    path=tmp_path/'manifest.json';path.write_text(json.dumps(manifest))
    return {'PROCEDURE_CONFIGURATION_MANIFEST':str(path),'PROCEDURE_CONFIGURATION_SHA256':hashlib.sha256(path.read_bytes()).hexdigest()}

def test_pending_governance_stays_blocked_and_approved_fixture_admits(tmp_path):
    env=bundle(tmp_path);cfg=build_procedure_configuration(env)
    kwargs=dict(procedure_id='AI-SUPPORT-SBX-AZ-RG-LIST-001',procedure_version='1.0',procedure_name='Inventario gobernado de grupos de recursos Azure')
    with pytest.raises(ValueError):cfg.admission.admit(**kwargs)
    cfg=build_procedure_configuration(bundle(tmp_path,approved=True))
    assert cfg.admission.admit(**kwargs).source=='catalog'

def test_modified_bundle_is_rejected_before_provider_construction(tmp_path,rig):
    env=bundle(tmp_path);(tmp_path/'catalog.json').write_text('{}')
    rig.environment.update(env)
    with pytest.raises(ValueError,match='digest'):rig.invoke('application')
    assert rig.effects==[]

def test_procedure_bundle_reaches_human_and_recovery_workflow_factory(tmp_path,rig,monkeypatch):
    rig.environment.update(bundle(tmp_path));captures=[]
    def leaf(**kwargs):captures.append(kwargs);return object()
    monkeypatch.setattr(rig.base,'build_incident_resolution_workflow',leaf)
    boot=rig.invoke('application')
    boot.dependencies.workflow_factory()
    boot.continuation_worker.dependencies.workflow_factory()
    assert len(captures)==2
    for key in ('governed_procedure_admission_policy','procedure_capability_registry'):
        assert captures[0][key] is captures[1][key]

@pytest.mark.parametrize('env',[{'PROCEDURE_CONFIGURATION_MANIFEST':'x'},{'PROCEDURE_CONFIGURATION_SHA256':'0'*64}])
def test_partial_configuration_never_falls_back(env):
    with pytest.raises(ValueError):build_procedure_configuration(env)

def test_absent_bundle_keeps_existing_default():
    assert build_procedure_configuration({}) is None

def test_recovered_op66_configuration_admits_original_read_and_preserves_vm_catalog():
    root=Path(__file__).resolve().parents[2]
    directory=root/'src/config/f27_rg_list'
    manifest=directory/'manifest.json'
    cfg=build_procedure_configuration({
        'PROCEDURE_CONFIGURATION_MANIFEST':str(manifest),
        'PROCEDURE_CONFIGURATION_SHA256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
    })
    result=cfg.admission.admit(
        procedure_id='NTTSY-SBX-AZ-RG-LIST-001',procedure_version='1.0',
        procedure_name='Listado gobernado de grupos de recursos de una suscripción Azure',
    )
    assert result.source=='catalog'
    original=json.loads((root/'src/workflows/incident_resolution/procedure_catalog.v1.json').read_text())
    merged=json.loads((directory/'catalog.json').read_text())
    assert merged['procedures'][:len(original['procedures'])]==original['procedures']
    governance=json.loads((directory/'governance.json').read_text())['procedures']
    assert len(governance)==1
    assert governance[0]['owner']=='icenter-microsoft'
    assert governance[0]['governance_approval_reference']=='F27-OP66R-GOV-NTTSY-SBX-AZ-RG-LIST-001-1.0-20261023'
