with source as (

    select *
    from {{ source('staging', 'flight_price_observations') }}

),

renamed as (

    select
        observation_id,
        response_id,
        origin_iata,
        destination_iata,
        route_key,
        departure_date,
        return_date,
        price,
        currency_code,
        airline_code,
        flight_number,
        transfers,
        duration_minutes,
        collected_ts,
        (collected_ts AT TIME ZONE 'Europe/Moscow')::date as collected_date,
        source_system,
        created_at

    from source

)

select *
from renamed