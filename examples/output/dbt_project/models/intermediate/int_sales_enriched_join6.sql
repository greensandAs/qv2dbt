-- Model: int_sales_enriched_join6  (layer: intermediate)
-- Migrated from QlikView table 'SalesEnriched__join6' [resident]

{{ config(materialized='view') }}

with base as (
    select
    ProductID,
    ProductName,
    TherapeuticArea
    from {{ ref('stg_products') }}
)

select *
from base
