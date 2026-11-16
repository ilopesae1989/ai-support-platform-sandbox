from __future__ import annotations

import ast
import importlib
import inspect
import io
import textwrap
import tokenize

import pytest

from src.channels.teams.bootstrap import (
    TeamsManagedIdentityAppSettings,
)

from src.channels.teams.production_settings import (
    TeamsProductionHostSettings,
)

from src.persistence.azure_sql.connection_provider import (
    AzureSqlManagedIdentitySettings,
)

from src.workflows.incident_resolution.azure_vm_observation_settings import (
    AzureVmObservationManagedIdentitySettings,
)


TARGET_MODULE = (
    "src.channels.teams.production_composition"
)


TEAMS_USER_ASSIGNED_CLIENT_ID = (
    "11111111-1111-4111-8111-111111111111"
)

SQL_USER_ASSIGNED_CLIENT_ID = (
    "22222222-2222-4222-8222-222222222222"
)

VM_USER_ASSIGNED_CLIENT_ID = (
    "a3333333-3333-4333-8333-333333333333"
)

GRAPH_MEMBERSHIP_CHECKER = object()


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def _environment():
    return {
        "CLIENT_ID": (
            "teams-app-client-id"
        ),
        "MANAGED_IDENTITY_CLIENT_ID": (
            "system"
        ),
        "TENANT_ID": (
            "bot-tenant-id"
        ),
        "TEAMS_CHANNEL_TENANT_ID": (
            "channel-tenant-id"
        ),
        "TEAMS_AUTHORIZED_TECHNICIANS_GROUP_OBJECT_ID": (
            "55555555-5555-4555-8555-555555555555"
        ),
        "AZURE_SQL_SERVER": (
            "ai-support-platform-sbx"
            ".database.windows.net"
        ),
        "AZURE_SQL_DATABASE": (
            "ai_support_platform_sbx"
        ),
    }


def _host_settings():
    return TeamsProductionHostSettings(
        app_settings=(
            TeamsManagedIdentityAppSettings(
                client_id=(
                    "teams-app-client-id"
                ),
                managed_identity_client_id=(
                    "system"
                ),
                bot_tenant_id=(
                    "bot-tenant-id"
                ),
                teams_channel_tenant_id=(
                    "channel-tenant-id"
                ),
                authorized_technicians_group_object_id=(
                    "55555555-5555-4555-8555-555555555555"
                ),
            )
        ),
        azure_sql_settings=(
            AzureSqlManagedIdentitySettings(
                server=(
                    "ai-support-platform-sbx"
                    ".database.windows.net"
                ),
                database=(
                    "ai_support_platform_sbx"
                ),
            )
        ),
    )


def test_production_composition_has_exact_surface():
    module = _module()

    factory = getattr(
        module,
        "build_production_teams_host",
        None,
    )

    assert callable(
        factory
    )

    signature = inspect.signature(
        factory
    )

    assert tuple(
        signature.parameters
    ) == (
        "environment",
    )


def test_production_composition_rejects_unstructured_environment():
    module = _module()

    for invalid_environment in (
        None,
        object(),
        [],
        "KEY=value",
    ):
        with pytest.raises(
            TypeError
        ):
            module.build_production_teams_host(
                invalid_environment
            )


