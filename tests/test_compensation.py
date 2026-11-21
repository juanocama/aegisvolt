import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))

def test_state_model_shape():
    saga={"state":"COMPENSATION_FAILED","reservation_status":"compensating","charge_status":"compensating","error":"timeout"}
    assert saga["state"]=="COMPENSATION_FAILED"
    assert saga["reservation_status"]=="compensating"
