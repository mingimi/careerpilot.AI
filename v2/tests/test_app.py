from pathlib import Path
from streamlit.testing.v1 import AppTest
from careerpilot.store import Store
from careerpilot.core import normalize

APP=str(Path(__file__).resolve().parents[1]/'app.py')
def test_user_journey(tmp_path,monkeypatch):
    db=tmp_path/'app.db';monkeypatch.setenv('CAREERPILOT_DB',str(db))
    at=AppTest.from_file(APP,default_timeout=20).run()
    assert not at.exception
    at.sidebar.radio[0].set_value('My profile').run()
    fields={x.label:x for x in at.text_input}
    fields['Confirmed skills (comma-separated)'].set_value('Marketing, Excel')
    fields['Target roles (comma-separated)'].set_value('Marketing Associate')
    fields['Preferred locations (comma-separated)'].set_value('India')
    fields['Preferred JD keywords (comma-separated)'].set_value('growth')
    next(b for b in at.button if b.label=='Save profile').click().run()
    assert not at.exception and Store(db).profile()['skills']==['Marketing','Excel']
    at.sidebar.radio[0].set_value('Company watchlist').run()
    at.text_input[0].set_value('Acme')
    next(b for b in at.button if b.label=='Add company').click().run()
    assert not at.exception and len(Store(db).companies())==1
    j=normalize('Acme','test','1','Marketing Associate','Marketing and Excel for growth. 0 years of experience.','India')
    monkeypatch.setattr('careerpilot.workflow.discover',lambda *a:([j],'Complete test feed'))
    next(b for b in at.button if b.label=='Refresh watchlist').click().run()
    assert not at.exception
    at.sidebar.radio[0].set_value('Job dashboard').run()
    assert at.metric[0].value=='1'
    assert not at.exception
    at.sidebar.radio[0].set_value('Notifications').run()
    assert len(Store(db).alerts())==1
    next(b for b in at.button if b.label=='Mark read').click().run()
    assert Store(db).alerts()[0]['acknowledged']==1
    at.sidebar.radio[0].set_value('How it works').run()
    assert not at.exception
    at.sidebar.radio[0].set_value('Job dashboard').run()
    at.sidebar.toggle[0].set_value(True).run()
    assert at.metric[0].value=='3' and not at.exception
