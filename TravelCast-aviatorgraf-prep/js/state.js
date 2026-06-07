export const appState = {
  airportStatusRecords: [],
  selectedAirport: null,
  graphicsQueue: [],
  sourceSystems: [],
  demoModeActive: true,
  warnings: []
};

const QUEUE_KEY = "travelcast_aviatorgraf_graphics_queue";

export function loadQueue() {
  try {
    appState.graphicsQueue = JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
  } catch {
    appState.graphicsQueue = [];
  }
  return appState.graphicsQueue;
}

export function saveQueue() {
  localStorage.setItem(QUEUE_KEY, JSON.stringify(appState.graphicsQueue));
}

export function addQueueItem(item) {
  appState.graphicsQueue.push({ id: crypto.randomUUID(), status: "Draft", generatedAt: new Date().toISOString(), ...item });
  saveQueue();
}

export function updateQueueItem(id, patch) {
  appState.graphicsQueue = appState.graphicsQueue.map(q => q.id === id ? { ...q, ...patch } : q);
  saveQueue();
}

export function removeQueueItem(id) {
  appState.graphicsQueue = appState.graphicsQueue.filter(q => q.id !== id);
  saveQueue();
}
