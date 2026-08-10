from __future__ import annotations

from copy import (
    deepcopy,
)

from collections.abc import (
    Mapping,
)

from enum import Enum

from typing import (
    Any,
    Self,
)

from pydantic import (
    BaseModel,
    ConfigDict,
)

from src.runtime.procedure.models import (
    ResolvedParameter,
)


class FrozenList(list):
    """
    Lista compatible con list para preservar los
    contratos existentes, pero sin operaciones
    mutables.

    También congela recursivamente sus valores.
    """

    @staticmethod
    def _blocked(
        *args,
        **kwargs,
    ):
        raise TypeError(
            "La colección pertenece a un "
            "snapshot inmutable."
        )

    __setitem__ = _blocked
    __delitem__ = _blocked

    append = _blocked
    clear = _blocked
    extend = _blocked
    insert = _blocked
    pop = _blocked
    remove = _blocked
    reverse = _blocked
    sort = _blocked

    __iadd__ = _blocked
    __imul__ = _blocked

    def __copy__(
        self,
    ):
        """
        Crea otra colección frozen sin utilizar
        las operaciones mutables bloqueadas.
        """

        return type(self)(
            list(self)
        )

    def __deepcopy__(
        self,
        memo,
    ):
        """
        deepcopy debe preservar la inmutabilidad
        y copiar profundamente el contenido.
        """

        existing = memo.get(
            id(self)
        )

        if existing is not None:
            return existing

        copied = type(self)(
            deepcopy(
                list(self),
                memo,
            )
        )

        memo[
            id(self)
        ] = copied

        return copied

    def __reduce_ex__(
        self,
        protocol,
    ):
        """
        Reconstrucción pickle explícita.

        Evita que pickle intente reconstruir esta
        lista mediante append/extend, operaciones
        que están bloqueadas deliberadamente.
        """

        return (
            type(self),
            (
                list(self),
            ),
        )


class FrozenDict(dict):
    """
    Dict compatible con dict para preservar los
    contratos existentes, pero sin operaciones
    mutables.
    """

    @staticmethod
    def _blocked(
        *args,
        **kwargs,
    ):
        raise TypeError(
            "El mapping pertenece a un "
            "snapshot inmutable."
        )

    __setitem__ = _blocked
    __delitem__ = _blocked

    clear = _blocked
    pop = _blocked
    popitem = _blocked
    setdefault = _blocked
    update = _blocked

    __ior__ = _blocked

    def __copy__(
        self,
    ):
        """
        Crea otro mapping frozen.
        """

        return type(self)(
            dict(self)
        )

    def __deepcopy__(
        self,
        memo,
    ):
        """
        Copia profundamente claves/valores sin
        utilizar update/__setitem__ bloqueados.
        """

        existing = memo.get(
            id(self)
        )

        if existing is not None:
            return existing

        copied = type(self)(
            deepcopy(
                dict(self),
                memo,
            )
        )

        memo[
            id(self)
        ] = copied

        return copied

    def __reduce_ex__(
        self,
        protocol,
    ):
        """
        Reconstrucción pickle explícita.

        Evita que pickle necesite utilizar
        __setitem__/update durante la restauración.
        """

        return (
            type(self),
            (
                dict(self),
            ),
        )


def freeze_payload(
    value: Any,
) -> Any:
    """
    Convierte recursivamente payloads de evidencia
    en estructuras inmutables.

    La función actúa sobre evidencia/auditoría;
    nunca sobre los argumentos usados para ejecutar
    una herramienta.

    Tipos provider-specific no representables de
    forma estable se conservan como texto.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
            bytes,
        ),
    ):
        return value

    if isinstance(
        value,
        Enum,
    ):
        return freeze_payload(
            value.value
        )

    if isinstance(
        value,
        BaseModel,
    ):
        return freeze_payload(
            value.model_dump(
                mode="python"
            )
        )

    if isinstance(
        value,
        Mapping,
    ):
        return FrozenDict(
            {
                key:
                    freeze_payload(
                        item
                    )
                for key, item
                in value.items()
            }
        )

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        return FrozenList(
            [
                freeze_payload(
                    item
                )
                for item
                in value
            ]
        )

    if isinstance(
        value,
        (
            set,
            frozenset,
        ),
    ):
        return FrozenList(
            [
                freeze_payload(
                    item
                )
                for item
                in sorted(
                    value,
                    key=repr,
                )
            ]
        )

    to_dict = getattr(
        value,
        "to_dict",
        None,
    )

    if callable(
        to_dict
    ):
        try:
            return freeze_payload(
                to_dict()
            )
        except Exception:
            pass

    return str(
        value
    )


def freeze_list(
    value,
) -> FrozenList:
    """
    Congela una colección ya validada por Pydantic
    sin transformar sus elementos de modelo.
    """

    if value is None:
        return FrozenList()

    return FrozenList(
        list(
            value
        )
    )


class ImmutableSnapshotModel(
    BaseModel
):
    """
    Modelo base para evidencia inmutable.

    frozen bloquea asignaciones de atributos.
    FrozenList/FrozenDict cierran la mutación
    profunda de colecciones.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    def model_copy(
        self,
        *,
        update: Mapping[
            str,
            Any,
        ] | None = None,
        deep: bool = False,
    ) -> Self:
        if update:
            raise TypeError(
                f"{type(self).__name__} es un "
                "snapshot inmutable y no permite "
                "model_copy(update=...)."
            )

        return super().model_copy(
            update=None,
            deep=deep,
        )


class FrozenResolvedParameter(
    ResolvedParameter
):
    """
    Snapshot inmutable de name/value/source.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )

    def model_copy(
        self,
        *,
        update: Mapping[
            str,
            Any,
        ] | None = None,
        deep: bool = False,
    ) -> Self:
        if update:
            raise TypeError(
                "FrozenResolvedParameter es un "
                "snapshot inmutable."
            )

        return super().model_copy(
            update=None,
            deep=deep,
        )
