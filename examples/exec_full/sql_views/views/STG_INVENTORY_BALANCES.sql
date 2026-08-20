-- InventoryBalances  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_INVENTORY_BALANCES as
select
    "Line Desc 1",
    ClassTurns,
    ThroughputQty,
    CostPrice,
    StockOH
from LUNDBECK_UKIE.RAW.INVENTORYBALANCES as base
;
