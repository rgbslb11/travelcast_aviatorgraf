export function renderRoutecast() {
  document.querySelector("#routecast").innerHTML = `<div class="card"><h2>RouteCast</h2><p>RouteCast Basic = OSRM + NWS/Open-Meteo forecast proxy. Enhanced route risk can later add OpenWeather Road Risk, Synoptic/RWIS, and 511/DOT events.</p><div class="graphics-copy"><strong>Demo Route:</strong> DEN airport to downtown Denver<br>Impact: Monitor<br>Reason: Thunderstorms near terminal area may affect ground transfer timing.</div></div>`;
}
