export const APP_CONFIG = {
  appName: "TravelCast AviatorGraf Prep",
  supabaseUrl: "REPLACE_WITH_SUPABASE_URL",
  supabaseAnonKey: "REPLACE_WITH_SUPABASE_ANON_KEY",
  demoMode: true,
  hostedMode: false,
  freshness: {
    airportStatusMaxAgeMinutes: 10,
    forecastMaxAgeMinutes: 120,
    metarMaxAgeMinutes: 60,
    tafMaxAgeMinutes: 360
  }
};
