"""Class to help uploading data to a storage account"""

import logging
from contextlib import ContextDecorator
from typing import Any

from azure.storage.blob import BlobClient, BlobType
from config import settings

logger = logging.getLogger(settings.LOGGER_NAME)


class AzureBlobClientCreateError(Exception):
    def __init__(
        self,
        storage_account_name: str,
        container_name: str,
        blob_name: str,
        e: Exception,
    ) -> None:
        exc_message = f"Failed to create queue https://{storage_account_name}/{container_name!a}/{blob_name!a}. - Error: {e}"
        super().__init__(exc_message)
        self.message: str = exc_message


class AzureStorageAccount(ContextDecorator):
    """Class representing a Azure Storage Account including context manager interfaces"""

    def __init__(self, storage_account_name: str, key: str) -> None:
        self.storage_account_name: str = storage_account_name
        self.key: str = key

    def __del__(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        pass

    def get_connection_str(self) -> str:
        """Returns the connection string for the storage account."""
        return (
            f"DefaultEndpointsProtocol=https;AccountName={self.storage_account_name};"
            + f"AccountKey={self.key};EndpointSuffix=core.windows.net"
        )

    def get_blob_client(
        self, container_name: str, blob_name: str
    ) -> BlobClient:
        """Gets a BlobClient for a storage blob"""
        # https://learn.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.blobclient?view=azure-python#azure-storage-blob-blobclient-from-connection-string
        connection_str = self.get_connection_str()
        try:
            blob_client = BlobClient.from_connection_string(
                conn_str=connection_str,
                container_name=container_name,
                blob_name=blob_name,
            )
        except Exception as e:
            raise AzureBlobClientCreateError(
                self.storage_account_name, container_name, blob_name, e
            )
        else:
            return blob_client

    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: str,
        overwrite: bool = False,
        metadata: dict[str, Any] | None = None,
        content_type: str | None = "application/octet-stream",
        encoding: str | None = "utf-8",
    ) -> dict[str, Any]:
        try:
            blob_client: BlobClient = self.get_blob_client(
                container_name, blob_name
            )
        except Exception as e:
            raise e
        else:
            try:
                result = blob_client.upload_blob(
                    data=data,
                    blob_type=BlobType.BLOCKBLOB,
                    length=len(data),
                    metadata=metadata,
                    overwrite=overwrite,
                    content_type=content_type,
                    encoding=encoding,
                )
            except Exception as e:
                raise e
            else:
                return result
            finally:
                blob_client.close()
