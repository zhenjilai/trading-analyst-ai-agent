import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
import json
from datetime import date, datetime

class FOMCDatabase:
    """Handle PostgreSQL operations for FOMC data"""

    def __init__(self, connection_params: Dict):
        self.connection_params = connection_params

    @contextmanager
    def get_connection(self):
        conn = psycopg2.connect(**self.connection_params)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    # --- Get Latest Dates ---
    def get_latest_statement_date(self) -> Optional[str]:
        return self._get_latest_date("monetory_policy.statements", "release_date")

    def get_latest_minutes_date(self) -> Optional[str]:
        return self._get_latest_date("monetory_policy.fomc", "release_date")

    def get_latest_projection_date(self) -> Optional[str]:
        return self._get_latest_date("monetory_policy.projection_notes", "release_date")

    def get_latest_implementation_date(self) -> Optional[str]:
        return self._get_latest_date("monetory_policy.implementation_notes", "release_date")

    def _get_latest_date(self, table: str, column: str) -> Optional[str]:
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(f"""
                        SELECT TO_CHAR({column}, 'YYYY-MM-DD') AS date_str
                        FROM {table}
                        ORDER BY {column} DESC
                        LIMIT 1;
                    """)
                    result = cursor.fetchone()
                    return result['date_str'] if result else None
        except Exception as e:
            print(f"Error getting latest date from {table}: {e}")
            return None

    def get_six_months_fomc_verdict(self) -> List[Dict]:
        """Get the last 6 months of FOMC verdicts/analyses"""
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT 
                            TO_CHAR(execution_date, 'YYYY-MM-DD') AS execution_date,
                            TO_CHAR(statement_date, 'YYYY-MM-DD') AS statement_date,
                            TO_CHAR(implementation_note_date, 'YYYY-MM-DD') AS implementation_date,
                            TO_CHAR(projection_note_date, 'YYYY-MM-DD') AS projection_date,
                            TO_CHAR(minutes_date, 'YYYY-MM-DD') AS minutes_date,
                            content
                        FROM analysis.monetary_policies
                        ORDER BY execution_date DESC
                        LIMIT 6
                    """)
                    return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting 6 months FOMC verdict: {e}")
            return []

    # --- Upserts (FIXED: 2 Columns Only) ---
    def upsert_statement(self, release_date: str, statement: str, conn=None) -> bool:
        query = """
        INSERT INTO monetory_policy.statements (release_date, statement)
        VALUES (%s, %s)
        ON CONFLICT (release_date) DO UPDATE SET statement = EXCLUDED.statement;
        """
        return self._execute_upsert(query, (release_date, statement), conn)

    def upsert_minutes(self, release_date: str, minutes_content: str, conn=None) -> bool:
        query = """
        INSERT INTO monetory_policy.fomc (release_date, minutes_content)
        VALUES (%s, %s)
        ON CONFLICT (release_date) DO UPDATE SET minutes_content = EXCLUDED.minutes_content;
        """
        return self._execute_upsert(query, (release_date, minutes_content), conn)

    def upsert_projection_note(self, release_date: str, projection_note: str, conn=None) -> bool:
        query = """
        INSERT INTO monetory_policy.projection_notes (release_date, projection_note)
        VALUES (%s, %s)
        ON CONFLICT (release_date) DO UPDATE SET projection_note = EXCLUDED.projection_note;
        """
        return self._execute_upsert(query, (release_date, projection_note), conn)

    def upsert_implementation_note(self, release_date: str, implementation_note: str, conn=None) -> bool:
        query = """
        INSERT INTO monetory_policy.implementation_notes (release_date, implementation_note)
        VALUES (%s, %s)
        ON CONFLICT (release_date) DO UPDATE SET implementation_note = EXCLUDED.implementation_note;
        """
        return self._execute_upsert(query, (release_date, implementation_note), conn)

    # --- Save Analysis ---
    def save_fomc_analysis(self, data: Dict[str, Any], conn=None) -> bool:
        query = """
        INSERT INTO analysis.monetary_policies (
            statement_date,
            execution_date, 
            implementation_note_date, 
            projection_note_date, 
            minutes_date, 
            content
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (statement_date) 
        DO UPDATE SET 
            execution_date = EXCLUDED.execution_date,
            implementation_note_date = EXCLUDED.implementation_note_date,
            projection_note_date = EXCLUDED.projection_note_date,
            minutes_date = EXCLUDED.minutes_date,
            content = EXCLUDED.content;
        """
        
        def json_serial(obj):
            """JSON serializer for objects not serializable by default json code"""
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        content_val = json.dumps(data.get('content'), default=json_serial) if isinstance(data.get('content'), (dict, list)) else data.get('content')
    
        params = (
            data.get('statement_release_date'),
            data.get('execution_date'),
            data.get('implementation_note_release_date'),
            data.get('projection_note_release_date'),
            data.get('minutes_release_date'),
            content_val
        )
        return self._execute_upsert(query, params, conn)

    def _execute_upsert(self, query, params, conn=None) -> bool:
        try:
            if conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
            else:
                with self.get_connection() as new_conn:
                    with new_conn.cursor() as cursor:
                        cursor.execute(query, params)
            return True
        except Exception as e:
            print(f"DB Upsert Error: {e}")
            return False

def create_database_schema(connection_params: Dict):
    """Schema creation (Matches your 2-column format)"""
    schema_sql = """
    CREATE SCHEMA IF NOT EXISTS monetory_policy;
    CREATE SCHEMA IF NOT EXISTS analysis;
    
    CREATE TABLE IF NOT EXISTS monetory_policy.statements (
        release_date DATE PRIMARY KEY,
        statement TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS monetory_policy.fomc (
        release_date DATE PRIMARY KEY,
        minutes_content TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS monetory_policy.projection_notes (
        release_date DATE PRIMARY KEY,
        projection_note TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS monetory_policy.implementation_notes (
        release_date DATE PRIMARY KEY,
        implementation_note TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS analysis.monetary_policies (
        statement_date DATE PRIMARY KEY,
        execution_date DATE NOT NULL,
        implementation_note_date DATE,
        projection_note_date DATE,
        minutes_date DATE,
        content TEXT
    );
    """
    try:
        conn = psycopg2.connect(**connection_params)
        with conn.cursor() as cursor:
            cursor.execute(schema_sql)
        conn.commit()
        conn.close()
        print("Database schema ensured.")
    except Exception as e:
        print(f"Error creating database schema: {e}")