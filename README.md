# Private Market Deal Monitor

Private-market dashboard and email-report service using a captured EquityZen available-listings snapshot.

## Run
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python app.py
```
Open `http://localhost:8080`.

## Functions
- Normalized deal table
- CSV export
- HTML email preview
- SMTP send endpoint (`POST /send`) to `nickq@aims.com.au`
- Environment-variable placeholders for provider credentials

## Email
Configure any SMTP service in `.env`/environment variables. No Gmail dependency is required.

## Provider implementation
The MVP deliberately does not guess undocumented commercial API endpoints. Replace the sample rows in `rows()` with licensed adapters after receiving provider credentials/schema. NPM supports API delivery via Nasdaq Data Link; Forge markets a Data API; Clarity offers partner APIs. EquityZen should be integrated only after confirming licensed feed/API terms.

## Production next steps
1. Add provider-specific adapter classes and secret management.
2. Add PostgreSQL + historical snapshots.
3. Add company/security identity mapping and share-class normalization.
4. Add composite price, spread, discount/premium, liquidity and confidence calculations.
5. Add scheduler (daily/weekly) and change-only email alerts.
6. Add SSO/RBAC and audit logs for AIMS use.

## Primary source
The bundled `data/equityzen_available.json` contains a dated snapshot of 60
companies marked Live on the authenticated available-listings page on 21 Oct
2026. Pagination failed and the source subsequently denied access, so coverage
is partial. No automatic refresh or account credentials are included.

Share prices, where present, were read from Explore cards in the same session
and matched by company URL and displayed implied valuation. They are indicative
company-level observations, not verified terms for every live offering. Missing
prices remain null. The UI and email disclose snapshot limits, USD units and
implied valuation. Historical Forge observations are no longer mixed into the
available listings.

Set `EQUITYZEN_DATA_FILE` to a server-local JSON array to replace this snapshot.
Each record requires `company`; optional fields match the CSV schema. Separate
offering records are preserved. Unknown fields are ignored and invalid numeric
values fail explicitly. Source URLs and observation timestamps are retained in
CSV for provenance; provider names are hidden from the site and email.
