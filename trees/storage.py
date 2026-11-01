import posixpath
from uuid import uuid4

from django.core.exceptions import SuspiciousFileOperation
from storages.backends.s3 import S3Storage


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
