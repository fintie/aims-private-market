from flask import Flask, render_template_string, request, Response
from datetime import datetime, timezone
import csv, io, os, smtplib, requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

app = Flask(__name__)
DEFAULT_RECIPIENTS = ['nickq@aims.com.au', 'nickc@aims.com.au', 'augustine.goh@aims.com.au']
RECIPIENTS = [x.strip() for x in os.getenv('REPORT_RECIPIENTS', ','.join(DEFAULT_RECIPIENTS)).split(',') if x.strip()]

PUBLIC_DATA = [
 {'company':'Databricks','platform':'Forge','product':'Forge Price / Marketplace','deal_type':'Public market observation','share_class':'—','price':268.50,'bid':None,'ask':None,'deal_size':None,'valuation':201640000000,'last_funding':'Series L-2 — 13 Aug 2026 — $190B — $253.00 PPS','discount':None,'activity':'High','updated':'Forge Price updated 28 Sep 2026','source':'https://forgeglobal.com/databricks_stock/'},
 {'company':'Stripe','platform':'Forge','product':'Forge Price / Marketplace','deal_type':'Public market observation','share_class':'—','price':72.45,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'Tender Offer 3 — 24 Feb 2026 — $159B — $62.47 PPS','discount':None,'activity':'Limited','updated':'Public Forge snapshot 1 Oct 2026','source':'https://forgeglobal.com/'},
 {'company':'Saronic','platform':'Forge','product':'Forge Price / Marketplace','deal_type':'Public market observation','share_class':'—','price':34.29,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'Series D — 31 Mar 2026 — $9.25B — $27.45 PPS','discount':None,'activity':'High','updated':'Public Forge snapshot 1 Oct 2026','source':'https://forgeglobal.com/'},
 {'company':'Polymarket','platform':'Forge','product':'Forge Price / Marketplace','deal_type':'Public market observation','share_class':'—','price':137.70,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'Series E — 26 Mar 2026 — $15B — $144.08 PPS','discount':None,'activity':'High','updated':'Public Forge snapshot 1 Oct 2026','source':'https://forgeglobal.com/'},
 {'company':'Replit','platform':'Forge','product':'Forge Price / Marketplace','deal_type':'Public market observation','share_class':'—','price':259.43,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'Series D — 11 Mar 2026 — $9B — $248.26 PPS','discount':None,'activity':'High','updated':'Public Forge snapshot 1 Oct 2026','source':'https://forgeglobal.com/'},
 {'company':'SambaNova Systems','platform':'Forge','product':'Forge Price / Marketplace','deal_type':'Public market observation','share_class':'—','price':69.01,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'Series F Voting — 8 Jul 2026 — $11B — $127.10 PPS','discount':None,'activity':'High','updated':'Public Forge snapshot 1 Oct 2026','source':'https://forgeglobal.com/'},
 {'company':'Ramp','platform':'Forge','product':'Forge Price / Marketplace','deal_type':'Public market observation','share_class':'—','price':125.54,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'Series F — 4 Jun 2026 — $44B — $120.00 PPS','discount':None,'activity':'Medium','updated':'Public Forge snapshot 1 Oct 2026','source':'https://forgeglobal.com/'},
 {'company':'Rippling','platform':'Forge','product':'Forge Price / Marketplace','deal_type':'Public market observation','share_class':'—','price':47.28,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'Tender Offer 1 — 9 May 2025 — $16.8B — $52.00 PPS','discount':None,'activity':'Low','updated':'Public Forge snapshot 1 Oct 2026','source':'https://forgeglobal.com/'},
 {'company':'NPM / Daq feed','platform':'NPM','product':'Daq Premium API','deal_type':'Licensed data feed','share_class':'—','price':None,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'API provides primary rounds/history plus premium bid/offer and reported trades','discount':None,'activity':'Credential required','updated':'Configure NPM_API_KEY / licensed feed','source':'https://www.nasdaqprivatemarket.com/data-intelligence/'},
 {'company':'Clarity private-market feed','platform':'Clarity (Hiive)','product':'Market Data / Partner APIs','deal_type':'Licensed data feed','share_class':'—','price':None,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'Partner APIs support private-market opportunities, market data and liquidity workflows','discount':None,'activity':'Credential required','updated':'Configure CLARITY_API_KEY / partner feed','source':'https://www.clarity.com/partner-solutions'},
 {'company':'EquityZen private-market feed','platform':'EquityZen','product':'Marketplace','deal_type':'Licensed/account data','share_class':'—','price':None,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'No undocumented API assumed','discount':None,'activity':'Access required','updated':'Configure approved commercial feed when available','source':'https://equityzen.com/'},
]
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

def rows():
    # Provider adapters intentionally fall back to sample/placeholder rows until licensed credentials are supplied.
    return PUBLIC_DATA

def money(v):
    return '—' if v is None else '${:,.2f}'.format(v)

