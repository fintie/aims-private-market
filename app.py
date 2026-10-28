from flask import Flask, render_template, request, Response, abort, url_for
from datetime import datetime, timezone
from pathlib import Path
from markupsafe import escape
import csv, io, json, os, smtplib, requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

app = Flask(__name__)
DEFAULT_RECIPIENTS = ['nickq@aims.com.au', 'nickc@aims.com.au', 'augustine.goh@aims.com.au']
RECIPIENTS = [x.strip() for x in os.getenv('REPORT_RECIPIENTS', ','.join(DEFAULT_RECIPIENTS)).split(',') if x.strip()]

BASE_FIELDS = ('company', 'platform', 'product', 'deal_type', 'share_class', 'price', 'bid', 'ask', 'deal_size', 'valuation', 'last_funding', 'discount', 'activity', 'updated', 'source')

def npm_status():
    key = os.getenv('NPM_API_KEY', '').strip()
    if not key:
        return {'configured': False, 'auth': 'not tested', 'message': 'NPM_API_KEY is not configured in the service environment.'}

    # Nasdaq Data Link does not expose a universal endpoint that lists every
    # premium entitlement for an API key. Test authentication against a known
    # public Data Link table; NPM entitlement is tested separately when an NPM
    # table code is configured.
    status = {'configured': True, 'auth': 'unknown', 'npm_entitlement': 'unknown'}
    try:
        auth_url = 'https://data.nasdaq.com/api/v3/datatables/SHARADAR/TICKERS.json'
        r = requests.get(auth_url, params={'api_key': key, 'qopts.per_page': 1}, timeout=12)
        if r.status_code == 200:
            status['auth'] = 'valid'
        elif r.status_code in (400, 401, 403):
            status['auth'] = 'rejected'
            try:
                status['message'] = r.json().get('quandl_error', {}).get('message', 'Nasdaq rejected the authentication request.')
            except Exception:
                status['message'] = 'Nasdaq rejected the authentication request.'
            return status
        else:
            status['auth'] = 'service error'
            status['message'] = f'Nasdaq returned HTTP {r.status_code}.'
            return status

        table = os.getenv('NPM_TABLE_CODE', '').strip().strip('/')
        if not table:
            status['message'] = 'API key authenticated. Set NPM_TABLE_CODE after NPM/Daq provides the entitled table code.'
            return status

        parts = table.split('/')
        if len(parts) != 2:
            status['npm_entitlement'] = 'configuration error'
            status['message'] = 'NPM_TABLE_CODE must use DATABASE/TABLE format.'
            return status

        meta_url = f'https://data.nasdaq.com/api/v3/datatables/{parts[0]}/{parts[1]}/metadata.json'
        m = requests.get(meta_url, params={'api_key': key}, timeout=12)
        if m.status_code == 200:
            payload = m.json().get('datatable', {})
            status['npm_entitlement'] = 'available'
            status['table'] = table
            status['table_name'] = payload.get('name')
            status['refreshed_at'] = (payload.get('status') or {}).get('refreshed_at') or payload.get('refreshed_at')
        elif m.status_code == 403:
            status['npm_entitlement'] = 'not entitled'
            status['message'] = 'The API key is valid but Nasdaq reports no permission for the configured NPM table.'
        else:
            status['npm_entitlement'] = 'error'
            status['message'] = f'NPM metadata request returned HTTP {m.status_code}.'
    except requests.RequestException as e:
        status['auth'] = 'network error'
        status['message'] = str(e)
    return status

PRIMARY_SOURCE = 'EquityZen'
SNAPSHOT_NOTE = ('Available-listings snapshot captured 21 Oct 2026. '
                 '60 companies captured; coverage is partial because the source stopped loading. '
                 'Availability may have changed. Prices and implied valuations are indicative, '
                 'in USD, and may refer to different offerings. Missing prices are shown as —. '
                 'This snapshot does not refresh automatically.')
DEFAULT_FEED = Path(__file__).parent / 'data' / 'equityzen_available.json'
ROW_FIELDS = BASE_FIELDS + ('price_source', 'valuation_type', 'availability_source', 'observed_at', 'minimum_investment', 'time_to_close', 'last_valuation', 'terms_verified')

