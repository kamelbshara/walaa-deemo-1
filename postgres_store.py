"""PostgreSQL storage for Vercel; SQLite remains available for local development."""
import re

class Row(dict):
    def __getitem__(self,key):
        return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)

def row_factory(cursor):
    names=[c.name for c in (cursor.description or [])]
    return lambda values:Row(zip(names,values))

class Database:
    def __init__(self,url):
        import psycopg
        self.connection=psycopg.connect(url,row_factory=row_factory,connect_timeout=10)
        # All classroom reads can expire timers. Serialize transactions across
        # serverless instances, matching SQLite's single-writer semantics.
        self.connection.execute('SELECT pg_advisory_xact_lock(83640129)')
    def __enter__(self):return self
    def __exit__(self,kind,value,tb):
        try:
            self.connection.rollback() if kind else self.connection.commit()
        finally:self.connection.close()
    def commit(self):self.connection.commit()
    def execute(self,sql,params=()):
        if sql=='BEGIN IMMEDIATE':
            return self.connection.execute('SELECT 1')
        if sql.startswith('PRAGMA table_info('):
            table=sql.split('(')[1].split(')')[0]
            return self.connection.execute('SELECT ordinal_position AS cid,column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position',(table,))
        if sql.startswith('PRAGMA '):return self.connection.execute('SELECT 1')
        if 'INSERT OR IGNORE' in sql:
            sql=sql.replace('INSERT OR IGNORE','INSERT')+' ON CONFLICT DO NOTHING'
        if 'INSERT OR REPLACE INTO work_samples' in sql:
            sql=sql.replace('INSERT OR REPLACE','INSERT')+' ON CONFLICT(student,slide) DO UPDATE SET reasoning=EXCLUDED.reasoning,strokes=EXCLUDED.strokes,updated=EXCLUDED.updated'
        sql=re.sub(r'\bREAL\b','DOUBLE PRECISION',sql)
        sql=sql.replace('CREATE TABLE IF NOT EXISTS attempts(id','CREATE TABLE IF NOT EXISTS attempts(rowid BIGINT GENERATED ALWAYS AS IDENTITY, id')
        sql=sql.replace('?', '%s')
        return self.connection.execute(sql,params or None)
    def executescript(self,sql):
        for statement in sql.split(';'):
            if statement.strip():self.execute(statement.strip())
