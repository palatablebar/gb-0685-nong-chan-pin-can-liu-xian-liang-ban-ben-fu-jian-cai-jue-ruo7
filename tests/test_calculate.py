from copy import deepcopy
from app.workflow import run
from app.modules.m5_calculate.rules import select_reports,apply

def test_real_retest_replaces_initial(raw):
    s=run(raw,{});assert len(s['calculations'])==24 and s['calculations'][0]['id']=='00002' and s['calculations'][0]['replaces']=='00001'
def test_real_other_analyte_not_erased(raw):
    s=run(raw,{});assert s['business']=={'total':24,'pass':12,'fail':12,'uncertain':0,'unit':'检测项目'}
def test_wrong_sample_reference_rejected(raw):
    s=run(raw,{},4);s['measurements'][1]['sample_id']='OTHER';chosen,bad=select_reports(s['measurements']);assert bad['00002']=='REFERENCE' and any(r['id']=='00001' for r in chosen)
def test_wrong_method_reference_rejected(raw):
    s=run(raw,{},4);s['measurements'][1]['method']='GC-MS';_,bad=select_reports(s['measurements']);assert bad['00002']=='REFERENCE'
def test_future_reference_rejected(raw):
    s=run(raw,{},4);s['measurements'][1]['reported']='2026-08-01';_,bad=select_reports(s['measurements']);assert bad['00002']=='REFERENCE'
def test_cycle_rejected(raw):
    # TRAP-20
    s=run(raw,{},4);s['measurements'][0]['relation']='00002';_,bad=select_reports(s['measurements']);assert '00001' in bad and '00002' in bad
def test_input_order_cannot_change_verdict(raw):
    a=run(raw,{},4);b=deepcopy(a);b['measurements'].reverse();ca,ba=select_reports(a['measurements']);cb,bb=select_reports(b['measurements']);assert sorted(r['id'] for r in ca)==sorted(r['id'] for r in cb) and ba==bb


def test_same_report_id_latest_revision_is_authoritative(raw):
    s=run(raw,{},4);new=dict(s['measurements'][1],version='3',lower='0.006',upper='0.006',code='FAIL');s['measurements'].append(new);chosen,bad=select_reports(s['measurements'])
    assert next(r for r in chosen if r['id']=='00002')['code']=='FAIL' and '00002' not in bad


def _csv(rows):
    header = 'id,sample_id,batch,product,analyte,method,version,sampled,reported,result,unit,lod,relation,note'
    return (header + '\n' + '\n'.join(rows) + '\n').encode()


def test_cross_unit_retest_supports_one_conclusion():
    # 原检 mg/kg、复检 ug/kg 写同一浓度：折算后区间一致，可共同支撑
    s = run(_csv([
        '00001,S001,B001,苹果,P01,LC-MS/MS,1,2026-08-01,2026-08-02,0.004,mg/kg,0.001,,初检',
        '00002,S001,B001,苹果,P01,LC-MS/MS,2,2026-08-01,2026-08-03,4,ug/kg,1,00001,复检',
    ]), {})
    calc = s['calculations'][0]
    assert calc['id'] == '00002' and calc['code'] == 'PASS' and calc['cross_unit'] is True
    assert calc['support_ids'] == ['00001', '00002']
    assert '跨单位' in calc['support_note']
    support = s['unit_support'][0]
    assert support['units'] == ['mg/kg', 'ug/kg'] and support['interval']['lower'] == '0.004'


def test_equal_interval_after_unit_conversion_is_not_conflict():
    # 0.1 mg/kg 与 100 ug/kg 数值写法不同但区间相同，不得判为并列矛盾
    s = run(_csv([
        '00001,S001,B001,苹果,P01,LC-MS/MS,1,2026-08-01,2026-08-02,0.1,mg/kg,0.01,,初检',
        '00002,S001,B001,苹果,P01,LC-MS/MS,2,2026-08-01,2026-08-03,100,ug/kg,10,00001,复检A',
        '00003,S001,B001,苹果,P01,LC-MS/MS,2,2026-08-01,2026-08-03,0.1,mg/kg,0.01,00001,复检B',
    ]), {})
    assert s['calculations'][0]['id'] == '00002' and s['calculations'][0]['support_ids'] == ['00001', '00002', '00003']
    assert not s['quarantine']


def test_adoption_failure_retains_previous_conclusion():
    # 并列复检在折算后区间矛盾：矛盾复检隔离并保留旧结论，区间供判级与归档沿用
    s = run(_csv([
        '00001,S001,B001,苹果,P01,LC-MS/MS,1,2026-08-01,2026-08-02,0.004,mg/kg,0.001,,初检',
        '00002,S001,B001,苹果,P01,LC-MS/MS,2,2026-08-01,2026-08-03,0.010,mg/kg,0.001,00001,复检A',
        '00003,S001,B001,苹果,P01,LC-MS/MS,2,2026-08-01,2026-08-03,20,ug/kg,1,00001,复检B',
    ]), {})
    calc = s['calculations'][0]
    assert calc['id'] == '00001' and calc['code'] == 'PASS' and calc['fallback'] is True
    assert {q['id'] for q in s['quarantine']} == {'00002', '00003'}
    assert all(q['code'] == 'SUPERSEDE' for q in s['quarantine'])
    assert all(q['raw'] for q in s['quarantine'])
    assert s['coverage']['complete'] is True and s['archive']['ready'] is True
    grade = s['reconcile']['grades'][0]
    assert grade['code'] == 'PASS' and grade['basis']['lower'] == '0.004' and grade['fallback'] is True