def test_composition_delegates_exact_boundaries(
    monkeypatch,
):
    module = _module()

    environment = (
        _environment()
    )

    host_settings = (
        _host_settings()
    )

    observation_settings = (
        AzureVmObservationManagedIdentitySettings()
    )

    reader = object()
    bootstrap = object()

    calls = []

    def fake_host_settings_builder(
        actual_environment,
    ):
        calls.append(
            (
                "host_settings",
                actual_environment,
            )
        )

        return host_settings

    def fake_graph_builder(
        *,
        managed_identity_client_id,
    ):
        calls.append((
            "graph_membership",
            managed_identity_client_id,
        ))
        return GRAPH_MEMBERSHIP_CHECKER

    def fake_observation_settings_builder(
        actual_environment,
    ):
        calls.append(
            (
                "observation_settings",
                actual_environment,
            )
        )

        return observation_settings

    def fake_reader_builder(
        actual_settings,
    ):
        calls.append(
            (
                "reader",
                actual_settings,
            )
        )

        return reader

    def fake_bootstrap_builder(
        app_settings,
        azure_sql_settings,
        *,
        membership_checker,
        azure_vm_power_state_reader,
    ):
        calls.append(
            (
                "bootstrap",
                app_settings,
                azure_sql_settings,
                membership_checker,
                azure_vm_power_state_reader,
            )
        )

        return bootstrap

    monkeypatch.setattr(
        module,
        "build_production_teams_host_settings",
        fake_host_settings_builder,
    )

    monkeypatch.setattr(
        module,
        "build_managed_identity_graph_membership_client",
        fake_graph_builder,
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_settings",
        fake_observation_settings_builder,
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_reader",
        fake_reader_builder,
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_hitl_app",
        fake_bootstrap_builder,
    )

    actual = (
        module
        .build_production_teams_host(
            environment
        )
    )

    assert actual is bootstrap

    assert calls == [
        (
            "host_settings",
            environment,
        ),
        (
            "graph_membership",
            "system",
        ),
        (
            "observation_settings",
            environment,
        ),
        (
            "reader",
            observation_settings,
        ),
        (
            "bootstrap",
            host_settings.app_settings,
            host_settings.azure_sql_settings,
            GRAPH_MEMBERSHIP_CHECKER,
            reader,
        ),
    ]


def test_three_managed_identity_boundaries_remain_independent(
    monkeypatch,
):
    module = _module()

    environment = (
        _environment()
    )

    environment[
        "MANAGED_IDENTITY_CLIENT_ID"
    ] = (
        TEAMS_USER_ASSIGNED_CLIENT_ID
    )

    environment[
        "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID"
    ] = (
        SQL_USER_ASSIGNED_CLIENT_ID
    )

    environment[
        "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID"
    ] = (
        VM_USER_ASSIGNED_CLIENT_ID
    )

    captured = {}

    reader = object()
    bootstrap = object()

    def fake_graph_builder(
        *,
        managed_identity_client_id,
    ):
        captured["graph_identity"] = (
            managed_identity_client_id
        )
        return GRAPH_MEMBERSHIP_CHECKER

    def fake_reader_builder(
        settings,
    ):
        captured[
            "vm_identity"
        ] = (
            settings
            .managed_identity_client_id
        )

        return reader

    def fake_bootstrap_builder(
        app_settings,
        azure_sql_settings,
        *,
        membership_checker,
        azure_vm_power_state_reader,
    ):
        captured[
            "teams_identity"
        ] = (
            app_settings
            .managed_identity_client_id
        )

        captured[
            "sql_identity"
        ] = (
            azure_sql_settings
            .managed_identity_client_id
        )

        captured[
            "graph_checker"
        ] = membership_checker

        captured[
            "reader"
        ] = (
            azure_vm_power_state_reader
        )

        return bootstrap

    monkeypatch.setattr(
        module,
        "build_managed_identity_graph_membership_client",
        fake_graph_builder,
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_reader",
        fake_reader_builder,
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_hitl_app",
        fake_bootstrap_builder,
    )

    actual = (
        module
        .build_production_teams_host(
            environment
        )
    )

    assert actual is bootstrap

    assert captured == {
        "teams_identity": (
            TEAMS_USER_ASSIGNED_CLIENT_ID
        ),
        "graph_identity": (
            TEAMS_USER_ASSIGNED_CLIENT_ID
        ),
        "sql_identity": (
            SQL_USER_ASSIGNED_CLIENT_ID
        ),
        "vm_identity": (
            VM_USER_ASSIGNED_CLIENT_ID
        ),
        "graph_checker": GRAPH_MEMBERSHIP_CHECKER,
        "reader": reader,
    }


