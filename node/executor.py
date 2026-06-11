from lark import Tree, Token
from node.storage import Storage
from node.parser import parse_sql


class Executor:

    def __init__(self, data_dir="data"):
        self.storage = Storage(data_dir=data_dir)

    def run(self, sql):
        try:
            tree = parse_sql(sql)
            stmt = self._first_rule(tree)
            stmt = self._first_rule(stmt)
            return self._dispatch(stmt)
        except Exception as e:
            return {"error": str(e)}

    def _dispatch(self, stmt):
        handlers = {
            "select_stmt": self._select,
            "insert_stmt": self._insert,
            "update_stmt": self._update,
            "delete_stmt": self._delete,
            "create_stmt": self._create,
        }
        handler = handlers.get(stmt.data)
        if not handler:
            raise ValueError(f"Unknown statement: {stmt.data}")
        return handler(stmt)

    def _create(self, stmt):
        name = self._token_val(stmt, "NAME")
        schema = {}
        pk = None
        for col_def in self._rules(stmt, "col_def"):
            col_name = str(col_def.children[0])
            col_type_node = self._first_rule(col_def)
            inner = col_type_node.children[0]
            if isinstance(inner, Tree) and inner.data == "varchar_type":
                length = None
                if len(inner.children) > 1 and inner.children[1] is not None:
                    length = int(inner.children[1])
                col_type = f"VARCHAR({length})" if length is not None else "VARCHAR"
            else:
                col_type = str(inner).upper()
            is_pk = any(
                isinstance(c, Token) and c.type == "PRIMARY"
                for c in col_def.children
            )
            schema[col_name] = col_type
            if is_pk:
                pk = col_name
        self.storage.create_table(name, schema, pk)
        return {"ok": True, "message": f"Table '{name}' created"}

    def _insert(self, stmt):
        name = self._token_val(stmt, "NAME")
        cols = self._col_list(self._rule(stmt, "col_list"))
        vals = self._value_list(self._rule(stmt, "value_list"))
        if len(cols) != len(vals):
            raise ValueError("Column count does not match value count")
        self.storage.insert(name, dict(zip(cols, vals)))
        return {"ok": True, "message": "1 row inserted"}

    def _select(self, stmt):
        name     = self._token_val(stmt, "NAME")
        col_node = self._rule(stmt, "columns")
        star     = any(
            isinstance(c, Token) and c.type == "STAR"
            for c in col_node.children
        )
        cols      = ["*"] if star else self._col_list(self._rule(col_node, "col_list"))
        cond_node = self._rule(stmt, "condition")
        cond      = self._condition(cond_node) if cond_node else None
        rows      = self.storage.select(name, cols, cond)
        return {"ok": True, "rows": rows, "count": len(rows)}

    def _update(self, stmt):
        name = self._token_val(stmt, "NAME")
        asgns = {}
        for a in self._rules(stmt, "assignment"):
            col = str(a.children[0])
            val = self._val(self._rule(a, "value"))
            asgns[col] = val
        cond_node = self._rule(stmt, "condition")
        cond      = self._condition(cond_node) if cond_node else None
        n = self.storage.update(name, asgns, cond)
        return {"ok": True, "message": f"{n} row(s) updated"}

    def _delete(self, stmt):
        name      = self._token_val(stmt, "NAME")
        cond_node = self._rule(stmt, "condition")
        cond      = self._condition(cond_node) if cond_node else None
        n = self.storage.delete(name, cond)
        return {"ok": True, "message": f"{n} row(s) deleted"}

    def _first_rule(self, tree):
        return next(c for c in tree.children if isinstance(c, Tree))

    def _rule(self, tree, name):
        return next(
            (c for c in tree.children if isinstance(c, Tree) and c.data == name),
            None
        )

    def _rules(self, tree, name):
        return [c for c in tree.children if isinstance(c, Tree) and c.data == name]

    def _token_val(self, tree, tok_type):
        for c in tree.children:
            if isinstance(c, Token) and c.type == tok_type:
                return str(c)
        raise ValueError(f"Token '{tok_type}' not found in {tree.data}")

    def _col_list(self, node):
        return [
            str(c) for c in node.children
            if isinstance(c, Token) and c.type == "NAME"
        ]

    def _value_list(self, node):
        return [self._val(v) for v in self._rules(node, "value")]

    def _val(self, node):
        tok = node.children[0]
        if tok.type == "NUMBER":
            return float(tok) if "." in str(tok) else int(tok)
        if tok.type == "ESCAPED_STRING":
            return str(tok)[1:-1]
        if tok.type == "TRUE" or (tok.type == "NAME" and str(tok).upper() == "TRUE"):
            return True
        if tok.type == "FALSE" or (tok.type == "NAME" and str(tok).upper() == "FALSE"):
            return False
        return str(tok)

    def _condition(self, node):
        col = str(node.children[0])
        op  = str(node.children[1])
        val = self._val(self._rule(node, 'value'))
        return {'col': col, 'op': op, 'val': val}
