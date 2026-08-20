-- CustomerAddressMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_CUSTOMER_ADDRESS_MASTER as
select
    "Address Number",
    "Customer Address 1",
    "Zip Code"
from LUNDBECK_UKIE.RAW.CUSTOMERADDRESSMASTER as base
;
