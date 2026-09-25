"""Opt-in email / WhatsApp delivery. Provider acceptance is not final delivery."""
import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
import requests
from .store import now

DEFAULTS = dict(email_enabled=False, email_to='', whatsapp_enabled=False, whatsapp_to='', auto_send=False)

def setup(store):
    store.db.executescript('''
    CREATE TABLE IF NOT EXISTS notification_settings (id INTEGER PRIMARY KEY, payload TEXT);
    CREATE TABLE IF NOT EXISTS deliveries (
      job_id TEXT, channel TEXT, destination TEXT, status TEXT, detail TEXT, updated TEXT,
      PRIMARY KEY(job_id,channel));
    ''')

def settings(store):
    setup(store)
    row = store.db.execute('SELECT payload FROM notification_settings WHERE id=1').fetchone()
    return {**DEFAULTS, **(json.loads(row[0]) if row else {})}

def save_settings(store, value):
    setup(store)
    if value['email_enabled'] and not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',value['email_to']):
        raise ValueError('Enter a valid single email address.')
    if value['whatsapp_enabled'] and not re.fullmatch(r'\+[1-9]\d{7,14}',value['whatsapp_to']):
        raise ValueError('Use an international WhatsApp number, for example +919876543210.')
    with store.db:
        store.db.execute('INSERT OR REPLACE INTO notification_settings VALUES(1,?)',(json.dumps(value),))

def credentials(overrides=None):
    keys = ['SMTP_HOST','SMTP_PORT','SMTP_USERNAME','SMTP_PASSWORD','SMTP_FROM','TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_WHATSAPP_FROM','TWILIO_CONTENT_SID']
    return {k:str((overrides or {}).get(k) or os.getenv(k,'')) for k in keys}

def validate_provider(channel, config):
    required = ['SMTP_HOST','SMTP_USERNAME','SMTP_PASSWORD'] if channel=='email' else ['TWILIO_ACCOUNT_SID','TWILIO_AUTH_TOKEN','TWILIO_WHATSAPP_FROM']
    missing = [k for k in required if not config.get(k)]
    if missing: raise ValueError('Missing configuration: ' + ', '.join(missing))
    if channel=='email' and config.get('SMTP_PORT','') not in ('','465','587'):
        raise ValueError('Use SMTP port 465 (TLS) or 587 (STARTTLS).')
    if channel=='whatsapp':
        if not re.fullmatch(r'AC[0-9a-fA-F]{32}',config['TWILIO_ACCOUNT_SID']): raise ValueError('Invalid Twilio account SID.')
        if not re.fullmatch(r'(?:whatsapp:)?\+[1-9]\d{7,14}',config['TWILIO_WHATSAPP_FROM']): raise ValueError('Invalid Twilio WhatsApp sender number.')
        if config.get('TWILIO_CONTENT_SID') and not re.fullmatch(r'HX[0-9a-fA-F]{32}',config['TWILIO_CONTENT_SID']): raise ValueError('Invalid Twilio template Content SID.')

def message(payload):
    job, result = payload['job'], payload['match']
    return (f"CareerPilot: {job['title']} at {job['company']}\n"
            f"Fit: {result['score']}/100 | {job.get('location') or 'Location not listed'}\n"
            f"{job.get('url','')}\nFit is a heuristic, not a hiring probability. Verify the listing.")

def send(channel, destination, payload, config):
    validate_provider(channel,config)
    if channel=='email':
        msg=EmailMessage()
        msg['Subject']='CareerPilot — job alert'
        msg['From']=config.get('SMTP_FROM') or config['SMTP_USERNAME']
        msg['To']=destination
        msg.set_content(message(payload))
        port=int(config.get('SMTP_PORT') or 465)
        context=ssl.create_default_context()
        smtp = smtplib.SMTP_SSL(config['SMTP_HOST'],port,timeout=20,context=context) if port==465 else smtplib.SMTP(config['SMTP_HOST'],port,timeout=20)
        with smtp:
            if port==587: smtp.starttls(context=context)
            smtp.login(config['SMTP_USERNAME'],config['SMTP_PASSWORD'])
            refused=smtp.send_message(msg)
            if refused: raise ValueError('Recipient rejected by mail server.')
        return 'Accepted by email server; inbox delivery unconfirmed.'
    sender=config['TWILIO_WHATSAPP_FROM'].removeprefix('whatsapp:')
    data={'From':'whatsapp:'+sender,'To':'whatsapp:'+destination}
    if config.get('TWILIO_CONTENT_SID'):
        job=payload['job']
        data.update(ContentSid=config['TWILIO_CONTENT_SID'],ContentVariables=json.dumps({'1':job['title'][:150],'2':job['company'][:100],'3':str(payload['match']['score']),'4':job.get('url') or 'Open CareerPilot for details'}))
    else: data['Body']=message(payload)
    r=requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{config['TWILIO_ACCOUNT_SID']}/Messages.json",auth=(config['TWILIO_ACCOUNT_SID'],config['TWILIO_AUTH_TOKEN']),data=data,timeout=20,allow_redirects=False)
    if r.status_code!=201:
        raise ValueError(f'Twilio rejected the request (HTTP {r.status_code}). Check sender, recipient opt-in and template/window in Twilio.')
    return 'Accepted by Twilio; delivery unconfirmed. Message ID: '+str(r.json().get('sid','unknown'))

def dispatch(store, config, job_ids=None, sender=send):
    """Atomic per-channel claims prevent reruns from sending duplicate requests.

    Ambiguous failures are held for review, never automatically retried.
    Limit each batch to 10 alerts to control cost and request duration.
    """
    prefs=settings(store); outcomes=[]
    for alert in list(reversed(store.alerts())):
        if job_ids is not None and alert['job_id'] not in job_ids: continue
        if len(outcomes)>=10: break
        for channel in ('email','whatsapp'):
            if not prefs[channel+'_enabled']: continue
            if len(outcomes)>=10: break
            destination=prefs[channel+'_to']
            try: validate_provider(channel,config)
            except ValueError as exc:
                outcomes.append({'channel':channel,'status':'Not configured','detail':str(exc)}); continue
            with store.db:
                claimed=store.db.execute('INSERT OR IGNORE INTO deliveries VALUES(?,?,?,?,?,?)',(alert['job_id'],channel,destination,'unknown','Request started; if interrupted, check provider before resending.',now())).rowcount
            if not claimed: continue
            try: detail=sender(channel,destination,alert['payload'],config);status='accepted'
            except Exception:
                status='unknown';detail='Not confirmed. Check provider logs and configuration. Automatic retry is disabled to avoid duplicates.'
            with store.db:
                store.db.execute('UPDATE deliveries SET status=?,detail=?,updated=? WHERE job_id=? AND channel=?',(status,detail,now(),alert['job_id'],channel))
            outcomes.append(dict(channel=channel,status=status,detail=detail))
    return outcomes

def history(store):
    setup(store)
    return [dict(r) for r in store.db.execute('SELECT * FROM deliveries ORDER BY updated DESC')]

TEST_PAYLOAD={'job':{'title':'Connection test','company':'CareerPilot','location':'Test only','url':''},'match':{'score':0}}
