"""BigQuery tool using personal user credentials (gcloud auth login).

The default ADC is reserved for the service account (Gemini/Vertex AI).
BigQuery data access uses your personal email via gcloud user credentials.

Setup:
    gcloud auth login    # Authenticate with your personal email
"""

from typing import Any, Dict, List

from google.api_core.exceptions import BadRequest, GoogleAPICallError
from google.cloud import bigquery

from src.health_chatbot_Google_ADK.config_adk import BQ_DATASET, BQ_PROJECT, BQ_TABLE


# Initialize BQ client - uses ADC by default.
# For personal credentials, run: gcloud auth application-default login
# Or set GOOGLE_APPLICATION_CREDENTIALS to point to a user credential file.
import os
from google.auth import load_credentials_from_file

adc_path = os.path.join(os.environ["APPDATA"],"gcloud","application_default_credentials.json",)

creds, _ = load_credentials_from_file(adc_path)
_bq_client = bigquery.Client(project=BQ_PROJECT, credentials=creds)

_db_schema = None


def get_db_schema() -> Dict[str, Any]:
    """Retrieve the database schema for the BigQuery table.

    Fetches the schema on first call and caches it in memory.
    Subsequent calls return the cached schema.

    Returns
    -------
    Union[List[Dict[str, Any]], str]
        On success: list of dicts with column_name and data_type.
        On failure: error message string.
    """
    global _db_schema

    if _db_schema:
        return _db_schema

    info_schema_path = f"`{BQ_PROJECT}.{BQ_DATASET}.INFORMATION_SCHEMA.COLUMNS`"

    sql = f"""
        SELECT column_name, data_type
        FROM {info_schema_path}
        WHERE table_name = '{BQ_TABLE}'
    """

    result = run_bigquery_query(sql)

    if result["success"]:
        _db_schema = result["rows"]
        return _db_schema
    else:
        return result["error_message"]


def run_bigquery_query(sql: str, max_rows: int = 1000) -> Dict[str, Any]:
    """Execute a BigQuery SQL query and return structured results.

    Parameters
    ----------
    sql : str
        Fully-qualified BigQuery SQL query.
    max_rows : int
        Maximum number of rows to return.

    Returns
    -------
    Dict[str, Any]
        {
            "success": bool,
            "sql": str,
            "row_count": int,
            "rows": List[Dict],
            "error_message": Optional[str]
        }
    """
    try:
        query_job = _bq_client.query(sql)
        results = query_job.result(max_results=max_rows)
        rows: List[Dict[str, Any]] = [dict(row) for row in results]

        return {
            "success": True,
            "sql": sql,
            "row_count": len(rows),
            "rows": rows,
            "error_message": None,
        }

    except BadRequest as e:
        return {
            "success": False,
            "sql": sql,
            "row_count": 0,
            "rows": [],
            "error_message": _extract_bq_error(e),
        }

    except GoogleAPICallError as e:
        return {
            "success": False,
            "sql": sql,
            "row_count": 0,
            "rows": [],
            "error_message": str(e),
        }

    except Exception as e:
        return {
            "success": False,
            "sql": sql,
            "row_count": 0,
            "rows": [],
            "error_message": str(e),
        }


def _extract_bq_error(error: BadRequest) -> str:
    """Extract a concise error message from BigQuery BadRequest."""
    if error.message and "Syntax error" in error.message:
        return error.message
    return str(error)
