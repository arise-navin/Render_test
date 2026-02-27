from agents import architecture, scripts, performance, security, integration, data_health, upgrade, license_optimization
from concurrent.futures import ThreadPoolExecutor, as_completed

AGENTS = {
    "architecture": architecture.run,
    "scripts": scripts.run,
    "performance": performance.run,
    "security": security.run,
    "integration": integration.run,
    "data_health": data_health.run,
    "upgrade": upgrade.run,
    "license_optimization": license_optimization.run,
}

def run_all():
    """Run all agents in parallel for maximum speed."""
    results = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_key = {executor.submit(fn): key for key, fn in AGENTS.items()}
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
            except Exception as e:
                results[key] = {"error": str(e), "risk_score": None, "total_records": 0}
    return results