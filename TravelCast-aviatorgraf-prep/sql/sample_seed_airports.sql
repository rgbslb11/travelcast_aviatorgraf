insert into airports (airport_id, iata, icao, faa_lid, display_name, airport_name, city, state, country, region, timezone, latitude, longitude, elevation_ft, active)
values
('KDEN','DEN','KDEN','DEN','Denver','Denver International Airport','Denver','CO','US','Rocky Mountains','America/Denver',39.8561,-104.6737,5434,true),
('KDFW','DFW','KDFW','DFW','Dallas/Fort Worth','Dallas Fort Worth International Airport','Dallas','TX','US','Southern Plains','America/Chicago',32.8998,-97.0403,607,true),
('KATL','ATL','KATL','ATL','Atlanta','Hartsfield-Jackson Atlanta International Airport','Atlanta','GA','US','Southeast','America/New_York',33.6367,-84.4281,1026,true),
('KMIA','MIA','KMIA','MIA','Miami','Miami International Airport','Miami','FL','US','Florida','America/New_York',25.7959,-80.2870,8,true),
('KSFO','SFO','KSFO','SFO','San Francisco','San Francisco International Airport','San Francisco','CA','US','West Coast','America/Los_Angeles',37.6213,-122.3790,13,true),
('KLAS','LAS','KLAS','LAS','Las Vegas','Harry Reid International Airport','Las Vegas','NV','US','Desert Southwest','America/Los_Angeles',36.0840,-115.1537,2181,true),
('KLAX','LAX','KLAX','LAX','Los Angeles','Los Angeles International Airport','Los Angeles','CA','US','West Coast','America/Los_Angeles',33.9416,-118.4085,128,true),
('KJFK','JFK','KJFK','JFK','New York JFK','John F. Kennedy International Airport','New York','NY','US','Northeast','America/New_York',40.6413,-73.7781,13,true),
('KORD','ORD','KORD','ORD','Chicago O''Hare','Chicago O''Hare International Airport','Chicago','IL','US','Great Lakes','America/Chicago',41.9742,-87.9073,672,true),
('KIAH','IAH','KIAH','IAH','Houston Intercontinental','George Bush Intercontinental Airport','Houston','TX','US','Southern Plains','America/Chicago',29.9902,-95.3368,97,true)
on conflict (airport_id) do update set airport_name = excluded.airport_name, active = excluded.active;
