"""Template checker — example for implementing new vendor checkers.

This file is NOT auto-registered because its name starts with an underscore.

To create a new checker:

1. Copy this file to a new file (e.g., juniper.py)
2. Update manufacturer_name, base_url, and rate_limit
3. Implement the check() method
"""

from datetime import datetime

from ..checker import BaseChecker
from ..models import EOLResult, EOLStatus, HardwareModel


class TemplateChecker(BaseChecker):
    """Example checker for a vendor. Copy and modify for real implementations."""

    manufacturer_name = "template"
    rate_limit = 5
    base_url = "https://example.com"

    async def check(self, model: HardwareModel) -> EOLResult:
        """Check EOL status for a single model.

        Override this method with vendor-specific scraping/API logic.
        """
        return EOLResult(
            model=model,
            status=EOLStatus.UNKNOWN,
            checked_at=datetime.now(),
            notes="Template checker — not a real implementation",
        )
