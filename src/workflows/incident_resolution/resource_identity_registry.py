from __future__ import annotations

from collections.abc import (
    Iterable,
)

from .azure_resource_identity import (
    AzureSubscriptionIdentityResolver,
    AzureVirtualMachineIdentityResolver,
)

from .resource_identity import (
    ResourceIdentityResolver,
)


class ResourceIdentityRegistryError(
    ValueError
):
    """
    Error determinista del registro de resolvers
    de identidad operacional.
    """

    pass


class ResourceIdentityResolverNotFoundError(
    ResourceIdentityRegistryError
):
    """
    No existe un resolver autorizado para la
    combinación exacta domain + resource_type.
    """

    pass


class DuplicateResourceIdentityResolverError(
    ResourceIdentityRegistryError
):
    """
    Existen dos resolvers intentando adquirir
    autoridad sobre la misma identidad lógica.
    """

    pass


class ResourceIdentityRegistry:
    """
    Registro determinista de resolvers de identidad.

    La clave de selección es exactamente:

        (
            operation_domain,
            resource_type,
        )

    No existe:

    - fuzzy matching;
    - lower()/upper();
    - aliases;
    - inferencia;
    - fallback a otro resolver;
    - selección mediante LLM.

    Registrar un resolver NO autoriza ninguna
    operación sobre el recurso.

    Sólo establece cómo construir su identidad
    operacional canónica.
    """

    def __init__(
        self,
        *,
        resolvers: Iterable[
            ResourceIdentityResolver
        ],
    ) -> None:

        self._resolvers: dict[
            tuple[str, str],
            ResourceIdentityResolver,
        ] = {}

        for resolver in resolvers:
            self.register(
                resolver
            )

    def register(
        self,
        resolver: ResourceIdentityResolver,
    ) -> None:
        """
        Registra un resolver exactamente una vez
        para domain + resource_type.
        """

        key = (
            resolver.operation_domain,
            resolver.resource_type,
        )

        if key in self._resolvers:
            raise (
                DuplicateResourceIdentityResolverError(
                    "Ya existe un resolver de "
                    "identidad registrado para "
                    "operation_domain="
                    f"{resolver.operation_domain!r}, "
                    "resource_type="
                    f"{resolver.resource_type!r}."
                )
            )

        self._resolvers[
            key
        ] = resolver

    def get_resolver(
        self,
        *,
        operation_domain: str,
        resource_type: str,
    ) -> ResourceIdentityResolver:
        """
        Obtiene el resolver autorizado para la
        combinación EXACTA solicitada.

        Si no existe, falla cerrado.
        """

        key = (
            operation_domain,
            resource_type,
        )

        resolver = (
            self._resolvers.get(
                key
            )
        )

        if resolver is None:
            raise (
                ResourceIdentityResolverNotFoundError(
                    "No existe un resolver de "
                    "identidad registrado para "
                    "operation_domain="
                    f"{operation_domain!r}, "
                    "resource_type="
                    f"{resource_type!r}."
                )
            )

        return resolver

    def contains(
        self,
        *,
        operation_domain: str,
        resource_type: str,
    ) -> bool:
        """
        Indica si existe un resolver registrado
        para la combinación exacta.
        """

        return (
            (
                operation_domain,
                resource_type,
            )
            in self._resolvers
        )

    def count(
        self,
    ) -> int:
        return len(
            self._resolvers
        )


def build_default_resource_identity_registry(
) -> ResourceIdentityRegistry:
    """
    Construye el catálogo de identidades soportadas
    actualmente por la plataforma.

    Añadir aquí un resolver significa:

        "la plataforma sabe identificar este tipo
         de recurso"

    NO significa:

        "la plataforma puede modificarlo".

    La autorización operacional pertenece al
    Capability Catalog / Policy Registry.
    """

    return ResourceIdentityRegistry(
        resolvers=[
            AzureSubscriptionIdentityResolver(),
            AzureVirtualMachineIdentityResolver(),
        ]
    )