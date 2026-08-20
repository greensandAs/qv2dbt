-- Model: int_fact_table  (layer: intermediate)
-- Migrated from QlikView table 'FactTable' [resident]
-- WARNING: Table 'FactTable' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    MonthlyRegionKey,
    Region,
    "Address Number",
    CustKey,
    "Invoice Number",
    "Item-Branch Key",
    "Late Shipment",
    "Line Desc 1",
    "Open Order Amount",
    "Order Number",
    "Order Status",
    OrderDate,
    OrderID,
    OrderStat,
    "Promised Delivery Date",
    "Sales Amount",
    "Sales Cost Amount",
    "Sales Margin Amount",
    "Sales Price",
    "Sales Quantity",
    "Ship To",
    YYYYMM
    from {{ ref('stg_fact_table_init') }}
)

select *
from base
union all
select * from {{ ref('int_fact_table_join37') }}
