-- ============================================================
-- TravelCast AviatorGraf Prep
-- 01_seed_focus_airports.sql
-- ============================================================
-- PURPOSE
--   Upsert the 71 TravelCast focus airports into the airports table.
--   Safe to rerun — uses INSERT ... ON CONFLICT DO UPDATE.
--
-- RUN ORDER
--   Run AFTER 00_supabase_bootstrap.sql.
--   Paste into Supabase SQL Editor and click Run.
--
-- NO SECRETS IN THIS FILE
-- ============================================================

INSERT INTO airports
  (airport_id, iata, icao, faa_lid, display_name, city, region, country, latitude, longitude, active)
VALUES
-- ── Northeast ────────────────────────────────────────────────────────
  ('KJFK','JFK','KJFK','JFK','New York JFK','New York','Northeast','US',40.6413,-73.7781,true),
  ('KEWR','EWR','KEWR','EWR','Newark Liberty','Newark','Northeast','US',40.6925,-74.1687,true),
  ('KLGA','LGA','KLGA','LGA','New York LaGuardia','New York','Northeast','US',40.7772,-73.8726,true),
  ('KBOS','BOS','KBOS','BOS','Boston Logan','Boston','Northeast','US',42.3656,-71.0096,true),
  ('KPHL','PHL','KPHL','PHL','Philadelphia Intl','Philadelphia','Northeast','US',39.8744,-75.2424,true),
  ('KIAD','IAD','KIAD','IAD','Washington Dulles','Washington','Northeast','US',38.9531,-77.4565,true),
  ('KDCA','DCA','KDCA','DCA','Washington Reagan','Washington','Northeast','US',38.8521,-77.0378,true),
  ('KBWI','BWI','KBWI','BWI','Baltimore/Washington','Baltimore','Northeast','US',39.1754,-76.6682,true),
  ('KBUF','BUF','KBUF','BUF','Buffalo Niagara','Buffalo','Northeast','US',42.9405,-78.7322,true),
  ('KRIC','RIC','KRIC','RIC','Richmond Intl','Richmond','Northeast','US',37.5052,-77.3197,true),
-- ── Southeast ────────────────────────────────────────────────────────
  ('KATL','ATL','KATL','ATL','Atlanta','Atlanta','Southeast','US',33.6367,-84.4281,true),
  ('KCLT','CLT','KCLT','CLT','Charlotte Douglas','Charlotte','Southeast','US',35.2140,-80.9431,true),
  ('KRDU','RDU','KRDU','RDU','Raleigh-Durham','Raleigh','Southeast','US',35.8777,-78.7875,true),
  ('KMCO','MCO','KMCO','MCO','Orlando Intl','Orlando','Southeast','US',28.4294,-81.3089,true),
  ('KTPA','TPA','KTPA','TPA','Tampa Intl','Tampa','Southeast','US',27.9755,-82.5332,true),
  ('KJAX','JAX','KJAX','JAX','Jacksonville Intl','Jacksonville','Southeast','US',30.4941,-81.6879,true),
  ('KSAV','SAV','KSAV','SAV','Savannah/Hilton Head','Savannah','Southeast','US',32.1276,-81.2021,true),
  ('KCHS','CHS','KCHS','CHS','Charleston Intl','Charleston','Southeast','US',32.8986,-80.0405,true),
-- ── Florida ──────────────────────────────────────────────────────────
  ('KMIA','MIA','KMIA','MIA','Miami Intl','Miami','Florida','US',25.7959,-80.2870,true),
  ('KFLL','FLL','KFLL','FLL','Fort Lauderdale-Hollywood','Fort Lauderdale','Florida','US',26.0726,-80.1527,true),
  ('KPBI','PBI','KPBI','PBI','Palm Beach Intl','West Palm Beach','Florida','US',26.6832,-80.0956,true),
  ('KRSW','RSW','KRSW','RSW','Southwest Florida Intl','Fort Myers','Florida','US',26.5362,-81.7552,true),
