# main.py
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .model import DBConnectionCreate, AskRequest
from .db_manager import save_connection, test_connection, run_readonly_query
from .schema_fetcher import fetch_schema
from .llm_agent import generate_sql
from .sql_validator import is_safe_sql

# basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm-db-assistant")

app = FastAPI(title="LLM DB Assistant")

@app.get("/")
def root():
    return {
        "status": "running",
        "service": "LLM DB Assistant Backend",
        "message": "Your FastAPI backend is live on Render!"
    }

@app.post("/connect")
def connect(cfg: DBConnectionCreate):
    save_connection(cfg.name, cfg.dict())
    try:
        test_connection(cfg.name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Connection test failed: {e}")
    return {"status": "connected", "name": cfg.name}


@app.get("/schema/{connection_name}")
def get_schema(connection_name: str):
    try:
        schema = fetch_schema(connection_name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return schema


@app.post("/ask")
def ask(req: AskRequest):

    try:
        schema = fetch_schema(req.connection_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Connection not found: {req.connection_name}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch schema: {e}")

    try:
        sql = generate_sql(schema, req.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation error: {e}")

    if not sql or not isinstance(sql, str):
        raise HTTPException(status_code=500, detail="LLM did not return valid SQL.")

    logger.info("Generated SQL: %s", sql)

    try:
        if not is_safe_sql(sql):
            raise HTTPException(status_code=400, detail="Generated SQL failed safety checks.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SQL safety check failed: {e}")

    try:
        result = run_readonly_query(req.connection_name, sql)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution error: {e}")

    if isinstance(result, dict):
        cols = result.get("columns", [])
        rows = result.get("rows", [])
    elif isinstance(result, (list, tuple)) and len(result) == 2:
        cols, rows = result
    else:
        raise HTTPException(status_code=500, detail="Unexpected query result format")

    try:
        columns_list = list(cols)
    except Exception:
        columns_list = cols

    return {
        "sql": sql,
        "columns": columns_list,
        "rows": rows,
    }
