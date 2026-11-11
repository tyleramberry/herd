import json, threading
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from herd import tools
from herd.dashboard import plugin_api as api
@pytest.fixture
def client(tmp_path,monkeypatch):
 monkeypatch.setattr(api,'_db_path',lambda:tmp_path/'probe.db'); monkeypatch.setattr(api,'_initialized',set()); monkeypatch.setattr(api,'_broadcast',lambda m:None); app=FastAPI(); app.include_router(api.router,prefix='/api/plugins/hermes-multiplayer'); return TestClient(app)
def ch(c,n): return c.post('/api/plugins/hermes-multiplayer/channels',json={'name':n}).json()
def post(c,i,**d): return c.post(f'/api/plugins/hermes-multiplayer/channels/{i}/messages',json=d)
def ev(n,v): print(f'PROBE {n}: {v}')
def test_1(client):
 a,b=ch(client,'alpha'),ch(client,'beta'); x=post(client,a['id'],id='same',content='original').json(); y=post(client,b['id'],id='same',content='different').json(); aa=client.get(f"/api/plugins/hermes-multiplayer/channels/{a['id']}/messages").json(); bb=client.get(f"/api/plugins/hermes-multiplayer/channels/{b['id']}/messages").json(); ev(1,{'replay':y,'alpha':len(aa),'beta':len(bb)}); assert x==y and len(aa)==1 and not bb
def test_2(client):
 i=ch(client,'time')['id']; u=f'/api/plugins/hermes-multiplayer/channels/{i}/messages'; ts=['2026-11-04T12:00:00Z','2026-11-04T12:00:00+00:00','2026-11-04T12:00:00.123456+00:00']
 for n,t in enumerate(ts): assert post(client,i,id=f't{n}',content=f'm{n}',created_at=t).status_code==200
 o={t:[m['id'] for m in client.get(u,params={'after':t}).json()] for t in ts}; ev(2,o); assert o[ts[0]]==[] and o[ts[1]]==['t2','t0'] and o[ts[2]]==['t0']
def test_3(client):
 i=ch(client,'large')['id']; s=('🌿🧪 café 漢字 — '*700)+'END✨'; post(client,i,content=s); got=client.get(f'/api/plugins/hermes-multiplayer/channels/{i}/messages').json()[0]['content']; ev(3,{'chars':len(s),'bytes':len(s.encode()),'intact':got==s}); assert got==s and len(s.encode())>=10000
def test_4(client):
 ch(client,'ops'); d=client.post('/api/plugins/hermes-multiplayer/channels',json={'name':'#ops'}); s=ch(client,'  #  design  '); h=client.post('/api/plugins/hermes-multiplayer/channels',json={'name':'#'}); b=client.post('/api/plugins/hermes-multiplayer/channels',json={'name':'   '}); t={n:json.loads(tools.herd_post({'channel':n,'content':'ok'})) for n in ['#ops','ops']}; v={'duplicate':d.status_code,'trimmed':s['name'],'hash':h.status_code,'blank':b.status_code,'tool_ok':{n:x['ok'] for n,x in t.items()}}; ev(4,v); assert d.status_code==409 and s['name']=='design' and h.status_code==b.status_code==422 and all(x['ok'] for x in t.values())
def test_5(client):
 b=ch(client,'target'); c=ch(client,b['id']); r=api.resolve_channel(b['id']); p=api.post_agent_message(b['id'],'x'); v={'B_id':b['id'],'collision_id':c['id'],'resolved':r['id'],'posted':p['channel_id']}; ev(5,v); assert r['id']==b['id'] and p['channel_id']==b['id']
def test_6(client):
 u='/api/plugins/hermes-multiplayer/participants'; a=client.post(u,json={'id':'p','display_name':'Old','kind':'human'}).json(); z=client.post(u,json={'id':'p','display_name':'New','kind':'garbage-🤖'}); m=client.post(u,json={}); q=next(x for x in client.get(u).json() if x['id']=='p'); v={'same_id':z.json()['id']==a['id'],'name':q['display_name'],'kind':q['kind'],'missing':m.status_code}; ev(6,v); assert z.status_code==200 and q['display_name']=='New' and q['kind']=='garbage-🤖' and m.status_code==422
def test_7(client,tmp_path,monkeypatch):
 db=tmp_path/'concurrent.db'; monkeypatch.setattr(api,'_db_path',lambda:db); monkeypatch.setattr(api,'_initialized',set()); i=ch(client,'concurrent')['id']; errs=[]; bar=threading.Barrier(2)
 def run(n):
  try:
   with TestClient(client.app) as c:
    bar.wait()
    for k in range(20):
     r=post(c,i,id=f'{n}-{k}',content='x')
     if r.status_code!=200: errs.append(r.status_code)
  except Exception as e: errs.append(repr(e))
 ts=[threading.Thread(target=run,args=(n,)) for n in range(2)]; [t.start() for t in ts]; [t.join() for t in ts]; rows=client.get(f'/api/plugins/hermes-multiplayer/channels/{i}/messages').json(); ev(7,{'rows':len(rows),'errors':errs}); assert len(rows)==40 and not errs
def test_8(client):
 cases={'unknown':{'channel':'absent','content':'x'},'empty':{'channel':'general','content':''},'whitespace':{'channel':'general','content':'  '},'missing':{},'none':{'channel':'general','content':None}}; o={}
 for n,a in cases.items():
  try: x=json.loads(tools.herd_post(a)); o[n]={'valid_json':True,'ok':x.get('ok'),'error':x.get('error')}
  except Exception as e: o[n]={'valid_json':False,'error':repr(e)}
 ev(8,o); assert all(x['valid_json'] and x['ok'] is False and isinstance(x['error'],str) and x['error'] and 'Traceback' not in str(x) for x in o.values())
def test_9(client,monkeypatch):
 es=[]; monkeypatch.setattr(api,'_broadcast',lambda m:es.append(dict(m))); i=ch(client,'broadcast')['id']; a=post(client,i,id='replay',content='one').json(); n=len(es); b=post(client,i,id='replay',content='two').json(); ev(9,{'original_calls':n,'after_replay':len(es),'same_stored':a==b}); assert n==1 and len(es)==2 and a==b
