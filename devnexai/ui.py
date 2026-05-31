"""Capa de presentación de DevNexAI.

Usa `rich` si está disponible (paneles, spinner, syntax highlighting).
Si no, cae a salida ANSI simple para no romper en entornos mínimos.
"""

from __future__ import annotations

from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text
    from rich.markdown import Markdown
    _RICH = True
except ImportError:  # pragma: no cover
    _RICH = False


# Extensiones -> lexer para syntax highlighting
_LEXERS = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".jsx": "jsx",
    ".tsx": "tsx", ".json": "json", ".html": "html", ".css": "css",
    ".sh": "bash", ".md": "markdown", ".yml": "yaml", ".yaml": "yaml",
    ".sql": "sql", ".go": "go", ".rs": "rust", ".java": "java", ".c": "c",
    ".cpp": "cpp", ".rb": "ruby", ".php": "php", ".toml": "toml",
}

BANNER_ART = r"""██████╗ ███████╗██╗   ██╗███╗   ██╗███████╗██╗  ██╗ █████╗ ██╗
██╔══██╗██╔════╝██║   ██║████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗██║
██║  ██║█████╗  ██║   ██║██╔██╗ ██║█████╗   ╚███╔╝ ███████║██║
██║  ██║██╔══╝  ╚██╗ ██╔╝██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║██║
██████╔╝███████╗ ╚████╔╝ ██║ ╚████║███████╗██╔╝ ██╗██║  ██║██║
╚═════╝ ╚══════╝  ╚═══╝  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝"""


class _AnsiFallback:
    R = "\033[0m"; B = "\033[1m"; DIM = "\033[2m"
    CYAN = "\033[36m"; GREEN = "\033[32m"; YEL = "\033[33m"
    MAG = "\033[35m"; RED = "\033[31m"