def test_environment_mapping_is_not_mutated(
    monkeypatch,
):
    module = _module()

    environment = (
        _environment()
    )

    before = dict(
        environment
    )

    monkeypatch.setattr(
        module,
        "build_production_teams_hitl_app",
        lambda *args, **kwargs: object(),
    )

    monkeypatch.setattr(
        module,
        "build_managed_identity_graph_membership_client",
        lambda **kwargs: GRAPH_MEMBERSHIP_CHECKER,
    )

    monkeypatch.setattr(
        module,
        "build_azure_vm_observation_reader",
        lambda settings: object(),
    )

    module.build_production_teams_host(
        environment
    )

    assert environment == before


def test_client_secret_policy_is_preserved_end_to_end():
    module = _module()

    environment = (
        _environment()
    )

    environment[
        "CLIENT_SECRET"
    ] = "forbidden"

    with pytest.raises(
        ValueError
    ):
        module.build_production_teams_host(
            environment
        )


def _assert_declarative_foundry_registry(source):
    """Permit the published registry interface, without giving it authority."""
    registry = "CapabilityFoundryAgentBindingRegistry"
    parameter = "capability_foundry_agent_binding_registry"
    factory_name = (
        "build_production_teams_host_with_communication_and_incident_agents"
    )
    delegate = (
        "build_production_teams_hitl_app_with_communication_and_incident_agents"
    )
    tree = ast.parse(source)
    factories = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == factory_name
    ]
    assert len(factories) == 1
    factory = factories[0]
    assert not factory.decorator_list

    imports = [
        node for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == (
            "src.workflows.incident_resolution.capability_foundry_agent_binding"
        )
    ]
    assert len(imports) == 1
    binding_import = imports[0]
    assert binding_import.level == 0
    assert [(alias.name, alias.asname) for alias in binding_import.names] == [
        (registry, None)
    ]

    # Both descriptors are declarative opt-ins. Fix their complete small
    # validation/forwarding contract, retaining rejection of hidden authority.
    contract = ast.parse(
        f"def contract(*, {parameter}: {registry} | None = None, "
        "vm_start_route: GovernedVmStartRoute | None = None, "
        "attestation_publisher=None, "
        "vm_start_binding: VmStartFoundryBinding | None = None, "
        "procedure_configuration: ProcedureConfiguration | None = None):\n"
        "    if vm_start_binding is not None:\n"
        "        if not isinstance(vm_start_binding, VmStartFoundryBinding):\n"
        "            raise TypeError('vm_start_binding must be VmStartFoundryBinding.')\n"
        "        if vm_start_route is not None:\n"
        "            raise ValueError('Specify vm_start_binding or vm_start_route, never both.')\n"
        "    selector_options = {}\n"
        "    if attestation_publisher is not None:\n"
        "        from src.attestation.governor_outbox import GovernorAttestationPublisher\n"
        "        if type(attestation_publisher) is not GovernorAttestationPublisher:\n"
        "            raise TypeError('Explicit governor attestation publisher required')\n"
        "        selector_options['attestation_publisher'] = attestation_publisher\n"
        "    if procedure_configuration is not None:\n"
        "        if not isinstance(procedure_configuration, ProcedureConfiguration):\n"
        "            raise TypeError('procedure_configuration must be ProcedureConfiguration.')\n"
        "        selector_options['procedure_configuration'] = procedure_configuration\n"
        "    if vm_start_binding is not None:\n"
        "        selector_options['vm_start_binding'] = vm_start_binding\n"
        "    if vm_start_route is not None:\n"
        "        if not isinstance(vm_start_route, GovernedVmStartRoute):\n"
        "            raise TypeError('vm_start_route must be GovernedVmStartRoute.')\n"
        "        selector_options['vm_start_route'] = vm_start_route\n"
        f"    if {parameter} is not None:\n"
        f"        if not isinstance({parameter}, {registry}):\n"
        f"            raise TypeError('{parameter} debe ser {registry}.')\n"
        f"        selector_options['{parameter}'] = {parameter}\n"
    ).body[0]
    write_imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
                     and node.module == 'src.workflows.incident_resolution.vm_start_foundry_binding']
    assert len(write_imports) == 1 and write_imports[0].level == 0
    assert [(x.name, x.asname) for x in write_imports[0].names] == [
        ('GovernedVmStartRoute', None), ('VmStartFoundryBinding', None)]
    procedure_imports = [node for node in tree.body if isinstance(node, ast.ImportFrom)
                         and node.module == 'src.config.procedure_configuration']
    assert len(procedure_imports) == 1 and procedure_imports[0].level == 0
    assert [(x.name, x.asname) for x in procedure_imports[0].names] == [('ProcedureConfiguration', None)]
    arguments = []
    for expected in contract.args.kwonlyargs:
        matches = [(a, d) for a, d in zip(factory.args.kwonlyargs, factory.args.kw_defaults)
                   if a.arg == expected.arg]
        assert len(matches) == 1
        argument, default = matches[0]
        assert ast.dump(argument) == ast.dump(expected)
        assert isinstance(default, ast.Constant) and default.value is None
        arguments.append(argument)
    body = factory.body
    if ast.get_docstring(factory) is not None:
        body = body[1:]
    prefix = body[:len(contract.body)]
    assert [ast.dump(node) for node in prefix] == [ast.dump(node) for node in contract.body]

    foundry_regions = (binding_import, write_imports[0], procedure_imports[0], *arguments, *prefix)
    allowed = {node for region in foundry_regions for node in ast.walk(region)}
    returns = [node for node in ast.walk(factory) if isinstance(node, ast.Return)]
    assert len(returns) == 2
    for statement in returns:
        call = statement.value
        assert isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        assert call.func.id == delegate
        forwarding = [
            keyword.value for keyword in call.keywords
            if keyword.arg is None
            and isinstance(keyword.value, ast.Name)
            and keyword.value.id == "selector_options"
        ]
        assert len(forwarding) == 1
        allowed.update((call.func, *forwarding))

    # These local bindings may only import, type-check and forward the registry.
    allowed.add(factory)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == delegate and alias.asname is None:
                    assert node.module == "src.channels.teams.production_bootstrap"
                    assert node.level == 0
                    allowed.add(alias)
    protected = {registry, parameter, "selector_options", factory_name, delegate,
                 "GovernorAttestationPublisher", "attestation_publisher", "VmStartFoundryBinding", "GovernedVmStartRoute", "vm_start_binding", "vm_start_route", "procedure_configuration", "ProcedureConfiguration"}
    for node in ast.walk(tree):
        for field in ("id", "arg", "name", "asname", "rest"):
            value = getattr(node, field, None)
            if isinstance(value, str) and value in protected:
                assert node in allowed, "Registry binding used outside its contract"
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            assert protected.isdisjoint(node.names)

    # Token positions keep comments/strings outside the approved nodes visible.
    lines = source.splitlines()

    def ast_position(position):
        line, column = position
        return line, len(lines[line - 1][:column].encode("utf-8"))

    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if "foundry" not in token.string.lower():
            continue
        assert token.type in (tokenize.NAME, tokenize.STRING)
        start, end = ast_position(token.start), ast_position(token.end)
        assert any(
            (node.lineno, node.col_offset) <= start
            and end <= (node.end_lineno, node.end_col_offset)
            for node in foundry_regions
        ), "Foundry reference outside the declarative registry contract"


