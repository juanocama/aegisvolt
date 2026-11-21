import os


FEATURE_FLAG_NAMES = (
    "ENABLE_DYNAMIC_SURGE_PRICING",
    "ENABLE_FAST_CHARGE_BOOST",
    "SIMULATE_CHARGER_HARDWARE_FAULT",
)


def load_feature_flags() -> dict[str, bool]:
    flags = {}
    for name in FEATURE_FLAG_NAMES:
        value = os.getenv(name)
        if value is None:
            flags[name] = False
        elif value.strip().lower() in {"true", "1"}:
            flags[name] = True
        elif value.strip().lower() in {"false", "0"}:
            flags[name] = False
        else:
            raise ValueError(f"{name} must be set to true or false")
    return flags
