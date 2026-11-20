"""Download missing dashboard datasets from a private R2 bucket."""

from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from urllib.parse import urlparse

import streamlit as st

LOCAL_DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "local"
DATA_FILENAMES = (
    "lithuanian_education_warehouse.duckdb",
    "national_budget_expenditure_quarters_2024.csv",
)
_DOWNLOAD_LOCK = Lock()


class DataSetupError(RuntimeError):
    """A safe, user-facing description of a data setup problem."""


def _r2_connection():
    try:
        settings = st.secrets["r2"]
        values = {
            name: str(settings[name]).strip()
            for name in (
                "endpoint_url", "access_key_id", "secret_access_key", "bucket_name"
            )
        }
    except (FileNotFoundError, KeyError):
        raise DataSetupError(
            "Required datasets are missing. Configure the [r2] section in "
            "Streamlit Secrets, or restore the files in data/local/."
        ) from None
    endpoint = urlparse(values["endpoint_url"])
    if (
        not all(values.values())
        or endpoint.scheme != "https"
        or not endpoint.hostname
        or not endpoint.hostname.endswith(".r2.cloudflarestorage.com")
        or endpoint.username
        or endpoint.password
        or endpoint.path not in ("", "/")
        or endpoint.query
        or endpoint.fragment
    ):
        raise DataSetupError(
            "Check the R2 secrets: all four values are required, and endpoint_url "
            "must be the HTTPS S3 API endpoint provided by Cloudflare."
        )

    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=values["endpoint_url"],
        aws_access_key_id=values["access_key_id"],
        aws_secret_access_key=values["secret_access_key"],
        region_name="auto",
        config=Config(
            connect_timeout=10,
            read_timeout=60,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )
    return client, values["bucket_name"]


def ensure_local_data():
    """Keep local files; download only missing or empty files, atomically."""
    with _DOWNLOAD_LOCK:
        missing = [
            name for name in DATA_FILENAMES
            if not (LOCAL_DATA_DIRECTORY / name).is_file()
            or (LOCAL_DATA_DIRECTORY / name).stat().st_size == 0
        ]
        if not missing:
            return
        try:
            client, bucket = _r2_connection()
            LOCAL_DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
            for name in missing:
                temporary = None
                try:
                    with NamedTemporaryFile(
                        dir=LOCAL_DATA_DIRECTORY, prefix=f".{name}.", suffix=".part",
                        delete=False,
                    ) as handle:
                        temporary = Path(handle.name)
                    client.download_file(bucket, name, str(temporary))
                    if temporary.stat().st_size == 0:
                        raise ValueError("Empty dataset")
                    temporary.replace(LOCAL_DATA_DIRECTORY / name)
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
        except DataSetupError:
            raise
        except Exception:
            # SDK errors may include private endpoints or object details.
            raise DataSetupError(
                "The dashboard could not download its data. Check the R2 secrets, "
                "read permissions and the two uploaded filenames, then retry."
            ) from None
