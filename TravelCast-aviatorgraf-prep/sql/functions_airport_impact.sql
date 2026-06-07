-- Starter impact helper. Adjust logic after real source data is flowing.
create or replace function travelcast_impact_rank(color text)
returns integer language sql immutable as $$
  select case
    when lower(coalesce(color,'')) like '%red%' then 3
    when lower(coalesce(color,'')) like '%amber%' then 2
    when lower(coalesce(color,'')) like '%green%' then 1
    else 0
  end;
$$;
