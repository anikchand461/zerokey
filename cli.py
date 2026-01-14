# cli.py
import typer
import requests
import json
from typing import Optional, List
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich import print as rprint
from rich.text import Text
from rich.box import ROUNDED

console = Console()

app = typer.Typer(
    name="zerokey",
    help="Zerokey CLI - Secure & unified API key management",
    add_completion=False,
    no_args_is_help=True,
)

# Config
BASE_URL = "http://127.0.0.1:8000"  # Change to production URL later
CONFIG_FILE = Path.home() / ".zerokey" / "config.json"
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

def save_token(token: str):
    CONFIG_FILE.write_text(json.dumps({"access_token": token}))

def load_token() -> Optional[str]:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text()).get("access_token")
    return None

def get_headers() -> dict:
    token = load_token()
    if not token:
        console.print("[bold red]✗ Not logged in. Run:[/bold red] zerokey login")
        raise typer.Exit(1)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# ────────────────────────────────────────────────
# Auth Commands
# ────────────────────────────────────────────────

@app.command()
def register():
    """Register a new account"""
    username = typer.prompt("Username")
    password = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
    email = typer.prompt("Email (optional)", default="", show_default=False) or None

    payload = {"username": username, "password": password}
    if email:
        payload["email"] = email

    with console.status("[cyan]Creating account..."):
        try:
            r = requests.post(f"{BASE_URL}/auth/register", json=payload)
            r.raise_for_status()
            console.print(Panel(
                "[bold green]✓ Account created successfully![/bold green]\nNow login with zerokey login",
                title="Success",
                border_style="green",
                expand=False
            ))
        except requests.HTTPError as e:
            console.print(f"[red]✗ Error: {e.response.json().get('detail', 'Unknown error')}[/red]")
            raise typer.Exit(1)

@app.command()
def login():
    """Login to your account"""
    username = typer.prompt("Username")
    password = typer.prompt("Password", hide_input=True)

    payload = f"username={username}&password={password}"
    with console.status("[cyan]Logging in..."):
        try:
            r = requests.post(
                f"{BASE_URL}/auth/login",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=payload
            )
            r.raise_for_status()
            token = r.json()["access_token"]
            save_token(token)
            console.print(Panel(
                "[bold green]✓ Login successful![/bold green]\nToken saved securely.",
                title="Success",
                border_style="green",
                expand=False
            ))
        except requests.HTTPError as e:
            console.print(f"[red]✗ Login failed: {e.response.json().get('detail', 'Unknown error')}[/red]")
            raise typer.Exit(1)

@app.command()
def logout():
    """Logout and clear saved token"""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        console.print("[green]✓ Logged out successfully.[/green]")
    else:
        console.print("[yellow]No saved token found.[/yellow]")

# ────────────────────────────────────────────────
# API Key Management – Beautiful Table
# ────────────────────────────────────────────────

@app.command()
def add_key():
    """Add a new API key (provider auto-detected)"""
    name = typer.prompt("Name (e.g. production-groq)")
    key = typer.prompt("API Key")
    expires = typer.prompt("Expiration date (YYYY-MM-DD) or press Enter for Never", default="", show_default=False)

    payload = {"name": name, "key": key}
    if expires.strip():
        payload["expires_at"] = expires

    with console.status("[cyan]Adding key..."):
        try:
            r = requests.post(f"{BASE_URL}/keys", json=payload, headers=get_headers())
            r.raise_for_status()
            data = r.json()

            # Fixed: Proper rich markup (no invalid combined tags)
            success_text = Text.assemble(
                ("✓ Key added successfully!\n\n", "bold green"),
                ("Provider: ", "bold"), (f"{data['provider']}\n", "cyan"),
                ("Name: ", "bold"), (f"{data['name']}\n", "white"),
                ("Unified API Key: ", "bold"), (f"{data['unified_api_key']}\n", "blue"),
                ("Endpoint: ", "bold"), (f"{data['unified_endpoint']}\n", "blue"),
                ("Expires: ", "bold"), (f"{data['expires_at'] or 'Never'}", "yellow")
            )

            console.print(Panel(
                success_text,
                title="New Key Added",
                border_style="green",
                padding=(1, 2),
                expand=False
            ))

        except requests.HTTPError as e:
            error_detail = e.response.json().get('detail', 'Unknown error')
            console.print(f"[red]✗ {error_detail}[/red]")
            raise typer.Exit(1)