def rows():
    feed_path = os.getenv('EQUITYZEN_DATA_FILE', '').strip() or DEFAULT_FEED
    with open(feed_path, encoding='utf-8') as feed:
        records = json.load(feed)
    if not isinstance(records, list):
        raise ValueError('EQUITYZEN_DATA_FILE must contain a JSON array of company records')
    result = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get('company'), str) or not record['company'].strip():
            raise ValueError('Each company record must include a company name')
        if 'equityzen' in record['company'].casefold():
            continue
        row = {key: record.get(key) for key in ROW_FIELDS}
        for key in ('price', 'bid', 'ask', 'deal_size', 'valuation', 'minimum_investment', 'last_valuation'):
            value = row[key]
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0):
                raise ValueError(f'{key} must be a non-negative number or null')
        if row['valuation'] == 0:
            row['valuation'] = None
        row['platform'] = PRIMARY_SOURCE
        row['product'] = record.get('product') or 'Single-company investment'
        row['deal_type'] = record.get('deal_type') or 'Private-market investment'
        row['activity'] = record.get('activity') or 'Availability unverified'
        row['updated'] = record.get('updated') or 'Timestamp unavailable'
        row['share_class'] = record.get('share_class') or '—'
        result.append(row)
    return result

def money(v):
    return '—' if v is None else '${:,.2f}'.format(v)

def email_html(data):
    trs=''.join(f"<tr><td>{escape(r['company'])}</td><td>{escape(r['deal_type'])}</td><td>{money(r['price'])}</td><td>{money(r['valuation'])}</td><td>{money(r['bid'])}</td><td>{money(r['ask'])}</td><td>{escape(r['activity'])}</td><td>{escape(r['updated'])}</td></tr>" for r in data)
    return f'''<h2>Private Market Deal Monitor</h2><p>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p><table border="1" cellpadding="7" cellspacing="0" style="border-collapse:collapse;font-family:Arial;font-size:12px"><tr style="background:#10243e;color:white"><th>Company</th><th>Deal Type</th><th>Share Price (USD)</th><th>Implied Valuation (USD)</th><th>Bid</th><th>Ask</th><th>Activity</th><th>Updated</th></tr>{trs}</table><p><small>{escape(SNAPSHOT_NOTE)}</small></p>'''

def products(data):
    grouped = {}
    for row in data:
        key = (row['company'], row['product'])
        grouped.setdefault(key, []).append(row)
    return [dict(id=i, company=key[0], product=key[1], deals=deals)
            for i, (key, deals) in enumerate(grouped.items())]


def premium(row):
    # Only compare values explicitly verified as terms of the same offering.
    if row['terms_verified'] is True and row['valuation'] is not None and row['last_valuation']:
        value = (row['valuation'] / row['last_valuation'] - 1) * 100
        return f'{abs(value):.1f}% ' + ('discount' if value < 0 else 'premium' if value > 0 else 'at last valuation')
    return 'Not available'

@app.route('/health')
def health(): return {'ok': True, 'service': 'private-market'}

@app.route('/npm-status')
def npm_status_route():
    return npm_status()

@app.route('/')
def home():
    data = rows()
    return render_template('market.html', products=products(data), selected=None,
                           count=len(data), money=money, premium=premium, snapshot_note=SNAPSHOT_NOTE)

@app.route('/products/<int:product_id>')
def product_detail(product_id):
    data = rows()
    catalog = products(data)
    if product_id >= len(catalog):
        abort(404)
    return render_template('market.html', products=catalog, selected=catalog[product_id],
                           count=len(data), money=money, premium=premium, snapshot_note=SNAPSHOT_NOTE)

@app.route('/export.csv')
def export_csv():
    data=rows(); buf=io.StringIO(); w=csv.DictWriter(buf,fieldnames=ROW_FIELDS); w.writeheader(); w.writerows(data)
    return Response(buf.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=private_market_deals.csv'})

@app.route('/email-preview')
def preview(): return email_html(rows())

@app.route('/send', methods=['POST'])
def send():
    host=os.getenv('SMTP_HOST'); user=os.getenv('SMTP_USER'); password=os.getenv('SMTP_PASSWORD'); sender=os.getenv('SMTP_FROM',user)
    port=int(os.getenv('SMTP_PORT','587'))
    if not all([host,user,password,sender]): return {'ok':False,'error':'SMTP_HOST, SMTP_USER, SMTP_PASSWORD and SMTP_FROM/SMTP_USER are required'},400
    msg=MIMEMultipart('alternative'); msg['Subject']=f"Private Market Deal Monitor — {datetime.now().strftime('%d %b %Y')}"; msg['From']=sender; msg['To']=', '.join(RECIPIENTS)
    msg.attach(MIMEText(email_html(rows()),'html'))
    with smtplib.SMTP(host,port,timeout=20) as s:
        s.starttls(); s.login(user,password); s.sendmail(sender,RECIPIENTS,msg.as_string())
    return {'ok':True,'sent_to':RECIPIENTS}

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','8080')),debug=False)
