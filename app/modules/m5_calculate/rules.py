from collections import defaultdict
from decimal import Decimal
from app.modules.m4_segments.units import interval,label

SHARED=('sample_id','batch','product','analyte','method','sampled')

def _rank(report):
    return (report['reported'],Decimal(str(report['version'])))

def _unit_key(report):
    return str(report.get('reported_unit') or report.get('unit') or '').strip().lower()

def _interval(report):
    return interval(report['lower'],report['upper'],report.get('upper_exclusive'))

def _support_for(report,candidates):
    """Reports that state the same concentration interval as `report`.

    Intervals are compared as Decimals after M4 canonicalised every report to
    mg/kg, so mg/kg, ug/kg and ppb spellings can support one conclusion.
    """
    target=_interval(report)
    support=[r for r in candidates if _interval(r)==target]
    support.sort(key=lambda r:r['id'])
    return support

def _describe(chosen,support):
    if not support:return '无共同区间'
    units=[]
    for r in support:
        unit=str(r.get('reported_unit') or r.get('unit') or '')
        if unit and unit not in units:units.append(unit)
    # Use the chosen report's own canonical values for display so the printed
    # interval keeps that report's precision; all support members are equal.
    lower,upper,exclusive=_interval(chosen)
    span=label(lower,upper,exclusive)
    if len(units)>1:return '跨单位（'+'、'.join(units)+'）折算 mg/kg 后区间一致，可共同支撑结论 '+span
    if len(support)>1:return '同单位多份报告区间一致，可共同支撑结论 '+span
    return '单份报告支撑结论 '+span

def select_reports(reports):
    versions={}
    for r in reports:
        if r['id'] not in versions or Decimal(str(r['version']))>Decimal(str(versions[r['id']]['version'])):versions[r['id']]=r
    reports=list(versions.values());lookup={r['id']:r for r in reports};bad={};valid=[]
    # A relation is a replacement chain; detect cycles before following any edge.
    for r in reports:
        chain=[];current=r
        while current.get('relation'):
            if current['id'] in chain:
                for rid in chain:bad[rid]='REFERENCE'
                break
            chain.append(current['id']);parent=lookup.get(current['relation'])
            if parent is None:bad[r['id']]='REFERENCE';break
            if any(current[k]!=parent[k] for k in SHARED) or current['reported']<=parent['reported']:
                bad[r['id']]='REFERENCE';break
            current=parent
        if current['id'] in bad:bad[r['id']]='REFERENCE'
    grouped=defaultdict(list)
    for r in reports:
        if r['id'] not in bad:grouped[(r['sample_id'],r['batch'],r['product'],r['analyte'])].append(r)
    for key in sorted(grouped):
        rows=grouped[key]
        roots=[r for r in rows if not r['relation']]
        if len(roots)!=1:
            for r in rows:bad[r['id']]='CONFLICT'
            continue
        root=roots[0]
        # Only reports connected to the single primary sample result may supersede it.
        candidates=[r for r in rows if r['id'] not in bad]
        # Take the newest layer whose members agree on the mg/kg interval. A
        # tied layer that disagrees fails adoption: its dissenters are
        # quarantined with their reason, and the already-established conclusion
        # (the primary report, or the newest agreeing older layer) is retained.
        chosen=None;fallback=False
        for rank in sorted({_rank(r) for r in candidates},reverse=True):
            layer=[r for r in candidates if _rank(r)==rank]
            if len({_interval(r) for r in layer})>1:
                fallback=True
                # The primary report is the established conclusion; only the
                # contradictory newcomers are isolated, never the root itself.
                for r in layer:
                    if r['id']!=root['id']:bad[r['id']]='SUPERSEDE'
                if any(r['id']==root['id'] for r in layer):chosen=root;break
                continue
            chosen=sorted(layer,key=lambda r:r['id'])[0]
            break
        if chosen is None:
            # Every layer was contradictory: keep the primary report's own
            # conclusion so the group is not lost, and record the fallback.
            fallback=True;chosen=root
        candidates=[r for r in candidates if r['id'] not in bad]
        support=_support_for(chosen,candidates)
        chosen=dict(chosen)
        chosen['support']=[{'id':r['id'],'reported_unit':r.get('reported_unit',r.get('unit')),
            'result':r.get('reported_result',r.get('result')),'lod':r.get('reported_lod',r.get('lod')),
            'lower':r['lower'],'upper':r['upper'],'upper_exclusive':r.get('upper_exclusive'),
            'relation':r.get('relation','')} for r in support]
        chosen['support_ids']=[r['id'] for r in support]
        chosen['cross_unit']=len({_unit_key(r) for r in support})>1
        chosen['support_note']=_describe(chosen,support)
        if fallback:chosen['support_note']+='（复检采信失败，保留原结论）'
        chosen['fallback']=fallback
        valid.append(chosen)
    return valid,bad

def apply(state):
    chosen,bad=select_reports(state['measurements']);lines=set()
    for r in state['measurements']:
        if r['id'] in bad:
            lines.add(r['_line']);state['quarantine'].append({'line':r['_line'],'id':r['id'],'code':bad[r['id']],'raw':r['_raw']})
    state['rows']=[r for r in state['rows'] if r['_line'] not in lines]
    calculations=[{'id':r['id'],'line':r['_line'],'sample_id':r['sample_id'],'batch':r['batch'],'product':r.get('product',''),'analyte':r['analyte'],'method':r['method'],
        'standard':r['standard_id'],'lower':r['lower'],'upper':r['upper'],'upper_exclusive':r['upper_exclusive'],'limit':r['limit'],'unit':r.get('unit','mg/kg'),
        'reported_unit':r.get('reported_unit',r.get('unit')),'reported_result':r.get('reported_result',r.get('result')),'reported_lod':r.get('reported_lod',r.get('lod')),
        'code':r['code'],'replaces':r['relation'],'support':r['support'],'support_ids':r['support_ids'],'cross_unit':r['cross_unit'],
        'support_note':r['support_note'],'fallback':r['fallback']} for r in chosen if r['id'] not in bad]
    state['calculations']=calculations
    state['unit_support']=[{'id':r['id'],'sample_id':r['sample_id'],'analyte':r['analyte'],'batch':r['batch'],
        'interval':{'lower':r['lower'],'upper':r['upper'],'upper_exclusive':r['upper_exclusive'],'unit':r['unit'],'limit':r['limit']},
        'units':list(dict.fromkeys(x['reported_unit'] for x in r['support'])),'support_ids':r['support_ids'],
        'cross_unit':r['cross_unit'],'note':r['support_note'],'fallback':r['fallback']} for r in calculations if len(r['support'])>1 or r['fallback']]
    state['business']={'total':len(calculations),'pass':sum(r['code']=='PASS' for r in calculations),'fail':sum(r['code']=='FAIL' for r in calculations),'uncertain':sum(r['code']=='UNCERTAIN' for r in calculations),'unit':'检测项目'}
    # Every accepted sample/project group must carry exactly one conclusion.
    # This coverage follows the same merged interval used for the batch grade,
    # so a failed adoption that retains the primary conclusion still archives.
    groups={(r['sample_id'],r['batch'],r.get('product',''),r['analyte']) for r in state['rows']}
    covered={(r['sample_id'],r['batch'],r.get('product',''),r['analyte']) for r in calculations}
    state['coverage']={'groups':len(groups),'covered':len(covered),'complete':groups==covered,
        'cross_unit':sum(1 for r in calculations if r['cross_unit']),'fallback':sum(1 for r in calculations if r['fallback'])}
    return state
