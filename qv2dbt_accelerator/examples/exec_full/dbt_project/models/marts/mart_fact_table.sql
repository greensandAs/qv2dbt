-- Model: mart_fact_table  (layer: mart)
-- Migrated from QlikView table 'FactTable' [resident]

{{ config(materialized='table') }}

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
    from {{ ref('mart_fact_table_init') }}
)

select *
from base
