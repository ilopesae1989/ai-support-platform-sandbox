"""Bounded BlockBlob custody with separate writer/verifier clients.

No SAS, account keys, overwrite, append, delete, policy mutation or cleanup.
Each create is one SDK operation with retries disabled by the factory. A failed
write is uncertain, including ResourceExistsError; recovery is explicitly read-only.
"""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from threading import Lock
from urllib.parse import urlsplit, parse_qsl

from azure.core.pipeline.transport import RequestsTransport

from src.persistence.receipt_custody import sha256

_NAME = re.compile(r"v1/[0-9a-f]{64}/(?:backend|attestor)-[0-9a-f]{64}\.json\Z")


class SinglePutTransport(RequestsTransport):
    """Reject a second wire send to the same object, even an auth-challenge replay.

    The lifetime guard complements storage conditional creation. It is not a
    cross-process ledger; after a process crash recovery must use reconcile().
    """
    def __init__(self, *, account_url, container):
        super().__init__(use_env_settings=False)
        self._prefix = account_url + "/" + container + "/"
        self._sent = set()
        self._lock = Lock()

    def send(self, request, **kwargs):
        parts = urlsplit(request.url)
        target = parts.scheme + "://" + parts.netloc + parts.path
        if (request.method != "PUT" or not target.startswith(self._prefix)
                or not _NAME.fullmatch(target[len(self._prefix):])
                or parts.fragment
                or any(k != "timeout" for k, v in parse_qsl(parts.query))
                or request.headers.get("x-ms-blob-type") != "BlockBlob"
                or request.headers.get("If-None-Match") != "*"):
            raise ValueError("Only conditional single BlockBlob PUT is allowed")
        with self._lock:
            if target in self._sent:
                raise RuntimeError("Write already attempted; reconcile without writes")
            self._sent.add(target)  # Before any transport call, including timeout.
        return super().send(request, **kwargs)


@dataclass(frozen=True)
class LockedContainerPolicy:
    resource_id: str
    etag: str
    retention_days: int
    # AppendBlob-only protection does not weaken BlockBlob immutability.
    # Pin this separately from allowProtectedAppendWritesAll, which must be off.
    allow_protected_append_writes: bool = False

    def __post_init__(self):
        from uuid import UUID
        if not re.fullmatch(
            r"/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/[A-Za-z0-9_.()-]{1,90}"
            r"/providers/Microsoft.Storage/storageAccounts/[a-z0-9]{3,24}"
            r"/blobServices/default/containers/[a-z0-9][a-z0-9-]{1,61}[a-z0-9]"
            r"/immutabilityPolicies/default", self.resource_id):
            raise ValueError("Exact container policy resource ID required")
        UUID(self.resource_id.split("/")[2])
        if (type(self.allow_protected_append_writes) is not bool
                or type(self.retention_days) is not int or not 1 <= self.retention_days <= 146000
                or type(self.etag) is not str or not 1 <= len(self.etag) <= 128
                or any(ord(x) < 32 or ord(x) > 126 for x in self.etag)):
            raise ValueError("Invalid pinned retention policy")

    def verify(self, response):
        if not isinstance(response, Mapping):
            raise ValueError("Policy response missing")
        p = response.get("properties", {})
        if not (response.get("id", "").lower() == self.resource_id.lower()
                and response.get("etag") == self.etag
                and p.get("state") == "Locked"
                and type(p.get("immutabilityPeriodSinceCreationInDays")) is int
                and p["immutabilityPeriodSinceCreationInDays"] == self.retention_days
                and p.get("allowProtectedAppendWrites", False) is self.allow_protected_append_writes
                and p.get("allowProtectedAppendWritesAll", False) is False):
            raise ValueError("Locked closed-object policy differs from pinned policy")


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class AzureBlobReceiptObjects:
    def __init__(self, *, account_url, container, writer, reader, policy_reader,
                 policy: LockedContainerPolicy, retain_until: datetime):
        if not re.fullmatch(r"https://[a-z0-9]{3,24}\.blob\.core\.windows\.net", account_url):
            raise ValueError("Pinned Azure public-cloud Blob endpoint required, no SAS")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", container) or "--" in container:
            raise ValueError("Invalid container")
        expected = account_url.removeprefix("https://").split(".")[0]
        if (f"/storageAccounts/{expected}/blobServices/default/containers/{container}/"
                not in policy.resource_id):
            raise ValueError("Policy target differs from object target")
        if writer is reader:
            raise ValueError("Independent reader client required")
        self._url, self._container = account_url, container
        self._writer, self._reader = writer, reader
        self._policy_reader, self._policy = policy_reader, policy
        self._retain_until = _utc(retain_until)

    @staticmethod
    def _validate(name, data):
        if not _NAME.fullmatch(name) or type(data) is not bytes or not 0 < len(data) <= 65536:
            raise ValueError("Invalid receipt object")
        if not name.endswith("-" + sha256(data) + ".json"):
            raise ValueError("Object name does not commit to complete signed bytes")

    def _check_policy(self):
        self._policy.verify(self._policy_reader())

    def create_and_verify(self, name, data):
        self._validate(name, data)
        self._check_policy()
        blob = self._writer.get_blob_client(name)
        # Explicit BlockBlob: overwrite=False alone has different AppendBlob semantics.
        blob.upload_blob(data, blob_type="BlockBlob", length=len(data), overwrite=False,
                         max_concurrency=1, timeout=15)
        return self.read_and_verify(name, data)

    def read_and_verify(self, name, data):
        from azure.core import MatchConditions
        self._validate(name, data)
        self._check_policy()
        blob = self._reader.get_blob_client(name)
        properties = blob.get_blob_properties(timeout=15)
        etag, created = properties.etag, _utc(properties.creation_time)
        if (properties.blob_type != "BlockBlob" or properties.size != len(data)
                or not isinstance(etag, str) or not etag or len(etag) > 128):
            raise ValueError("Object properties mismatch")
        expiry = created + timedelta(days=self._policy.retention_days)
        if expiry < self._retain_until or expiry <= datetime.now(timezone.utc):
            raise ValueError("Retention does not cover required interval")
        content = blob.download_blob(offset=0, length=len(data), etag=etag,
                                     match_condition=MatchConditions.IfNotModified,
                                     max_concurrency=1, timeout=15).readall()
        if content != data:
            raise ValueError("Receipt readback differs")
        after = blob.get_blob_properties(timeout=15)
        if after.etag != etag or after.size != len(data) or after.creation_time != properties.creation_time:
            raise ValueError("Object changed during readback")
        self._check_policy()
        return {
            "name": name, "uri": self._url + "/" + self._container + "/" + name,
            "etag": etag, "sha256": sha256(data), "bytes": len(data),
            "policy_id": self._policy.resource_id, "policy_etag": self._policy.etag,
            "policy_state": "Locked", "retention_days": self._policy.retention_days,
            "policy_append_blobs_allowed": self._policy.allow_protected_append_writes,
            "policy_append_all_allowed": False,
            "created_utc": created.isoformat(), "retained_until_utc": expiry.isoformat(),
        }