-- ── Great Lakes ──────────────────────────────────────────────────────
  ('KORD','ORD','KORD','ORD','Chicago O''Hare','Chicago','Great Lakes','US',41.9742,-87.9073,true),
  ('KMDW','MDW','KMDW','MDW','Chicago Midway','Chicago','Great Lakes','US',41.7859,-87.7440,true),
  ('KDTW','DTW','KDTW','DTW','Detroit Metro','Detroit','Great Lakes','US',42.2162,-83.3554,true),
  ('KCLE','CLE','KCLE','CLE','Cleveland Hopkins','Cleveland','Great Lakes','US',41.4117,-81.8498,true),
  ('KPIT','PIT','KPIT','PIT','Pittsburgh Intl','Pittsburgh','Great Lakes','US',40.4915,-80.2329,true),
  ('KCVG','CVG','KCVG','CVG','Cincinnati/N. Kentucky','Cincinnati','Great Lakes','US',39.0488,-84.6678,true),
  ('KMSP','MSP','KMSP','MSP','Minneapolis-St. Paul','Minneapolis','Great Lakes','US',44.8820,-93.2218,true),
  ('KMKE','MKE','KMKE','MKE','Milwaukee Mitchell','Milwaukee','Great Lakes','US',42.9472,-87.8966,true),
-- ── Southern Plains ──────────────────────────────────────────────────
  ('KDFW','DFW','KDFW','DFW','Dallas/Fort Worth','Dallas','Southern Plains','US',32.8998,-97.0403,true),
  ('KIAH','IAH','KIAH','IAH','Houston Intercontinental','Houston','Southern Plains','US',29.9902,-95.3368,true),
  ('KDAL','DAL','KDAL','DAL','Dallas Love Field','Dallas','Southern Plains','US',32.8473,-96.8517,true),
  ('KHOU','HOU','KHOU','HOU','Houston Hobby','Houston','Southern Plains','US',29.6454,-95.2789,true),
  ('KAUS','AUS','KAUS','AUS','Austin-Bergstrom','Austin','Southern Plains','US',30.1975,-97.6664,true),
  ('KSAT','SAT','KSAT','SAT','San Antonio Intl','San Antonio','Southern Plains','US',29.5337,-98.4698,true),
  ('KMSY','MSY','KMSY','MSY','New Orleans Armstrong','New Orleans','Southern Plains','US',29.9934,-90.2580,true),
  ('KBNA','BNA','KBNA','BNA','Nashville Intl','Nashville','Southern Plains','US',36.1245,-86.6782,true),
  ('KOKC','OKC','KOKC','OKC','Oklahoma City Will Rogers','Oklahoma City','Southern Plains','US',35.3931,-97.6007,true),
  ('KTUL','TUL','KTUL','TUL','Tulsa Intl','Tulsa','Southern Plains','US',36.1984,-95.8881,true),
-- ── Mid-South ────────────────────────────────────────────────────────
  ('KMEM','MEM','KMEM','MEM','Memphis Intl','Memphis','Mid-South','US',35.0424,-89.9767,true),
  ('KSTL','STL','KSTL','STL','St. Louis Lambert','St. Louis','Mid-South','US',38.7487,-90.3700,true),
  ('KIND','IND','KIND','IND','Indianapolis Intl','Indianapolis','Mid-South','US',39.7173,-86.2944,true),
  ('KCMH','CMH','KCMH','CMH','Columbus John Glenn','Columbus','Mid-South','US',39.9980,-82.8919,true),
  ('KMCI','MCI','KMCI','MCI','Kansas City Intl','Kansas City','Mid-South','US',39.2976,-94.7139,true),
-- ── Midwest ──────────────────────────────────────────────────────────
  ('KDSM','DSM','KDSM','DSM','Des Moines Intl','Des Moines','Midwest','US',41.5340,-93.6631,true),
  ('KOMA','OMA','KOMA','OMA','Eppley Airfield','Omaha','Midwest','US',41.3032,-95.8941,true),
  ('KLIT','LIT','KLIT','LIT','Little Rock Clinton','Little Rock','Midwest','US',34.7294,-92.2243,true),
