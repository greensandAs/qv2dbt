-- HistoryFlag  [staging]  (from QlikView 'qvd')
select
    DATEADD('MONTH', 9, YYYYMM) as YYYYMM,
    _HistoryFlag
from LUNDBECK_UKIE.RAW.HISTORYFLAG as base
;
