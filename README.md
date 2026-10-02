# AIMS Private Market Deal Monitor

MVP dashboard and email-report service for Clarity (formerly Hiive), Nasdaq Private Market, Forge and EquityZen.

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
