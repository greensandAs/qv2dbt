-- Model: stg_inventory_balances  (layer: staging)
-- Migrated from QlikView table 'InventoryBalances' [qvd]
-- WARNING: Table 'InventoryBalances' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    "Line Desc 1",
    ClassTurns,
    ThroughputQty,
    CostPrice,
    StockOH
    from {{ source('qlikview_raw', 'inventorybalances') }}
)

select *
from base
