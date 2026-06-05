from lark import Lark
import pathlib

_grammar_path = pathlib.Path(__file__).parent / "sql_grammar.lark"
_grammar = _grammar_path.read_text()

parser = Lark(_grammar, parser="earley", ambiguity="resolve")

def parse_sql(sql: str):
    """Parse a SQL string and return the Lark Tree."""
    return parser.parse(sql.strip())

def pretty(sql: str) -> str:
    """Return a pretty-printed parse tree string."""
    try:
        tree = parse_sql(sql)
        return tree.pretty()
    except Exception as e:
        return f"Parse error: {e}"