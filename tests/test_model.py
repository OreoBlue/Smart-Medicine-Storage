import json
from pathlib import Path
from src.model import number,normalize_telemetry,normalize_events,event_counts,sample_demo,marker,connection_state

ROOT=Path(__file__).resolve().parents[1]
SAMPLE=json.loads((ROOT/'data'/'demo_snapshot.json').read_text(encoding='utf-8'))

def test_real_export_fields():
    s=normalize_telemetry(SAMPLE['telemetry'])
    assert s['temperature']==24
    assert s['cooler_on'] is True
    assert s['light_adc']==1001
    assert s['mode']=='AUTO'
    assert s['light_anomaly'] is True
    assert s['uptime_ms']==23459

def test_missing_invalid_telemetry():
    s=normalize_telemetry({'temperature':-999,'humidity':float('nan'),'door_open':'false'})
    assert s['temperature'] is None
    assert s['humidity'] is None
    assert s['door_open'] is None
    assert number('N/A') is None

def test_events_legacy_uptime_only():
    events=normalize_events(SAMPLE['event_logs'])
    assert len(events)==len(SAMPLE['event_logs'])
    assert events[0]['Waktu server']=='—'
    assert all('Uptime ESP32' in row for row in events)
    assert sum(event_counts(events).values())==len(events)

def test_demo_does_not_modify_source():
    original=dict(SAMPLE['telemetry']); demo=sample_demo(original,8)
    assert demo['boot_id']=='LOCAL-DEMO'
    assert original==SAMPLE['telemetry']
    assert 0<=demo['light_pct']<=100

def test_status_initial_not_online():
    s=normalize_telemetry(SAMPLE['telemetry'])
    assert connection_state(s,100,None,103)[0]=='UNCHECKED'
    assert connection_state(s,100,None,116)[0]=='STALE'
    assert connection_state(s,100,104,108)[0]=='FLOWING'
    assert marker(s)[1]==23459

def test_empty_snapshot():
    assert connection_state(normalize_telemetry(None),None,None,123)[0]=='EMPTY'

def test_new_firmware_aliases():
    s=normalize_telemetry({'state':'HUM_ALARM','mode':'Auto','alarm_on':True,'humidity_alarm':True,'light_alarm':True,'light_raw':650,'updated_at':1760000000000})
    assert s['alarm_led_on'] is True and s['buzzer_on'] is True
    assert s['humidity_warning'] and s['light_anomaly']
    assert s['mode']=='AUTO' and s['light_adc']==650
