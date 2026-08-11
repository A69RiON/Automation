from __future__ import annotations
import os
from .common import SourceHealth, utcnow_iso

class AmazonAUSource:
    name="Amazon AU"
    def collect(self):
        # Creators API requires Amazon Associates/Creators API onboarding.
        # The adapter is intentionally credential-gated rather than scraping Amazon HTML.
        client_id=os.getenv("AMAZON_CREATORS_CLIENT_ID", "").strip()
        client_secret=os.getenv("AMAZON_CREATORS_CLIENT_SECRET", "").strip()
        if not client_id or not client_secret:
            return [], SourceHealth(self.name,"not_configured",utcnow_iso(),0,
                "Requires Amazon AU Associates + Creators API credentials; OzBargain may still surface Amazon AU deals")
        return [], SourceHealth(self.name,"partial",utcnow_iso(),0,
            "Credentials detected; endpoint/query implementation requires the approved Creators API account configuration")