-- ── Rocky Mountains ──────────────────────────────────────────────────
  ('KDEN','DEN','KDEN','DEN','Denver Intl','Denver','Rocky Mountains','US',39.8561,-104.6737,true),
  ('KSLC','SLC','KSLC','SLC','Salt Lake City Intl','Salt Lake City','Rocky Mountains','US',40.7884,-111.9778,true),
  ('KABQ','ABQ','KABQ','ABQ','Albuquerque Sunport','Albuquerque','Rocky Mountains','US',35.0402,-106.6090,true),
  ('KBOI','BOI','KBOI','BOI','Boise Airport','Boise','Rocky Mountains','US',43.5644,-116.2228,true),
  ('KCOS','COS','KCOS','COS','Colorado Springs','Colorado Springs','Rocky Mountains','US',38.8058,-104.7006,true),
  ('KBZN','BZN','KBZN','BZN','Bozeman Yellowstone','Bozeman','Rocky Mountains','US',45.7775,-111.1533,true),
-- ── Desert Southwest ─────────────────────────────────────────────────
  ('KLAS','LAS','KLAS','LAS','Las Vegas Harry Reid','Las Vegas','Desert Southwest','US',36.0840,-115.1537,true),
  ('KPHX','PHX','KPHX','PHX','Phoenix Sky Harbor','Phoenix','Desert Southwest','US',33.4373,-112.0078,true),
  ('KTUS','TUS','KTUS','TUS','Tucson Intl','Tucson','Desert Southwest','US',32.1161,-110.9410,true),
  ('KELP','ELP','KELP','ELP','El Paso Intl','El Paso','Desert Southwest','US',31.8072,-106.3779,true),
-- ── West Coast ───────────────────────────────────────────────────────
  ('KLAX','LAX','KLAX','LAX','Los Angeles Intl','Los Angeles','West Coast','US',33.9416,-118.4085,true),
  ('KSFO','SFO','KSFO','SFO','San Francisco Intl','San Francisco','West Coast','US',37.6213,-122.3790,true),
  ('KSAN','SAN','KSAN','SAN','San Diego Intl','San Diego','West Coast','US',32.7338,-117.1933,true),
  ('KSJC','SJC','KSJC','SJC','San Jose Intl','San Jose','West Coast','US',37.3626,-121.9290,true),
  ('KOAK','OAK','KOAK','OAK','Oakland Intl','Oakland','West Coast','US',37.7213,-122.2208,true),
  ('KSEA','SEA','KSEA','SEA','Seattle-Tacoma Intl','Seattle','West Coast','US',47.4502,-122.3088,true),
  ('KPDX','PDX','KPDX','PDX','Portland Intl','Portland','West Coast','US',45.5898,-122.5951,true),
  ('KSMF','SMF','KSMF','SMF','Sacramento Intl','Sacramento','West Coast','US',38.6954,-121.5908,true),
  ('KGEG','GEG','KGEG','GEG','Spokane Intl','Spokane','West Coast','US',47.6199,-117.5338,true),
-- ── Pacific ──────────────────────────────────────────────────────────
  ('PHNL','HNL','PHNL','HNL','Honolulu Intl','Honolulu','Pacific','US',21.3245,-157.9251,true),
  ('PHOG','OGG','PHOG','OGG','Kahului Airport','Maui','Pacific','US',20.8986,-156.4305,true),
  ('PANC','ANC','PANC','ANC','Anchorage Intl','Anchorage','Pacific','US',61.1741,-149.9961,true),
  ('TJSJ','SJU','TJSJ','SJU','San Juan Luis Munoz Marin','San Juan','Pacific','US',18.4394,-66.0018,true)
ON CONFLICT (airport_id) DO UPDATE SET
  iata          = EXCLUDED.iata,
  icao          = EXCLUDED.icao,
  faa_lid       = EXCLUDED.faa_lid,
  display_name  = EXCLUDED.display_name,
  city          = EXCLUDED.city,
  region        = EXCLUDED.region,
  country       = EXCLUDED.country,
  latitude      = EXCLUDED.latitude,
  longitude     = EXCLUDED.longitude,
  active        = EXCLUDED.active;

-- Verify count after upsert
SELECT region, count(*) AS airport_count
FROM airports
WHERE active = true
GROUP BY region
ORDER BY region;
