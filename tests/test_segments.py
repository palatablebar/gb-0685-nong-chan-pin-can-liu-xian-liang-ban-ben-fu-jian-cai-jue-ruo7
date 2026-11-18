import pytest
from app.workflow import run
from app.modules.m4_segments.rules import concentration
from app.errors import DomainError

def test_detection_interval_crosses_limit():
    r=concentration('<0.01','mg/kg','0.01','0.005');assert r['code']=='UNCERTAIN' and r['lower']=='0' and r['upper']=='0.01'
def test_detection_interval_below_limit():assert concentration('<0.01','mg/kg','0.01','0.01')['code']=='PASS'
def test_unit_conversion():
    # TRAP-15
    r=concentration('30','ug/kg','1','0.02');assert r['upper']=='0.030' and r['code']=='FAIL'
def test_numeric_equal_limit_passes():assert concentration('0.005','mg/kg','0.001','0.005')['code']=='PASS'
def test_real_initial_uncertain(raw):assert run(raw,{},4)['measurements'][0]['code']=='UNCERTAIN'
def test_real_second_pesticide_exceeds(raw):assert run(raw,{},4)['measurements'][2]['code']=='FAIL'
def test_lod_inconsistent_rejected():
    with pytest.raises(DomainError):concentration('<0.01','mg/kg','0.02','0.005')


def test_unit_spellings_resolve_to_same_scale():
    # TRAP-15：μg/kg、ppb 等写法与 ug/kg 同尺度，不得因写法不同而隔离
    from app.modules.m4_segments.units import resolve
    from decimal import Decimal
    for unit in ('μg/kg', 'µg/kg', 'UG/KG', 'ppb', 'ng/g'):
        canonical, factor, shown = resolve(unit)
        assert canonical == 'mg/kg' and factor == Decimal('.001') and shown
    assert resolve('mg／kg')[1] == Decimal(1)
    assert resolve('ppm')[1] == Decimal(1)
