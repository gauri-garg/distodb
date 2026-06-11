import pytest
from lark import UnexpectedToken, UnexpectedCharacters, UnexpectedInput
from node.parser import parse_sql

# ── Valid queries ────────────────────────────────────────────

def test_select_star():
    t = parse_sql("SELECT * FROM products")
    assert t.data == "start"

def test_select_columns():
    parse_sql("SELECT id, name FROM products")

def test_select_where():
    parse_sql("SELECT * FROM products WHERE id = 1")

def test_select_where_string():
    parse_sql('SELECT * FROM users WHERE name = "Alice"')

def test_select_where_gt():
    parse_sql("SELECT * FROM orders WHERE amount > 100")

def test_select_lowercase():
    parse_sql("select * from products")

def test_insert_basic():
    parse_sql('INSERT INTO products (id, name) VALUES (1, "Laptop")')

def test_insert_numbers_only():
    parse_sql("INSERT INTO inventory (id, qty) VALUES (5, 200)")

def test_update_with_where():
    parse_sql('UPDATE products SET name = "Phone" WHERE id = 1')

def test_update_no_where():
    parse_sql("UPDATE products SET qty = 0")

def test_delete_with_where():
    parse_sql("DELETE FROM products WHERE id = 99")

def test_delete_no_where():
    parse_sql("DELETE FROM products")

def test_create_table_basic():
    parse_sql("CREATE TABLE products (id INT PRIMARY KEY, name TEXT)")

def test_create_table_float():
    parse_sql("CREATE TABLE prices (id INT PRIMARY KEY, price FLOAT)")

def test_create_table_multiple_cols():
    parse_sql("CREATE TABLE orders (id INT PRIMARY KEY, product TEXT, qty INT, price FLOAT)")

def test_where_neq():
    parse_sql('SELECT * FROM orders WHERE status != "shipped"')

def test_where_lte():
    parse_sql("SELECT * FROM products WHERE price <= 999")

def test_parser_bool_types():
    parse_sql("CREATE TABLE t (id INT PRIMARY KEY, active BOOL, verified BOOLEAN)")

def test_parser_varchar_types():
    parse_sql("CREATE TABLE t (name VARCHAR PRIMARY KEY, email VARCHAR(100))")

def test_parser_bool_literals():
    parse_sql("SELECT * FROM users WHERE active = TRUE")
    parse_sql("SELECT * FROM users WHERE active = FALSE")
    parse_sql("INSERT INTO users (id, active) VALUES (1, TRUE)")

# ── Invalid queries (must raise errors) ─────────────────────

def test_missing_from():
    with pytest.raises(Exception):
        parse_sql("SELECT * products")

def test_empty_string():
    with pytest.raises(Exception):
        parse_sql("")

def test_garbage_input():
    with pytest.raises(Exception):
        parse_sql("not sql at all !@#")