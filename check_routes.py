import logging
from app import app

# Controleer geregistreerde routes
print("Geregistreerde routes:")
sorted_rules = sorted(app.url_map.iter_rules(), key=lambda x: str(x))
for rule in sorted_rules:
    print(f"{rule} -> {rule.endpoint}")

# Controleer specifiek op login en index routes
print("\nZoeken naar specifieke routes:")
login_route = any(rule.endpoint == 'login' for rule in app.url_map.iter_rules())
index_route = any(rule.endpoint == 'dashboard' for rule in app.url_map.iter_rules())

print(f"Login route gevonden: {login_route}")
print(f"Index route gevonden: {index_route}")

# Controleer geïmporteerde modules
import sys
print("\nGeïmporteerde modules:")
for module_name, module in sys.modules.items():
    if 'routes' in module_name:
        print(f"- {module_name}")