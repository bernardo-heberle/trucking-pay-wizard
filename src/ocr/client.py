import os

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

from src.ocr.exceptions import OcrError

_ENDPOINT_VAR = "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
_KEY_VAR = "AZURE_DOCUMENT_INTELLIGENCE_KEY"


def build_client() -> DocumentIntelligenceClient:
    """Read Azure credentials from the environment and return a configured client.

    Calls `load_dotenv()` so a `.env` file in the working directory is picked up
    automatically.

    Raises:
        OcrError: Either credential environment variable is missing or empty.
    """
    load_dotenv()

    endpoint = os.getenv(_ENDPOINT_VAR)
    key = os.getenv(_KEY_VAR)

    if not endpoint:
        raise OcrError(
            f"Azure endpoint not found. Set {_ENDPOINT_VAR!r} in your .env file."
        )
    if not key:
        raise OcrError(
            f"Azure key not found. Set {_KEY_VAR!r} in your .env file."
        )

    return DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )
