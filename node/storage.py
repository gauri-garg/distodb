class Storage:

    def __init__(self):
        self.tables = {}

    def create_table(self, name, schema, pk):
        if name in self.tables:
            raise ValueError(f"Table '{name}' already exists")
        self.tables[name] = {"schema": schema, "pk": pk, "rows": []}

    def insert(self, table, row):
        self._check(table)
        t = self.tables[table]
        pk = t["pk"]
        if pk and any(r[pk] == row[pk] for r in t["rows"]):
            raise ValueError(f"Duplicate primary key: {pk}={row[pk]}")
        t["rows"].append(row)

    def select(self, table, columns, condition=None):
        self._check(table)
        rows = list(self.tables[table]["rows"])
        if condition:
            rows = [r for r in rows if self._match(r, condition)]
        if columns == ["*"]:
            return rows
        return [{c: r[c] for c in columns} for r in rows]

    def update(self, table, assignments, condition=None):
        self._check(table)
        count = 0
        for row in self.tables[table]["rows"]:
            if condition is None or self._match(row, condition):
                row.update(assignments)
                count += 1
        return count

    def delete(self, table, condition=None):
        self._check(table)
        before = len(self.tables[table]["rows"])
        if condition:
            self.tables[table]["rows"] = [
                r for r in self.tables[table]["rows"]
                if not self._match(r, condition)
            ]
        else:
            self.tables[table]["rows"] = []
        return before - len(self.tables[table]["rows"])

    def _check(self, name):
        if name not in self.tables:
            raise ValueError(f"Table '{name}' does not exist")

    def _match(self, row, condition):
        col = condition["col"]
        op  = condition["op"]
        val = condition["val"]
        rv  = row.get(col)
        if rv is None:
            return False
        try:
            rv  = float(rv)  if "." in str(rv)  else int(rv)
            val = float(val) if "." in str(val) else int(val)
        except (ValueError, TypeError):
            pass
        if op == "=":
            return rv == val
        if op == "!=":
            return rv != val
        if op == ">":
            return rv > val
        if op == "<":
            return rv < val
        if op == ">=":
            return rv >= val
        if op == "<=":
            return rv <= val
        return False
