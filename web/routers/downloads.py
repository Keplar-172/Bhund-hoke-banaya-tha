"""Download routes - export files in various formats."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from datetime import date
import os
import tempfile

from web.auth import require_auth, User
from leaderboard import (
    export_summary_to_excel,
    export_detailed_to_excel,
    export_master_to_excel,
    export_scorecard_to_excel,
    export_team_points_to_excel,
    export_teams_to_excel,
    export_analytics_to_excel,
)
from calculator import calculate_match_scores
from storage import get_cached_scorecard

router = APIRouter()

MATCH_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "Match data")


def _get_cfg(request: Request):
    """Tournament from ?league=<id> (old keys 'ipl'/'wwc' still work)."""
    import tournaments
    key = request.query_params.get("league")
    t = tournaments.get(key) if key else tournaments.default()
    if t is None:
        raise HTTPException(status_code=404, detail=f"Unknown tournament '{key}'")
    return t


@router.get("/master")
async def download_master(request: Request, user: User = Depends(require_auth)):
    """Download master scoresheet Excel (pass ?league=wwc for WWC)."""
    cfg = _get_cfg(request)
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_master_scoresheet_{cfg.short_name}.xlsx")

    export_master_to_excel(filename, cfg)

    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Nothing to export yet for this tournament")

    return FileResponse(
        path=filename,
        filename=f"{today}_master_scoresheet_{cfg.short_name}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/match/{match_id}/team-points")
async def download_team_points(
    match_id: int, request: Request, user: User = Depends(require_auth)
):
    """Download team points for a specific match (pass ?league=wwc for WWC)."""
    cfg = _get_cfg(request)
    scorecard_data = get_cached_scorecard(match_id, cfg)
    if not scorecard_data:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

    match_results = calculate_match_scores(scorecard_data, cfg)

    desc = f"Match {match_id}"
    header = scorecard_data.get("matchHeader", {})
    if header:
        t1 = header.get("team1", {}).get("shortName", "")
        t2 = header.get("team2", {}).get("shortName", "")
        status = header.get("status", "")
        if t1 and t2:
            desc = f"{t1} vs {t2} – {status}"

    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_team_points_{match_id}_{cfg.short_name}.xlsx")

    export_team_points_to_excel(match_results, desc, filename, cfg=cfg)

    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Nothing to export yet for this tournament")

    return FileResponse(
        path=filename,
        filename=f"{today}_team_points_{match_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/match/{match_id}/scorecard")
async def download_scorecard(
    match_id: int, request: Request, user: User = Depends(require_auth)
):
    """Download cricket scorecard for a specific match (pass ?league=wwc for WWC)."""
    cfg = _get_cfg(request)
    scorecard_data = get_cached_scorecard(match_id, cfg)
    if not scorecard_data:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_scorecard_{match_id}_{cfg.short_name}.xlsx")

    export_scorecard_to_excel(scorecard_data, filename, match_id)

    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Nothing to export yet for this tournament")

    return FileResponse(
        path=filename,
        filename=f"{today}_scorecard_{match_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def _copy_sheets(src_path: str, dest_wb) -> None:
    """Append every sheet of the workbook at src_path to dest_wb, keeping
    values, styles, column widths, row heights and merged cells."""
    from copy import copy
    from openpyxl import load_workbook

    src_wb = load_workbook(src_path)
    for src in src_wb.worksheets:
        title = src.title
        n = 2
        while title in dest_wb.sheetnames:  # avoid clashing sheet names
            title = f"{src.title[:28]} {n}"
            n += 1
        dest = dest_wb.create_sheet(title)
        for row in src.iter_rows():
            for cell in row:
                new = dest.cell(row=cell.row, column=cell.column, value=cell.value)
                if cell.has_style:
                    new.font = copy(cell.font)
                    new.border = copy(cell.border)
                    new.fill = copy(cell.fill)
                    new.number_format = cell.number_format
                    new.alignment = copy(cell.alignment)
        for key, dim in src.column_dimensions.items():
            dest.column_dimensions[key].width = dim.width
        for key, dim in src.row_dimensions.items():
            if dim.height:
                dest.row_dimensions[key].height = dim.height
        for rng in src.merged_cells.ranges:
            dest.merge_cells(str(rng))
        dest.freeze_panes = src.freeze_panes


@router.get("/match/{match_id}")
async def download_match_sheet(
    match_id: int, request: Request, user: User = Depends(require_auth)
):
    """One workbook per match: team points (rankings plus a sheet per team)
    followed by the cricket scorecard innings. Replaces downloading the
    team-points and scorecard files separately; both old routes still work."""
    from openpyxl import load_workbook
    from web.services import _build_match_meta

    cfg = _get_cfg(request)
    scorecard_data = get_cached_scorecard(match_id, cfg)
    if not scorecard_data:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

    meta = _build_match_meta(match_id, cfg)
    label = meta.get("match_number_label") or f"Match {match_id}"
    desc = f"{label}: {meta.get('description', '')}".strip(": ")

    today = date.today().strftime("%Y%m%d")
    with tempfile.TemporaryDirectory() as tmp:
        points_path = os.path.join(tmp, "points.xlsx")
        card_path = os.path.join(tmp, "scorecard.xlsx")
        export_team_points_to_excel(calculate_match_scores(scorecard_data, cfg), desc, points_path, cfg=cfg)
        export_scorecard_to_excel(scorecard_data, card_path, match_id)
        if not os.path.exists(points_path):
            raise HTTPException(status_code=404, detail="Nothing to export yet for this match")

        wb = load_workbook(points_path)
        if os.path.exists(card_path):
            _copy_sheets(card_path, wb)

        safe_label = "".join(ch if ch.isalnum() else "-" for ch in label).strip("-")
        download_name = f"{today}_{cfg.short_name}_{safe_label}_match_sheet.xlsx"
        out_path = os.path.join(MATCH_DATA_DIR, f"{today}_match_sheet_{match_id}_{cfg.short_name}.xlsx")
        os.makedirs(MATCH_DATA_DIR, exist_ok=True)
        wb.save(out_path)

    return FileResponse(
        path=out_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/teams")
async def download_teams(request: Request, user: User = Depends(require_auth)):
    """Download all team rosters (pass ?league=wwc for WWC)."""
    cfg = _get_cfg(request)
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_teams_{cfg.short_name}.xlsx")

    export_teams_to_excel(filename, cfg)

    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Nothing to export yet for this tournament")

    return FileResponse(
        path=filename,
        filename=f"{today}_teams_{cfg.short_name}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@router.get("/analytics")
async def download_analytics(request: Request, user: User = Depends(require_auth)):
    """Download analytics dashboard (pass ?league=wwc for WWC)."""
    cfg = _get_cfg(request)
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_analytics_{cfg.short_name}.xlsx")

    export_analytics_to_excel(filename, cfg)

    if not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Nothing to export yet for this tournament")

    return FileResponse(
        path=filename,
        filename=f"{today}_analytics_{cfg.short_name}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
