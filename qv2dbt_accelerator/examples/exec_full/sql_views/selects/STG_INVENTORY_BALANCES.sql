-- InventoryBalances  [staging]  (from QlikView 'qvd')
select
    "Line Desc 1",
    ClassTurns,
    ThroughputQty,
    CostPrice,
    StockOH
from LUNDBECK_UKIE.RAW.INVENTORYBALANCES as base
;
