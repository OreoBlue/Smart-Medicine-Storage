from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def test_json_files():
    for file in ('firebase/rules.example.json','firebase/controls.initial.json','data/demo_snapshot.json','wokwi_reference/diagram.json'):
        json.loads((ROOT/file).read_text(encoding='utf-8'))

def test_diagram_pin_mapping():
    d=json.loads((ROOT/'wokwi_reference/diagram.json').read_text())
    pairs={(c[0],c[1]) for c in d['connections']}
    for link in [('esp:D4','dht1:SDA'),('esp:D34','ldr1:AO'),('esp:D32','sw1:2'),('esp:D33','btn1:1.l'),('esp:D26','r1:1'),('esp:D25','r2:1'),('esp:D27','bz1:2')]:
        assert link in pairs

def test_no_firebase_database_write_calls_from_dashboard():
    src=(ROOT/'src/firebase_reader.py').read_text()
    assert '.put(' not in src and '.patch(' not in src and '.delete(' not in src
    assert 'self.session.get(' in src
    assert (ROOT/'.streamlit/secrets.toml').exists() is False
