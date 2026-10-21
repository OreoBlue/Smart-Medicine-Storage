import pytest
from src.firebase_reader import FirebaseReader,FirebaseReadError

class FakeResponse:
    def __init__(self,status,data):self.status_code=status;self.data=data
    def json(self):return self.data
class FakeSession:
    def __init__(self):self.calls=[];self.get_count=0
    def post(self,url,**kw):
        self.calls.append(('POST',url,kw))
        return FakeResponse(200,{'id_token':'TEST-ID-TOKEN','refresh_token':'NEW_REFRESH_TOKEN','expires_in':'3600'})
    def get(self,url,**kw):
        self.calls.append(('GET',url,kw));self.get_count+=1
        return FakeResponse(200, {'temperature':24} if 'telemetry' in url else {'event1':{'type':'BOOT','timestamp_ms':10,'detail':'ok'}})

def make(session):
    return FirebaseReader('https://test-default-rtdb.firebaseio.com','API_KEY','REFRESH_TOKEN',session=session,clock=lambda:100)

def test_reads_only_approved_paths():
    f=FakeSession();a=make(f)
    telemetry,events=a.fetch()
    assert telemetry['temperature']==24 and 'event1' in events
    assert sum(x[0]=='POST' for x in f.calls)==1
    assert sum(x[0]=='GET' for x in f.calls)==2
    assert all('/telemetry.json' in v[1] or '/event_logs.json' in v[1] for v in f.calls if v[0]=='GET')
    assert all(v[2]['params']['auth']=='TEST-ID-TOKEN' for v in f.calls if v[0]=='GET')
    assert f.calls[-1][2]['params']['limitToLast']==120
    assert all(v[0]!='PUT' and v[0]!='PATCH' and v[0]!='DELETE' for v in f.calls)

def test_forbid_controls():
    with pytest.raises(ValueError): make(FakeSession()).read('controls')

def test_forbid_non_https():
    with pytest.raises(ValueError): FirebaseReader('http://example.com','KEY','TOKEN')

def test_403_reports_rules_without_token():
    class Denied(FakeSession):
        def get(self,url,**kw):return FakeResponse(403,{'error':'Permission denied'})
    with pytest.raises(FirebaseReadError,match='403') as ex: make(Denied()).read('telemetry')
    assert 'TEST-ID-TOKEN' not in str(ex.value)
