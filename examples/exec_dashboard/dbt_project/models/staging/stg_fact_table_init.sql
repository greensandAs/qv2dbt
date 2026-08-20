-- Model: stg_fact_table_init  (layer: staging)
-- Migrated from QlikView table 'FactTable Init' [qvd]

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
    DATEADD('MONTH', 9, OrderDate) as ORDERDATE,
    OrderID,
    OrderStat,
    DATEADD('MONTH', 9, "Promised Delivery Date") as PROMISED DELIVERY DATE,
    "Sales Amount",
    "Sales Cost Amount",
    "Sales Margin Amount",
    "Sales Price",
    "Sales Quantity",
    "Ship To",
    DATEADD('MONTH', 9, YYYYMM) as YYYYMM
    from {{ source('qlikview_raw', 'facttable') }}
)

select *
from base
