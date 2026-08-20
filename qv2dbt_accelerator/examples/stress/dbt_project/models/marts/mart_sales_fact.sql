-- Model: mart_sales_fact  (layer: mart)
-- Migrated from QlikView table 'sales_fact' [resident]
-- WARNING: Aggregating LOAD (GROUP BY) - verify aggregate expressions.

{{ config(materialized='table') }}

with base as (
    select
    ProductID,
    Country,
    YEAR(OrderDate) as ORDERYEAR,
    MONTH(OrderDate) as ORDERMONTH,
    SUM(GrossAmount) as TOTALREVENUE,
    COUNT(OrderID) as ORDERCOUNT,
    AVG(GrossAmount) as AVGORDERVALUE,
    MEDIAN(GrossAmount) as MEDIANORDERVALUE
    from {{ ref('int_orders') }}
    group by ProductID, Country, YEAR(OrderDate), MONTH(OrderDate)
)

select *
from base