@app.command(name="ls")
def list_keys():
    """List all your API keys with serial numbers (beautiful table)"""
    try:
        r = requests.get(f"{BASE_URL}/keys", headers=get_headers())
        r.raise_for_status()
        keys = r.json()

        if not keys:
            console.print(Panel("[yellow]No keys stored yet. Add one with 'zerokey add-key'[/yellow]", border_style="yellow"))
            return

        table = Table(title="Your Zerokey Vault", show_header=True, header_style="bold magenta", box=ROUNDED)
        table.add_column("Sl. No.", style="cyan bold", justify="center")
        table.add_column("Name", style="bold white")
        table.add_column("Provider", style="green")
        table.add_column("Unified API Key", style="blue")
        table.add_column("Expires", style="yellow", justify="right")

        for idx, k in enumerate(keys, 1):
            expires = k.get('expires_at') or "Never"
            table.add_row(
                f"[bold cyan]{idx}[/bold cyan]",
                k['name'],
                k['provider'],
                k['unified_api_key'][:30] + "..." if len(k['unified_api_key']) > 30 else k['unified_api_key'],
                expires
            )

        console.print(table)
        console.print(f"\n[italic dim]Total keys: {len(keys)}[/italic dim]")

    except requests.HTTPError as e:
        console.print(f"[red]✗ Failed to load keys: {e.response.json().get('detail', 'Unknown error')}[/red]")

@app.command()
def delete(sl_no: int = typer.Argument(..., help="Serial number from 'zerokey ls'")):
    """Delete an API key using its serial number"""
    try:
        r = requests.get(f"{BASE_URL}/keys", headers=get_headers())
        r.raise_for_status()
        keys = r.json()
    except requests.HTTPError:
        console.print("[red]✗ Could not fetch keys[/red]")
        raise typer.Exit(1)

    if not keys:
        console.print("[yellow]No keys to delete[/yellow]")
        raise typer.Exit()

    if sl_no < 1 or sl_no > len(keys):
        console.print(f"[red]Invalid serial number. Valid range: 1–{len(keys)}[/red]")
        raise typer.Exit(1)

    key = keys[sl_no - 1]
    key_id = key["id"]
    key_name = key["name"]
    key_provider = key["provider"]

    console.print(Panel(
        f"[bold yellow]Delete key:[/bold yellow] {key_name} ({key_provider})\n"
        f"Sl. No.: [cyan]{sl_no}[/cyan]",
        title="Confirmation",
        border_style="yellow"
    ))

    if not typer.confirm("Are you sure?"):
        console.print("[green]Cancelled.[/green]")
        raise typer.Exit()

    with console.status("[cyan]Deleting..."):
        try:
            r = requests.delete(f"{BASE_URL}/keys/{key_id}", headers=get_headers())
            r.raise_for_status()
            console.print(f"[green]✓ Key '{key_name}' (Sl. No. {sl_no}) deleted successfully.[/green]")
        except requests.HTTPError as e:
            console.print(f"[red]✗ Delete failed: {e.response.json().get('detail', 'Unknown error')}[/red]")

# ────────────────────────────────────────────────
# Beautiful Usage Curve
# ────────────────────────────────────────────────

