-- HistoryFlag  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_HISTORY_FLAG as
select
    DATEADD('MONTH', 9, YYYYMM) as YYYYMM,
    _HistoryFlag
from LUNDBECK_UKIE.RAW.HISTORYFLAG as base
;
