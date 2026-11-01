import posixpath
from uuid import uuid4
from urllib.parse import urlsplit, urlunsplit

from django.core.exceptions import SuspiciousFileOperation
from storages.backends.s3 import S3Storage


def use_supabase_direct_storage_endpoint(endpoint_url):
    endpoint = urlsplit(endpoint_url)
    hostname = endpoint.hostname
    if not hostname or not hostname.endswith(".supabase.co"):
        return endpoint_url
    if hostname.endswith(".storage.supabase.co"):
        return endpoint_url

    project_ref = hostname.removesuffix(".supabase.co")
    if not project_ref or "." in project_ref:
        return endpoint_url

    direct_hostname = f"{project_ref}.storage.supabase.co"
    if endpoint.port:
        direct_hostname = f"{direct_hostname}:{endpoint.port}"
    return urlunsplit(
        (
            endpoint.scheme,
            direct_hostname,
            endpoint.path,
            endpoint.query,
            endpoint.fragment,
        )
    )


class UniqueUploadS3Storage(S3Storage):
    def get_available_name(self, name, max_length=None):
        directory, _ = posixpath.split(name)
        extension = posixpath.splitext(name)[1]
        available_length = max_length
        if available_length is not None:
            available_length -= len(directory) + (1 if directory else 0)
            if available_length < 32:
                raise SuspiciousFileOperation(
                    "Storage path is too long to generate a unique filename."
                )
            extension = extension[: max(0, available_length - 32)]

        filename = f"{uuid4().hex}{extension}"
        unique_name = posixpath.join(directory, filename)
        return super().get_available_name(unique_name, max_length)
