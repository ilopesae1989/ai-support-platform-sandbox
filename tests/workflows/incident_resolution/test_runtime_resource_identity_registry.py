import inspect
from types import SimpleNamespace

import pytest

from src.workflows.incident_resolution.executors.runtime import (
    ProcedureRuntimeExecutor,
)

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)

from src.workflows.incident_resolution.resource_identity import (
    ResolvedResourceIdentity,
    ResourceIdentityResolutionError,
)

from src.workflows.incident_resolution.resource_identity_registry import (
    ResourceIdentityRegistry,
)


class DemoWidgetIdentityResolver:
    """
    Resolver deliberadamente ajeno a Azure.

    Demuestra que Runtime puede trabajar con un
    nuevo resource_type sin modificación de su código.
    """

    operation_domain = (
        "application"
    )

    resource_type = (
        "Contoso.Support/widgets"
    )

    required_parameters = (
        "correlation_id",
    )

    def resolve(
        self,
        context: OperationalContext,
    ) -> ResolvedResourceIdentity:

        return ResolvedResourceIdentity(
            operation_domain=(
                self.operation_domain
            ),

            resource_type=(
                self.resource_type
            ),

            canonical_target_resource=(
                "contoso://widgets/widget-01"
            ),

            required_parameters=(
                self.required_parameters
            ),

            allowed_cognitive_targets=(
                "widget-01",
                "contoso://widgets/widget-01",
            ),
        )


def create_context(
    *,
    target_resource="widget-01",
):
    step = SimpleNamespace(
        operation_domain=(
            "application"
        ),

        target_resource=(
            target_resource
        ),

        required_parameters=[
            "correlation_id",
        ],
    )

    result = SimpleNamespace(
        step=step
    )

    operational = OperationalContext(
        alert_id="ALT-WIDGET-001",

        resource_type=(
            "Contoso.Support/widgets"
        ),

        correlation_id=(
            "corr-widget-001"
        ),
    )

    return SimpleNamespace(
        result=result,
        operational_context=operational,
    )


def create_runtime():
    registry = ResourceIdentityRegistry(
        resolvers=[
            DemoWidgetIdentityResolver(),
        ]
    )

    return ProcedureRuntimeExecutor(
        resource_identity_registry=(
            registry
        )
    )


def test_runtime_uses_injected_generic_identity_resolver():
    runtime = create_runtime()

    target = (
        runtime
        ._resolve_authoritative_target_resource(
            create_context()
        )
    )

    assert (
        target
        == "contoso://widgets/widget-01"
    )


def test_runtime_rejects_cognitive_target_mismatch_generically():
    runtime = create_runtime()

    with pytest.raises(
        ResourceIdentityResolutionError,
        match="target_resource",
    ):
        (
            runtime
            ._resolve_authoritative_target_resource(
                create_context(
                    target_resource=(
                        "widget-attacker"
                    )
                )
            )
        )


def test_runtime_contains_no_azure_vm_identity_logic():
    source = inspect.getsource(
        ProcedureRuntimeExecutor
        ._resolve_authoritative_target_resource
    )

    forbidden_fragments = (
        "virtualMachines",
        "Microsoft.Compute",
        "vm_name",
        "build_azure_vm_resource_id",
        "subscription_id",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source