def _assert_composition_has_no_hidden_authority(source):
    lowered = source.lower()

    required = (
        "build_production_teams_host_settings",
        "build_managed_identity_graph_membership_client",
        "build_azure_vm_observation_settings",
        "build_azure_vm_observation_reader",
        "build_production_teams_hitl_app",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "os.getenv",
        "os.environ",
        "from_environment",
        "managedidentitycredential(",
        "defaultazurecredential",
        "azureclicredential",
        "build_azure_vm_observation_credential",
        "azuresdkvmpowerstatereader(",
        "get_token(",
        "read_power_state(",
        "computemanagementclient",
        "virtual_machines",
        "instance_view(",
        "build_azure_sql_teams_hitl_persistence",
        "build_teams_hitl_app",
        "mssql_python.connect",
        "asyncio.run",
        ".start(",
        ".run(",
        "client_secret",
        "sqlite",
        "cosmos",
        "servicebus",
        "mcp",
    )

    for fragment in forbidden:
        assert fragment not in lowered

    _assert_declarative_foundry_registry(source)


def test_composition_has_no_hidden_runtime_or_direct_resource_authority():
    source = textwrap.dedent(inspect.getsource(_module()))
    _assert_composition_has_no_hidden_authority(source)


def test_declarative_registry_guard_accepts_formatting_changes():
    source = textwrap.dedent(inspect.getsource(_module()))
    source = source.replace(
        "    selector_options = {}",
        "    # Explicit dependency, with no construction.\n"
        "    selector_options = (\n        {}\n    )",
        1,
    )
    _assert_composition_has_no_hidden_authority(source)


@pytest.mark.parametrize(
    ("before", "after"),
    (
        pytest.param(
            None, "extra = CapabilityFoundryAgentBindingRegistry()",
            id="registry-construction",
        ),
        pytest.param(
            "    if incident_agents is None:",
            "    capability_foundry_agent_binding_registry.get('capability')\n"
            "    if incident_agents is None:",
            id="registry-inspection",
        ),
        pytest.param(
            "    if incident_agents is None:",
            "    selector_options.clear()\n    if incident_agents is None:",
            id="forwarding-diversion",
        ),
        pytest.param(
            "**selector_options,", "**{},", id="missing-forwarding",
        ),
        pytest.param(
            "    CapabilityFoundryAgentBindingRegistry,\n)",
            "    CapabilityFoundryAgentBindingRegistry as Registry,\n)",
            id="registry-import-alias",
        ),
        pytest.param(None, "extra = VmStartFoundryBinding()", id="write-binding-construction"),
        pytest.param(None, "extra = GovernedVmStartRoute()", id="write-route-construction"),
        pytest.param(
            "    if incident_agents is None:",
            "    selector_options['unapproved'] = vm_start_binding\n    if incident_agents is None:",
            id="write-extra-key",
        ),
        pytest.param(
            "    if vm_start_binding is not None:",
            "    if vm_start_binding is None:",
            id="write-inverted-opt-in",
        ),
        pytest.param(None, "extra = ProcedureConfiguration()", id="procedure-construction"),
        pytest.param(
            "    if incident_agents is None:",
            "    procedure_configuration.workflow_options()\n    if incident_agents is None:",
            id="procedure-inspection",
        ),
        pytest.param(
            "    if procedure_configuration is not None:",
            "    if procedure_configuration is None:",
            id="procedure-inverted-opt-in",
        ),
        pytest.param(None, "extra = FoundryClient()", id="provider-construction"),
        pytest.param(
            None, "extra = ManagedIdentityCredential()", id="direct-credential",
        ),
        pytest.param(
            None, "extra = ComputeManagementClient()", id="direct-sdk",
        ),
        pytest.param(
            None, "extra = mssql_python.connect('not-executed')", id="direct-io",
        ),
    ),
)
def test_composition_guard_rejects_authority_or_registry_diversion(before, after):
    source = textwrap.dedent(inspect.getsource(_module()))
    if before is None:
        source += "\n" + after + "\n"
    else:
        assert before in source
        source = source.replace(before, after, 1)
    with pytest.raises(AssertionError):
        _assert_composition_has_no_hidden_authority(source)
