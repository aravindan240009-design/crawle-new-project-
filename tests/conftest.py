import pytest

from backend.db import Database
from backend.fixtures import demo_sources


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / 'test.sqlite')
    database.initialize()
    database.execute('DELETE FROM sources')
    for source in demo_sources():
        database.execute('INSERT INTO sources(id,config) VALUES (?,?)', (source.id, source.model_dump_json()))
    return database
