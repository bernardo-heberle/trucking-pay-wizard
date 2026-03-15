import io
import os
import sys

import fitz  # pymupdf
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()

endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

if not endpoint or not key:
    print("ERROR: credentials not loaded — check your .env file")
    sys.exit(1)

# ── Put the path to your test PDF here ───────────────────────────────────────
PDF_PATH = r".\data\raw\test_doc.pdf"
# ─────────────────────────────────────────────────────────────────────────────

# Free tier (F0) limit is 4 MB per request — send one page at a time as JPEG
DPI = 150
client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))

src = fitz.open(PDF_PATH)
print(f"Document has {len(src)} page(s). Sending page by page at {DPI} DPI...\n")

for page_num, page in enumerate(src, start=1):
    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pix = page.get_pixmap(matrix=mat)
    jpeg_bytes = pix.tobytes("jpeg")

    size_mb = len(jpeg_bytes) / 1024 / 1024
    print(f"Page {page_num}/{len(src)} — {size_mb:.2f} MB — sending...")

    poller = client.begin_analyze_document("prebuilt-read", body=io.BytesIO(jpeg_bytes))
    result = poller.result()

    for line in result.pages[0].lines or []:
        print(f"  {line.content}")
    print()

print("SUCCESS — all pages processed.")
