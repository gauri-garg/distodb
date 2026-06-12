import argparse
import cmd
from node.executor import Executor


class DistoDBRepl(cmd.Cmd):
    intro  = "DistoDB v0.3 — Week 3 (Distributed)\nType SQL or 'quit' to exit.\n"
    prompt = "distodb> "

    def __init__(self, url=None):
        super().__init__()
        self.url = url
        if self.url:
            self.url = self.url.rstrip("/")
            print(f"Connected to network node at {self.url}\n")
            self.executor = None
        else:
            print("Running in local mode.\n")
            self.executor = Executor()

    def default(self, line):
        sql = line.strip()
        if not sql:
            return
        if sql.lower() in ("quit", "exit"):
            return True

        if self.url:
            import urllib.request
            import json
            try:
                req_data = json.dumps({"sql": sql}).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.url}/query",
                    data=req_data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as res:
                    result = json.loads(res.read().decode("utf-8"))
            except Exception as e:
                print(f"ERROR (Connection failed): {e}")
                return
        else:
            result = self.executor.run(sql)

        if "error" in result:
            print(f"ERROR: {result['error']}")
        elif "rows" in result:
            if not result["rows"]:
                print("(0 rows)")
            else:
                headers = list(result["rows"][0].keys())
                print(" | ".join(f"{h:<15}" for h in headers))
                print("-" * (18 * len(headers)))
                for row in result["rows"]:
                    print(" | ".join(f"{str(row.get(h,'')):<15}" for h in headers))
                print(f"\n({result['count']} row(s))")
        else:
            print(result.get("message", "OK"))

    def do_quit(self, _):
        "Exit the REPL."
        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DistoDB REPL Client")
    parser.add_argument("--url", type=str, default=None, help="Base URL of DistoDB HTTP node")
    args = parser.parse_args()
    DistoDBRepl(url=args.url).cmdloop()

