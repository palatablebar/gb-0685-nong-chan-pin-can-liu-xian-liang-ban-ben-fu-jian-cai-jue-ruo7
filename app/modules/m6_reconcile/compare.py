from collections import defaultdict
from app.modules.m4_segments.units import verdict
RANK={'PASS':0,'UNCERTAIN':1,'FAIL':2}

def balance(state):
    accepted=len(state['rows']);isolated=len(state['quarantine']);accounted=accepted+isolated+state['blank_count']+state['header_count']+state['duplicate_count']
    batches=defaultdict(list)
    for r in state['calculations']:batches[r['batch']].append(r)
    grades=[]
    for batch,rows in sorted(batches.items()):
        # Grade from the merged mg/kg interval (the same interval the M5
        # conclusion and the archive eligibility use), so a batch level always
        # follows the concentration range the accepted reports jointly support.
        graded=[(r,verdict(r['lower'],r['upper'],r['limit'])) for r in rows]
        code=max((c for _,c in graded),key=lambda c:RANK[c])
        decisive=sorted((r for r,c in graded if c==code),key=lambda r:(r['sample_id'],r['analyte']))[0]
        support=[r for r in rows if len(r.get('support',[]))>1]
        grades.append({'batch':batch,'code':code,'projects':len(rows),'samples':len({r['sample_id'] for r in rows}),
            # The batch grade is carried by the merged interval of the decisive
            # project, so a cross-unit retest that supports PASS/FAIL is used.
            'basis':{'id':decisive['id'],'analyte':decisive['analyte'],'lower':decisive['lower'],'upper':decisive['upper'],
                'upper_exclusive':decisive['upper_exclusive'],'unit':decisive.get('unit','mg/kg'),'limit':decisive['limit'],
                'source_ids':decisive.get('support_ids',[decisive['id']]),'units':[s.get('reported_unit') for s in decisive.get('support',[])]},
            'support_note':decisive['support_note'],'cross_unit':any(r.get('cross_unit') for r in rows),
            'fallback':any(r.get('fallback') for r in rows),'supported':len(support)})
    return {'input':state['input_count'],'accepted':accepted,'isolated':isolated,'blank':state['blank_count'],'headers':state['header_count'],'duplicates':state['duplicate_count'],'accounted':accounted,'balanced':accounted==state['input_count'],'business':state['business'],'grades':grades}
