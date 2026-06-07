export function renderFaaOps() {
  document.querySelector("#faa-ops").innerHTML = `<div class="card"><h2>ATCSCC / FAA Ops Plan</h2><p><strong>Operational Planning — FAA ATCSCC.</strong> This panel will show terminal active/planned, enroute planned, SWAP/CDR/capping/tunneling, and playbook correlations after the ATCSCC parser is wired.</p><div class="warning">Demo mode: no live ATCSCC plan loaded.</div></div>`;
}
