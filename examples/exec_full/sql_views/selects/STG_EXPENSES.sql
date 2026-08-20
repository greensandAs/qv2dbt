-- Expenses  [staging]  (from QlikView 'qvd')
select
    MonthlyRegionKey,
    Account,
    ExpenseActual,
    ExpenseBudget
from LUNDBECK_UKIE.RAW.EXPENSES as base
;
