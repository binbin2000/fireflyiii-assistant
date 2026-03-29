"""Interactive CLI for reviewing and categorizing Firefly III transactions."""

import os
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.columns import Columns
from rich.text import Text

from .firefly_client import FireflyClient
from .categorizer import Categorizer, Suggestion


console = Console()


# ─── Formatting helpers ──────────────────────────────────────────────────────

def _fmt_amount(amount: float, currency: str = 'kr') -> str:
    return f'{amount:,.2f} {currency}'


def _fmt_date(date_str: str) -> str:
    return (date_str or '')[:10] or '–'


def _suggestion_badge(source: str) -> str:
    return '🤖 AI' if source == 'ai' else ('📚 Historik' if source == 'history' else '✏️  Manuell')


# ─── Display ─────────────────────────────────────────────────────────────────

def show_transaction(txn: dict, suggestion: Suggestion, index: int, total: int):
    """Render a transaction and its suggestion in the terminal."""
    currency = txn.get('currency_code') or 'kr'

    info = Table(show_header=False, box=None, padding=(0, 1))
    info.add_column(style='bold cyan', width=18)
    info.add_column()

    info.add_row('Beskrivning', txn['description'] or '–')
    info.add_row('Belopp', _fmt_amount(txn['amount'], currency))
    info.add_row('Datum', _fmt_date(txn.get('date', '')))
    info.add_row('Från konto', txn.get('source_name') or '–')
    info.add_row('Destination', txn.get('destination_name') or '–')

    if txn.get('category_name'):
        info.add_row('Nuv. kategori', f'[dim]{txn["category_name"]}[/dim]')

    info.add_row('', '')

    if suggestion.has_any():
        badge = _suggestion_badge(suggestion.source)
        conf_pct = f'{suggestion.confidence * 100:.0f}%'
        info.add_row(
            f'[bold yellow]Förslag[/bold yellow]',
            f'{badge}  [dim]konfidens {conf_pct}[/dim]',
        )
        if suggestion.category_name:
            info.add_row('  Kategori', f'[green]{suggestion.category_name}[/green]')
        if suggestion.budget_name:
            info.add_row('  Budget', f'[blue]{suggestion.budget_name}[/blue]')
        if suggestion.destination_name:
            info.add_row('  Leverantör', f'[magenta]{suggestion.destination_name}[/magenta]')
        if suggestion.reasoning:
            info.add_row('  Motivering', f'[dim]{suggestion.reasoning}[/dim]')
        if suggestion.matched_description and suggestion.source == 'history':
            info.add_row('  Matchad mot', f'[dim italic]{suggestion.matched_description}[/dim italic]')
    else:
        info.add_row('[bold red]Förslag[/bold red]', '[dim]Inget förslag tillgängligt[/dim]')

    console.print(Panel(
        info,
        title=f'[bold] Transaktion {index} / {total} [/bold]',
        border_style='blue',
        padding=(0, 1),
    ))


def show_summary_table(pending: list):
    """Show a summary table of all queued updates before applying."""
    t = Table(title='Ändringar att spara', show_header=True, header_style='bold')
    t.add_column('Beskrivning', max_width=35)
    t.add_column('Belopp', justify='right')
    t.add_column('Kategori', style='green')
    t.add_column('Budget', style='blue')
    t.add_column('Leverantör', style='magenta')
    t.add_column('Källa', style='dim')

    for txn, sg in pending:
        currency = txn.get('currency_code') or 'kr'
        t.add_row(
            txn['description'][:35],
            _fmt_amount(txn['amount'], currency),
            sg.category_name or '–',
            sg.budget_name or '–',
            sg.destination_name or '–',
            _suggestion_badge(sg.source),
        )
    console.print(t)


# ─── Edit flow ───────────────────────────────────────────────────────────────

