"""Version-checked DSS inference endpoints; all training runs offline."""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from backend.app.api.metadata import get_db
from backend.app.schemas.dss import DailyForecastResponse, MonthlyForecastResponse
from backend.app.services import dss_service as service
from ml.demand_forecast.registry import entries
from ml.demand_forecast.predict import ForecastInputError

router=APIRouter(prefix='/api/dss',tags=['DSS'])

def invoke(callback):
    try:
        return callback()
    except ForecastInputError as exc:
        raise HTTPException(422,str(exc)) from exc
    except (OSError,ValueError,KeyError) as exc:
        raise HTTPException(503,'Forecast artifacts unavailable or incompatible with the published data. Run offline training and check provenance.') from exc

@router.get('/status')
def dss_status(conn=Depends(get_db)):
    models=invoke(lambda: entries(service.published_version(conn)))
    return {'module':'dss','status':'ready','models':[m['model_id'] for m,_ in models]}

@router.get('/models')
def models(conn=Depends(get_db)):
    available=invoke(lambda: entries(service.published_version(conn)))
    return {'models':[{'id':m['model_id'],'label':m['algorithm']+' / '+m['imputation_policy'],
        'kind':m['kind'],'default':m['default'],'model_version':m['model_version'],
        'data_version':m['data_version'],'metric_protocol':m['metric_protocol'],
        'label_delay_days':m['availability_assumptions']['label_delay_days']} for m,_ in available]}

@router.get('/demand-forecast',response_model=DailyForecastResponse)
def daily(as_of_date:date=date(2017,8,31),model_name:str|None=None,horizon:int=Query(7,ge=1,le=7),
          budget_units:Decimal=Query(Decimal('100'),gt=0,le=10000,decimal_places=2),conn=Depends(get_db)):
    return invoke(lambda: service.daily_forecast(conn,as_of_date,model_name,horizon,budget_units))

@router.get('/monthly-demand-forecast',response_model=MonthlyForecastResponse)
def monthly(as_of_date:date=date(2017,8,31),model_name:str|None=None,conn=Depends(get_db)):
    return invoke(lambda: service.monthly_forecast(conn,as_of_date,model_name))
