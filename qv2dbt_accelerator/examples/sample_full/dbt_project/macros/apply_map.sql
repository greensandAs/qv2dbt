{# Resolves a QlikView ApplyMap() against a generated mapping model.
   Usage (emitted by the accelerator):
     {{ apply_map('MapName', "<key_sql>", "<default_sql>") }}
#}
{% macro apply_map(map_name, key_sql, default_sql='null') %}
    coalesce(
        (
            select mapped_value
            from {{ ref('map_' ~ map_name | lower) }}
            where mapped_key = {{ key_sql }}
            limit 1
        ),
        {{ default_sql }}
    )
{% endmacro %}
