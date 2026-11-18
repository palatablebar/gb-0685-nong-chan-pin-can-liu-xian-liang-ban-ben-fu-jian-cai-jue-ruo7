import io,csv,json,hashlib
from app.reasons import REASONS

HEADER=['记录类型','批次','来源行','业务ID','原因码','内容','说明']

def bundle(state):
    out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(HEADER)
    rid=state.get('run_id','preview')
    writer.writerow(['运行清单',rid,'','','',json.dumps(state.get('manifest',{}),ensure_ascii=False,sort_keys=True),''])
    writer.writerow(['对账',rid,'','','',json.dumps(state.get('reconcile',{}),ensure_ascii=False,sort_keys=True),''])
    # Every accepted source report is kept, including the initial report that a
    # retest superseded, so the original record is never lost from evidence.
    for row in state.get('rows',[]):
        writer.writerow(['原始报告',row.get('batch',''),row.get('_line',''),row.get('id',''),'',json.dumps(row.get('_raw',row),ensure_ascii=False,sort_keys=True),row.get('unit','')])
    for row in state.get('calculations',[]):
        writer.writerow(['计算',rid,row.get('line',''),row.get('id',''),row.get('code',''),json.dumps(row,ensure_ascii=False,sort_keys=True),row.get('support_note','')])
    # Cross-unit support is recorded as its own evidence line: which reports
    # share one mg/kg interval and therefore may jointly carry the conclusion.
    for row in state.get('unit_support',[]):
        writer.writerow(['跨单位支撑',row.get('batch',''),'',' / '.join(row.get('support_ids',[])),'',
            json.dumps(row,ensure_ascii=False,sort_keys=True),row.get('note','')])
    for row in state.get('quarantine',[]):
        code=row.get('code','')
        writer.writerow(['隔离',rid,row.get('line',''),row.get('id',''),code,
            json.dumps({'code':code,'reason':REASONS.get(code,''),'raw':row.get('raw',{})},ensure_ascii=False,sort_keys=True),REASONS.get(code,'')])
    return '\ufeff'+out.getvalue()

def checksum(state):
    return hashlib.sha256(bundle(state).encode('utf-8')).hexdigest()
