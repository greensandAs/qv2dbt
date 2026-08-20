-- ARSummary-1  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_ARSUMMARY_1 as
select
    CustKeyAR,
    ARAge,
    ARAgeBal
from LUNDBECK_UKIE.RAW.ARSUMMARY_1 as base
;
