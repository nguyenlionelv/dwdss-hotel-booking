"""Real Mart, saved inference and additive API contract regression."""
import os
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.schemas.dss import DailyForecastResponse
from backend.app.services.dss_service import thresholds
from ml.demand_forecast.registry import resolve
from ml.demand_forecast.predict import inputs, daily_prediction

@pytest.mark.skipif(os.getenv('DWDSS_INTEGRATION')!='1',reason='Requires local published Mart and saved artifacts')
def test_advisories_preserve_saved_predictions_and_strict_tiers():
    client=TestClient(create_app())
    models=client.get('/api/dss/models').json()['models']
    for model in (m for m in models if m['kind']=='daily'):
        response=client.get('/api/dss/demand-forecast',params={'model_name':model['id'],'as_of_date':'2017-08-24'})
        assert response.status_code==200,response.text
        payload=response.json()
        DailyForecastResponse.model_validate(payload)
        metadata,state=resolve(model['id'],payload['data_version'],'daily')
        daily,bookings=inputs(metadata)
        dates,values,latest=daily_prediction(metadata,state,daily,bookings,pd.Timestamp('2017-08-24'))
        assert [r['predicted_guest_count'] for r in payload['forecasts']]==values
        assert payload['dss_threshold_rule']==thresholds(daily,latest)
        assert all(r['demand_level']=='INSUFFICIENT_HISTORY' for r in payload['forecasts'])
        support=payload['decision_support']
        assert support['metadata']['history_end']==str(latest.date())
        assert support['metadata']['available_case_56']['sample_count']==53
        assert support['metadata']['available_case_56']['supported']
        assert support['state'] in ('NEUTRAL','INSIGHTS') and len(support['insights'])<=3
        assert all(i['category']=='DEMAND_INSIGHT' and i['recommended_action'] is None for i in support['insights'])
        allocation = payload['resource_allocation']
        assert allocation['status'] == 'ready'
        assert allocation['policy_version'] == 'allocation-v1'
        assert allocation['budget_units'] == 100
        assert len(allocation['daily_allocation']) == 7
        assert [day['date'] for day in allocation['daily_allocation']] == [row['forecast_date'] for row in payload['forecasts']]
        assert [day['predicted_guests'] for day in allocation['daily_allocation']] == values
        assert sum(round(day['allocation_share'] * 1_000_000) for day in allocation['daily_allocation']) == 1_000_000
        assert sum(round(day['allocation_units'] * 100) for day in allocation['daily_allocation']) == 10_000
        assert allocation['metadata']['effective_history_cutoff'] == str(latest.date())
        assert allocation['metadata']['data_version'] == payload['data_version']
        assert allocation['metadata']['model_version'] == payload['model_version']

    custom = client.get('/api/dss/demand-forecast', params={
        'model_name': next(m['id'] for m in models if m['kind'] == 'daily'),
        'as_of_date': '2017-08-24', 'budget_units': '123.45'})
    assert custom.status_code == 200, custom.text
    units = custom.json()['resource_allocation']['daily_allocation']
    assert sum(round(day['allocation_units'] * 100) for day in units) == 12345
    invalid_budget = client.get('/api/dss/demand-forecast', params={'budget_units': '123.456'})
    assert invalid_budget.status_code == 422
