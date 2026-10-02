from flask import Flask, render_template_string, request, Response
from datetime import datetime, timezone
import csv, io, os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

app = Flask(__name__)
RECIPIENT = os.getenv('REPORT_RECIPIENT', 'nickq@aims.com.au')

SAMPLE = [
 {'company':'Databricks','platform':'Forge','product':'Forge Data / Marketplace','deal_type':'Secondary','share_class':'Common','price':268.50,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'Series L-2','discount':None,'activity':'High','updated':'Sample / replace with API','source':'Forge'},
 {'company':'SpaceX','platform':'NPM','product':'Daq / NPM Price','deal_type':'Pricing intelligence','share_class':'Common','price':None,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'—','discount':None,'activity':'—','updated':'Awaiting API credentials','source':'NPM'},
 {'company':'OpenAI','platform':'Clarity (Hiive)','product':'Private Market / Partner API','deal_type':'Secondary / IOI','share_class':'—','price':None,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'—','discount':None,'activity':'—','updated':'Awaiting partner feed','source':'Clarity'},
 {'company':'Stripe','platform':'EquityZen','product':'Single-company investment','deal_type':'Offering','share_class':'—','price':None,'bid':None,'ask':None,'deal_size':None,'valuation':None,'last_funding':'—','discount':None,'activity':'—','updated':'Awaiting licensed feed','source':'EquityZen'},
]

def rows():
    # Provider adapters intentionally fall back to sample/placeholder rows until licensed credentials are supplied.
    return SAMPLE

def money(v):
    return '—' if v is None else '${:,.2f}'.format(v)

def email_html(data):
    trs=''.join(f"<tr><td>{r['company']}</td><td>{r['platform']}</td><td>{r['product']}</td><td>{r['deal_type']}</td><td>{money(r['price'])}</td><td>{money(r['bid'])}</td><td>{money(r['ask'])}</td><td>{r['activity']}</td><td>{r['updated']}</td></tr>" for r in data)
    return f'''<h2>AIMS Private Market Deal Monitor</h2><p>Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p><table border="1" cellpadding="7" cellspacing="0" style="border-collapse:collapse;font-family:Arial;font-size:12px"><tr style="background:#10243e;color:white"><th>Company</th><th>Platform</th><th>Product</th><th>Deal Type</th><th>Price</th><th>Bid</th><th>Ask</th><th>Activity</th><th>Updated</th></tr>{trs}</table><p><small>Private-market prices may be indicative. Verify source, share class, transfer restrictions and timestamp before use.</small></p>'''

PAGE='''<!doctype html><html><head><meta charset="utf-8"><title>AIMS Private Market Monitor</title><style>
body{font-family:Arial;margin:0;background:#f4f7fb;color:#14213d}.top{background:#10243e;color:white;padding:24px 34px}.wrap{padding:24px 34px}.cards{display:flex;gap:14px;margin-bottom:18px}.card{background:white;padding:16px;border-radius:10px;box-shadow:0 1px 5px #ccd5e0;min-width:180px}.n{font-size:26px;font-weight:bold}.actions{margin:14px 0}.btn{background:#286cf5;color:white;border:0;border-radius:6px;padding:10px 14px;text-decoration:none;margin-right:8px}table{width:100%;border-collapse:collapse;background:white;font-size:13px}th{background:#10243e;color:white;text-align:left;padding:10px}td{padding:9px;border-bottom:1px solid #e5e7eb}.note{color:#64748b;font-size:12px;margin-top:14px}</style></head><body><div class="top"><h1>AIMS Private Market Deal Monitor</h1><div>Clarity/Hiive · Nasdaq Private Market · Forge · EquityZen</div></div><div class="wrap"><div class="cards"><div class="card"><div class="n">{{data|length}}</div>Rows</div><div class="card"><div class="n">4</div>Platforms</div><div class="card"><div class="n">{{recipient}}</div>Email target</div></div><div class="actions"><a class="btn" href="/export.csv">Export CSV</a><a class="btn" href="/email-preview">Email Preview</a></div><table><tr><th>Company</th><th>Platform</th><th>Product</th><th>Deal Type</th><th>Share Class</th><th>Price</th><th>Bid</th><th>Ask</th><th>Deal Size</th><th>Valuation</th><th>Activity</th><th>Updated</th></tr>{% for r in data %}<tr><td>{{r.company}}</td><td>{{r.platform}}</td><td>{{r.product}}</td><td>{{r.deal_type}}</td><td>{{r.share_class}}</td><td>{{money(r.price)}}</td><td>{{money(r.bid)}}</td><td>{{money(r.ask)}}</td><td>{{money(r.deal_size)}}</td><td>{{money(r.valuation)}}</td><td>{{r.activity}}</td><td>{{r.updated}}</td></tr>{% endfor %}</table><div class="note">MVP uses placeholders where licensed API credentials are not configured. Do not treat indicative private-market data as an executable quote.</div></div></body></html>'''

@app.route('/')
def home(): return render_template_string(PAGE,data=rows(),recipient=RECIPIENT,money=money)

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
    msg=MIMEMultipart('alternative'); msg['Subject']=f"AIMS Private Market Deal Monitor — {datetime.now().strftime('%d %b %Y')}"; msg['From']=sender; msg['To']=RECIPIENT
    msg.attach(MIMEText(email_html(rows()),'html'))
    with smtplib.SMTP(host,port,timeout=20) as s:
        s.starttls(); s.login(user,password); s.sendmail(sender,[RECIPIENT],msg.as_string())
    return {'ok':True,'sent_to':RECIPIENT}

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','8080')),debug=False)
