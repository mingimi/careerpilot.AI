import json
import hmac
import os
import streamlit as st
from careerpilot.core import parse_resume, skills_from, match
from careerpilot.store import Store
from careerpilot.workflow import scan
from careerpilot.discovery import validate_url
from careerpilot.demo import jobs as demo_jobs
from careerpilot import notifications as notify

def notification_config():
    try:
        values = dict(st.secrets)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        values = {}
    return notify.credentials(values)

def private_workspace():
    host = str(st.context.headers.get('Host', '')).split(':')[0].lower()
    remote = bool(host and host not in ('localhost','127.0.0.1','::1'))
    try:
        password = str(st.secrets.get('CAREERPILOT_APP_PASSWORD',''))
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        password = os.getenv('CAREERPILOT_APP_PASSWORD','')
    if remote and not password:
        st.error('Personal workspace is locked. Set CAREERPILOT_APP_PASSWORD in Streamlit app secrets to enable it.')
        st.stop()
    if password and not st.session_state.get('careerpilot_authenticated'):
        st.title('CareerPilot private workspace')
        candidate = st.text_input('App password',type='password')
        if st.button('Unlock workspace'):
            if hmac.compare_digest(candidate,password):
                st.session_state['careerpilot_authenticated']=True
                st.rerun()
            else: st.error('Incorrect password.')
        st.stop()

st.set_page_config(page_title='CareerPilot v2',page_icon='✦',layout='wide')
private_workspace()
st.markdown('''<style>.block-container{max-width:1200px;padding-top:4rem} [data-testid="stMetric"]{background:#13283b;padding:18px;border-radius:14px} h1{letter-spacing:-1px}</style>''',unsafe_allow_html=True)
st.caption('CAREERPILOT AI / COMPANY INTELLIGENCE')
st.title('Your next move, with evidence.')
st.write('Follow companies. Discover roles. Understand your fit.')
store = Store()
profile = store.profile()
with st.sidebar:
    st.header('CareerPilot v2')
    page = st.radio('Workspace',['Job dashboard','My profile','Company watchlist','Notifications','How it works'])
    demo = st.toggle('Explore demo jobs',value=False)
    threshold = st.slider('High-match alert threshold',50,100,75)
    st.caption('Local, single-user workspace. Discovery needs no API key. Delivery requires provider setup. Refresh is manual.')
    if demo: st.warning('Fictional examples. Demo jobs never enter your watchlist or alerts.')

if page == 'My profile':
    st.header('Build your profile')
    st.caption('Your resume stays in the local database. Review detected skills; no experience or skills are invented.')
    upload = st.file_uploader('Resume (PDF, DOCX or TXT; max 5 MB)',type=['pdf','docx','txt'])
    if upload and st.button('Read uploaded resume'):
        try:
            text = parse_resume(upload.name,upload.getvalue())
            st.session_state['resume_text'] = text
            st.session_state['skills_text'] = ', '.join(skills_from(text))
            st.success('Text extracted. Review below and save.')
        except ValueError as exc: st.error(str(exc))
    with st.form('profile'):
        resume = st.text_area('Resume text',value=profile.get('resume_text',''),height=180,key='resume_text')
        skills = st.text_input('Confirmed skills (comma-separated)',value=', '.join(profile.get('skills',[])),key='skills_text')
        roles = st.text_input('Target roles (comma-separated)',value=', '.join(profile.get('roles',[])),placeholder='Growth Marketing Associate, Product Operations Associate')
        years = st.number_input('Total professional experience in years',min_value=0.,max_value=60.,value=float(profile.get('years',0)),step=.5)
        locations = st.text_input('Preferred locations (comma-separated)',value=', '.join(profile.get('locations',[])),placeholder='India, Bengaluru')
        keywords = st.text_input('Preferred JD keywords (comma-separated)',value=', '.join(profile.get('keywords',[])),placeholder='AI, consumer, growth')
        st.caption('Location matching uses listed words. “Remote” does not establish eligibility to work from your country.')
        save = st.form_submit_button('Save profile',type='primary')
    if save:
        split = lambda s: list(dict.fromkeys(x.strip() for x in s.split(',') if x.strip()))
        if not roles.strip(): st.error('Add at least one target role.')
        else:
            store.save_profile(dict(resume_text=resume,skills=split(skills),roles=split(roles),years=years,locations=split(locations),keywords=split(keywords)))
            st.success('Profile saved. Dashboard scores now use these preferences.')

