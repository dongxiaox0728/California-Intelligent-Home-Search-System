"""
    Run the frozen queries through both systems and prepare blind judging pools.

    Run with the project virtual environment:
        python3 benchmarks/run_retrieval_benchmark.py
    Resume an interrupted run:
        python3 benchmarks/run_retrieval_benchmark.py --output benchmarks/retrieval_v1/runs/RUN_DIRECTORY

    Saves top 100 per system. Pools top 10 per system by default. Expected query
        labels never drive retrieval. Existing records are reused only with matching
        query/artifact/code fingerprints. MySQL reads use one consistent read snapshot.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
COLUMNS=('L_ListingID','L_Address','L_City','L_Type_','L_SystemPrice',
         'L_Keyword2','LM_Dec_3','LM_Int2_3','ListingContractDate','L_Remarks')


def default(value):
    if isinstance(value,(date,datetime)): return value.isoformat()
    if isinstance(value,Decimal): return float(value)
    if hasattr(value,'item'): return value.item()
    raise TypeError(type(value).__name__)


def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def dump(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,default=default,allow_nan=False)+'\n',encoding='utf-8')
    temporary.replace(path)


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def safe_error(exc):
    message=str(exc)
    for name in ('OPENAI_API_KEY','MYSQL_PASSWORD'):
        secret=os.getenv(name)
        if secret and len(secret)>3:message=message.replace(secret,'[redacted]')
    return {'type':type(exc).__name__,'message':message[:2000]}


def write_outputs(output,queries,records,documents,pool_depth):
    run_rows=[]; pool_rows=[]; blind_rows=[]; diagnostics=[]
    for query in queries:
        qid=query['query_id']
        record=records.get(qid)
        if record is None:continue
        sources={}
        for system in ('baseline','new'):
            outcome=record[system]
            diagnostics.append({'query_id':qid,'category':query['category'],'system':system,
                                'status':outcome['status'],'seconds':outcome.get('seconds'),
                                'result_count':len(outcome.get('results',[])),
                                'expected_mode':query['expected_mode'],
                                'actual_mode':outcome.get('report',{}).get('mode'),
                                'error':outcome.get('error')})
            for row in outcome.get('results',[]):
                lid=str(row['L_ListingID']).strip()
                run_rows.append({'query_id':qid,'system':system,'listing_id':lid,'rank':row['rank'],
                                 'score':row.get('final_score',row.get('similarity_score')),
                                 'semantic_score':row.get('similarity_score'),
                                 'structured_score':row.get('structured_score')})
                if row['rank']<=pool_depth:
                    sources.setdefault(lid,{})[system]={'rank':row['rank'],
                        'score':row.get('final_score',row.get('similarity_score'))}
        ids=sorted(sources)
        random.Random('retrieval_v1:'+qid).shuffle(ids)
        for i,lid in enumerate(ids,1):
            doc=documents[lid]
            pool_rows.append({'query_id':qid,'listing_id':lid,'sources':sources[lid]})
            blind_rows.append({'judgment_id':f'{qid}-J{i:02d}','query_id':qid,'query':query['query'],
                              'listing_id':lid,**doc,'relevance_grade':'','hard_constraints_met':'',
                              'evidence_or_notes':'','human_reviewed':''})
    def csv_write(name,data,fields):
        with (output/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
            writer.writeheader();writer.writerows(data)
    csv_write('runs.csv',run_rows,['query_id','system','listing_id','rank','score','semantic_score','structured_score'])
    with (output/'pool_provenance.jsonl').open('w',encoding='utf-8') as f:
        for row in pool_rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    with (output/'judging_pool.jsonl').open('w',encoding='utf-8') as f:
        for row in blind_rows:f.write(json.dumps(row,ensure_ascii=False,default=default,allow_nan=False)+'\n')
    csv_write('judging_pool.csv',blind_rows,['judgment_id','query_id','query','listing_id',*COLUMNS,
                                          'relevance_grade','hard_constraints_met','evidence_or_notes','human_reviewed'])
    dump(output/'diagnostics.json',diagnostics)
    counts=Counter(d['status'] for d in diagnostics)
    mismatches=[d['query_id'] for d in diagnostics if d['system']=='new' and d['status']=='ok'
                and d['actual_mode']!=d['expected_mode']]
    summary={'queries_completed':len(records),'query_count':len(queries),'run_depth':100,
             'pool_depth_per_system':pool_depth,'status_counts':dict(counts),
             'ranked_result_rows':len(run_rows),'unique_query_listing_pairs':len(pool_rows),
             'new_system_mode_mismatch_query_ids':mismatches,
             'note':'Pools from queries with a failed system are incomplete; consult diagnostics. '
                    'No relevance grades have been assigned.'}
    dump(output/'summary.json',summary)
    return summary


def main():
    cli=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument('--queries',type=Path,default=ROOT/'benchmarks/retrieval_v1/queries.jsonl')
    cli.add_argument('--output',type=Path)
    cli.add_argument('--pool-depth',type=int,default=10)
    cli.add_argument('--limit',type=int,help='Optional small preflight run; use a separate output directory.')
    args=cli.parse_args()
    if not 1<=args.pool_depth<=100:cli.error('--pool-depth must be 1 to 100')
    if args.limit is not None and args.limit<1:cli.error('--limit must be positive')
    queries=[json.loads(line) for line in args.queries.read_text().splitlines() if line.strip()]
    if args.limit:queries=queries[:args.limit]
    output=args.output or ROOT/'benchmarks/retrieval_v1/runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output.mkdir(parents=True,exist_ok=True);(output/'queries').mkdir(exist_ok=True)
    # Offline model loading avoids changing/download of the embedding model during the run.
    os.environ.setdefault('HF_HUB_OFFLINE','1')
    from scripts.query_parser import QueryParser
    from scripts.hard_constraints_filter import HardConstraintsFilter
    from scripts.semantic_searcher import SemanticSearcher
    from scripts.search_orchestrator import SearchOrchestrator

    searcher=SemanticSearcher();searcher.load()
    searcher._prepare_eligible_positions()  # Verify saved model/index/metadata pairing.
    connection=HardConstraintsFilter._connect()
    try:
        connection.start_transaction(isolation_level='REPEATABLE READ',consistent_snapshot=True,readonly=True)
        cursor=connection.cursor(dictionary=True)
        selection=', '.join(f'`{col}`' for col in COLUMNS)
        cursor.execute(f'SELECT {selection} FROM rets_property')
        snapshot={}
        for row in cursor.fetchall():
            lid=str(row['L_ListingID']).strip();row['L_ListingID']=lid
            if lid in snapshot and snapshot[lid]!=row:
                raise ValueError('Conflicting duplicate IDs in database snapshot.')
            snapshot[lid]=row
        cursor.close()
        index_ids=set(searcher.metadata['L_ListingID'].str.strip())
        common=index_ids & snapshot.keys()
        if not common:raise ValueError('Database and indexed dataset have no IDs in common.')
        documents={lid:snapshot[lid] for lid in sorted(common)}
        snapshot_bytes=''.join(json.dumps(doc,ensure_ascii=False,default=default,sort_keys=True,allow_nan=False)+'\n'
                               for doc in documents.values()).encode('utf-8')
        # Check that listing remarks associated with the saved embeddings have not drifted.
        mismatches=0
        for row in searcher.metadata.to_dict('records'):
            lid=str(row['L_ListingID']).strip()
            if lid in common and str(row.get('remarks','')).strip()!=str(snapshot[lid]['L_Remarks'] or '').strip():
                mismatches+=1
        if mismatches:raise ValueError(f'{mismatches} indexed listings have changed remarks; freeze matching artifacts before benchmarking.')
        code_files=['query_parser.py','hard_constraints_filter.py','semantic_searcher.py',
                    'structured_ranker.py','weighted_ranker.py','search_orchestrator.py']
        fingerprints={name:digest(ROOT/'scripts'/name) for name in code_files}
        fingerprints.update({name:digest(ROOT/'data/models'/name) for name in
                             ['listing_semantic.index','listing_metadata.csv','listing_semantic.json']})
        manifest={'query_file_sha256':digest(args.queries),'query_ids':[q['query_id'] for q in queries],
                  'fingerprints':fingerprints,'snapshot_sha256':hashlib.sha256(snapshot_bytes).hexdigest(),
                  'indexed_listing_count':len(index_ids),'shared_listing_count':len(common),
                  'database_unique_listing_count':len(snapshot),'pool_depth':args.pool_depth,
                  'model':searcher.model_name,'cleanup_model':os.getenv('OPENAI_CLEANUP_MODEL','gpt-6-astra'),
                  'fairness':'Both systems restricted to shared indexed IDs. Actual parser output drives new retrieval.',
                  'snapshot':'MySQL REPEATABLE READ consistent read transaction; fields saved in corpus_snapshot.jsonl.'}
        manifest_path=output/'manifest.json'
        if manifest_path.exists():
            if json.loads(manifest_path.read_text())!=manifest:
                raise ValueError('Run inputs changed; use a new output directory instead of mixing runs.')
        else:
            dump(manifest_path,manifest)
            (output/'corpus_snapshot.jsonl').write_bytes(snapshot_bytes)
            (output/'queries_input.jsonl').write_text(''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in queries))
        del snapshot_bytes

        class SharedUniverseFilter(HardConstraintsFilter):
            def build_query(self,parsed):
                sql,parameters=super().build_query(parsed)
                return sql.replace('SELECT *',f'SELECT {selection}',1),parameters
            def filter(self,parsed):
                return [row for row in super().filter(parsed) if str(row['L_ListingID']).strip() in common]

        # Use actual database vocabulary without shell/Docker-dependent startup.
        # This supplies the same DB city/type lookup, without reading expected query labels.
        parser=QueryParser(load_database_cities=False)
        parser.valid_cities={str(row['L_City']).strip().lower():str(row['L_City']).strip()
                             for row in snapshot.values() if row.get('L_City')}
        parser.valid_property_types={str(row['L_Type_']).strip().lower():str(row['L_Type_']).strip()
                                     for row in snapshot.values() if row.get('L_Type_')}
        parser.city_source='database consistent snapshot'
        orchestrator=SearchOrchestrator(parser,SharedUniverseFilter(connection),searcher,
                                        date_column='ListingContractDate')
        records={}
        print(f'RUN_DIRECTORY={output}',flush=True)
        print(f'Shared corpus: {len(common):,} listings; top 100 each, pool top {args.pool_depth}.',flush=True)
        for i,query in enumerate(queries,1):
            qid=query['query_id'];saved=output/'queries'/f'{qid}.json'
            if saved.exists():
                records[qid]=json.loads(saved.read_text())
                print(f'[{i}/{len(queries)}] {qid}: resumed saved query',flush=True)
                continue
            record={'query_id':qid,'query':query['query']}
            start=perf_counter()
            try:
                # Original method: full-query embedding, no hard filtering.
                depth=100 if len(common)==len(index_ids) else len(index_ids)
                baseline=searcher.search(query['query'],top_k=depth)
                baseline=[r for r in baseline if str(r['L_ListingID']).strip() in common][:100]
                for rank,row in enumerate(baseline,1):row['rank']=rank
                record['baseline']={'status':'ok','seconds':perf_counter()-start,'results':baseline}
            except Exception as exc:
                record['baseline']={'status':'error','seconds':perf_counter()-start,'results':[],'error':safe_error(exc)}
            start=perf_counter()
            try:
                report=orchestrator.search(query['query'],top_k=100)
                results=report.pop('results')
                record['new']={'status':'ok','seconds':perf_counter()-start,'results':results,'report':report}
            except Exception as exc:
                record['new']={'status':'error','seconds':perf_counter()-start,'results':[],'error':safe_error(exc)}
            dump(saved,record);records[qid]=record
            new=record['new']
            print(f"[{i}/{len(queries)}] {qid}: baseline={record['baseline']['status']} "
                  f"new={new['status']} mode={new.get('report',{}).get('mode','n/a')} "
                  f"results={len(new['results'])} time={new['seconds']:.1f}s",flush=True)
            if new['status']=='error':
                print('New-system error:',new['error'],flush=True)
            write_outputs(output,queries,records,documents,args.pool_depth)
        summary=write_outputs(output,queries,records,documents,args.pool_depth)
        (output/'README.md').write_text('''# Retrieval runs and judging pool

runs.csv contains both systems' top-100 rankings and scores. queries/ contains complete per-query results, timings and parsed-query diagnostics. corpus_snapshot.jsonl is the shared listing snapshot. manifest.json records hashes, configuration and corpus coverage. queries_input.jsonl preserves query intentions; those annotations were not used to drive retrieval.

judging_pool.csv and judging_pool.jsonl contain the randomized, deduplicated union of each system's top 10 (or configured pool depth), with listing evidence and blank judgment fields. Do not show judges runs.csv, pool_provenance.jsonl or queries/ because they reveal system identity, rank and scores. pool_provenance.jsonl is the private source/rank mapping.

Assign relevance labels before calculating retrieval metrics. A zero-result successful run is different from a failed query; inspect diagnostics.json. An incomplete pool must not be treated as a completed two-system comparison. New-system route mismatches against intended categories are recorded in summary.json; retrieval used the actual parser output without correcting it to expected labels. Timings exclude model initialization and are measured sequentially, not a production latency benchmark.

Copy the blank judging pool before adding labels; resuming this collector regenerates it. Raw result scores from the two systems are not directly comparable relevance grades.
''')
        print('FINAL_SUMMARY='+json.dumps(summary),flush=True)
    finally:
        connection.rollback();connection.close()


if __name__=='__main__':main()
