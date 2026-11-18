import csv,io,json
from app import store
from app.modules.m7_archive.export_out import bundle,checksum
from app.workflow import load,run
from app.errors import DomainError
import pytest

def test_export_rows(state):
    rows=list(csv.reader(io.StringIO(bundle(state).lstrip('\ufeff'))));assert rows[0][0]=='记录类型' and rows[1][0]=='运行清单'
def test_export_quarantine(state):
    assert bundle(state).count('隔离')==len(state['quarantine'])
def test_checksum_stable(state):
    assert checksum(state)==state['archive']['sha256'] and len(checksum(state))==64
def test_archive_ready(state):
    assert state['archive']['ready'] is True
def test_idempotent_store(state,tmp_path,monkeypatch):
    monkeypatch.setenv('DB_PATH',str(tmp_path/'r.db'))
    a=store.save(state['run_id'],state);b=store.save(state['run_id'],state)
    assert a['run_id']==b['run_id'] and len(store.history())==1
def test_stale_review(state,tmp_path,monkeypatch):
    # TRAP-26
    monkeypatch.setenv('DB_PATH',str(tmp_path/'r.db'));store.save(state['run_id'],state)
    assert store.review(state['run_id'],1,'通过')['review_version']==2
    with pytest.raises(DomainError) as e:store.review(state['run_id'],1,'退回')
    assert e.value.status==409
def test_persistent_new_connection(state,tmp_path,monkeypatch):
    monkeypatch.setenv('DB_PATH',str(tmp_path/'r.db'));store.save(state['run_id'],state)
    assert store.get(state['run_id'])['calculations']==state['calculations']


def test_archive_keeps_original_reports_and_isolation_reasons(state):
    # 原始报告（含被替代的初检）与隔离原因都必须在证据中留痕
    text = bundle(state)
    assert '原始报告' in text and '初检报告' in text
    assert '隔离原因' in text or '原因码' in text
    from app.reasons import REASONS
    for q in state['quarantine']:
        assert REASONS[q['code']] in text


def test_archive_records_cross_unit_support():
    from app.modules.m5_calculate.rules import apply as calculate
    header = 'id,sample_id,batch,product,analyte,method,version,sampled,reported,result,unit,lod,relation,note'
    s = run((header + '\n'
        + '00001,S001,B001,苹果,P01,LC-MS/MS,1,2026-08-01,2026-08-02,0.004,mg/kg,0.001,,初检\n'
        + '00002,S001,B001,苹果,P01,LC-MS/MS,2,2026-08-01,2026-08-03,4,ug/kg,1,00001,复检\n').encode(), {})
    assert '跨单位支撑' in bundle(s) and s['archive']['cross_unit_projects'] == 1


def test_rerun_same_source_keeps_recorded_conclusion(state,tmp_path,monkeypatch):
    # 同源重跑不得新增或改换已确认结论
    monkeypatch.setenv('DB_PATH',str(tmp_path/'r.db'));store.save(state['run_id'],state)
    store.review(state['run_id'],1,'通过')
    changed=json.loads(json.dumps(state));changed['calculations']=[];changed['reconcile']['grades']=[]
    after=store.save(state['run_id'],changed)
    assert len(store.history())==1 and after['review_version']==2 and after['decision']=='通过'
    assert after['calculations']==state['calculations']


def test_archive_not_ready_when_coverage_has_gap(state):
    # 判级/归档沿用同一区间：缺失结论的项目组使归档不可用
    from app.modules.m7_archive.service import execute
    broken=json.loads(json.dumps(state));broken['calculations']=broken['calculations'][1:]
    broken['coverage']={'groups':24,'covered':23,'complete':False,'cross_unit':0,'fallback':0}
    out=execute(broken)
    assert out['archive']['ready'] is False and out['archive']['coverage_complete'] is False
