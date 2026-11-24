"""Functions every template can use. Call register(templates) once per Jinja2Templates."""
import market
import team_names
import tournaments


def _market_pending(league, owner) -> int:
    if not league or not owner or not market.is_open(league):
        return 0
    import trades
    return trades.pending_count(league, owner)


def register(templates) -> None:
    g = templates.env.globals
    g["all_tournaments"] = tournaments.all_tournaments
    g["team_name"] = team_names.display
    g["team_names"] = team_names.names
    g["market_visible"] = market.visible
    g["market_stage"] = lambda t: market.load(t)["stage"]
    g["market_pending"] = _market_pending
    g["crores"] = market.crores