elif page == 'Company watchlist':
    st.header('Companies you want to follow')
    st.caption('Save any company name. Add its official careers URL to scan. Greenhouse and Lever board URLs work directly.')
    with st.form('company'):
        name = st.text_input('Company name')
        url = st.text_input('Careers URL (optional)',placeholder='https://job-boards.greenhouse.io/company')
        add = st.form_submit_button('Add company')
    if add:
        try:
            if url: validate_url(url.strip())
            store.add_company(name,url)
            st.success('Company saved.')
        except ValueError as exc: st.error(str(exc))
    if st.button('Refresh watchlist',type='primary',disabled=not bool(profile) or not bool(store.companies())):
        with st.spinner('Checking public sources. Large watchlists can take several minutes…'):
            previous_ids = {a['job_id'] for a in store.alerts()}
            result = scan(store,threshold)
            if notify.settings(store)['auto_send']:
                new_ids = {a['job_id'] for a in store.alerts()} - previous_ids
                delivery_results = notify.dispatch(store, notification_config(), new_ids)
                if delivery_results: st.write(delivery_results)
        st.success('Refresh finished. See individual source results below.')
    if not profile: st.info('Save your profile to enable refresh and matching.')
    for company in store.companies():
        with st.expander(company['name'],expanded=True):
            updated = st.text_input('Careers URL',value=company['url'],key=f'url{company["id"]}')
            if st.button('Update URL',key=f'update{company["id"]}'):
                try:
                    validate_url(updated)
                    store.update_company(company['id'],updated)
                    st.rerun()
                except ValueError as exc: st.error(str(exc))
            st.write(company['status'])
            st.caption('Last checked: ' + (company['checked'] or 'Never'))
            if st.button('Remove company and its saved jobs',key=f'delete{company["id"]}'):
                store.remove_company(company['id']); st.rerun()

elif page == 'Job dashboard':
    jobs = demo_jobs() if demo else store.jobs()
    if demo: st.warning('DEMO DATA — fictional jobs from the original CareerPilot project, updated for scoring demonstrations.')
    if not profile: st.info('Start in My profile. Save your skills and preferences to get meaningful matches.')
    scored = sorted([(j,match(j,profile)) for j in jobs],key=lambda pair:pair[1]['score'],reverse=True)
    a,b,c = st.columns(3)
    a.metric('Discovered jobs',len(jobs)); b.metric('High matches',sum(m['score']>=threshold for j,m in scored)); c.metric('Companies followed',len(store.companies()))
    search = st.text_input('Search title, company or location')
    minimum = st.slider('Minimum fit score',0,100,0)
    st.caption('Fit points are explained heuristics, not hiring probabilities. Unknown evidence earns zero points. Saved listings may have closed; verify the source.')
    filtered = [(j,m) for j,m in scored if m['score']>=minimum and search.lower() in (j['title']+' '+j['company']+' '+j['location']).lower()]
    if not filtered: st.info('No jobs here yet. Add a company and refresh its watchlist, or explore demo jobs.')
    for job,result in filtered:
        with st.container(border=True):
            left,right = st.columns([4,2])
            left.subheader(job['title']); right.metric('Fit points',f'{result["score"]}/100')
            st.write(f'{job["company"]} · {job["location"] or "Location unknown"}')
            st.caption(f'Evidence coverage: {result["coverage"]}% · Source: {job["source"]} · Last seen: {job.get("last_seen","Demo")}')
            with st.expander('Why this matches / gaps'):
                st.dataframe([dict(dimension=k,points=v['points'],maximum=v['weight'],evidence=v['explanation']) for k,v in result['dimensions'].items()],hide_index=True,use_container_width=True)
            with st.expander('Full extracted job description'): st.text(job['description'] or 'Description unavailable')
            if job['url'].startswith('https://'): st.link_button('View official listing',job['url'])
    st.download_button('Export displayed jobs',json.dumps([dict(j,match=m) for j,m in filtered],indent=2),file_name='careerpilot-jobs.json',mime='application/json')

