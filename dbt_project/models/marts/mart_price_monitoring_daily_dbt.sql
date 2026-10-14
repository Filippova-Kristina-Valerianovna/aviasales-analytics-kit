with observations as (

    select *
    from {{ ref('stg_flight_price_observations') }}

),

daily_prices as (

    select
        collected_date,
        route_key,
        origin_iata,
        destination_iata,
        departure_date,
        currency_code,

        count(*) as offers_count,

        min(price) as min_price,
        round(avg(price), 2) as avg_price,
        percentile_cont(0.5::double precision)
            within group (order by price::double precision)
            as median_price,
        max(price) as max_price,

        count(*) filter (
            where transfers = 0
        ) as direct_offers_count,

        round(
            (count(*) filter (where transfers = 0))::numeric
            / nullif(count(*), 0)::numeric,
            4
        ) as direct_offers_share,

        round(avg(transfers), 2) as avg_transfers,
        round(avg(duration_minutes), 0) as avg_duration_minutes,

        min(collected_ts) as first_collected_ts,
        max(collected_ts) as last_collected_ts,

        min(departure_date - collected_date)
            as min_days_before_departure,
        max(departure_date - collected_date)
            as max_days_before_departure

    from observations

    group by
        collected_date,
        route_key,
        origin_iata,
        destination_iata,
        departure_date,
        currency_code

)

select *
from daily_prices