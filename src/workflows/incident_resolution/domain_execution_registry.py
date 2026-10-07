from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from .domain_execution_bindings import DomainExecutionBindings
from .domain_execution_path import DomainExecutionPath


class DomainExecutionRegistrationError(ValueError):
    """La declaracion de un dominio no satisface el contrato exacto."""


class DomainExecutionRegistryError(ValueError):
    """El registro de dominios no satisface el contrato exacto."""


@dataclass(frozen=True)
class DomainExecutionRegistration:
    """Asocia un dominio exacto con un tramo de ejecucion ya declarado.

    El registro no concede authority operacional, no instala capabilities,
    no construye routing y no ejecuta el tramo.
    """

    operation_domain: str
    execution_path: DomainExecutionPath

    def __post_init__(self) -> None:
        if (
            not isinstance(self.operation_domain, str)
            or not self.operation_domain
            or self.operation_domain != self.operation_domain.strip()
        ):
            raise DomainExecutionRegistrationError(
                "operation_domain debe ser string no vacio sin espacios exteriores."
            )

        if not isinstance(self.execution_path, DomainExecutionPath):
            raise DomainExecutionRegistrationError(
                "execution_path debe ser DomainExecutionPath."
            )

        if (
            self.execution_path.execution_binding.operation_domain
            != self.operation_domain
        ):
            raise DomainExecutionRegistrationError(
                "operation_domain no coincide exactamente con el binding del path."
            )

        self.execution_path.validate()


@dataclass(frozen=True, init=False)
class DomainExecutionRegistry:
    """Snapshot exacto de dominios construidos y sus paths declarados.

    Conserva referencias; no clona executors, no registra capabilities,
    no construye WorkflowBuilder/Case y no hace dispatch.
    """

    registrations: tuple[DomainExecutionRegistration, ...]
    _by_domain: Mapping[str, DomainExecutionRegistration] = field(
        repr=False,
        compare=False,
    )
    _execution_bindings: DomainExecutionBindings = field(
        repr=False,
        compare=False,
    )

    def __init__(
        self,
        *,
        registrations: Iterable[DomainExecutionRegistration],
    ) -> None:
        try:
            snapshot = tuple(registrations)
        except TypeError as exc:
            raise DomainExecutionRegistryError(
                "registrations debe ser iterable de DomainExecutionRegistration."
            ) from exc

        by_domain: dict[str, DomainExecutionRegistration] = {}
        bindings = []

        for registration in snapshot:
            if not isinstance(registration, DomainExecutionRegistration):
                raise DomainExecutionRegistryError(
                    "Cada miembro debe ser DomainExecutionRegistration."
                )

            domain = registration.operation_domain
            if domain in by_domain:
                raise DomainExecutionRegistryError(
                    "operation_domain duplicado en DomainExecutionRegistry."
                )

            registration.execution_path.validate()
            by_domain[domain] = registration
            bindings.append(
                registration.execution_path.execution_binding
            )

        selector = DomainExecutionBindings(
            bindings=tuple(bindings),
        )

        object.__setattr__(self, "registrations", snapshot)
        object.__setattr__(
            self,
            "_by_domain",
            MappingProxyType(by_domain),
        )
        object.__setattr__(
            self,
            "_execution_bindings",
            selector,
        )

    @staticmethod
    def _validate_lookup_domain(operation_domain: object) -> str:
        if (
            not isinstance(operation_domain, str)
            or not operation_domain
            or operation_domain != operation_domain.strip()
        ):
            raise DomainExecutionRegistryError(
                "operation_domain debe ser string no vacio sin espacios exteriores."
            )
        return operation_domain

    def get(
        self,
        operation_domain: str,
    ) -> DomainExecutionRegistration:
        key = self._validate_lookup_domain(operation_domain)
        registration = self._by_domain.get(key)
        if registration is None:
            raise DomainExecutionRegistryError(
                "operation_domain no registrado exactamente."
            )

        registration.execution_path.validate()
        return registration

    @property
    def execution_paths(self) -> tuple[DomainExecutionPath, ...]:
        paths: list[DomainExecutionPath] = []
        for registration in self.registrations:
            registration.execution_path.validate()
            paths.append(registration.execution_path)
        return tuple(paths)

    @property
    def execution_bindings(self) -> DomainExecutionBindings:
        for registration in self.registrations:
            registration.execution_path.validate()
        return self._execution_bindings
