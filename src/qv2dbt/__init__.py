"""qv2dbt - QlikView ETL to dbt/Snowflake migration accelerator."""
from .pipeline import run_migration

__all__ = ["run_migration"]
__version__ = "0.1.0"
