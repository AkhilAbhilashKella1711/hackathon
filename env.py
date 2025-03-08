import os
from pathlib import Path

from dotenv import load_dotenv

# imprt timezone type
from pytz import timezone

# Fetch the environment type, defaulting to 'development' if not set
ENVIRONMENT = os.getenv("ENVIRONMENT", default="development")

# # # # Construct the name of the .env file
env_path = Path(f".env.{ENVIRONMENT}")

# # # # Load the appropriate .env file
load_dotenv(dotenv_path=env_path)

litellm_proxy_api_base = os.getenv("LITELLM_PROXY_API_BASE")
litellm_proxy_api_key = os.getenv("LITELLM_PROXY_API_KEY")
klot_data_service_url = os.getenv("KLOT_DATA_SERVICE_URL", "")
port = os.getenv("PORT", "5005")
web_server_secret = os.getenv("WEB_SERVER_SECRET")
llm_service_url = os.getenv("LLM_SERVICE_URL")
mongodb_url = os.getenv("MONGO_URL","")
mongodb_db = os.getenv("MONGODB_NAME","")
temporal_url = os.getenv("TEMPORAL_URL","")
azure_storage_account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
azure_storage_account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
azure_storage_default_container = os.getenv("AZURE_STORAGE_DEFAULT_CONTAINER", "wexa")
temporal_namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
temporal_cloud = os.getenv("TEMPORAL_CLOUD", "false") == "true"
data_service_mongodb_url = os.getenv("DATA_SERVICE_MONGODB_URL", "")
data_service_mongodb_name = os.getenv("DATA_SERVICE_MONGODB_NAME", "")
table_mongo_url = os.getenv("TABLE_MONGO_URL", "")
table_db_name = os.getenv("TABLE_DB_NAME", "")
bland_api_key = os.getenv("BLAND_API_KEY", "")
hack_service = os.getenv("HACK_SERVICE", "")