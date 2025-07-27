import psycopg2
import os
from dotenv import load_dotenv
import threading # To ensure thread-safe instantiation if Flask app serves multiple requests concurrently

load_dotenv() # Load environment variables from .env file

class Database:
    # Use a simple Singleton pattern to ensure only one connection manager
    _instance = None
    _lock = threading.Lock() # For thread-safe initialization

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance._init_db_params()
                cls._instance._conn = None
                cls._instance._cursor = None
                cls._instance._connect_attempted = False # Track if connection was ever attempted
        return cls._instance

    def _init_db_params(self):
        self.db_host = os.getenv('DB_HOST')
        self.db_user = os.getenv('DB_USER')
        self.db_pass = os.getenv('DB_PASS')
        self.db_name = os.getenv('DB_NAME')
        self.db_port = os.getenv('DB_PORT')

    def connect(self):
        # Only connect if there's no active connection or if it's closed
        if self._conn is None or self._conn.closed:
            try:
                self._conn = psycopg2.connect(
                    host=self.db_host,
                    user=self.db_user,
                    password=self.db_pass,
                    dbname=self.db_name,
                    port=self.db_port
                )
                self._conn.autocommit = True # Useful for read-only dashboards, commits immediately
                self._cursor = self._conn.cursor()
                print("Database re-connected successfully!")
                self._connect_attempted = True
            except Exception as e:
                print(f"Error connecting to the database: {e}")
                self._conn = None
                self._cursor = None
                self._connect_attempted = False # Reset if connection fails
        elif not self._connect_attempted: # First successful connection message
             print("Database connection already established.")
             self._connect_attempted = True # Mark as attempted

    def disconnect(self):
        # This method is primarily for explicit shutdown (e.g., when the app stops)
        # We don't disconnect after every query anymore.
        if self._cursor:
            try:
                self._cursor.close()
            except psycopg2.Error as e:
                print(f"Error closing cursor: {e}")
        if self._conn:
            try:
                self._conn.close()
            except psycopg2.Error as e:
                print(f"Error closing connection: {e}")
        self._conn = None
        self._cursor = None
        print("Explicit database disconnect called.")


    def execute_query(self, query, params=None, fetch_type='all'):
        self.connect() # Ensure connection is active before executing

        if self._conn is None or self._cursor is None:
            print("No active database connection. Cannot execute query.")
            return [] if fetch_type == 'all' else None

        try:
            self._cursor.execute(query, params)
            if self._cursor.description: # Check if there are results to fetch (e.g., SELECT statements)
                columns = [desc[0] for desc in self._cursor.description]
                if fetch_type == 'all':
                    data = self._cursor.fetchall()
                    return [dict(zip(columns, row)) for row in data]
                elif fetch_type == 'one':
                    data = self._cursor.fetchone()
                    return dict(zip(columns, data)) if data else None
            else: # For non-SELECT statements (INSERT, UPDATE, DELETE)
                return True # Indicate success
        except psycopg2.OperationalError as op_err:
            # Handle cases where connection might have dropped (e.g., idle timeout)
            print(f"Operational error: {op_err}. Attempting to reconnect on next query.")
            self._conn = None # Mark connection as invalid, it will reconnect on next call to connect()
            self._cursor = None
            return [] if fetch_type == 'all' else None # Return empty or handle as appropriate
        except Exception as e:
            print(f"Error executing query: {e}")
            return [] if fetch_type == 'all' else None

    def fetch_all(self, query, params=None):
        return self.execute_query(query, params, fetch_type='all')

    def fetch_one(self, query, params=None):
        return self.execute_query(query, params, fetch_type='one')