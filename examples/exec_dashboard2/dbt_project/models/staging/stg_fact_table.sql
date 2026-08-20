-- Model: stg_fact_table  (layer: staging)
-- Migrated from QlikView table 'FactTable' [qvd]
-- WARNING: Table 'FactTable' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    Region   ||  '_'  ||  TO_DATE(DATEADD('MONTH', 12, YYYYMM), 'YYYYMM') as MONTHLYREGIONKEY,
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
    TO_DATE(DATEADD('MONTH', 24, OrderDate)) as ORDERDATE,
    OrderID,
    OrderStat,
    DATEADD('MONTH', 24, "Promised Delivery Date") as PROMISED DELIVERY DATE,
    "Sales Amount",
    "Sales Cost Amount",
    "Sales Margin Amount",
    "Sales Price",
    "Sales Quantity",
    "Ship To",
    DATEADD('MONTH', 12, YYYYMM) as YYYYMM
    from {{ source('qlikview_raw', 'facttable') }}
)

select *
from base
