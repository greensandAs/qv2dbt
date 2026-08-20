-- Mapping table migrated from QlikView MAPPING LOAD 'map_1'.
-- Used by the apply_map() macro to resolve ApplyMap() calls.
{{ config(materialized='table') }}

select
    CountryCode as mapped_key,
    CountryName as mapped_value
from {{ ref('lib_dw_qvd_country_qvd') }}
