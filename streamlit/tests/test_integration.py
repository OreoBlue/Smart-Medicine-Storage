"""Offline unit + mocked HTTP contract tests; NOT an actual Wokwi/Firebase live test."""
from __future__ import annotations
import json
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from dashboard_data import device_freshness, effective_mode, firebase_time, normalize_events, sensor_value
from demo import new_demo, snapshot, step, change, toggle_door
from firebase_client import FirebaseClient, FirebaseError, AuthState

ROOT = Path(__file__).resolve().parents[2]


class TestDataset(unittest.TestCase):
    def test_real_export_compatible(self):
        export = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'legacy_export_sample.json').read_text())
        if export:
            self.assertIn('telemetry', export)
            self.assertEqual(export['controls']['mode'], '')  # Found in upload; seed repairs this
            self.assertEqual(effective_mode(export['controls'], export['telemetry']), 'AUTO')
            self.assertEqual(device_freshness(export['telemetry'], int(time.time()*1000))[0], 'UNKNOWN')

    def test_freshness(self):
        now=1_800_000_000_000
        self.assertEqual(device_freshness({'updated_at':now-4500},now),('ONLINE',4500))
        self.assertEqual(device_freshness({'updated_at':now-17000},now)[0],'STALE')
        self.assertEqual(device_freshness({'temperature':5},now)[0],'UNKNOWN')
        self.assertEqual(device_freshness(None,now)[0],'NO_DATA')

    def test_format(self):
        self.assertIsNone(sensor_value(-999))
        self.assertIsNone(sensor_value(float('nan')))
        self.assertIsNone(sensor_value(True))
        self.assertTrue(firebase_time(1_800_000_000_000).endswith('WIB'))
        raw={'-A':{'type':'START'},'-B':{'type':'LATEST'}}
        self.assertEqual(normalize_events(raw)[0]['type'],'LATEST')

    def test_wiring(self):
        d=json.loads((ROOT/'wokwi'/'diagram.json').read_text())
        conns={tuple(e[:2]) for e in d['connections']}
        for a,b in [ ('esp:D4','dht1:SDA'),('esp:D34','ldr1:AO'), ('esp:D32','sw1:2'),
                     ('esp:D33','btn1:1.l'),('esp:D26','r1:1'),('esp:D25','r2:1'),('esp:D27','bz1:2')]:
            self.assertIn((a,b),conns)
        sw=next(p for p in d['parts'] if p['id']=='sw1')
        self.assertEqual(sw['attrs']['value'],'1')

    def test_security_rules_and_seed(self):
        seed=json.loads((ROOT/'firebase'/'seed_controls.json').read_text())
        self.assertEqual(seed['controls'],{'mode':'AUTO','manual_cooler_req':False,'inject_sensor_fault':False})
        rules=json.loads((ROOT/'firebase'/'rules.example.json').read_text())['rules']
        self.assertFalse(rules['.read'])
        self.assertFalse(rules['.write'])
        self.assertIn('ISI_UID_DEVICE', rules['telemetry']['.write'])
        self.assertIn('ISI_UID_OPERATOR', rules['controls']['.write'])

