import os
import json

class Storage:

    def __init__(self, data_dir=None):
        self.data_dir = data_dir
        self.tables = {}
        if self.data_dir:
            os.makedirs(self.data_dir, exist_ok=True)
            self._load_tables()

    def _load_tables(self):
        for filename in os.listdir(self.data_dir):
            if filename.endswith(".json"):
                table_name = filename[:-5]
                path = os.path.join(self.data_dir, filename)
                try:
                    with open(path, "r") as f:
                        self.tables[table_name] = json.load(f)
                except Exception as e:
                    raise IOError(f"Failed to load table '{table_name}' from {path}: {e}")

    def _save_table(self, name):
        if self.data_dir:
            path = os.path.join(self.data_dir, f"{name}.json")
            try:
                with open(path, "w") as f:
                    json.dump(self.tables[name], f, indent=2)
            except Exception as e:
                raise IOError(f"Failed to save table '{name}' to {path}: {e}")

    def create_table(self, name, schema, pk):
        if name in self.tables:
            raise ValueError(f"Table '{name}' already exists")
        self.tables[name] = {"schema": schema, "pk": pk, "rows": []}
        self._save_table(name)

    def insert(self, table, row):
        self._check(table)
        t = self.tables[table]
        schema = t["schema"]
        pk = t["pk"]

        # Validate that all keys in the inserted row exist in the schema
        for col in row:
            if col not in schema:
                raise ValueError(f"Column '{col}' is not in the schema of table '{table}'")

        # Coerce types and validate
        validated_row = {}
        for col_name, col_type in schema.items():
            val = row.get(col_name)
            if val is None:
                if col_name == pk:
                    raise ValueError(f"Primary key column '{col_name}' cannot be NULL")
                validated_row[col_name] = None
            else:
                validated_row[col_name] = self._coerce_val(col_name, col_type, val)

        # Check duplicate primary key
        if pk:
            pk_val = validated_row[pk]
            if any(r[pk] == pk_val for r in t["rows"]):
                raise ValueError(f"Duplicate primary key: {pk}={pk_val}")

        t["rows"].append(validated_row)
        self._save_table(table)

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
        schema = self.tables[table]["schema"]
        pk = self.tables[table]["pk"]
        
        # Validate assignments
        validated_assignments = {}
        for col, val in assignments.items():
            if col not in schema:
                raise ValueError(f"Column '{col}' is not in the schema of table '{table}'")
            if val is None:
                if col == pk:
                    raise ValueError(f"Primary key column '{col}' cannot be NULL")
                validated_assignments[col] = None
            else:
                validated_assignments[col] = self._coerce_val(col, schema[col], val)

        count = 0
        rows = self.tables[table]["rows"]

        # If primary key is updated, check for uniqueness
        if pk in validated_assignments:
            new_pk_val = validated_assignments[pk]
            matching_rows = [r for r in rows if condition is None or self._match(r, condition)]
            if len(matching_rows) > 1:
                raise ValueError(f"Duplicate primary key: {pk}={new_pk_val} (multiple rows would be updated to the same primary key)")
            if len(matching_rows) == 1:
                if any(r[pk] == new_pk_val for r in rows if r not in matching_rows):
                    raise ValueError(f"Duplicate primary key: {pk}={new_pk_val}")

        for row in rows:
            if condition is None or self._match(row, condition):
                row.update(validated_assignments)
                count += 1

        if count > 0:
            self._save_table(table)
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
        
        diff = before - len(self.tables[table]["rows"])
        self._save_table(table)
        return diff

    def _coerce_val(self, col_name, col_type, val):
        if val is None:
            return None
        try:
            if col_type == "INT":
                f_val = float(val)
                if not f_val.is_integer() and not isinstance(val, int):
                    raise ValueError()
                return int(f_val)
            elif col_type == "FLOAT":
                return float(val)
            elif col_type == "TEXT":
                return str(val)
            elif col_type.startswith("VARCHAR"):
                str_val = str(val)
                if "(" in col_type:
                    length = int(col_type.split("(")[1].split(")")[0])
                    if len(str_val) > length:
                        raise ValueError(f"Value too long for column '{col_name}' of type {col_type}")
                return str_val
            elif col_type in ("BOOL", "BOOLEAN"):
                if isinstance(val, bool):
                    return val
                s_val = str(val).lower()
                if s_val in ("true", "1", "yes"):
                    return True
                if s_val in ("false", "0", "no"):
                    return False
                raise ValueError()
            else:
                return val
        except (ValueError, TypeError) as e:
            if str(e):
                raise ValueError(str(e))
            raise ValueError(f"Invalid value for column '{col_name}' of type {col_type}: {val!r}")

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

