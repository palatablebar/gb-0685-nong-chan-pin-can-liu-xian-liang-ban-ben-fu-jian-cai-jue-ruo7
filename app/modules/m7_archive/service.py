from app.modules.m7_archive.export_out import checksum

def execute(state):
    coverage=state.get('coverage',{})
    balanced=state.get('reconcile',{}).get('balanced',False)
    complete=coverage.get('complete',True)
    # Archive eligibility follows the same merged interval that produced the
    # batch grade: a balanced ledger plus one conclusion for every accepted
    # sample/project group.  A failed adoption that retained the primary
    # conclusion still satisfies this, because that conclusion covers its group.
    state['archive']={'sha256':checksum(state),'evidence_count':len(state.get('calculations',[]))+len(state.get('unit_support',[]))+len(state.get('rows',[]))+len(state.get('quarantine',[])),
        'ready':bool(balanced and complete),'balanced':bool(balanced),'coverage_complete':bool(complete),
        'cross_unit_projects':coverage.get('cross_unit',0),'retained_conclusions':coverage.get('fallback',0),
        'basis':[{'batch':g['batch'],'code':g['code'],'interval':g.get('basis')} for g in state.get('reconcile',{}).get('grades',[])]}
    return state
