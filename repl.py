import cmd
from node.parser import pretty, parse_sql

class DistoDBRepl(cmd.Cmd):
    intro  = "DistoDB v0.1 — Week 1 SQL Parser\nType SQL or 'quit' to exit.\n"
    prompt = "distodb> "

    def default(self, line: str):
        """Handle any input as a SQL query."""
        if line.strip().lower() in ("quit", "exit"):
            return True
        print(pretty(line))

    def do_quit(self, _):
        "Exit the REPL."
        return True

if __name__ == "__main__":
    DistoDBRepl().cmdloop()