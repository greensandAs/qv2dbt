-- Model: mart_sales_fact  (layer: mart)
-- Migrated from QlikView table 'sales_fact' [resident]
-- WARNING: Aggregating LOAD (GROUP BY) - verify aggregate expressions.

{{ config(materialized='table') }}

with base as (
    select
    ProductID,
    Country,
    TherapeuticArea,
    YEAR(OrderDate) as ORDERYEAR,
    SUM(GrossAmount) as TOTALREVENUE,
    SUM(Quantity) as TOTALUNITS
    from {{ ref('int_sales_enriched') }}
    group by ProductID, Country, TherapeuticArea, YEAR(OrderDate)
)

select *
from base
