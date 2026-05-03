from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

from src import credentials as _creds
from src.ocr.exceptions import OcrError


def build_client() -> DocumentIntelligenceClient:
    """Read Azure credentials from the credential store and return a configured client.

    Raises:
        OcrError: Either credential is missing from both keyring and environment.
    """
    endpoint = _creds.get_azure_endpoint()
    key = _creds.get_azure_key()

    if not endpoint:
        raise OcrError(
            "Azure endpoint not found. "
            "Set it via the credentials screen or AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT in .env."
        )
    if not key:
        raise OcrError(
            "Azure key not found. "
            "Set it via the credentials screen or AZURE_DOCUMENT_INTELLIGENCE_KEY in .env."
        )

    return DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )
