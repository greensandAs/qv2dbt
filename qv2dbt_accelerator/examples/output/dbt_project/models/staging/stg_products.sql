-- Model: stg_products  (layer: staging)
-- Migrated from QlikView table 'Products' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    ProductID,
    ProductName,
    "Therapeutic Area" as THERAPEUTICAREA,
    TO_NUMBER(UnitPrice) as UNITPRICE,
    CASE WHEN Discontinued = 1 THEN 'Y' ELSE 'N' END as ISDISCONTINUED
    from {{ source('qlikview_raw', 'products') }}
)

select *
from base
