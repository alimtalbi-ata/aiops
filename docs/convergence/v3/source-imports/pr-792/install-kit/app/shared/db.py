import os
from contextlib import contextmanager
import psycopg
@contextmanager
def db():
    with psycopg.connect(os.environ['DATABASE_URL']) as c:
        yield c
