# Throwaway audit script (TASK-2999): reads frozen records.jsonl files read-only
# and writes a per-cell coverage CSV into the research OUTBOX.
import json, glob, collections, csv
RUNS = {
 'run6':'TWIN2K_UNBLINDING_LOGPROBS_6TASKS-20260919T025143',
 'run10':'T2K10-20260923T034851',
 'exp':'expansion/work/T2KX-20261022T222604',
}
def Cell(): return dict(n=0,bad=0,inference=None,itemkeys=set(),temps=set(),seeds=set())
cell = collections.defaultdict(Cell)
bad_examples=[]
for r,p in RUNS.items():
    for fp in sorted(glob.glob(p+'/**/records.jsonl', recursive=True)):
        parts = fp.split('/')
        model = parts[1] if r!='exp' else parts[3]
        leg = parts[2] if r!='exp' else parts[4]
        with open(fp) as fh:
            for line in fh:
                d=json.loads(line)
                c=cell[(r,model,leg)]; c['n']+=1
                ok = d.get('succeeded', True) and (d.get('error') in (None,'')) and (d.get('choice_succeeded',True))
                if not ok:
                    c['bad']+=1
                    if len(bad_examples)<5: bad_examples.append((fp,d.get('error') or d.get('choice_error')))
                inf=d.get('inference') or {}
                c['temps'].add(inf.get('temperature')); c['seeds'].add(inf.get('seed'))
                if c['inference'] is None and inf: c['inference']=tuple(sorted(inf.keys()))
                for kk in ('expected_response','digit_items','item_index','p_norm','branch_mass','low_branch_mass','decision_position'):
                    if kk in d: c['itemkeys'].add(kk)
rows=[]
for (r,m,leg),c in sorted(cell.items()):
    rows.append(dict(run=r,model=m,leg=leg,n=c['n'],invalid_or_failed=c['bad'],
                     temps=';'.join(str(x) for x in sorted(c['temps'],key=str)),
                     seeds=';'.join(str(x) for x in sorted(c['seeds'],key=str)),
                     inf_keys='|'.join(c['inference'] or ()),fields='|'.join(sorted(c['itemkeys']))))
out='/home/justin/work/crew/research/OUTBOX/stage9_artifacts/COVERAGE_PER_CELL.csv'
with open(out,'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print('cells',len(rows),'total',sum(r['n'] for r in rows))
print('bad examples',bad_examples)
pf=sum(r['n'] for r in rows if r['run']=='run6' and 'PREFLIGHT' in r['leg'])
print('run6 preflight',pf)
for r in rows[:2]+rows[-2:]: print(r)
