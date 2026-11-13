"""Export and validate immutable, versioned ML snapshots from the published Mart."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from psycopg.rows import dict_row

from pipeline.source_to_staging.common import connect, sha256, source_set, ROOT
from pipeline.staging_to_dw.config import load_config
from pipeline.quality.mart_checks import report as quality_report


def validate_frames(daily, bookings, provenance):
    if daily.empty or bookings.empty:
        raise ValueError('Empty ML snapshot')
    dates = pd.DatetimeIndex(daily.full_date)
    if not dates.equals(pd.date_range(dates.min(), dates.max())):
        raise ValueError('ML calendar must be unique, ordered and continuous')
    if set(daily.data_version) != {provenance['data_version']}:
        raise ValueError('ML data version mismatch')
    if not daily.guest_data_status.eq('COMPLETE').equals(daily.target_guests.notna()):
        raise ValueError('Canonical label/status mismatch')
    if bookings.duplicated(['source_file_sha256', 'source_row_id']).any():
        raise ValueError('Duplicate booking lineage')
    if set(bookings.source_file_sha256) != {provenance['source_checksums']['booking']}:
        raise ValueError('Booking source version mismatch')
    valid = bookings[bookings.is_canceled.eq(0) & bookings.guest_eligible]
    observed = valid.groupby('full_date').total_guests.agg(['sum', 'count']).reindex(dates, fill_value=0)
    for column, metric in [('observed_total_guests', 'sum'), ('guest_valid_booking_count', 'count')]:
        if not np.array_equal(daily[column].astype(float), observed[metric].astype(float)):
            raise ValueError('ML booking-to-daily reconciliation failed: ' + column)


def export_snapshot(output, dbname=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    _, sources, fingerprint = source_set()
    with connect(dbname) as conn:
        quality = quality_report(conn, load_config())
    if not quality['passed'] or quality['errors']:
        raise ValueError('Published DW/Mart quality failed')
    with connect(dbname) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT dw_run_id,data_version FROM mart.dataset_state')
            state = cur.fetchone()
            if not state or str(state['data_version']) != str(quality['data_version']):
                raise ValueError('Publication changed during ML export')
            cur.execute('''SELECT m.*, q.excluded_booking_count FROM mart.daily_hotel_operations m
                JOIN dw.daily_data_quality q USING(date_key) ORDER BY m.full_date''')
            daily = pd.DataFrame(cur.fetchall())
            cur.execute('''SELECT f.source_file_sha256,f.source_row_id,d.full_date,f.is_canceled,
                f.total_guests,f.guest_eligible FROM dw.fact_booking f
                JOIN dw.dim_date d USING(date_key) ORDER BY f.source_row_id''')
            bookings = pd.DataFrame(cur.fetchall())
    for frame in (daily, bookings):
        frame['full_date'] = pd.to_datetime(frame.full_date)
    daily['data_version'] = daily.data_version.astype(str)
    raw = pd.read_csv(sources['booking']['resolved_path'], usecols=['reserved_room_type'], keep_default_na=False)
    raw['source_row_id'] = np.arange(2, len(raw) + 2)
    bookings = bookings.merge(raw, on='source_row_id', how='left', validate='one_to_one', indicator=True)
    if not bookings._merge.eq('both').all():
        raise ValueError('Verified raw does not cover facts')
    bookings = bookings.drop(columns='_merge')
    bookings['reserved_room_type'] = bookings.reserved_room_type.astype('string').str.strip().replace('', pd.NA)
    provenance = {'data_version': str(state['data_version']), 'run_id': str(state['dw_run_id']),
        'source_checksums': {k: v['sha256'] for k, v in sources.items()},
        'source_set_fingerprint': fingerprint, 'point_in_time_verified': False,
        'label_definition': 'Final non-canceled reservation guests by arrival date; not occupancy or verified check-in'}
    validate_frames(daily, bookings, provenance)
    for name, value in [('provenance.json', provenance), ('quality.json', quality)]:
        (output / name).write_text(json.dumps(value, indent=2, default=str), encoding='utf-8')
    daily.to_csv(output / 'daily_input.csv', index=False, lineterminator='\n')
    bookings.to_csv(output / 'booking_input.csv', index=False, lineterminator='\n')
    manifest = {name: sha256(output / name) for name in ['daily_input.csv', 'booking_input.csv', 'provenance.json', 'quality.json']}
    (output / 'input_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return load_snapshot(output)


def load_snapshot(path):
    path = Path(path)
    manifest = json.loads((path / 'input_manifest.json').read_text())
    for name in ['daily_input.csv', 'booking_input.csv', 'provenance.json', 'quality.json']:
        if sha256(path / name) != manifest[name]:
            raise ValueError('ML snapshot checksum mismatch: ' + name)
    provenance = json.loads((path / 'provenance.json').read_text())
    quality = json.loads((path / 'quality.json').read_text())
    if not quality['passed'] or quality['errors'] or str(quality['data_version']) != provenance['data_version']:
        raise ValueError('ML snapshot quality/version mismatch')
    daily = pd.read_csv(path / 'daily_input.csv', parse_dates=['full_date'])
    bookings = pd.read_csv(path / 'booking_input.csv', parse_dates=['full_date'], keep_default_na=False)
    bookings['total_guests'] = pd.to_numeric(bookings.total_guests.replace('', np.nan))
    bookings['reserved_room_type'] = bookings.reserved_room_type.astype('string').replace('', pd.NA)
    validate_frames(daily, bookings, provenance)
    return daily, bookings, provenance
