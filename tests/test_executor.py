import pytest
from node.executor import Executor


@pytest.fixture
def db():
    e = Executor(data_dir=None)
    e.run("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")
    return e


def test_create_table():
    e = Executor(data_dir=None)
    r = e.run("CREATE TABLE t (id INT PRIMARY KEY, val TEXT)")
    assert r["ok"] is True

def test_create_duplicate_errors(db):
    r = db.run("CREATE TABLE products (id INT PRIMARY KEY)")
    assert "error" in r

def test_insert_row(db):
    r = db.run('INSERT INTO products (id, name) VALUES (1, "Laptop")')
    assert r["ok"] is True

def test_insert_duplicate_pk_errors(db):
    db.run('INSERT INTO products (id, name) VALUES (1, "Laptop")')
    r = db.run('INSERT INTO products (id, name) VALUES (1, "Dupe")')
    assert "error" in r

def test_select_empty(db):
    r = db.run("SELECT * FROM products")
    assert r["rows"] == []

def test_select_all(db):
    db.run('INSERT INTO products (id, name) VALUES (1, "Laptop")')
    db.run('INSERT INTO products (id, name) VALUES (2, "Phone")')
    r = db.run("SELECT * FROM products")
    assert r["count"] == 2

def test_select_where(db):
    db.run('INSERT INTO products (id, name) VALUES (1, "Laptop")')
    db.run('INSERT INTO products (id, name) VALUES (2, "Phone")')
    r = db.run("SELECT * FROM products WHERE id = 1")
    assert r["count"] == 1
    assert r["rows"][0]["name"] == "Laptop"

def test_select_where_no_match(db):
    db.run('INSERT INTO products (id, name) VALUES (1, "Laptop")')
    r = db.run("SELECT * FROM products WHERE id = 99")
    assert r["count"] == 0

def test_select_columns(db):
    db.run('INSERT INTO products (id, name) VALUES (1, "Laptop")')
    r = db.run("SELECT name FROM products")
    assert "id" not in r["rows"][0]
    assert "name" in r["rows"][0]

def test_update_with_where(db):
    db.run('INSERT INTO products (id, name) VALUES (1, "Laptop")')
    db.run('UPDATE products SET name = "Tablet" WHERE id = 1')
    r = db.run("SELECT * FROM products WHERE id = 1")
    assert r["rows"][0]["name"] == "Tablet"

def test_update_no_where(db):
    db.run('INSERT INTO products (id, name) VALUES (1, "A")')
    db.run('INSERT INTO products (id, name) VALUES (2, "B")')
    r = db.run('UPDATE products SET name = "X"')
    assert "2 row" in r["message"]

def test_delete_with_where(db):
    db.run('INSERT INTO products (id, name) VALUES (1, "Laptop")')
    db.run("DELETE FROM products WHERE id = 1")
    r = db.run("SELECT * FROM products")
    assert r["count"] == 0

def test_delete_no_where(db):
    db.run('INSERT INTO products (id, name) VALUES (1, "A")')
    db.run('INSERT INTO products (id, name) VALUES (2, "B")')
    db.run("DELETE FROM products")
    r = db.run("SELECT * FROM products")
    assert r["count"] == 0

def test_query_missing_table(db):
    r = db.run("SELECT * FROM ghost")
    assert "error" in r

def test_bad_sql(db):
    r = db.run("not sql at all")
    assert "error" in r


def test_type_coercion(db):
    # Coercing float representation of integer to int, and number to string
    r = db.run("INSERT INTO products (id, name) VALUES (1.0, 123)")
    assert r["ok"] is True
    
    r = db.run("SELECT * FROM products WHERE id = 1")
    assert r["count"] == 1
    assert r["rows"][0]["id"] == 1
    assert isinstance(r["rows"][0]["id"], int)
    assert r["rows"][0]["name"] == "123"
    assert isinstance(r["rows"][0]["name"], str)

    # Coercing invalid types should fail
    r = db.run('INSERT INTO products (id, name) VALUES ("abc", "Laptop")')
    assert "error" in r


def test_missing_columns_default_none(db):
    r = db.run("INSERT INTO products (id) VALUES (2)")
    assert r["ok"] is True
    r = db.run("SELECT * FROM products WHERE id = 2")
    assert r["count"] == 1
    assert r["rows"][0]["name"] is None


def test_schema_column_checking(db):
    r = db.run('INSERT INTO products (id, name, extra) VALUES (3, "Laptop", "value")')
    assert "error" in r


def test_disk_persistence(tmp_path):
    data_dir = str(tmp_path)
    e1 = Executor(data_dir=data_dir)
    r = e1.run("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")
    assert r["ok"] is True
    
    r = e1.run('INSERT INTO products (id, name) VALUES (1, "Laptop")')
    assert r["ok"] is True

    # Check that file exists on disk
    import os
    import json
    table_file = os.path.join(data_dir, "products.json")
    assert os.path.exists(table_file)
    with open(table_file, "r") as f:
        data = json.load(f)
        assert data["schema"] == {"id": "INT", "name": "TEXT"}
        assert data["pk"] == "id"
        assert len(data["rows"]) == 1
        assert data["rows"][0]["id"] == 1
        assert data["rows"][0]["name"] == "Laptop"

    # Instantiate a new executor pointing to the same data directory
    e2 = Executor(data_dir=data_dir)
    r = e2.run("SELECT * FROM products WHERE id = 1")
    assert r["count"] == 1
    assert r["rows"][0]["name"] == "Laptop"


def test_bool_datatype():
    e = Executor(data_dir=None)
    e.run("CREATE TABLE users (id INT PRIMARY KEY, active BOOL, verified BOOLEAN)")
    
    r = e.run("INSERT INTO users (id, active, verified) VALUES (1, TRUE, FALSE)")
    assert r["ok"] is True
    
    r = e.run('INSERT INTO users (id, active, verified) VALUES (2, "1", "0")')
    assert r["ok"] is True
    
    r = e.run('INSERT INTO users (id, active, verified) VALUES (3, "yes", "no")')
    assert r["ok"] is True
    
    # Check stored types
    r = e.run("SELECT * FROM users WHERE id = 1")
    assert r["rows"][0]["active"] is True
    assert r["rows"][0]["verified"] is False
    
    # Check query filtering
    r = e.run("SELECT * FROM users WHERE active = TRUE")
    assert r["count"] == 3
    
    # Invalid boolean should fail
    r = e.run('INSERT INTO users (id, active, verified) VALUES (4, "invalid", TRUE)')
    assert "error" in r


def test_varchar_datatype():
    e = Executor(data_dir=None)
    e.run("CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(10), bio VARCHAR)")
    
    # Valid insert
    r = e.run('INSERT INTO users (id, name, bio) VALUES (1, "Alice", "Developer")')
    assert r["ok"] is True
    
    # Check value is a string
    r = e.run("SELECT * FROM users WHERE id = 1")
    assert r["rows"][0]["name"] == "Alice"
    assert isinstance(r["rows"][0]["name"], str)
    
    # Exceeding VARCHAR length constraint should fail
    r = e.run('INSERT INTO users (id, name, bio) VALUES (2, "A_very_long_name", "Should fail")')
    assert "error" in r
    
    # Coercing non-string values to string
    r = e.run('INSERT INTO users (id, name, bio) VALUES (3, 12345, "Will convert to string")')
    assert r["ok"] is True
    r = e.run("SELECT * FROM users WHERE id = 3")
    assert r["rows"][0]["name"] == "12345"
