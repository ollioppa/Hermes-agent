#!/usr/bin/env python3
"""Offline synthetic inputs through real scanner, DB, reader and position owners."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import date
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
import opportunity_radar.db as db_module
from opportunity_radar.db import RadarDB
from opportunity_radar.cli import import_case_payload
from opportunity_radar.models import MarketSnapshot
from opportunity_radar.universe import UniverseMember
from opportunity_radar.report import render_change_only
from opportunity_radar.quarterly_watch import watch_letter_context
from opportunity_radar.position_review import monthly_brief_context
from opportunity_radar.mailer import deliver_mail_once
import run_trend_screening as scanner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'demo-output')
    args = parser.parse_args()
    output = args.output.resolve()
    # Exclusive directory prevents accidental reuse of a real database.
    output.mkdir(parents=True, exist_ok=False)
    radar = RadarDB(output / 'radar.sqlite3')
    as_of = date(2026, 9, 8)
    member = UniverseMember('SYNTHETIC:DEMO', 'DEMO', 'Invented demonstration company',
                            'stock', 'US', 'XNYS', 'USD', 'synthetic')
    monthly = {'DEMO': [(date(y, 12, 31), float(60 + 10 * (y-2021))) for y in range(2021, 2026)]
                      + [(date(2026, 1, 31), 150.0), (date(2026, 2, 28), 100.0)]}
    latest = {'DEMO': (as_of, 100.0)}
    inputs = {'monthly': monthly, 'latest': latest, 'as_of': as_of}
    revision = hashlib.sha256(json.dumps(inputs, default=str, sort_keys=True).encode()).hexdigest()
    (output / 'synthetic-inputs.json').write_text(json.dumps(inputs, default=str, indent=2)+'\n')
    signals = scanner.compute_current_signals([member], monthly, latest, as_of=as_of,
                                               source_url='https://example.invalid/invented-history')
    assert len(signals) == 1
    # Only provenance label changes: numerical calculation and publication are real.
    scanner.PROVIDER = 'synthetic-offline-demo'
    publication = scanner.publish(radar, signals, as_of=as_of, source_revision=revision)
    retry = scanner.publish(radar, signals, as_of=as_of, source_revision=revision)
    assert publication['selected'] == 1 and retry['status'] == 'ALREADY_PUBLISHED'
    candidate = radar.next_research_candidate()
    assert candidate and candidate['symbol'] == 'DEMO'
    report = output / 'invented-research.md'
    report.write_text('# Invented demonstration only\n\nNo real company, source or investment conclusion.\n')
    radar.record_candidate_decision('DEMO','AWAITING_USER','Synthetic handoff, not research',
        candidate_id=candidate['id'], signal_date='2026-02', report_path=str(report),
        reader_text='Invented example awaiting a separate human decision.', decided_by='fixture-research')
    assert radar.list_cases() == []
    pending = watch_letter_context(radar, '2026-Q3')
    assert len(pending['awaiting_candidates']) == 1
    review = {key: 'Invented schema example; no financial claim' for key in (
        'motor','environment','relative_strength','expectation','asymmetry','counterpath','falsifier',
        'moat_competition','cash_conversion','balance_financing','capital_allocation','valuation','margins','dilution')}
    review.update(evidence_as_of='2026-09-08', missing_to_ready='No open condition; invented decision-ready example',
        customer_economics={key:'Invented example' for key in ('historical_path','growth_composition','customer_value','support_intensity','margin_source_and_use','rent_quality','normalization_test')})
    def snapshot(symbol, role):
        return asdict(MarketSnapshot(symbol,role,100.0,'2026-09-08','2026-09-08T22:00:00Z',
                                    'USD','synthetic-offline-demo','invented close; not total return'))
    payload={'symbol':'DEMO','name':member.name,'kind':'stock','sector_symbol':'XLK',
        'review':review,'sources':['https://example.invalid/invented-research'],'immediate_investable':True,
        'candidate_id':candidate['id'],
        'snapshots':{'case':snapshot('DEMO','case'),'spy':snapshot('SPY','benchmark'),'sector':snapshot('XLK','sector')}}
    case_id=radar.promote_candidate(int(str(candidate['id'])),payload)
    assert radar.get_case(case_id)['status']=='READY'
    assert watch_letter_context(radar,'2026-Q3')['awaiting_candidates']==[]
    ready_context=watch_letter_context(radar,'2026-Q3')
    assert len(ready_context['ready_cases'])==1
    position={'symbol':'DEMO','name':member.name,'kind':'stock','currency':'USD','linked_case_symbol':'DEMO',
        'purchase_date':'2026-09-08','purchase_date_is_approximate':False,'average_price':100.0,
        'quantity':10.0,'invested_amount':1000.0,'objective':'Invented demonstration holding',
        'horizon':'three years','exit_strategy':'Invented thesis break','benchmark_symbol':'SPY',
        'baseline_as_of':'2026-09-08','provenance':'Generated in this script, not broker data'}
    position_id=radar.import_position(position,confirmed_by='owner')
    shown=radar.show_position('DEMO')
    review_id=radar.record_position_review('DEMO',{'review_date':'2026-09-09','position_id':position_id,
        'baseline_id':shown['baselines'][0]['id'],'recommendation':'EXIT','summary':'Invented EXIT recommendation',
        'strongest_counterevidence':'Invented opposing view','report_path':str(report),
        'missing_decision_fact':None,'next_check_on':None,'reviewer':'synthetic-offline-demo'})
    assert radar.show_position('DEMO')['quantity']==10.0
    monthly_context=monthly_brief_context(radar,'2026-09')
    assert radar.monthly_position_review_status('2026-09')['complete']
    assert watch_letter_context(radar,'2026-Q3')['ready_cases']==[]
    event={'position_id':position_id,'execution_reference':'invented-trim-001','action':'TRIM',
           'event_date':'2026-09-10','quantity':2.0,'price':110.0,'reason':'Invented confirmed execution'}
    radar.confirm_position_event('DEMO',event,confirmed_by='owner')
    assert radar.show_position('DEMO')['quantity']==8.0
    body=render_change_only(radar,output/'reader.md')
    assert body and 'DEMO' in body and render_change_only(radar,output/'reader.md') is None
    class LocalMail:
        sent=0
        def find_verified(self,subject,recipient):return None
        def send_and_verify(self,subject,recipient,body):
            self.sent+=1
            (output/'local-mail.md').write_text(body)
            return 'local-fixture-only'
    transport=LocalMail()
    mail=deliver_mail_once(radar,transport,'demo:local','Radar demo [local]','nobody@example.invalid',body)
    again=deliver_mail_once(radar,transport,'demo:local','Radar demo [local]','nobody@example.invalid',body)
    assert mail['status']=='sent' and again['status']=='already_delivered' and transport.sent==1
    summary={'synthetic':True,'live_network':False,'live_mail':False,'llm':False,
        'signals':len(signals),'screen_retry':retry['status'],'candidate_id':candidate['id'],
        'case_status':radar.get_case(case_id)['status'],'position_quantity':radar.show_position('DEMO')['quantity'],
        'position_status':radar.show_position('DEMO')['status'],'local_transport_calls':transport.sent,
        'reader_sha256':hashlib.sha256(body.encode()).hexdigest(),
        'input_sha256':revision,'review_id':review_id}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'summary':summary,'imports':{'db':db_module.__file__,'scanner':scanner.__file__},
                      'output':str(output)},sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
