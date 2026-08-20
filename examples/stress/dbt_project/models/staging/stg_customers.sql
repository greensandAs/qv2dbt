-- Model: stg_customers  (layer: staging)
-- Migrated from QlikView table 'Customers' [qvd]
-- WARNING: ApplyMap('CountryMap', ...) converted to apply_map() macro - confirm mapping table was generated.

{{ config(materialized='view') }}

with base as (
    select
    CustomerID,
    INITCAP(CustomerName) as CUSTOMERNAME,
    UPPER(TRIM(Email)) as EMAIL,
    {{ apply_map('CountryMap', "CountryCode", "'N/A'") }} as COUNTRY,
    LEFT(Phone, 3) as AREACODE,
    CASE WHEN CreditLimit IS NULL THEN 0 ELSE CreditLimit END as CREDITLIMIT,
    TO_DATE(SignupDate, 'YYYY-MM-DD') as SIGNUPDATE,
    DATEADD('YEAR', 1, SignupDate) as RENEWALDATE,
    SIGN(Balance) as BALANCESIGN
    from {{ source('qlikview_raw', 'customers') }}
    where LENGTH(CustomerID) > 0
)

select *
from base