def edit_suggestion(suggestion: Suggestion, categories: list, budgets: list) -> Suggestion:
    """Let the user manually edit a suggestion interactively."""
    console.print('\n[bold yellow]Redigera förslag[/bold yellow] [dim](lämna tomt = behåll befintligt, "-" = rensa)[/dim]\n')

    cat_names = ', '.join(c['name'] for c in categories[:12])
    console.print(f'[dim]Tillgängliga kategorier (urval): {cat_names}[/dim]')
    cat_input = Prompt.ask(
        f'Kategori',
        default=suggestion.category_name or '',
    ).strip()

    budget_names = ', '.join(b['name'] for b in budgets[:12])
    console.print(f'[dim]Tillgängliga budgetar (urval): {budget_names}[/dim]')
    budget_input = Prompt.ask(
        'Budget',
        default=suggestion.budget_name or '',
    ).strip()

    dest_input = Prompt.ask(
        'Leverantör',
        default=suggestion.destination_name or '',
    ).strip()

    # Resolve to exact names (or None if cleared with "-")
    def resolve_or_none(value: str, original: Optional[str]) -> Optional[str]:
        if value == '-':
            return None
        return value or original

    cat_name = resolve_or_none(cat_input, suggestion.category_name)
    budget_name = resolve_or_none(budget_input, suggestion.budget_name)
    dest_name = resolve_or_none(dest_input, suggestion.destination_name)

    # Normalize category and budget against known lists
    def fuzzy_match_name(value: Optional[str], lookup: list) -> Optional[str]:
        if not value:
            return None
        for item in lookup:
            if item['name'].lower() == value.lower():
                return item['name']
        # Try a starts-with match
        for item in lookup:
            if item['name'].lower().startswith(value.lower()):
                return item['name']
        return value  # Keep as-is (new vendor name is allowed)

    cat_name = fuzzy_match_name(cat_name, categories)
    budget_name = fuzzy_match_name(budget_name, budgets)

    return Suggestion(
        category_name=cat_name,
        budget_name=budget_name,
        destination_name=dest_name,
        confidence=1.0,
        source='manual',
        reasoning='Manuellt redigerad',
    )


# ─── Main entry point ─────────────────────────────────────────────────────────

