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
import click

console = Console()

app = typer.Typer(
    name="zerokey",
    help="Zerokey CLI - Secure & unified API key management",
    add_completion=False,
    no_args_is_help=True,
)

# Config
BASE_URL = "https://zerokey.onrender.com"  # Change to production URL later
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
    """Login to your account (JWT or GitHub)"""
    
    console.print("\n[bold cyan]Choose Authentication Method:[/bold cyan]\n")
    
    # Display options with logos/icons
    console.print("  [bold]1.[/bold] JWT Authentication (Username & Password)")
    console.print("  [bold]2.[/bold] GitHub OAuth")
    console.print("  [bold]3.[/bold] GitLab OAuth")
    console.print("  [bold]4.[/bold] Bitbucket OAuth\n")
    
    choice = typer.prompt(
        "Enter your choice",
        type=click.Choice(["1", "2", "3", "4"]),
        default="1"
    )
    
    if choice == "1":
        auth_choice = "jwt"
    elif choice == "2":
        auth_choice = "github"
    elif choice == "3":
        auth_choice = "gitlab"
    else:
        auth_choice = "bitbucket"
    
    if auth_choice == "jwt":
        console.print("\n[bold cyan] JWT Login[/bold cyan]")
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
                    "[bold green]✓ JWT Login successful![/bold green]\nToken saved securely.",
                    title="Success",
                    border_style="green",
                    expand=False
                ))
            except requests.HTTPError as e:
                console.print(f"[red]✗ Login failed: {e.response.json().get('detail', 'Unknown error')}[/red]")
                raise typer.Exit(1)
    
    elif auth_choice == "github":
        import webbrowser
        import time
        
        console.print(Panel(
            "[bold cyan]:github: GitHub Login Flow[/bold cyan]\n\n"
            "[yellow]Step 1:[/yellow] Opening GitHub authorization in your browser...\n"
            "[yellow]Step 2:[/yellow] After you authorize, your JWT will be shown in the browser\n"
            "[yellow]Step 3:[/yellow] Copy it and paste back here to finish CLI login",
            title="GitHub OAuth",
            border_style="cyan",
            expand=False
        ))
        
        github_url = f"{BASE_URL}/auth/github/login?state=cli"
        console.print(f"\n[blue]Opening: {github_url}[/blue]\n")
        
        webbrowser.open(github_url)
        
        console.print("\n[bold yellow]After authorizing, copy the JWT shown in the browser and paste it below.[/bold yellow]\n")
        pasted_token = typer.prompt("Paste JWT from browser", hide_input=True)

        if not pasted_token.strip():
            console.print("[red]✗ No token provided. Aborting.[/red]")
            raise typer.Exit(1)

        save_token(pasted_token.strip())
        console.print(Panel(
            "[bold green]✓ GitHub login successful via CLI![/bold green]\nToken saved securely.",
            title="Success",
            border_style="green",
            expand=False
        ))
    
    elif auth_choice == "gitlab":
        import webbrowser
        import time
        
        console.print(Panel(
            "[bold cyan]:gitlab: GitLab Login Flow[/bold cyan]\n\n"
            "[yellow]Step 1:[/yellow] Opening GitLab authorization in your browser...\n"
            "[yellow]Step 2:[/yellow] After you authorize, your JWT will be shown in the browser\n"
            "[yellow]Step 3:[/yellow] Copy it and paste back here to finish CLI login",
            title="GitLab OAuth",
            border_style="cyan",
            expand=False
        ))
        
        gitlab_url = f"{BASE_URL}/auth/gitlab/login?state=cli"
        console.print(f"\n[blue]Opening: {gitlab_url}[/blue]\n")
        
        webbrowser.open(gitlab_url)
        
        console.print("\n[bold yellow]After authorizing, copy the JWT shown in the browser and paste it below.[/bold yellow]\n")
        pasted_token = typer.prompt("Paste JWT from browser", hide_input=True)

        if not pasted_token.strip():
            console.print("[red]✗ No token provided. Aborting.[/red]")
            raise typer.Exit(1)

        save_token(pasted_token.strip())
        console.print(Panel(
            "[bold green]✓ GitLab login successful via CLI![/bold green]\nToken saved securely.",
            title="Success",
            border_style="green",
            expand=False
        ))

    elif auth_choice == "bitbucket":
        
        console.print(Panel(
            "[bold cyan]:bitbucket: Bitbucket Login Flow[/bold cyan]\n\n"
            "[yellow]Step 1:[/yellow] Opening Bitbucket authorization in your browser...\n"
            "[yellow]Step 2:[/yellow] After you authorize, your JWT will be shown in the browser\n"
            "[yellow]Step 3:[/yellow] Copy it and paste back here to finish CLI login",
            title="Bitbucket OAuth",
            border_style="cyan",
            expand=False
        ))
        
        bitbucket_url = f"{BASE_URL}/auth/bitbucket/login?state=cli"
        console.print(f"\n[blue]Opening: {bitbucket_url}[/blue]\n")
        
        webbrowser.open(bitbucket_url)
        
        console.print("\n[bold yellow]After authorizing, copy the JWT shown in the browser and paste it below.[/bold yellow]\n")
        pasted_token = typer.prompt("Paste JWT from browser", hide_input=True)

        if not pasted_token.strip():
            console.print("[red]✗ No token provided. Aborting.[/red]")
            raise typer.Exit(1)

        save_token(pasted_token.strip())
        console.print(Panel(
            "[bold green]✓ Bitbucket login successful via CLI![/bold green]\nToken saved securely.",
            title="Success",
            border_style="green",
            expand=False
        ))

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

            console.print(Panel.fit(
                f"[bold green]✓ Key added successfully![/bold green]\n\n"
                f"Provider: [cyan]{data['provider']}[/cyan]\n"
                f"Name: [bold]{data['name']}[/bold]\n"
                f"Unified API Key: [bold cyan]{data['unified_api_key']}[/bold cyan]\n"
                f"Endpoint: [blue]{data['unified_endpoint']}[/blue]\n"
                f"Expires: [yellow]{data['expires_at'] or 'Never'}[/yellow]",
                title="Key Details",
                border_style="green",
                padding=(1, 2)
            ))
        except requests.HTTPError as e:
            console.print(f"[red]✗ {e.response.json().get('detail', 'Failed to add key')}[/red]")
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

