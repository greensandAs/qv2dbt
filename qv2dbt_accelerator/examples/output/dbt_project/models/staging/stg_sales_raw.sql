-- Model: stg_sales_raw  (layer: staging)
-- Migrated from QlikView table 'SalesRaw' [qvd]
-- WARNING: ApplyMap('CountryMap', ...) converted to apply_map() macro - confirm mapping table was generated.

{{ config(materialized='view') }}

with base as (
    select
    OrderID,
    ProductID,
    CustomerID,
    CountryCode,
    TO_DATE(OrderDate) as ORDERDATE,
    TO_NUMBER(Quantity) as QUANTITY,
    TO_NUMBER(UnitPrice) * TO_NUMBER(Quantity) as GROSSAMOUNT,
    {{ apply_map('CountryMap', "CountryCode", "'Unknown'") }} as COUNTRY,
    LEFT(OrderID, 4) as ORDERPREFIX
    from {{ source('qlikview_raw', 'from_lib') }}
)

select *
from base
