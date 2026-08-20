-- Model: int_orders  (layer: intermediate)
-- Migrated from QlikView table 'Orders' [qvd]
-- WARNING: Function 'Peek()' requires manual review (no deterministic Snowflake equivalent).

{{ config(materialized='view') }}

with base as (
    select
    OrderID,
    CustomerID,
    ProductID,
    TO_NUMBER(Quantity) as QUANTITY,
    TO_NUMBER(UnitPrice) * TO_NUMBER(Quantity) as GROSSAMOUNT,
    GREATEST(Discount1, Discount2) as MAXDISCOUNT,
    /* TODO review */ Peek('PrevOrder', -1, 'Orders') as PREVORDERREF,
    TO_DATE(OrderDate) as ORDERDATE,
    DATE_TRUNC('MONTH', OrderDate) as ORDERMONTH
    from {{ source('qlikview_raw', 'orders') }}
)

select *
from base
left join {{ ref('int_orders_join3') }} as j1 using (CUSTOMERID)
