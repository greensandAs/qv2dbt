-- Expenses  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_EXPENSES as
select
    MonthlyRegionKey,
    Account,
    ExpenseActual,
    ExpenseBudget
from LUNDBECK_UKIE.RAW.EXPENSES as base
;
