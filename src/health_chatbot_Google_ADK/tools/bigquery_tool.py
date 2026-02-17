from typing import Dict, Any, List, Optional
from agents import function_tool
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPICallError, BadRequest
from src.health_chatbot.config import BQ_PROJECT, BQ_DATASET, BQ_TABLE


# Initialize client once (uses GOOGLE_APPLICATION_CREDENTIALS)
_bq_client = bigquery.Client(project=BQ_PROJECT)

_db_schema = None


def get_db_schema() -> Dict[str, Any]:
    """
    Retrieves the database schema for the specified BigQuery table using run_bigquery_query.

    This function fetches the schema on its first call and caches it in memory.
    Subsequent calls return the cached schema, avoiding redundant API requests.

    Returns
    -------
    Union[List[Dict[str, Any]], str]
        - On success: A list of dictionaries, where each dictionary
          represents a column in the schema (e.g., `{'column_name': 'age', 'data_type': 'INT64'}`).
        - On failure: A string containing the error message.
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


def _extract_bq_error(error: BadRequest) -> str:
    """
    Extract a concise, readable error message from BigQuery BadRequest.
    """

def run_bigquery_query(sql: str, max_rows: int = 1000) -> Dict[str, Any]:
    """
    Execute a BigQuery SQL query and return structured results.

    IMPORTANT DESIGN NOTES:
    - This function is intentionally synchronous.
    - This function must accept ONLY JSON-serializable arguments.
    - Fully-qualified SQL controls which project/dataset is queried.
    - This function does NOT retry on failure. Retry logic is handled by the SQLAgent itself.


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
        # Submit query
        query_job = _bq_client.query(sql)

        # Block until completion and fetch results
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
        # SQL syntax / semantic errors
        return {
            "success": False,
            "sql": sql,
            "row_count": 0,
            "rows": [],
            "error_message": _extract_bq_error(e),
        }

    except GoogleAPICallError as e:
        # Network / permission / API-level errors
        return {
            "success": False,
            "sql": sql,
            "row_count": 0,
            "rows": [],
            "error_message": str(e),
        }

    except Exception as e:
        # Catch-all for safety (agent will retry or fail gracefully)
        return {
            "success": False,
            "sql": sql,
            "row_count": 0,
            "rows": [],
            "error_message": str(e),
        }


def _extract_bq_error(error: BadRequest) -> str:
    """
    Extract a concise, readable error message from BigQuery BadRequest.
    """
    if error.message and "Syntax error" in error.message:
        return error.message
    return str(error)
