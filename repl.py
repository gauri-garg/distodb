import cmd
from node.executor import Executor


class DistoDBRepl(cmd.Cmd):
    intro  = "DistoDB v0.2 — Week 2\nType SQL or 'quit' to exit.\n"
    prompt = "distodb> "

    def __init__(self):
        super().__init__()
        self.executor = Executor()

    def default(self, line):
        if line.strip().lower() in ("quit", "exit"):
            return True
        result = self.executor.run(line)
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
    DistoDBRepl().cmdloop()