def run_categorizer(show_all: bool = False, limit: int = 50):
    """Run the interactive transaction categorizer."""
    firefly_url = os.getenv('FIREFLY_URL', '').strip()
    firefly_token = os.getenv('FIREFLY_TOKEN', '').strip()
    anthropic_key = os.getenv('ANTHROPIC_API_KEY', '').strip()

    errors = []
    if not firefly_url:
        errors.append('FIREFLY_URL saknas i .env')
    if not firefly_token:
        errors.append('FIREFLY_TOKEN saknas i .env')
    if not anthropic_key:
        errors.append('ANTHROPIC_API_KEY saknas i .env')
    if errors:
        for e in errors:
            console.print(f'[bold red]✗[/bold red] {e}')
        console.print('\nKopiera [bold].env.example[/bold] till [bold].env[/bold] och fyll i dina uppgifter.')
        sys.exit(1)

    console.print(Panel.fit(
        '[bold blue]Firefly III – AI Transaktionskategoriserare[/bold blue]\n'
        '[dim]Automatiska förslag med Claude + historikbaserad matchning[/dim]',
        border_style='blue',
    ))
    console.print()

    # ── Connect & fetch data ──────────────────────────────────────────────────
    with Progress(SpinnerColumn(), TextColumn('{task.description}'), console=console) as prog:
        task = prog.add_task('Ansluter till Firefly III…', total=None)

        try:
            client = FireflyClient(firefly_url, firefly_token)
            client.test_connection()
        except Exception as e:
            console.print(f'[bold red]Anslutningsfel:[/bold red] {e}')
            console.print('[dim]Kontrollera FIREFLY_URL och FIREFLY_TOKEN i .env[/dim]')
            sys.exit(1)

        prog.update(task, description='Hämtar kategorier, budgetar och konton…')
        try:
            categories = client.get_categories()
            budgets = client.get_budgets()
            expense_accounts = client.get_expense_accounts()
        except Exception as e:
            console.print(f'[bold red]Fel vid hämtning av data:[/bold red] {e}')
            sys.exit(1)

        prog.update(task, description='Läser in transaktionshistorik…')
        history = client.get_recent_categorized_transactions(limit=300)

        prog.update(task, description='Hämtar transaktioner att granska…')
        if show_all:
            transactions = client.get_all_recent_transactions(limit=limit)
        else:
            transactions = client.get_uncategorized_transactions(limit=limit)

        prog.update(task, description='Klar!')

    if not transactions:
        label = 'alla' if show_all else 'okategoriserade'
        console.print(f'[bold green]✓[/bold green] Inga {label} transaktioner att granska.')
        return

    label = 'transaktioner' if show_all else 'okategoriserade transaktioner'
    console.print(f'[bold]{len(transactions)} {label}[/bold] att granska')
    console.print(
        f'Kategorier: [cyan]{len(categories)}[/cyan]  '
        f'Budgetar: [blue]{len(budgets)}[/blue]  '
        f'Historik: [dim]{len(history)} poster[/dim]\n'
    )

    # ── Initialize AI categorizer ─────────────────────────────────────────────
    categorizer = Categorizer(
        api_key=anthropic_key,
        categories=categories,
        budgets=budgets,
        expense_accounts=expense_accounts,
        history=history,
    )

    # ── Review loop ───────────────────────────────────────────────────────────
    pending_updates: list = []
    accept_all = False

    for i, txn in enumerate(transactions, 1):
        console.print()

        with Progress(SpinnerColumn(), TextColumn('{task.description}'), console=console) as prog:
            t = prog.add_task(f'Analyserar transaktion {i}/{len(transactions)}…', total=None)
            suggestion = categorizer.suggest(txn)

        show_transaction(txn, suggestion, i, len(transactions))

        if accept_all:
            if suggestion.has_any():
                pending_updates.append((txn, suggestion))
                console.print('[dim]  → Auto-godkänd[/dim]')
            else:
                console.print('[dim]  → Hoppades över (inget förslag)[/dim]')
            continue

        # Prompt
        console.print(
            '[bold]Åtgärd:[/bold] '
            '[green]y[/green]=godkänn  '
            '[yellow]e[/yellow]=redigera  '
            '[dim]s[/dim]=hoppa över  '
            '[bold green]a[/bold green]=godkänn alla kvar  '
            '[bold red]q[/bold red]=avsluta'
        )
        choice = Prompt.ask('', choices=['y', 'e', 's', 'a', 'q'], default='y')

        if choice == 'q':
            console.print('[yellow]Avslutar…[/yellow]')
            break

        elif choice == 'a':
            accept_all = True
            if suggestion.has_any():
                pending_updates.append((txn, suggestion))

        elif choice == 'y':
            if suggestion.has_any():
                pending_updates.append((txn, suggestion))
                console.print('[green]  ✓ Godkänd[/green]')
            else:
                console.print('[yellow]  Inget förslag att spara[/yellow]')

        elif choice == 'e':
            edited = edit_suggestion(suggestion, categories, budgets)
            if edited.has_any():
                pending_updates.append((txn, edited))
                console.print(f'[green]  ✓ Sparad: {edited.summary()}[/green]')
            else:
                console.print('[dim]  Inga ändringar[/dim]')

        elif choice == 's':
            console.print('[dim]  Hoppades över[/dim]')

    # ── Apply updates ─────────────────────────────────────────────────────────
    if not pending_updates:
        console.print('\n[yellow]Inga ändringar att spara.[/yellow]')
        return

    console.print()
    show_summary_table(pending_updates)
    console.print()

    if not Confirm.ask(f'Spara [bold]{len(pending_updates)}[/bold] uppdateringar till Firefly III?'):
        console.print('[yellow]Avbröts – inga ändringar sparade.[/yellow]')
        return

    success = 0
    errors = 0

    with Progress(SpinnerColumn(), TextColumn('{task.description}'), console=console) as prog:
        task = prog.add_task('Sparar…', total=len(pending_updates))

        for txn, sg in pending_updates:
            prog.update(task, description=f'Sparar: {txn["description"][:40]}…')
            try:
                client.update_transaction(
                    group_id=txn['group_id'],
                    raw_split=txn['_raw_split'],
                    category_name=sg.category_name,
                    budget_name=sg.budget_name,
                    destination_name=sg.destination_name,
                )
                success += 1
            except Exception as e:
                console.print(f'[red]  ✗ Fel för "{txn["description"]}": {e}[/red]')
                errors += 1
            prog.advance(task)

    console.print()
    console.print(f'[bold green]✓ {success} transaktioner uppdaterade[/bold green]')
    if errors:
        console.print(f'[bold red]✗ {errors} fel[/bold red]')
