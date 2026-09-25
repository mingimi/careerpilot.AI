"""The v1 Career Manager pattern, upgraded to persistent company intelligence."""
from typing import TypedDict
from langgraph.graph import StateGraph, END
from .discovery import discover

class CareerState(TypedDict, total=False):
    store: object
    profile: dict
    threshold: int
    reports: list
    logs: list

def profile_node(state):
    return {'profile':state['store'].profile(), 'logs':['Loaded reviewed candidate profile.']}

def discovery_node(state):
    reports = []
    store = state['store']
    for company in store.companies():
        try:
            jobs, status = discover(company['name'], company['url'])
            new, alerts = store.ingest(company['id'],jobs,state['profile'],state['threshold'])
            message = f'{len(jobs)} jobs • {new} new • {alerts} alerts. {status}'
        except Exception as exc:
            # One malformed or unavailable company must not stop the watchlist.
            message = f'Scan failed: {type(exc).__name__}: {exc}'
        store.status(company['id'],message)
        reports.append(dict(company=company['name'],status=message))
    return {'reports':reports,'logs':state['logs'] + ['Discovered, normalized and scored jobs; persisted new-job events.']}

def build_graph():
    graph = StateGraph(CareerState)
    graph.add_node('profile',profile_node)
    graph.add_node('company_intelligence',discovery_node)
    graph.set_entry_point('profile')
    graph.add_edge('profile','company_intelligence')
    graph.add_edge('company_intelligence',END)
    return graph.compile()

def scan(store, threshold=75):
    if not store.profile(): raise ValueError('Save your profile before scanning.')
    return build_graph().invoke({'store':store,'threshold':threshold})
