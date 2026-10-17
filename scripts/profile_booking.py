#!/usr/bin/env python3
"""Read-only profiling for Hotel Booking Demand source; only Python standard library."""
import argparse, csv, hashlib, json, math
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

FIELDS = ['hotel','arrival_date_year','arrival_date_month','arrival_date_day_of_month','is_canceled', 'adults','children','babies','stays_in_weekend_nights','stays_in_week_nights','lead_time','adr','country']
INTEGER_FIELDS = ['is_canceled','adults','children','babies','stays_in_weekend_nights','stays_in_week_nights','lead_time']
NONNEGATIVE_FIELDS = ['adults','children','babies','stays_in_weekend_nights','stays_in_week_nights']
MONTH_NAMES = {m.lower():i for i,m in enumerate(['','January','February','March','April','May','June','July','August','September','October','November','December']) if m}

def parse_int(value):
    if value is None or not value.strip(): return None
    try:
        v=float(value)
        return int(v) if math.isfinite(v) and v.is_integer() else None
    except ValueError: return None

def parse_date(row):
    try:
        year = parse_int(row.get('arrival_date_year',''))
        month_raw = row.get('arrival_date_month','').strip()
        month = MONTH_NAMES.get(month_raw.lower(), parse_int(month_raw))
        day = parse_int(row.get('arrival_date_day_of_month',''))
        return date(year,month,day).isoformat()
    except (ValueError,TypeError,OverflowError): return None

def file_sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def profile(path, sample_limit=25):
    null=Counter(); types=defaultdict(Counter); hotels=Counter(); invalid=Counter(); examples=defaultdict(list)
    dates=defaultdict(list); counts=Counter(); all_cols=[]; raw_duplicates=0; seen=set()
    with path.open('r',encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle)
        all_cols=reader.fieldnames or []
        if not all_cols: raise ValueError('CSV has no header')
        missing=[c for c in FIELDS if c not in all_cols]
        if missing: raise ValueError('Missing required columns: '+', '.join(missing))
        for rowid,row in enumerate(reader,start=2):
            counts['source_rows']+=1
            hotel=row.get('hotel','').strip()
            hotels[hotel or '<MISSING>']+=1
            # Identical attributes do not prove duplicate reservations. Informational only.
            signature=tuple(row.get(k,'') for k in all_cols)
            if signature in seen: raw_duplicates+=1
            else: seen.add(signature)
            for col in all_cols:
                value=row.get(col)
                if value is None or value.strip()=='': null[col]+=1
            for col in INTEGER_FIELDS:
                value=row.get(col,'')
                if value.strip():
                    types[col]['parseable_int' if parse_int(value) is not None else 'non_integer']+=1
            arrival=parse_date(row)
            if arrival: dates[hotel].append(arrival)
            errors=[]
            if not arrival: errors.append('invalid_arrival_date')
            parsed={k:parse_int(row.get(k,'')) for k in INTEGER_FIELDS}
            if parsed['is_canceled'] not in (0,1): errors.append('invalid_cancellation_flag')
            for col in NONNEGATIVE_FIELDS:
                if col=='children' and parsed[col] is None: errors.append('missing_or_invalid_children')
                elif parsed[col] is None or parsed[col]<0: errors.append('invalid_'+col)
            if all(parsed[k] is not None for k in ['adults','children','babies']) and sum(parsed[k] for k in ['adults','children','babies'])==0:
                errors.append('zero_total_guests')
            if hotel=='City Hotel':
                counts['city_rows']+=1
                if errors: counts['city_rows_with_issues']+=1
                else: counts['city_rows_no_detected_issues']+=1
                for reason in errors:
                    invalid[reason]+=1
                    if len(examples[reason])<sample_limit: examples[reason].append(rowid)
            else: counts['non_city_rows']+=1
    return {
      'source':str(path),'source_sha256':file_sha256(path),'columns':all_cols,'required_columns':FIELDS,
      'counts':dict(counts),'hotel_counts':dict(hotels),
      'null_counts':dict(null),'null_rates':{k:round(null[k]/counts['source_rows'],5) if counts['source_rows'] else None for k in all_cols},
      'type_diagnostics':{k:dict(v) for k,v in types.items()},
      'identical_attribute_rows_after_first':raw_duplicates,
      'note_on_duplicates':'Identical CSV attributes DO NOT prove the same reservation. Never auto-drop them.',
      'city_issue_counts_by_rule':dict(invalid),'city_example_csv_line_numbers':dict(examples),
      'arrival_date_coverage_by_hotel':{k:{'min':min(v),'max':max(v),'valid_rows':len(v)} for k,v in dates.items() if v},
      'scope_note':'Profiling only: no source rows changed, filtered, quarantined, or loaded into staging.'}

def markdown_report(x):
    c=x['counts']; lines=['# Hotel Booking — Source Profiling','',f"Source: `{x['source']}`",f"SHA256: `{x['source_sha256']}`",'',
      '## Row overview','',f"- Raw rows: **{c.get('source_rows',0):,}**",f"- City Hotel rows: **{c.get('city_rows',0):,}**",f"- Non-City Hotel rows: **{c.get('non_city_rows',0):,}**",f"- City Hotel rows with detected issues: **{c.get('city_rows_with_issues',0):,}**",'',
      '## Issue counts (City Hotel only)','','| Rule | Rows |','|---|---:|']
    lines.extend(f'| `{k}` | {v:,} |' for k,v in sorted(x['city_issue_counts_by_rule'].items()))
    lines.extend(['','Counts per rule can overlap; do not sum to estimate rejected rows.','','## Null profiles','','| Field | Null count | Rate |','|---|---:|---:|'])
    lines.extend(f"| `{k}` | {x['null_counts'].get(k,0):,} | {x['null_rates'][k]:.2%} |" for k in x['columns'])
    lines.extend(['','## Arrival-date coverage','','| Hotel | Minimum | Maximum | Valid rows |','|---|---|---|---:|'])
    lines.extend(f"| {k} | {v['min']} | {v['max']} | {v['valid_rows']:,} |" for k,v in x['arrival_date_coverage_by_hotel'].items())
    lines.extend(['','## Caveats', '', '- Date is **scheduled arrival date**, not booking creation date.', '- This phase does not modify raw or perform DW exclusions.', '- Duplicate-looking booking rows are only reported, never dropped.', '- Missing ADR/country is reported but does not automatically reject rows.', '- Source identity, geography and upstream provenance must be independently documented.', ''])
    return '\n'.join(lines)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--csv',required=True,type=Path)
    ap.add_argument('--out',default='artifacts/profiling',type=Path)
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    results=profile(args.csv)
    (args.out/'booking_profile.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
    (args.out/'booking_profile.md').write_text(markdown_report(results),encoding='utf-8')
    print(f"Rows={results['counts']['source_rows']} City={results['counts'].get('city_rows',0)} issues={results['counts'].get('city_rows_with_issues',0)}")
    print('Written:',args.out/'booking_profile.md')
if __name__=='__main__': main()
