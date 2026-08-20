-- Calendar  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_CALENDAR as
select
    "Fiscal Quarter",
    FiscalMonthNum,
    "Fiscal Year",
    FiscalMonth,
    FiscalRollQt,
    YYYYMM
from LUNDBECK_UKIE.RAW.CALENDAR_2024 as base
;
