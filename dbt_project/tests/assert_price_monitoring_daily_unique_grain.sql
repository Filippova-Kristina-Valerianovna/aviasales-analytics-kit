select
    collected_date,
    route_key,
    origin_iata,
    destination_iata,
    departure_date,
    currency_code,
    count(*) as duplicate_count

from {{ ref('mart_price_monitoring_daily_dbt') }}

group by
    collected_date,
    route_key,
    origin_iata,
    destination_iata,
    departure_date,
    currency_code

having count(*) > 1