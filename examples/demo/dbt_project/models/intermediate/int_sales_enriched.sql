-- Model: int_sales_enriched  (layer: intermediate)
-- Migrated from QlikView table 'SalesEnriched' [resident]

{{ config(materialized='view') }}

with base as (
    select
    OrderID,
    ProductID,
    CustomerID,
    Country,
    OrderDate,
    Quantity,
    GrossAmount
    from {{ ref('int_sales_raw') }}
)

select *
from base
left join {{ ref('int_sales_enriched_join6') }} as j1 using (PRODUCTID)