class UI:
    """Fachada de presentación; misma API funcione rich o no."""

    def __init__(self) -> None:
        self.rich = _RICH
        if self.rich:
            self.console = Console()
        self._c = _AnsiFallback

    # ---------- banner / cabeceras ----------
    def banner(self, provider: str, model: str, cwd: Path) -> None:
        sub = "agente de codificación multi-LLM"
        # Modo demo: para capturas de pantalla, oculta la ruta real del usuario.
        # Actívalo con la variable de entorno DEVNEXAI_DEMO=1
        import os
        if os.environ.get("DEVNEXAI_DEMO"):
            cwd_display = "~/mi-proyecto"
        else:
            cwd_display = str(cwd)
        if self.rich:
            head = Text()
            head.append(BANNER_ART, style="bold dark_orange3")
            self.console.print(head)
            self.console.print(f"[dim italic]{sub}[/]\n")
            meta = Text()
            meta.append("Proveedor ", style="dim"); meta.append(provider, style="bold cyan")
            meta.append("   Modelo ", style="dim"); meta.append(model, style="bold green")
            meta.append("\nDir ", style="dim"); meta.append(cwd_display, style="white")
            self.console.print(Panel(meta, border_style="grey37", padding=(0, 2),
                                     title="sesión", title_align="left"))
            self.console.print(
                "[dim]Escribe tu petición. Comandos:[/] "
                "[bold]/salir[/] · [bold]/limpiar[/] · [bold]/modelo[/]\n")
        else:
            c = self._c
            print(f"{c.YEL}{c.B}\n{BANNER_ART}{c.R}\n{c.DIM}{sub}{c.R}")
            print(f"{c.DIM}Proveedor: {provider} · Modelo: {model} · Dir: {cwd_display}{c.R}")
            print(f"{c.DIM}Comandos: /salir  /limpiar  /modelo{c.R}\n")

    def prompt(self) -> str:
        if self.rich:
            self.console.print("[bold magenta]❯[/] ", end="")
            return input()
        return input(f"{self._c.MAG}{self._c.B}❯ {self._c.R}")

    # ---------- eventos del agente ----------
    def tool_call(self, name: str, args: dict) -> None:
        preview = args.get("command") or args.get("path") or ""
        if self.rich:
            self.console.print(f"  [yellow]⚙[/] [bold]{name}[/][dim]({preview})[/]")
        else:
            print(f"{self._c.DIM}  ⚙ {name}({preview}){self._c.R}")

    def tool_result(self, name: str, output: str, path: str | None = None) -> None:
        out = output.strip()
        # Si fue escritura/lectura de un archivo de código, intentamos resaltar.
        if self.rich and path:
            ext = Path(path).suffix.lower()
            lexer = _LEXERS.get(ext)
            if lexer and name in ("write_file", "read_file") and "\n" in out:
                code = _strip_line_numbers(out) if name == "read_file" else out
                self.console.print(Panel(
                    Syntax(code, lexer, theme="monokai", line_numbers=True,
                           word_wrap=True),
                    border_style="grey30", title=path, title_align="left",
                    padding=(0, 1)))
                return
        head = out.splitlines()[0] if out else ""
        more = " …" if out.count("\n") else ""
        if self.rich:
            self.console.print(f"    [dim]↳ {head[:100]}{more}[/]")
        else:
            print(f"{self._c.DIM}    ↳ {head[:100]}{more}{self._c.R}")

    def assistant(self, text: str) -> None:
        if self.rich:
            self.console.print(Panel(Markdown(text), border_style="green",
                                     title="DevNexAI", title_align="left",
                                     padding=(0, 1)))
        else:
            print(f"\n{self._c.GREEN}{text}{self._c.R}")

    def thinking(self):
        """Context manager para el spinner mientras el LLM responde."""
        if self.rich:
            return self.console.status("[cyan]pensando…[/]", spinner="dots")
        return _NullStatus()

    # ---------- mensajes utilitarios ----------
    def info(self, msg: str) -> None:
        self.console.print(f"[dim]{msg}[/]") if self.rich else print(f"{self._c.DIM}{msg}{self._c.R}")

    def ok(self, msg: str) -> None:
        self.console.print(f"[green]✓ {msg}[/]") if self.rich else print(f"{self._c.GREEN}✓ {msg}{self._c.R}")

    def warn(self, msg: str) -> None:
        self.console.print(f"[yellow]{msg}[/]") if self.rich else print(f"{self._c.YEL}{msg}{self._c.R}")

    def error(self, msg: str) -> None:
        self.console.print(f"[red]{msg}[/]") if self.rich else print(f"{self._c.RED}{msg}{self._c.R}")

    def providers_table(self, provs: dict, active: str | None, mask) -> None:
        if not self.rich:
            print("Proveedores configurados:")
            for kind, e in provs.items():
                mark = " (activo)" if kind == active else ""
                print(f"  • {kind} — {e.get('model') or 'por defecto'}  {mask(e.get('api_key',''))}{mark}")
            return
        t = Table(title="Proveedores configurados", border_style="grey37", title_justify="left")
        t.add_column("Proveedor", style="cyan", no_wrap=True)
        t.add_column("Modelo", style="green")
        t.add_column("API key", style="dim")
        t.add_column("", style="bold green")
        for kind, e in provs.items():
            t.add_row(kind, e.get("model") or "por defecto",
                      mask(e.get("api_key", "")), "● activo" if kind == active else "")
        self.console.print(t)

    # ---------- plan / subtareas ----------
    def plan(self, steps: list[dict]) -> None:
        icons = {"pendiente": "○", "en_progreso": "◐", "hecho": "●"}
        styles = {"pendiente": "dim", "en_progreso": "yellow", "hecho": "green"}
        if self.rich:
            body = Text()
            for s in steps:
                st = s.get("status", "pendiente")
                body.append(f"{icons.get(st, '○')} ", style=styles.get(st, "dim"))
                style = "strike dim" if st == "hecho" else styles.get(st, "white")
                body.append(s.get("task", "") + "\n", style=style)
            self.console.print(Panel(body, border_style="blue", title="plan",
                                     title_align="left", padding=(0, 1)))
        else:
            print("Plan:")
            for s in steps:
                print(f"  {icons.get(s.get('status'), '○')} {s.get('task','')}")

    def remembered(self, note: str) -> None:
        msg = f"💾 recordado: {note}"
        self.console.print(f"[dim]{msg}[/]") if self.rich else print(msg)

    # ---------- confirmación de comandos peligrosos ----------
    def confirm_danger(self, command: str, reason: str) -> bool:
        if self.rich:
            self.console.print(Panel(
                f"[bold red]Comando potencialmente peligroso[/]\n"
                f"[yellow]Motivo:[/] {reason}\n\n[white on grey15] {command} [/]",
                border_style="red", title="⚠ confirmación requerida",
                title_align="left", padding=(0, 1)))
            ans = input("  ¿Ejecutar de todos modos? [s/N]: ").strip().lower()
        else:
            print(f"\n⚠ Comando peligroso ({reason}):\n  {command}")
            ans = input("  ¿Ejecutar? [s/N]: ").strip().lower()
        return ans in ("s", "si", "sí", "y", "yes")


class _NullStatus:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _strip_line_numbers(numbered: str) -> str:
    """Quita el prefijo 'N\\t' que añade read_file para reconstruir el código."""
    lines = []
    for ln in numbered.splitlines():
        if "\t" in ln:
            lines.append(ln.split("\t", 1)[1])
        else:
            lines.append(ln)
    return "\n".join(lines)
