-- CustomerMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_CUSTOMER_MASTER as
select
    "Address Number",
    "Business Family",
    Segment,
    Customer,
    "Customer Number",
    "Customer Type",
    "Distribution Channel Mgr",
    Division,
    Phone,
    "Region Code",
    "Regional Sales Mgr",
    "Zone Mgr",
    "Sales Rep"
from LUNDBECK_UKIE.RAW.CUSTOMERMASTER as base
;
