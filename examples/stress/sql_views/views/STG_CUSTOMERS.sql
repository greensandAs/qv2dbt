-- Customers  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_CUSTOMERS as
select
    CustomerID,
    INITCAP(CustomerName) as CUSTOMERNAME,
    UPPER(TRIM(Email)) as EMAIL,
    coalesce((select MAPPED_VALUE from LUNDBECK_UKIE.STAGING.MAP_COUNTRY_MAP where MAPPED_KEY = CountryCode limit 1), 'N/A') as COUNTRY,
    LEFT(Phone, 3) as AREACODE,
    CASE WHEN CreditLimit IS NULL THEN 0 ELSE CreditLimit END as CREDITLIMIT,
    TO_DATE(SignupDate, 'YYYY-MM-DD') as SIGNUPDATE,
    DATEADD('YEAR', 1, SignupDate) as RENEWALDATE,
    SIGN(Balance) as BALANCESIGN
from LUNDBECK_UKIE.RAW.CUSTOMERS as base
where LENGTH(CustomerID) > 0
;
