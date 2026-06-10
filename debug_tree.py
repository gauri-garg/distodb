from node.parser import parse_sql
from lark import Tree, Token

tree = parse_sql("SELECT * FROM products WHERE id = 1")

def show(t, indent=0):
    if isinstance(t, Tree):
        print(" " * indent + f"Tree: {t.data}")
        for c in t.children:
            show(c, indent+2)
    else:
        print(" " * indent + f"Token: type={t.type!r} value={t.value!r}")

show(tree)
