import os


ENVIRONMENTS = {"dev", "test", "prod"}


def current_environment() -> str:
    environment = os.getenv("ENVIRONMENT", "dev").strip().lower()
    if environment not in ENVIRONMENTS:
        raise ValueError("ENVIRONMENT must be one of: dev, test, prod")
    return environment


def environment_table_name(service: str, setting_name: str = "TABLE_NAME") -> str:
    environment = current_environment()
    table_name = os.getenv(setting_name, f"aegisvolt-{environment}-{service}")
    if environment not in table_name.split("-"):
        raise ValueError(
            f"{setting_name} must include the active environment '{environment}'"
        )
    return table_name
