-- Calendar  [staging]  (from QlikView 'qvd')
select
    "Fiscal Quarter",
    FiscalMonthNum,
    "Fiscal Year",
    FiscalMonth,
    FiscalRollQt,
    YYYYMM
from LUNDBECK_UKIE.RAW.CALENDAR_2024 as base
;
