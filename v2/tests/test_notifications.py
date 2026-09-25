import pytest
from careerpilot.core import normalize
from careerpilot.store import Store
from careerpilot import notifications as n

PROFILE=dict(skills=['Marketing','Excel','Communication'],roles=['Growth Marketing Associate'],years=1,locations=['India'],keywords=['growth'])
def job(i):return normalize('Acme','fixture',str(i),'Growth Marketing Associate','Marketing, Excel, Communication. 1 year of experience. Support growth.','Mumbai, India','https://example.com/jobs/'+str(i))

def test_configuration_and_delivery_dedupe(tmp_path):
    s=Store(tmp_path/'db');s.add_company('Acme','')
    assert s.ingest(1,[job(1),job(2)],PROFILE)==(2,2)
    prefs=dict(email_enabled=True,email_to='me@example.com',whatsapp_enabled=True,whatsapp_to='+919876543210',auto_send=True)
    n.save_settings(s,prefs)
    sent=[]
    config=dict(SMTP_HOST='smtp.example.com',SMTP_USERNAME='me@example.com',SMTP_PASSWORD='test',TWILIO_ACCOUNT_SID='AC'+'a'*32,TWILIO_AUTH_TOKEN='test',TWILIO_WHATSAPP_FROM='+14155238886')
    def sender(channel,destination,payload,config):
        sent.append((channel,payload['job']['id']))
        return 'provider accepted'
    assert len(n.dispatch(s,config,sender=sender))==4
    assert len(n.dispatch(s,config,sender=sender))==0
    assert len(sent)==4
    assert len(n.history(s))==4
    assert all(x['status']=='accepted' for x in n.history(s))
    s.db.close();s=Store(tmp_path/'db')
    assert n.settings(s)==prefs and len(n.history(s))==4

def test_missing_configuration_does_not_claim(tmp_path):
    s=Store(tmp_path/'db');s.add_company('Acme','');s.ingest(1,[job(1)],PROFILE)
    n.save_settings(s,dict(email_enabled=True,email_to='me@example.com',whatsapp_enabled=False,whatsapp_to='',auto_send=False))
    outcomes=n.dispatch(s,{})
    assert outcomes[0]['status']=='Not configured'
    assert n.history(s)==[]

def test_provider_failure_held_for_review(tmp_path):
    s=Store(tmp_path/'db');s.add_company('Acme','');s.ingest(1,[job(1)],PROFILE)
    n.save_settings(s,dict(email_enabled=True,email_to='me@example.com',whatsapp_enabled=False,whatsapp_to='',auto_send=False))
    config=dict(SMTP_HOST='smtp.example.com',SMTP_USERNAME='me@example.com',SMTP_PASSWORD='test')
    def broken(*args):raise TimeoutError('secret detail')
    outcomes=n.dispatch(s,config,sender=broken)
    assert outcomes[0]['status']=='unknown' and 'secret detail' not in outcomes[0]['detail']
    assert n.dispatch(s,config,sender=broken)==[]

def test_validation(tmp_path):
    s=Store(tmp_path/'db')
    with pytest.raises(ValueError):n.save_settings(s,dict(email_enabled=True,email_to='bad',whatsapp_enabled=False,whatsapp_to='',auto_send=False))
    with pytest.raises(ValueError):n.save_settings(s,dict(email_enabled=False,email_to='',whatsapp_enabled=True,whatsapp_to='1234',auto_send=False))