elif page == 'Notifications':
    st.header('New high-match jobs')
    st.info('Choose email, WhatsApp, or both. Alerts contain the role, company, score and listing link—not your resume. Sending after refresh only includes newly queued alerts; use Send pending alerts for the existing queue.')
    prefs = notify.settings(store)
    with st.expander('Delivery settings', expanded=True):
        with st.form('notification_settings'):
            email_enabled = st.checkbox('Enable email', value=prefs['email_enabled'])
            email_to = st.text_input('Your email address', value=prefs['email_to'])
            whatsapp_enabled = st.checkbox('Enable WhatsApp', value=prefs['whatsapp_enabled'])
            whatsapp_to = st.text_input('Your WhatsApp number (with country code)', value=prefs['whatsapp_to'], placeholder='+919876543210')
            auto_send = st.checkbox('Send new alerts after I refresh the watchlist', value=prefs['auto_send'])
            st.caption('Saving enabled channels authorizes sending to these destinations when you use the send controls or enabled refresh option. Refresh is still manual. Up to 10 channel sends per batch; remaining alerts stay pending.')
            if st.form_submit_button('Save delivery settings'):
                try:
                    notify.save_settings(store, dict(email_enabled=email_enabled,email_to=email_to.strip(),whatsapp_enabled=whatsapp_enabled,whatsapp_to=whatsapp_to.strip(),auto_send=auto_send))
                    prefs = notify.settings(store)
                    st.success('Delivery preferences saved.')
                except ValueError as exc: st.error(str(exc))
        st.caption('Provider credentials belong in .streamlit/secrets.toml or environment variables. See NOTIFICATIONS.md in the project for setup; do not paste passwords into chat.')
        st.warning('WhatsApp uses Twilio and may incur charges. Join the Sandbox for testing; free-form messages require an active 24-hour reply window. For proactive alerts, configure an approved template.')
        for channel in ('email', 'whatsapp'):
            if st.button('Send test ' + channel, disabled=not prefs[channel+'_enabled']):
                try:
                    st.success(notify.send(channel,prefs[channel+'_to'],notify.TEST_PAYLOAD,notification_config()))
                except Exception:
                    st.error('Test not confirmed. Check provider settings and logs before trying again. No credentials are shown in this error.')
        if st.button('Send pending alerts',disabled=not (prefs['email_enabled'] or prefs['whatsapp_enabled'])):
            results = notify.dispatch(store,notification_config())
            if results: st.write(results)
            else: st.info('No unsent alerts for the enabled channels.')
    with st.expander('Delivery history'):
        st.caption('Accepted means the provider accepted the request, not that it reached your inbox or phone. Unknown requests are held without automatic retry. Mark read below does not send or cancel delivery.')
        delivery_history = notify.history(store)
        if delivery_history: st.dataframe(delivery_history, hide_index=True)
        else: st.write('No delivery attempts yet.')
    alerts = store.alerts()
    if not alerts: st.write('No alerts queued yet.')
    for alert in alerts:
        data = alert['payload']
        with st.container(border=True):
            st.write(f'{data["job"]["title"]} · {data["job"]["company"]} · {data["match"]["score"]}/100 at discovery')
            st.caption(alert['created'] + (' · Read' if alert['acknowledged'] else ' · Unread'))
            if not alert['acknowledged'] and st.button('Mark read',key=alert['job_id']):
                store.acknowledge(alert['job_id']); st.rerun()
    st.download_button('Export notification events',json.dumps(alerts,indent=2),file_name='careerpilot-notifications.json',mime='application/json')
else:
    st.header('A transparent career workflow')
    st.write('Profile → public job discovery → JD normalization → explained matching → saved jobs → notification queue')
    st.write('LangGraph coordinates the profile and company intelligence nodes. Separate modules handle ingestion, sources, scoring and persistence.')
    st.write('Weights: role 30, skills 30, experience 20, location 15, preferences 5. Missing evidence earns no points; coverage shows how much could be checked. Skills use an editable profile and a finite JD vocabulary. Experience extraction is numeric and should be reviewed.')
    st.write('Supported: Greenhouse, Lever (global/EU), and public JobPosting JSON-LD with up to 10 linked detail pages. No protected-site scraping, automatic applications or scheduled runs. Email and WhatsApp delivery are optional.')
    st.write('Future modules: interview intelligence, evidence-based resume tailoring, application tracking and scheduled discovery. The original v1 is preserved under legacy/.')
store.db.close()