class TestDemo(unittest.TestCase):
    def test_threshold_and_hysteresis(self):
        d=new_demo()
        d['temperature']=8.0;step(d,2200)
        self.assertTrue(d['cooler_on'])
        d['temperature']=7.0;step(d,2200)
        self.assertTrue(d['cooler_on'])
        d['temperature']=5.0;step(d,2200)
        self.assertFalse(d['cooler_on'])
        d['temperature']=12.0;step(d,2200)
        self.assertTrue(d['temp_alarm'])
        d['temperature']=11.0;step(d,2200)
        self.assertTrue(d['temp_alarm'])
        d['temperature']=10.0;step(d,2200)
        self.assertFalse(d['temp_alarm'])

    def test_door_immediate_interlock_and_delayed_alarm(self):
        d=new_demo(); change(d,mode='MANUAL');change(d,manual_cooler_req=True)
        self.assertTrue(d['cooler_on'])
        toggle_door(d)
        self.assertFalse(d['cooler_on'])
        self.assertFalse(d['door_alarm'])
        step(d,9000);self.assertFalse(d['door_alarm'])
        step(d,1000);self.assertTrue(d['door_alarm'])
        self.assertEqual(d['door_violations'],1)
        self.assertFalse(change(d,manual_cooler_req=True))
        toggle_door(d)
        self.assertFalse(d['door_alarm'])

    def test_sensor_interlock(self):
        d=new_demo();change(d,mode='MANUAL');change(d,manual_cooler_req=True)
        self.assertTrue(d['cooler_on'])
        change(d,inject_sensor_fault=True)
        self.assertEqual(d['state'],'FAULT')
        self.assertFalse(d['cooler_on'])
        self.assertFalse(change(d,manual_cooler_req=True))
        self.assertTrue(snapshot(d)['telemetry']['sensor_fault'])

    def test_light_and_humidity_alarm(self):
        d=new_demo();d['light_pct']=60;d['humidity']=65;step(d,3000)
        self.assertTrue(d['light_alarm'])
        self.assertTrue(d['humidity_alarm'])
        self.assertEqual(d['state'],'HUM_ALARM')
        d['humidity']=53;d['light_pct']=40;step(d,3000)
        self.assertFalse(d['humidity_alarm'])
        self.assertFalse(d['light_alarm'])

class TestRest(unittest.TestCase):
    def setUp(self):
        self.session=Mock()
        self.client=FirebaseClient('https://iotkel3-4c1aa-default-rtdb.firebaseio.com','PUBLIC_API_KEY',session=self.session)
        self.auth=AuthState('FAKE_TOKEN','FAKE_REFRESH','OP_UID','op@example.com',time.time()+3600)

    def response(self,payload):
        r=Mock(status_code=200);r.json.return_value=payload;return r

    def test_two_way_synchronization_contract(self):
        database={'telemetry':{'temperature':6.0,'humidity':44,'updated_at':int(time.time()*1000),
                               'cooler_on':False,'state':'NORMAL'},
                  'controls':{'mode':'AUTO','manual_cooler_req':False,'inject_sensor_fault':False},
                  'event_logs':{'-abc':{'type':'BOOT','detail':'start','timestamp_ms':200}}}
        sent=[]
        def responder(method,url,**kwargs):
            root=url.split('/')[-1].split('.')[0]
            if method=='PATCH':
                database[root].update(kwargs['json']);sent.append(kwargs['json']);return self.response(database[root])
            if method=='GET':return self.response(database[root])
            raise AssertionError(f'unexpected {method}')
        self.session.request.side_effect=responder
        values,auth=self.client.read_dashboard(self.auth)
        self.assertEqual(values['telemetry']['temperature'],6.0)
        self.assertEqual(values['controls']['mode'],'AUTO')
        self.client.write_controls(auth,{'mode':'MANUAL','manual_cooler_req':True})
        self.assertEqual(sent[-1],{'mode':'MANUAL','manual_cooler_req':True})
        self.assertEqual(database['controls']['mode'],'MANUAL')
        # read-back demonstrates path/schema handoff, not ESP32 actual execution
        result,_=self.client.read_dashboard(auth)
        self.assertEqual(result['controls']['mode'],'MANUAL')
        self.assertFalse(result['telemetry']['cooler_on'])

    def test_invalid_control_rejected(self):
        for change in ({'cooler_on':True},{'mode':'BROKEN'},{'inject_sensor_fault':1}):
            with self.assertRaises(ValueError):self.client.write_controls(self.auth,change)

    def test_expired_refresh(self):
        self.session.request.return_value=self.response({'id_token':'NEW','refresh_token':'R','user_id':'OP_UID','expires_in':'3600'})
        fresh=self.client.ensure_auth(AuthState('OLD','R','OP_UID','op@example.com',time.time()-20))
        self.assertEqual(fresh.id_token,'NEW')

    def test_no_open_url(self):
        for url in ['http://iotkel3.firebaseio.com','https://evil.test','https://one.firebaseio.com/foo',
                    'https://a.firebaseio.com?q=x']:
            with self.assertRaises(FirebaseError):FirebaseClient(url,'KEY')

if __name__=='__main__':unittest.main()
