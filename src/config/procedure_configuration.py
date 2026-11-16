"""Load a hash-pinned procedure bundle before constructing provider clients.

This wires existing catalog/governance/capability contracts into the served core.
It neither synthesizes governance approval nor enables a cloud deployment.
"""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from src.workflows.incident_resolution.capability_registry import build_default_capability_registry
from src.workflows.incident_resolution.procedure_catalog import load_procedure_catalog
from src.workflows.incident_resolution.procedure_governance import load_procedure_governance, ProcedureGovernanceApprovalPolicy
from src.workflows.incident_resolution.procedure_admission import ProcedureAdmissionPolicy, load_procedure_compatibility, DEFAULT_PROCEDURE_COMPATIBILITY_PATH
from src.workflows.incident_resolution.governed_procedure_admission import GovernedProcedureAdmissionPolicy
from src.workflows.incident_resolution.procedure_capability_registry import load_procedure_capability_bindings

PATH_KEY = 'PROCEDURE_CONFIGURATION_MANIFEST'
HASH_KEY = 'PROCEDURE_CONFIGURATION_SHA256'

@dataclass(frozen=True)
class ProcedureConfiguration:
    admission: GovernedProcedureAdmissionPolicy
    capabilities: object

    def workflow_options(self):
        return {'governed_procedure_admission_policy': self.admission,
                'procedure_capability_registry': self.capabilities}

def build_procedure_configuration(environment):
    if PATH_KEY not in environment and HASH_KEY not in environment:
        return None
    path, digest = environment.get(PATH_KEY), environment.get(HASH_KEY)
    if (type(path) is not str or not path or path != path.strip()
            or type(digest) is not str or not re.fullmatch('[0-9a-f]{64}', digest)):
        raise ValueError('Procedure configuration requires an explicit path and SHA256.')
    manifest = Path(path)
    raw = manifest.read_bytes()
    if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('Procedure manifest digest mismatch.')
    payload=json.loads(raw)
    if set(payload)!={'schema_version','files'} or payload['schema_version']!='1.0' or set(payload['files'])!={'catalog','governance','bindings'}:
        raise ValueError('Procedure manifest schema mismatch.')
    paths={}
    for kind, item in payload['files'].items():
        if (type(item) is not dict or set(item)!={'name','sha256'}
                or type(item['name']) is not str or not re.fullmatch(r'[A-Za-z0-9_-]+\.json',item['name'])
                or type(item['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',item['sha256'])):
            raise ValueError('Invalid procedure configuration file reference.')
        target=manifest.parent/item['name']
        if target.is_symlink():raise ValueError('Procedure configuration symlinks are excluded.')
        data=target.read_bytes()
        if len(data)>1048576 or hashlib.sha256(data).hexdigest()!=item['sha256']:
            raise ValueError('Procedure configuration file digest mismatch.')
        paths[kind]=target
    catalog=load_procedure_catalog(paths['catalog'])
    governance=load_procedure_governance(paths['governance'],catalog=catalog)
    capabilities=load_procedure_capability_bindings(paths['bindings'],catalog=catalog,capability_registry=build_default_capability_registry())
    admission=ProcedureAdmissionPolicy(catalog=catalog,legacy_compatibility=load_procedure_compatibility(DEFAULT_PROCEDURE_COMPATIBILITY_PATH))
    return ProcedureConfiguration(GovernedProcedureAdmissionPolicy(admission_policy=admission,
        governance_policy=ProcedureGovernanceApprovalPolicy(registry=governance)),capabilities)
