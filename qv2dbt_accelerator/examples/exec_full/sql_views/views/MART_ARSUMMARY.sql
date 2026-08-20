-- ARSummary  [mart]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.MARTS.MART_ARSUMMARY as
select
    CustKeyAR,
    ARGross,
    AROpen,
    ARCurrent,
    "AR1-30",
    "AR31-60",
    "AR60+",
    ARCredit,
    ARSalesPerDay,
    ARAvgBal
from LUNDBECK_UKIE.RAW.ARSUMMARY as base
;
