-- Model: stg_sales_py  (layer: staging)
-- Migrated from QlikView table 'SalesPY' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    OrderID,
    ProductID,
    CustomerID,
    CountryCode,
    TO_DATE(OrderDate, 'YYYY-MM-DD') as ORDERDATE,
    TO_NUMBER(Quantity) as QUANTITY,
    TO_NUMBER(GrossAmount) as GROSSAMOUNT
    from {{ source('qlikview_raw', 'sales_2025') }}
)

select *
from base
