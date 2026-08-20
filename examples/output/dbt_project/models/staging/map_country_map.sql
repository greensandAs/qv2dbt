-- Mapping table migrated from QlikView MAPPING LOAD 'CountryMap'.
-- Used by the apply_map() macro to resolve ApplyMap() calls.
{{ config(materialized='table') }}

select
    CountryCode as mapped_key,
    CountryName as mapped_value
from {{ ref('lib_data_files_qvd_country_ref_qvd') }}