def email_html(data):
    trs=''.join(f"<tr><td>{r['company']}</td><td>{r['platform']}</td><td>{r['product']}</td><td>{r['deal_type']}</td><td>{money(r['price'])}</td><td>{money(r['bid'])}</td><td>{money(r['ask'])}</td><td>{r['activity']}</td><td>{r['updated']}</td></tr>" for r in data)
    return f'''<h2>AIMS Private Market Deal Monitor</h2><p>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p><table border="1" cellpadding="7" cellspacing="0" style="border-collapse:collapse;font-family:Arial;font-size:12px"><tr style="background:#10243e;color:white"><th>Company</th><th>Platform</th><th>Product</th><th>Deal Type</th><th>Price</th><th>Bid</th><th>Ask</th><th>Activity</th><th>Updated</th></tr>{trs}</table><p><small>Private-market prices may be indicative. Verify source, share class, transfer restrictions and timestamp before use.</small></p>'''

PAGE='''<!doctype html><html><head><meta charset="utf-8"><title>AIMS Private Market Monitor</title><style>
body{font-family:Arial;margin:0;background:#f4f7fb;color:#14213d}.top{background:#10243e;color:white;padding:24px 34px}.wrap{padding:24px 34px}.cards{display:flex;gap:14px;margin-bottom:18px}.card{background:white;padding:16px;border-radius:10px;box-shadow:0 1px 5px #ccd5e0;min-width:180px}.n{font-size:26px;font-weight:bold}.actions{margin:14px 0}.btn{background:#286cf5;color:white;border:0;border-radius:6px;padding:10px 14px;text-decoration:none;margin-right:8px}table{width:100%;border-collapse:collapse;background:white;font-size:13px}th{background:#10243e;color:white;text-align:left;padding:10px}td{padding:9px;border-bottom:1px solid #e5e7eb}.note{color:#64748b;font-size:12px;margin-top:14px}</style></head><body><div class="top"><h1>AIMS Private Market Deal Monitor</h1><div>Clarity/Hiive · Nasdaq Private Market · Forge · EquityZen</div></div><div class="wrap"><div class="cards"><div class="card"><div class="n">{{data|length}}</div>Rows</div><div class="card"><div class="n">4</div>Platforms</div></div><div class="actions"><a class="btn" href="/export.csv">Export CSV</a><a class="btn" href="/email-preview">Email Preview</a></div><table><tr><th>Company</th><th>Platform</th><th>Product</th><th>Deal Type</th><th>Share Class</th><th>Price</th><th>Bid</th><th>Ask</th><th>Deal Size</th><th>Valuation</th><th>Activity</th><th>Updated</th></tr>{% for r in data %}<tr><td>{{r.company}}</td><td>{{r.platform}}</td><td>{{r.product}}</td><td>{{r.deal_type}}</td><td>{{r.share_class}}</td><td>{{money(r.price)}}</td><td>{{money(r.bid)}}</td><td>{{money(r.ask)}}</td><td>{{money(r.deal_size)}}</td><td>{{money(r.valuation)}}</td><td>{{r.activity}}</td><td>{{r.updated}}</td></tr>{% endfor %}</table><div class="note">MVP uses placeholders where licensed API credentials are not configured. Do not treat indicative private-market data as an executable quote.</div></div></body></html>'''

@app.route('/health')
def health(): return {'ok': True, 'service': 'aims-private-market'}

@app.route('/npm-status')
def npm_status_route():
    return npm_status()

@app.route('/')
def home(): return render_template_string(PAGE,data=rows(),recipient=', '.join(RECIPIENTS),money=money)

@app.route('/export.csv')
def export_csv():
    data=rows(); buf=io.StringIO(); w=csv.DictWriter(buf,fieldnames=data[0].keys()); w.writeheader(); w.writerows(data)
    return Response(buf.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=private_market_deals.csv'})

@app.route('/email-preview')
def preview(): return email_html(rows())

@app.route('/send', methods=['POST'])
def send():
    host=os.getenv('SMTP_HOST'); user=os.getenv('SMTP_USER'); password=os.getenv('SMTP_PASSWORD'); sender=os.getenv('SMTP_FROM',user)
    port=int(os.getenv('SMTP_PORT','587'))
    if not all([host,user,password,sender]): return {'ok':False,'error':'SMTP_HOST, SMTP_USER, SMTP_PASSWORD and SMTP_FROM/SMTP_USER are required'},400
    msg=MIMEMultipart('alternative'); msg['Subject']=f"AIMS Private Market Deal Monitor — {datetime.now().strftime('%d %b %Y')}"; msg['From']=sender; msg['To']=', '.join(RECIPIENTS)
    msg.attach(MIMEText(email_html(rows()),'html'))
    with smtplib.SMTP(host,port,timeout=20) as s:
        s.starttls(); s.login(user,password); s.sendmail(sender,RECIPIENTS,msg.as_string())
    return {'ok':True,'sent_to':RECIPIENTS}

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','8080')),debug=False)
