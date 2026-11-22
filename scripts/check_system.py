"""Check that system.yaml matches the OpenAPI documents.

Every endpoint a service calls across the seam must exist in the called
service's openapi.yaml, and every listed file and folder must exist.
"""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    system = yaml.safe_load((ROOT / "system.yaml").read_text(encoding="utf-8"))
    services = system["services"]
    errors = []

    for name, svc in services.items():
        for key in ("path", "openapi", "migrations"):
            if not (ROOT / svc[key]).exists():
                errors.append(f"{name}: {key} {svc[key]} does not exist")

    for name in system["ui"]["calls"]:
        if name not in services:
            errors.append(f"ui calls unknown service {name}")

    for name, svc in services.items():
        for call in svc.get("calls", []):
            target = services.get(call["service"])
            if target is None:
                errors.append(f"{name} calls unknown service {call['service']}")
                continue
            if call["url_env"] not in svc["env"]:
                errors.append(f"{name}: {call['url_env']} is not listed in env")
            doc = yaml.safe_load((ROOT / target["openapi"]).read_text(encoding="utf-8"))
            for endpoint in call["endpoints"]:
                method, path = endpoint.split(" ", 1)
                if method.lower() not in doc.get("paths", {}).get(path, {}):
                    errors.append(f"{name} calls {endpoint}, missing from {target['openapi']}")

    for message in errors:
        print("ERROR:", message)
    if not errors:
        print("system.yaml matches the OpenAPI documents")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
