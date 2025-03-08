from azure.storage.blob import BlobServiceClient
from temporalio.service import TLSConfig
from temporalio.client import Client
import env as config

storage_account_name = config.azure_storage_account_name
storage_account_key = config.azure_storage_account_key
temporal_namespace = config.temporal_namespace
container_name = "cacert"  # Private container name
blob_name_cert = (
    f"{temporal_namespace}.crt"  # Name of the cert file in the blob storage
)
blob_name_key = f"{temporal_namespace}.key"  # Name of the key file in the blob storage

# Create a Blob service client
blob_service_client = BlobServiceClient(
    account_url=f"https://{storage_account_name}.blob.core.windows.net",
    credential=storage_account_key,
)


async def download_blob(blob_name):
    blob_client = blob_service_client.get_blob_client(
        container=container_name, blob=blob_name
    )
    download_stream = blob_client.download_blob()
    return download_stream.readall()

async def tls_config():
    client_cert = await download_blob(blob_name_cert)
    client_key = await download_blob(blob_name_key)

    tls_config = TLSConfig(
        client_cert=client_cert,
        client_private_key=client_key,
    )

    return tls_config

async def create_temporal_client(namespace: str = config.temporal_namespace):
    temporal_url = config.temporal_url
    temporal_namespace = namespace
    temporal_cloud = (
        config.temporal_cloud
    )  # A boolean indicating whether to use TLS or not

    tls = False
    if temporal_cloud:
        tls = await tls_config()

    # Connecting to the Temporal client
    client = await Client.connect(
        temporal_url,
        namespace=temporal_namespace,
        tls=tls,
    )

    return client
