import io
import json
import pytest
from careerpilot.core import normalize, match, parse_resume, skills_from
from careerpilot.store import Store
from careerpilot.discovery import discover, jsonld_jobs, validate_url, DiscoveryError, feed
from careerpilot.workflow import scan

PROFILE = dict(skills=['Marketing','Excel','Communication'],roles=['Growth Marketing Associate'],years=1,locations=['India'],keywords=['growth'])
def job(): return normalize('Acme','fixture','1','Growth Marketing Associate','Marketing, Excel, Communication. 1 year of experience. Support growth.','Mumbai, India','https://example.com/jobs/1')

def test_scoring_and_unknowns():
    assert match(job(),PROFILE)['score']==100
    assert match(job(),{})['score']==0
    unknown=normalize('A','f','2','Unrelated','No listed requirements')
    assert match(unknown,PROFILE)['score']==0
    assert match(unknown,PROFILE)['coverage']==35
    assert skills_from('No sequel; SQL and Excel')==['SQL','Excel']

def test_experience():
    assert normalize('A','f','1','Role','Requires 3–5 years of relevant experience')['min_years']==3
    assert normalize('A','f','1','Role','Founded in 2012')['min_years'] is None

def test_resume():
    assert parse_resume('cv.txt',b'Marketing professional')=='Marketing professional'
    with pytest.raises(ValueError): parse_resume('cv.pdf',b'broken')
    with pytest.raises(ValueError): parse_resume('cv.txt',b'')
    from docx import Document
    doc=Document(); doc.add_paragraph('Marketing and SQL'); buf=io.BytesIO();doc.save(buf)
    assert 'Marketing and SQL' in parse_resume('cv.docx',buf.getvalue())
    from pypdf import PdfWriter
    writer=PdfWriter();writer.add_blank_page(width=100,height=100);buf=io.BytesIO();writer.write(buf)
    with pytest.raises(ValueError,match='No text'):parse_resume('cv.pdf',buf.getvalue())

def test_persistence_and_dedupe(tmp_path):
    path=tmp_path/'db.sqlite'; s=Store(path);s.save_profile(PROFILE);s.add_company('Acme','')
    assert s.ingest(1,[job()],PROFILE)==(1,1)
    assert s.ingest(1,[job()],PROFILE)==(0,0)
    assert len(s.alerts())==1
    s.db.close();s=Store(path)
    assert s.profile()==PROFILE and len(s.jobs())==1
    s.acknowledge(job()['id']);assert s.alerts()[0]['acknowledged']==1
    s.remove_company(1);assert not s.jobs() and not s.alerts()

def test_jsonld():
    payload={'@graph':[{'@type':'JobPosting','title':'Marketing Associate','description':'<p>Excel</p>','jobLocation':{'address':{'addressLocality':'Mumbai','addressCountry':'India'}},'url':'/jobs/1'}]}
    found=jsonld_jobs('<script type="application/ld+json">'+json.dumps(payload)+'</script>','Acme','https://example.com/careers')
    assert found[0]['url']=='https://example.com/jobs/1'
    assert found[0]['skills']==['Excel']
    assert found[0]['location']=='Mumbai, India'

@pytest.mark.parametrize('url',['https://127.0.0.1/jobs','http://example.com','https://glassdoor.com/jobs','https://ambitionbox.com','https://user:pw@example.com','https://[::1]/'])
def test_rejected_urls(url):
    with pytest.raises(DiscoveryError): validate_url(url)

def test_feeds():
    class Client:
        def get(self,url):
            if 'greenhouse' in url:return json.dumps({'jobs':[dict(id=1,title='Role',content='<p>SQL</p>',location={'name':'India'},absolute_url='https://example.com')]})
            return json.dumps([dict(id='2',text='Marketing',description='Intro',lists=[{'text':'Skills','content':'Excel'}],categories={'location':'India'},hostedUrl='https://example.com')])
    assert feed('Acme','greenhouse','acme',Client())[0]['description']=='SQL'
    assert 'Excel' in feed('Acme','lever','acme',Client())[0]['description']

def test_workflow_fault_isolation(tmp_path,monkeypatch):
    s=Store(tmp_path/'db');s.save_profile(PROFILE);s.add_company('Good','https://example.com');s.add_company('Bad','')
    def fake(name,url):
        if not url:raise DiscoveryError('URL required')
        return [job()],'Complete feed'
    monkeypatch.setattr('careerpilot.workflow.discover',fake)
    result=scan(s)
    assert len(result['reports'])==2 and len(s.jobs())==1 and len(s.alerts())==1
    scan(s);assert len(s.alerts())==1
    assert any('failed' in c['status'] for c in s.companies())
