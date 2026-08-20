-- Model: stg_inventory_balances  (layer: staging)
-- Migrated from QlikView table 'InventoryBalances' [qvd]

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