def sparkline(values: List[int], width: int = 50, height: int = 8) -> str:
    """Generate beautiful vertical sparkline with rich colors"""
    if not values:
        return "─" * width
    max_v = max(values) or 1
    min_v = min(values)
    range_v = max_v - min_v or 1
    scaled = [int((v - min_v) / range_v * (height - 1)) for v in values]
    lines = []
    for y in range(height - 1, -1, -1):
        line = ""
        for s in scaled:
            if s > y:
                line += "█"
            elif s == y:
                line += "▉"
            else:
                line += " "
        lines.append(line)
    return "\n".join(lines)

@app.command()
def usage(sl_no: Optional[int] = typer.Argument(None, help="Serial number from 'zerokey ls' (optional)")):
    """Show beautiful usage curve for all keys or specific key"""
    try:
        if sl_no is None:
            # Total usage
            r = requests.get(f"{BASE_URL}/usage", headers=get_headers())
            title = "Total Usage Across All Keys"
        else:
            # Get key list to map sl_no → id
            keys_r = requests.get(f"{BASE_URL}/keys", headers=get_headers())
            keys_r.raise_for_status()
            keys = keys_r.json()
            if sl_no < 1 or sl_no > len(keys):
                console.print(f"[red]Invalid serial number. Run 'zerokey ls' first.[/red]")
                raise typer.Exit(1)
            key_id = keys[sl_no - 1]["id"]
            key_name = keys[sl_no - 1]["name"]
            r = requests.get(f"{BASE_URL}/usage/{key_id}", headers=get_headers())
            title = f"Usage for {key_name} (Sl. No. {sl_no})"

        r.raise_for_status()
        data = r.json()
        logs = data.get("logs", []) if sl_no else data

        if not logs:
            console.print(Panel("[yellow]No usage recorded yet.[/yellow]", title=title, border_style="yellow"))
            return

        # Sort logs by time
        logs.sort(key=lambda x: x["created_at"])
        tokens = [log["total_tokens"] for log in logs]
        times = [datetime.fromisoformat(log["created_at"].replace("Z", "+00:00")) for log in logs]

        # Sparkline + Stats Panel
        spark = sparkline(tokens)
        total = sum(tokens)
        max_single = max(tokens) if tokens else 0
        calls = len(logs)
        time_range = f"{times[0].strftime('%b %d %Y')} → {times[-1].strftime('%b %d %Y')}"

        stats_text = Text.assemble(
            ("Total tokens: ", "bold green"), (f"{total:,}", "bold white"),
            ("\nHighest call: ", "bold green"), (f"{max_single:,}", "bold white"),
            ("\nTotal calls:  ", "bold green"), (f"{calls}", "bold white"),
            ("\nTime span:    ", "bold green"), (time_range, "bold white")
        )

        console.print(Panel(
            f"[bold cyan]{title}[/bold cyan]\n\n"
            f"{spark}\n\n"
            f"{stats_text}",
            title="Usage Curve & Stats",
            border_style="bright_blue",
            expand=False,
            padding=(1, 2)
        ))

    except requests.HTTPError as e:
        console.print(f"[red]✗ Failed to load usage: {e.response.json().get('detail', 'Unknown error')}[/red]")

# ────────────────────────────────────────────────
# Quick Proxy Call
# ────────────────────────────────────────────────

@app.command()
def call(
    unified_key: str = typer.Argument(..., help="Unified API key"),
    model: str = typer.Option("llama3-70b-8192", help="Model name"),
    message: str = typer.Option(..., prompt=True, help="Your prompt/message")
):
    """Quickly call an API using unified key"""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}]
    }

    with console.status("[cyan]Calling API..."):
        try:
            r = requests.post(
                f"{BASE_URL}/proxy/{unified_key}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            r.raise_for_status()
            console.print(Panel(
                json.dumps(r.json(), indent=2),
                title="API Response",
                border_style="green",
                expand=False
            ))
        except requests.HTTPError as e:
            console.print(f"[red]API call failed: {e.response.status_code}[/red]")
            console.print(e.response.text)

if __name__ == "__main__":
    app()