def build_managed_identity_receipt_objects(*, account_url, container, policy,
                                          writer_client_id, verifier_client_id,
                                          retain_until):
    """Construct clients without I/O. Caller owns closing via close callback.

    Identity permissions/network isolation must be qualified separately; different
    client IDs alone do not certify independence. No default/CLI credential fallback.
    """
    from uuid import UUID
    from azure.identity import ManagedIdentityCredential
    from azure.storage.blob import ContainerClient
    import httpx
    writer_id = str(UUID(writer_client_id))
    reader_id = str(UUID(verifier_client_id))
    if writer_id == reader_id:
        raise ValueError("Writer and verifier identities must differ")
    credentials = [ManagedIdentityCredential(client_id=x) for x in (writer_id, reader_id)]
    clients = []
    http = None
    try:
        for i, credential in enumerate(credentials):
            clients.append(ContainerClient(
                account_url, container, credential=credential,
                retry_total=0, retry_connect=0, retry_read=0, retry_status=0,
                retry_to_secondary=False, redirect_max=0,
                transport=(SinglePutTransport(account_url=account_url, container=container)
                           if i == 0 else RequestsTransport(use_env_settings=False)),
                max_single_put_size=65536, max_single_get_size=65536,
                connection_timeout=10, read_timeout=15,
            ))
        http = httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
        def read_policy():
            token = credentials[1].get_token("https://management.azure.com/.default")
            response = http.get("https://management.azure.com" + policy.resource_id,
                                params={"api-version": "2025-08-01"},
                                headers={"Authorization": "Bearer " + token.token})
            response.raise_for_status()
            return response.json()
        result = AzureBlobReceiptObjects(
            account_url=account_url, container=container, writer=clients[0], reader=clients[1],
            policy_reader=read_policy, policy=policy, retain_until=retain_until)
    except Exception:
        for obj in [http, *clients, *credentials]:
            if obj is not None:
                obj.close()
        raise
    def close():
        for obj in [http, *clients, *credentials]:
            try:
                obj.close()
            except Exception:
                pass
    return result, close
