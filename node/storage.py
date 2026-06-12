import os
import json
from node.wal import WAL

class Storage:

    def __init__(self, data_dir=None):
        self.data_dir = data_dir
        self.tables = {}
        if self.data_dir:
            os.makedirs(self.data_dir, exist_ok=True)
            self._load_tables()

    def _load_tables(self):
        # 1. Load existing JSON snapshots first
        for filename in os.listdir(self.data_dir):
            if filename.endswith(".json"):
                table_name = filename[:-5]
                path = os.path.join(self.data_dir, filename)
                try:
                    with open(path, "r") as f:
                        self.tables[table_name] = json.load(f)
                except Exception as e:
                    raise IOError(f"Failed to load table '{table_name}' from {path}: {e}")

        # 2. Check for WAL files and replay them if they contain entries
        for filename in os.listdir(self.data_dir):
            if filename.endswith(".wal"):
                table_name = filename[:-4]
                path = os.path.join(self.data_dir, filename)
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    if table_name not in self.tables:
                        self.tables[table_name] = {"schema": {}, "pk": None, "rows": []}
                    
                    try:
                        entries = WAL(path).read_all()
                        for entry in entries:
                            self._replay_entry(table_name, entry)
                        # After successful replay, do a clean save of the JSON snapshot and truncate the WAL
                        self._save_table(table_name)
                        self._truncate_wal(table_name)
                    except Exception as e:
                        raise IOError(f"Failed to replay WAL for table '{table_name}': {e}")

    def _replay_entry(self, table_name, entry):
        op = entry.get("op")
        if op == "create_table":
            schema = entry["schema"]
            pk = entry["pk"]
            self.tables[table_name] = {"schema": schema, "pk": pk, "rows": []}
        elif op == "insert":
            row = entry["row"]
            self._insert_local(table_name, row)
        elif op == "update":
            assignments = entry["assignments"]
            condition = entry["condition"]
            self._update_local(table_name, assignments, condition)
        elif op == "delete":
            condition = entry["condition"]
            self._delete_local(table_name, condition)

    def _write_wal(self, table_name, entry):
        if self.data_dir:
            path = os.path.join(self.data_dir, f"{table_name}.wal")
            try:
                WAL(path).append(entry)
            except Exception as e:
                raise IOError(f"Failed to write WAL for table '{table_name}': {e}")

    def _truncate_wal(self, table_name):
        if self.data_dir:
            path = os.path.join(self.data_dir, f"{table_name}.wal")
            try:
                WAL(path).clear()
            except Exception as e:
                raise IOError(f"Failed to truncate WAL for table '{table_name}': {e}")

    def _save_table(self, name):
        if self.data_dir:
            path = os.path.join(self.data_dir, f"{name}.json")
            tmp_path = path + ".tmp"
            try:
                # Write to temp file first, flush, fsync, then atomically replace
                with open(tmp_path, "w") as f:
                    json.dump(self.tables[name], f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, path)
            except Exception as e:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise IOError(f"Failed to save table '{name}' to {path}: {e}")

    def create_table(self, name, schema, pk):
        if name in self.tables:
            raise ValueError(f"Table '{name}' already exists")
        # Log creation to WAL first
        self._write_wal(name, {"op": "create_table", "schema": schema, "pk": pk})
        self.tables[name] = {"schema": schema, "pk": pk, "rows": []}
        self._save_table(name)
        self._truncate_wal(name)

    def insert(self, table, row):
        self._check(table)
        validated_row = self._validate_and_coerce_insert(table, row)
        # Log insert to WAL
        self._write_wal(table, {"op": "insert", "row": validated_row})
        self._insert_local(table, validated_row)
        self._save_table(table)
        self._truncate_wal(table)

    def _validate_and_coerce_insert(self, table, row):
        t = self.tables[table]
        schema = t["schema"]
        pk = t["pk"]

        for col in row:
            if col not in schema:
                raise ValueError(f"Column '{col}' is not in the schema of table '{table}'")

        validated_row = {}
        for col_name, col_type in schema.items():
            val = row.get(col_name)
            if val is None:
                if col_name == pk:
                    raise ValueError(f"Primary key column '{col_name}' cannot be NULL")
                validated_row[col_name] = None
            else:
                validated_row[col_name] = self._coerce_val(col_name, col_type, val)

        if pk:
            pk_val = validated_row[pk]
            if any(r[pk] == pk_val for r in t["rows"]):
                raise ValueError(f"Duplicate primary key: {pk}={pk_val}")
        return validated_row

    def _insert_local(self, table, validated_row):
        self.tables[table]["rows"].append(validated_row)

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
        validated_assignments = self._validate_and_coerce_update(table, assignments)
        # Log update to WAL
        self._write_wal(table, {"op": "update", "assignments": validated_assignments, "condition": condition})
        count = self._update_local(table, validated_assignments, condition)
        if count > 0:
            self._save_table(table)
        self._truncate_wal(table)
        return count

    def _validate_and_coerce_update(self, table, assignments):
        schema = self.tables[table]["schema"]
        pk = self.tables[table]["pk"]
        
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
        return validated_assignments

    def _update_local(self, table, validated_assignments, condition):
        pk = self.tables[table]["pk"]
        rows = self.tables[table]["rows"]

        if pk in validated_assignments:
            new_pk_val = validated_assignments[pk]
            matching_rows = [r for r in rows if condition is None or self._match(r, condition)]
            if len(matching_rows) > 1:
                raise ValueError(f"Duplicate primary key: {pk}={new_pk_val} (multiple rows would be updated to the same primary key)")
            if len(matching_rows) == 1:
                if any(r[pk] == new_pk_val for r in rows if r not in matching_rows):
                    raise ValueError(f"Duplicate primary key: {pk}={new_pk_val}")

        count = 0
        for row in rows:
            if condition is None or self._match(row, condition):
                row.update(validated_assignments)
                count += 1
        return count

    def delete(self, table, condition=None):
        self._check(table)
        # Log delete to WAL
        self._write_wal(table, {"op": "delete", "condition": condition})
        diff = self._delete_local(table, condition)
        self._save_table(table)
        self._truncate_wal(table)
        return diff

    def _delete_local(self, table, condition):
        before = len(self.tables[table]["rows"])
        if condition:
            self.tables[table]["rows"] = [
                r for r in self.tables[table]["rows"]
                if not self._match(r, condition)
            ]
        else:
            self.tables[table]["rows"] = []
        return before - len(self.tables[table]["rows"])

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