# cli.py (updated call command only - replace your existing call function)

@app.command()
def call(
    unified_key: str = typer.Argument(..., help="Unified API key (e.g. apikey-gemini-cbhgemini)"),
    model: str = typer.Option(..., prompt="Model name (e.g. llama-3.3-70b-versatile for Groq, gemini-1.5-flash for Gemini)", help="Model to use"),
    message: str = typer.Option(..., prompt=True, help="Your prompt/message")
):
    """Quickly call any API using unified key and show full proper JSON response"""
    # Parse unified_key
    parts = unified_key.split('-')
    if len(parts) < 3 or parts[0] != 'apikey':
        console.print("[red]Invalid unified key format. Expected: apikey-provider-name[/red]")
        raise typer.Exit(1)

    provider = parts[1]
    name_slug = '-'.join(parts[2:])

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}]
    }

    with console.status(f"[cyan]Calling {provider.upper()} ({model})..."):
        try:
            r = requests.post(
                f"{BASE_URL}/proxy/u/{provider}/{name_slug}",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {unified_key}"
                }
            )
            r.raise_for_status()
            response_data = r.json()

            # Full JSON string
            json_str = json.dumps(response_data, indent=2)

            # Simple colorization (keys cyan, values green)
            colored_json = Text()
            for line in json_str.splitlines():
                if ':' in line and not line.strip().startswith('}'):
                    key, value = line.split(":", 1)
                    colored_json.append(Text(key, style="cyan"))
                    colored_json.append(Text(":", style="white"))
                    colored_json.append(Text(value, style="green"))
                else:
                    colored_json.append(Text(line, style="white"))
                colored_json.append("\n")

            console.print(Panel(
                colored_json,
                title=f"Full API Response • {provider.upper()} • {model}",
                subtitle=f"Prompt: {message[:80]}{'...' if len(message) > 80 else ''}",
                border_style="bright_green",
                expand=True,
                padding=(1, 2)
            ))

        except requests.HTTPError as e:
            console.print(f"[red]✗ API call failed: {e.response.status_code}[/red]")
            try:
                console.print(Panel(
                    json.dumps(e.response.json(), indent=2),
                    title="Error Response",
                    border_style="red",
                    expand=True
                ))
            except:
                console.print(e.response.text)


if __name__ == "__main__":
    app()
