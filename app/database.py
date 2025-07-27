import time
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
import os
from dotenv import load_dotenv
import threading  # To ensure thread-safe instantiation if Flask app serves multiple requests concurrently

load_dotenv()  # Load environment variables from .env file


class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance._init_db_params()
                cls._instance._pool = None
                cls._instance._connect_attempted = False
            return cls._instance

    def _init_db_params(self):
        self.db_host = os.getenv('DB_HOST')
        self.db_user = os.getenv('DB_USER')
        self.db_pass = os.getenv('DB_PASS')
        self.db_name = os.getenv('DB_NAME')
        self.db_port = os.getenv('DB_PORT')

    def connect(self):
        if self._pool is None:
            try:
                self._pool = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=10,  # Adjust based on your needs
                    host=self.db_host,
                    user=self.db_user,
                    password=self.db_pass,
                    dbname=self.db_name,
                    port=self.db_port,
                    connect_timeout=10,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=5
                )
                print("Connection pool initialized successfully!")
                self._connect_attempted = True
            except Exception as e:
                print(f"Error initializing connection pool: {e}")
                self._pool = None
                self._connect_attempted = False

    def execute_query(self, query, params=None, fetch_type='all'):
        self.connect()  # Ensure connection pool is initialized
        if self._pool is None:
            print("No active connection pool. Cannot execute query.")
            return [] if fetch_type == 'all' else None

        conn = None
        cursor = None
        start_time = time.time()
        try:
            conn = self._pool.getconn()  # Get a connection from the pool
            conn.autocommit = True  # Set autocommit for read-only queries
            cursor = conn.cursor()
            cursor.execute(query, params)
            if cursor.description:  # Check if there are results to fetch
                columns = [desc[0] for desc in cursor.description]
                if fetch_type == 'all':
                    data = cursor.fetchall()
                    print(
                        f"Query executed in {time.time() - start_time:.2f} seconds: {query}")
                    return [dict(zip(columns, row)) for row in data]
                elif fetch_type == 'one':
                    data = cursor.fetchone()
                    print(
                        f"Query executed in {time.time() - start_time:.2f} seconds: {query}")
                    return dict(zip(columns, data)) if data else None
            else:  # For non-SELECT statements
                print(
                    f"Non-SELECT query executed in {time.time() - start_time:.2f} seconds: {query}")
                return True
        except psycopg2.OperationalError as op_err:
            print(
                f"Operational error after {time.time() - start_time:.2f} seconds: {op_err}. Query: {query}")
            return [] if fetch_type == 'all' else None
        except Exception as e:
            print(
                f"Error executing query after {time.time() - start_time:.2f} seconds: {e}. Query: {query}")
            return [] if fetch_type == 'all' else None
        finally:
            if cursor:
                try:
                    cursor.close()
                except psycopg2.Error as e:
                    print(f"Error closing cursor: {e}")
            if conn:
                try:
                    self._pool.putconn(conn)  # Return connection to the pool
                except psycopg2.Error as e:
                    print(f"Error returning connection to pool: {e}")

    def fetch_all(self, query, params=None):
        return self.execute_query(query, params, fetch_type='all')

    def fetch_one(self, query, params=None):
        return self.execute_query(query, params, fetch_type='one')
