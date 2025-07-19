import psycopg2
import asyncpg
from typing import Optional, List, Dict

DB_DSN = (
    "postgresql://"
    "Username:password@"
    "server/"
    "postgres?sslmode=require"
)

class DatabaseConn:
    def __init__(self):
        self.dsn = DB_DSN

    async def _connect(self):
        return await asyncpg.connect(self.dsn)

    async def execute_dynamic_ddl(self, query: str) -> Dict[str, str]:
        """Executes a DDL query (e.g., CREATE TABLE, ALTER TABLE)."""
        conn = await self._connect()
        try:
            await conn.execute(query)
            return {"status": "SUCCESS", "message": "Command executed successfully."}
        except Exception as e:
            return {"status": "FAILED", "message": f"Database error: {e}"}
        finally:
            await conn.close()

    async def _ensure_notes_table_exists(self):
        """Creates the 'notes' table if it doesn't exist. Called by DML functions."""
        query = """
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            title VARCHAR(200) UNIQUE NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
        await self.execute_dynamic_ddl(query)

    async def add_note(self, title: str, text: str) -> bool:
        await self._ensure_notes_table_exists()
        query = "INSERT INTO notes (title, text) VALUES ($1, $2) ON CONFLICT (title) DO NOTHING;"
        conn = await self._connect()
        try:
            result = await conn.execute(query, title, text)
            return "INSERT 0 1" in result
        finally:
            await conn.close()

    async def get_note_by_title(self, title: str) -> Optional[dict]:
        try:
            conn = await self._connect()
            query = "SELECT title, text, created_at, updated_at FROM notes WHERE title = $1;"
            result = await conn.fetchrow(query, title)
            await conn.close()
            return dict(result) if result else None
        except asyncpg.exceptions.UndefinedTableError:
            return None

    async def list_all_titles(self) -> List[str]:
        try:
            conn = await self._connect()
            query = "SELECT title FROM notes ORDER BY title;"
            results = await conn.fetch(query)
            await conn.close()
            return [row["title"] for row in results]
        except asyncpg.exceptions.UndefinedTableError:
            return []

    async def update_note(self, title: str, new_text: str) -> bool:
        conn = await self._connect()
        try:
            # This also updates the 'updated_at' timestamp via a trigger if it exists
            query = "UPDATE notes SET text = $1, updated_at = NOW() WHERE title = $2;"
            result = await conn.execute(query, new_text, title)
            return "UPDATE 1" in result
        except asyncpg.exceptions.UndefinedTableError:
            return False
        finally:
            await conn.close()

    async def delete_note(self, title: str) -> bool:
        conn = await self._connect()
        try:
            query = "DELETE FROM notes WHERE title = $1;"
            result = await conn.execute(query, title)
            return "DELETE 1" in result
        except asyncpg.exceptions.UndefinedTableError:
            return False
        finally:
            await conn.close()

    async def search_notes(self, search_term: str) -> List[str]:
        try:
            conn = await self._connect()
            query = "SELECT title FROM notes WHERE text ILIKE $1 ORDER BY title;"
            results = await conn.fetch(query, f"%{search_term}%")
            await conn.close()
            return [row["title"] for row in results]
        except asyncpg.exceptions.UndefinedTableError:
            return []
