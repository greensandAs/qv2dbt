-- Model: int_sales_raw  (layer: intermediate)
-- Migrated from QlikView table 'SalesRaw' [file]
-- WARNING: ApplyMap('CountryMap', ...) converted to apply_map() macro - confirm mapping table was generated.

{{ config(materialized='view') }}

with base as (
    select
    OrderID,
    ProductID,
    CustomerID,
    CountryCode,
    TO_DATE(OrderDate, 'YYYY-MM-DD') as ORDERDATE,
    TO_NUMBER(Quantity) as QUANTITY,
    TO_NUMBER(UnitPrice) * TO_NUMBER(Quantity) as GROSSAMOUNT,
    {{ apply_map('CountryMap', "CountryCode", "'Unknown'") }} as COUNTRY,
    LEFT(OrderID, 4) as ORDERPREFIX
    from {{ source('qlikview_raw', 'sales_2026') }}
    where LENGTH(OrderID) > 0
)

select *
from base
union all
select * from {{ ref('int_sales_raw_join4') }}
