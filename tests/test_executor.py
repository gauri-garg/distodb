import pytest
from node.executor import Executor


@pytest.fixture
def db():
    e = Executor()
    e.run("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")
    return e


def test_create_table():
    e = Executor()
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
