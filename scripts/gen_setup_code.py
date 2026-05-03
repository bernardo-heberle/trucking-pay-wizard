"""Generate a setup code for staff onboarding.

Run this script as IT / admin to produce a single string that staff paste
into the "Have a setup code?" field on first launch.  The code encodes all
three API credentials in a URL-safe base64 blob.  It is a convenience
helper — **not** a security measure — so treat the output as you would
the raw keys.

Usage::

    python scripts/gen_setup_code.py

The script uses ``getpass`` for key fields so they do not echo to the
terminal.  The output is printed at the end — copy it and paste into your
onboarding email.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

# Allow running from the project root without installing the package.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.setup_code import encode_setup_code  # noqa: E402


def main() -> None:
    print("Trucking Pay Wizard — Setup Code Generator")
    print("=" * 45)
    print(
        "Enter the three credentials below.  Key fields are masked.\n"
        "The generated code can be pasted by staff on first launch.\n"
    )

    anthropic_key = getpass.getpass("Anthropic API key (sk-ant-...): ").strip()
    if not anthropic_key:
        print("ERROR: Anthropic key cannot be empty.", file=sys.stderr)
        sys.exit(1)

    azure_endpoint = input("Azure endpoint (https://...cognitiveservices.azure.com/): ").strip()
    if not azure_endpoint:
        print("ERROR: Azure endpoint cannot be empty.", file=sys.stderr)
        sys.exit(1)

    azure_key = getpass.getpass("Azure Document Intelligence key: ").strip()
    if not azure_key:
        print("ERROR: Azure key cannot be empty.", file=sys.stderr)
        sys.exit(1)

    code = encode_setup_code(anthropic_key, azure_endpoint, azure_key)

    print("\n" + "=" * 45)
    print("Setup code (copy the entire line below):")
    print()
    print(code)
    print()
    print(
        "Send this code to each staff member alongside the install guide.\n"
        "They paste it into the 'Have a setup code?' field on first launch."
    )


if __name__ == "__main__":
    main()
