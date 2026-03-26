#!/usr/bin/env python3
"""
Pelotonia email report — sends daily or weekly summary of fundraising progress.

Includes:
  - 4 infographic cards (funds, riders, challengers, volunteers) in a 2×2 grid
  - Daily/weekly deltas: riders added, funds raised, top sub-team movers
  - Participation by sub-team table

Usage:
    # Preview daily HTML in terminal (no send)
    python app/daily_report.py --preview

    # Preview weekly HTML
    python app/daily_report.py --preview --weekly

    # Save HTML to file for inspection
    python app/daily_report.py --preview --output report.html

    # Send daily email
    python app/daily_report.py --send

    # Send weekly email
    python app/daily_report.py --send --weekly

    # Send to a different address
    python app/daily_report.py --send --to someone@example.com
"""

import argparse
import io
import os
import smtplib
import sqlite3
import sys
from datetime import datetime, timedelta
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from dotenv import load_dotenv
    load_dotenv()
    # Also try pelotonia-kids .env for Gmail creds
    kids_env = Path(__file__).resolve().parent.parent.parent / "pelotonia-kids" / ".env"
    if kids_env.exists():
        load_dotenv(kids_env)
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PELOTONIA_DB", SCRIPT_DIR / "pelotonia_data.db"))
PARENT_TEAM_ID = "a0s3t00000BKX8sAAH"

SENDER_EMAIL = os.environ.get("GMAIL_SENDER", "")
SENDER_NAME = os.environ.get("REPORT_SENDER_NAME", "Pelotonia Dashboard")
DEFAULT_TO = os.environ.get("REPORT_RECIPIENT", "")

# Goals (same as dashboard.py)
GOALS = {"riders": 2100, "challengers": 547, "volunteers": 1500, "funds": 6_000_000}
GOALS_SUBTEAMS = {
    "Audit": {"riders": 19, "challengers": 7, "funds": 57651},
    "Commercial, CRE, and Capital Markets": {"riders": 221, "challengers": 64, "funds": 726864},
    "Communications": {"riders": 11, "challengers": 2, "funds": 22182},
    "Consumer Regional Bank": {"riders": 1016, "challengers": 236, "funds": 1958856},
    "Corporate Operations": {"riders": 133, "challengers": 49, "funds": 735662},
    "Credit, Collections, and Financial Recovery Group": {"riders": 61, "challengers": 17, "funds": 192489},
    "Finance and Strategy": {"riders": 91, "challengers": 17, "funds": 316231},
    "Friends, Family, Retirees, and Alumni": {"riders": 117, "challengers": 4, "funds": 171647},
    "Human Resources": {"riders": 50, "challengers": 17, "funds": 158489},
    "Legal & Public Affairs": {"riders": 18, "challengers": 4, "funds": 199233},
    "Office of Inclusion": {"riders": 5, "challengers": 1, "funds": 16605},
    "Payments & TM": {"riders": 68, "challengers": 27, "funds": 161571},
    "Risk": {"riders": 59, "challengers": 19, "funds": 127397},
    "Tech/M&A and Cyber": {"riders": 231, "challengers": 82, "funds": 1145146},
}

# Campaign dates
CAMPAIGN_START = datetime(2026, 3, 4)
RIDE_DAY = datetime(2026, 8, 1)


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def money(v):
    """Format as $X,XXX or $X.XM."""
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    return f"${v:,.0f}"


def money_short(v):
    """Format as $Xk or $X.XM."""
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}k"
    return f"${v:,.0f}"


def delta_str(val, is_money=False):
    """Format a delta with +/- prefix and color."""
    if val > 0:
        fmt = money_short(val) if is_money else f"{val:,}"
        return f'<span style="color:#44D62C;font-weight:700">+{fmt}</span>'
    elif val < 0:
        fmt = money_short(abs(val)) if is_money else f"{abs(val):,}"
        return f'<span style="color:#e74c3c;font-weight:700">-{fmt}</span>'
    return '<span style="color:#888">—</span>'


def pct(current, goal):
    if not goal:
        return 0
    return min(current / goal * 100, 100)


def gather_data(weekly=False):
    """Pull all data needed for the report from SQLite.

    Args:
        weekly: If True, compute deltas over 7 days instead of 1 day.
    """
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    lookback_days = 7 if weekly else 1
    compare_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    # Current overview
    parent = conn.execute(
        "SELECT name, raised, COALESCE(goal_override, goal) as goal, all_time_raised, members_count "
        "FROM teams WHERE id=?", (PARENT_TEAM_ID,)
    ).fetchone()

    riders = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_rider=1").fetchone()["cnt"]
    challengers = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_challenger=1").fetchone()["cnt"]
    volunteers = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_volunteer=1").fetchone()["cnt"]
    members_total = conn.execute("SELECT COUNT(*) as cnt FROM members").fetchone()["cnt"]
    high_rollers = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE tags LIKE '%High Roller%'").fetchone()["cnt"]
    survivors = conn.execute("SELECT COUNT(*) as cnt FROM members WHERE is_cancer_survivor=1").fetchone()["cnt"]
    first_year = conn.execute("""SELECT COUNT(*) as cnt FROM members WHERE tags LIKE '%"1 year"%' AND is_rider=1""").fetchone()["cnt"]

    commit_row = conn.execute("""
        SELECT COALESCE(SUM(committed_amount),0) as total,
               COALESCE(SUM(CASE WHEN committed_high_roller=1 THEN committed_amount ELSE 0 END),0) as hr,
               COALESCE(SUM(CASE WHEN committed_high_roller=0 THEN committed_amount ELSE 0 END),0) as std
        FROM members WHERE team_id IS NOT NULL
    """).fetchone()

    # Snapshots for deltas (today vs compare_date)
    snap_today = conn.execute(
        "SELECT * FROM daily_snapshots WHERE team_id=? AND snapshot_date=?",
        (PARENT_TEAM_ID, today)
    ).fetchone()
    snap_compare = conn.execute(
        "SELECT * FROM daily_snapshots WHERE team_id=? AND snapshot_date<=? ORDER BY snapshot_date DESC LIMIT 1",
        (PARENT_TEAM_ID, compare_date)
    ).fetchone()

    # Sub-team breakdown
    team_rows = conn.execute("""
        SELECT t.name,
               SUM(CASE WHEN m.is_rider=1 OR (m.is_rider=0 AND m.is_challenger=0 AND m.is_volunteer=0
                   AND mr.member_public_id IS NOT NULL) THEN 1 ELSE 0 END) as riders,
               SUM(CASE WHEN m.is_challenger=1 AND m.is_rider=0 THEN 1 ELSE 0 END) as challengers,
               SUM(CASE WHEN m.is_volunteer=1 AND m.is_rider=0 AND m.is_challenger=0 THEN 1 ELSE 0 END) as volunteers,
               COUNT(DISTINCT m.public_id) as total,
               COALESCE(SUM(m.committed_amount),0) as total_committed,
               COALESCE(SUM(m.raised),0) as total_raised,
               SUM(CASE WHEN m.tags LIKE '%"1 year"%' AND m.is_rider=1 THEN 1 ELSE 0 END) as first_year
        FROM members m
        JOIN teams t ON m.team_id=t.id
        LEFT JOIN (SELECT DISTINCT member_public_id FROM member_routes) mr
            ON m.public_id=mr.member_public_id
        WHERE t.parent_id=?
        GROUP BY t.name
        ORDER BY SUM(m.committed_amount) DESC
    """, (PARENT_TEAM_ID,)).fetchall()

    # Sub-team snapshot deltas (today vs compare_date)
    subteam_deltas = {}
    sub_snaps_today = conn.execute("""
        SELECT ds.team_id, t.name, ds.raised, ds.members_count
        FROM daily_snapshots ds
        JOIN teams t ON ds.team_id=t.id
        WHERE ds.snapshot_date=? AND t.parent_id=?
    """, (today, PARENT_TEAM_ID)).fetchall()
    # For weekly, find the closest snapshot on or before compare_date per team
    sub_snaps_compare = conn.execute("""
        SELECT ds.team_id, t.name, ds.raised, ds.members_count
        FROM daily_snapshots ds
        JOIN teams t ON ds.team_id=t.id
        WHERE ds.snapshot_date=(
            SELECT MAX(ds2.snapshot_date) FROM daily_snapshots ds2
            WHERE ds2.team_id=ds.team_id AND ds2.snapshot_date<=?
        ) AND t.parent_id=?
    """, (compare_date, PARENT_TEAM_ID)).fetchall()

    compare_map = {r["team_id"]: dict(r) for r in sub_snaps_compare} if sub_snaps_compare else {}
    for row in sub_snaps_today:
        tid = row["team_id"]
        c = compare_map.get(tid, {})
        subteam_deltas[row["name"]] = {
            "raised_delta": (row["raised"] or 0) - (c.get("raised") or 0),
            "members_delta": (row["members_count"] or 0) - (c.get("members_count") or 0),
        }

    # Last scraped
    last_scraped = conn.execute("SELECT MAX(last_scraped) as ls FROM members").fetchone()["ls"]

    conn.close()

    # Compute deltas (per participant type when available, else total members)
    raised_delta = 0
    members_delta = 0
    riders_delta = 0
    challengers_delta = 0
    volunteers_delta = 0
    if snap_today and snap_compare:
        raised_delta = (snap_today["raised"] or 0) - (snap_compare["raised"] or 0)
        members_delta = (snap_today["members_count"] or 0) - (snap_compare["members_count"] or 0)
        # Only compute per-type deltas if the compare snapshot has the data
        # (columns were added mid-stream; older snapshots have 0)
        if (snap_compare["riders_count"] or 0) > 0:
            riders_delta = (snap_today["riders_count"] or 0) - (snap_compare["riders_count"] or 0)
            challengers_delta = (snap_today["challengers_count"] or 0) - (snap_compare["challengers_count"] or 0)
            volunteers_delta = (snap_today["volunteers_count"] or 0) - (snap_compare["volunteers_count"] or 0)

    # Campaign day
    now = datetime.now()
    campaign_day = max((now - CAMPAIGN_START).days, 0)
    days_to_ride = max((RIDE_DAY - now).days, 0)

    period_label = "weekly" if weekly else "daily"
    if weekly:
        week_start = (datetime.now() - timedelta(days=7)).strftime("%b %-d")
        week_end = datetime.now().strftime("%b %-d")
        date_str = f"Week of {week_start} — {week_end}, {now.year}"
    else:
        date_str = now.strftime("%A, %B %-d, %Y")

    return {
        "raised": parent["raised"] if parent else 0,
        "goal": parent["goal"] if parent else GOALS["funds"],
        "all_time": parent["all_time_raised"] if parent else 0,
        "riders": riders,
        "challengers": challengers,
        "volunteers": volunteers,
        "members_total": members_total,
        "high_rollers": high_rollers,
        "survivors": survivors,
        "first_year": first_year,
        "committed": commit_row["total"],
        "hr_committed": commit_row["hr"],
        "std_committed": commit_row["std"],
        "raised_delta": raised_delta,
        "members_delta": members_delta,
        "riders_delta": riders_delta,
        "challengers_delta": challengers_delta,
        "volunteers_delta": volunteers_delta,
        "teams": [dict(r) for r in team_rows],
        "subteam_deltas": subteam_deltas,
        "campaign_day": campaign_day,
        "days_to_ride": days_to_ride,
        "last_scraped": last_scraped,
        "date": date_str,
        "period": period_label,
    }


def build_html(data):
    """Build the HTML email body."""
    is_weekly = data.get("period") == "weekly"
    movers_label = "Top Movers This Week" if is_weekly else "Top Movers Today"
    delta_label = "this week" if is_weekly else "today"
    report_type = "Weekly Report" if is_weekly else "Daily Report"

    # Top movers (by raised delta)
    top_movers = sorted(
        [(name, d) for name, d in data["subteam_deltas"].items() if d["raised_delta"] > 0],
        key=lambda x: x[1]["raised_delta"],
        reverse=True
    )[:5 if is_weekly else 3]

    # Shorten sub-team names for display
    def short_name(name):
        return name.replace("Team Huntington Bank - ", "").replace("Credit, Collections, and Financial Recovery Group", "Credit, Collections, and FRG")

    # Card data
    cards = [
        {
            "label": "Funds Raised",
            "current": money(data["raised"]),
            "goal_val": data["goal"],
            "goal": money(data["goal"]),
            "pct": pct(data["raised"], data["goal"]),
            "delta": delta_str(data["raised_delta"], is_money=True),
            "chips": [
                ("Committed", money_short(data["committed"])),
                ("High Rollers", money_short(data["hr_committed"])),
                ("Standard", money_short(data["std_committed"])),
            ],
        },
        {
            "label": "Riders",
            "current": f"{data['riders']:,}",
            "goal_val": GOALS["riders"],
            "goal": f"{GOALS['riders']:,}",
            "pct": pct(data["riders"], GOALS["riders"]),
            "delta": delta_str(data["riders_delta"]),
            "chips": [
                ("Day", str(data["campaign_day"])),
                ("To Ride", f"{data['days_to_ride']}d"),
                ("1st Year", f"{data['first_year']:,}"),
            ],
        },
        {
            "label": "Challengers",
            "current": f"{data['challengers']:,}",
            "goal_val": GOALS["challengers"],
            "goal": f"{GOALS['challengers']:,}",
            "pct": pct(data["challengers"], GOALS["challengers"]),
            "delta": delta_str(data["challengers_delta"]),
            "chips": [
                ("Day", str(data["campaign_day"])),
                ("To Ride", f"{data['days_to_ride']}d"),
                ("Total", f"{data['members_total']:,}"),
            ],
        },
        {
            "label": "Volunteers",
            "current": f"{data['volunteers']:,}",
            "goal_val": GOALS["volunteers"],
            "goal": f"{GOALS['volunteers']:,}",
            "pct": pct(data["volunteers"], GOALS["volunteers"]),
            "delta": delta_str(data["volunteers_delta"]),
            "chips": [
                ("Day", str(data["campaign_day"])),
                ("To Ride", f"{data['days_to_ride']}d"),
                ("Total", f"{data['members_total']:,}"),
            ],
        },
    ]

    # Build card HTML
    def card_html(c):
        bar_color = "#44D62C" if c["pct"] >= 10 else "#6EF056"
        return f'''
        <td style="width:50%;padding:8px;vertical-align:top">
          <table cellpadding="0" cellspacing="0" border="0" width="100%"
                 style="background:#ffffff;border-radius:12px;border:1px solid #e8ece9;overflow:hidden">
            <tr><td style="padding:0"><div style="height:3px;background:linear-gradient(90deg,#00471F,#44D62C)"></div></td></tr>
            <tr><td style="padding:20px 20px 16px">
              <table cellpadding="0" cellspacing="0" border="0" width="100%">
                <tr>
                  <td style="font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#888;font-weight:600">{c["label"]}</td>
                  <td align="right" style="font-size:13px;font-weight:800;color:#00471F;background:rgba(68,214,44,0.1);padding:2px 8px;border-radius:12px">{c["pct"]:.1f}%</td>
                </tr>
              </table>
              <div style="font-size:36px;font-weight:800;color:#00471F;line-height:1.1;margin-top:8px">{c["current"]}</div>
              <div style="font-size:12px;color:#aaa;margin-top:4px">of <b style="color:#666">{c["goal"]}</b> goal {c["delta"]}</div>
              <!-- Progress bar -->
              <div style="margin-top:14px;height:10px;border-radius:5px;background:#e8ece9;overflow:hidden">
                <div style="height:100%;width:{c["pct"]:.1f}%;border-radius:5px;background:linear-gradient(90deg,#00471F,{bar_color})"></div>
              </div>
              <!-- Chips -->
              <table cellpadding="0" cellspacing="0" border="0" width="100%" style="margin-top:12px">
                <tr>
                  {"".join(f'<td style="text-align:center;padding:6px 2px;background:#f7f8f9;border-radius:6px"><div style="font-size:14px;font-weight:800;color:#00471F">{v}</div><div style="font-size:9px;color:#999;text-transform:uppercase;letter-spacing:0.3px;margin-top:1px">{l}</div></td>' for l, v in c["chips"])}
                </tr>
              </table>
            </td></tr>
          </table>
        </td>'''

    cards_grid = f'''
    <table cellpadding="0" cellspacing="0" border="0" width="100%">
      <tr>{card_html(cards[0])}{card_html(cards[1])}</tr>
      <tr><td colspan="2" style="height:8px"></td></tr>
      <tr>{card_html(cards[2])}{card_html(cards[3])}</tr>
    </table>'''

    # Daily movers section
    movers_html = ""
    if top_movers:
        mover_rows = ""
        for name, d in top_movers:
            mover_rows += f'''
            <tr>
              <td style="padding:6px 12px;font-size:13px;color:#333">{short_name(name)}</td>
              <td align="right" style="padding:6px 12px;font-size:13px;font-weight:700;color:#00471F">{delta_str(d["raised_delta"], is_money=True)}</td>
              <td align="right" style="padding:6px 12px;font-size:13px;color:#555">{delta_str(d["members_delta"])}</td>
            </tr>'''
        movers_html = f'''
        <div style="margin-top:24px">
          <div style="font-size:16px;font-weight:700;color:#00471F;margin-bottom:8px">{movers_label}</div>
          <table cellpadding="0" cellspacing="0" border="0" width="100%"
                 style="background:#fff;border:1px solid #e8ece9;border-radius:8px;overflow:hidden">
            <tr style="background:#f7f8f9">
              <th style="padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase;color:#888;font-weight:600">Sub-Team</th>
              <th style="padding:8px 12px;text-align:right;font-size:11px;text-transform:uppercase;color:#888;font-weight:600">Raised</th>
              <th style="padding:8px 12px;text-align:right;font-size:11px;text-transform:uppercase;color:#888;font-weight:600">Members</th>
            </tr>
            {mover_rows}
          </table>
        </div>'''

    # Participation by sub-team table
    team_rows_html = ""
    for t in data["teams"]:
        sn = short_name(t["name"])
        goals = GOALS_SUBTEAMS.get(sn, {})
        rider_goal = goals.get("riders", 0)
        fund_goal = goals.get("funds", 0)
        rider_pct = f"{t['riders']/rider_goal*100:.0f}%" if rider_goal else "—"
        fund_pct = f"{t['total_raised']/fund_goal*100:.0f}%" if fund_goal else "—"
        fund_goal_str = money_short(fund_goal) if fund_goal else "—"
        first_yr = t.get("first_year", 0)

        team_rows_html += f'''
        <tr style="border-bottom:1px solid #f0f0f0">
          <td style="padding:8px 10px;font-size:12px;color:#333;white-space:nowrap">{sn}</td>
          <td align="center" style="padding:8px 6px;font-size:12px;color:#333">{t["riders"]}</td>
          <td align="center" style="padding:8px 6px;font-size:12px;color:#333">{t["challengers"]}</td>
          <td align="center" style="padding:8px 6px;font-size:12px;color:#333">{t["volunteers"]}</td>
          <td align="center" style="padding:8px 6px;font-size:12px;color:#888">{first_yr}</td>
          <td align="center" style="padding:8px 6px;font-size:12px;color:#333;font-weight:600">{t["total"]}</td>
          <td align="right" style="padding:8px 6px;font-size:12px;color:#00471F;font-weight:600">{money_short(t["total_raised"])}</td>
          <td align="right" style="padding:8px 6px;font-size:12px;color:#888">{fund_goal_str}</td>
          <td align="right" style="padding:8px 6px;font-size:12px;color:#00471F;font-weight:600">{money_short(t["total_committed"])}</td>
          <td align="center" style="padding:8px 6px;font-size:11px;color:#888">{fund_pct}</td>
        </tr>'''

    subteam_table = f'''
    <div style="margin-top:24px">
      <div style="font-size:16px;font-weight:700;color:#00471F;margin-bottom:8px">Participation by Sub-Team</div>
      <table cellpadding="0" cellspacing="0" border="0" width="100%"
             style="background:#fff;border:1px solid #e8ece9;border-radius:8px;overflow:hidden;border-collapse:collapse">
        <tr style="background:#f7f8f9">
          <th style="padding:8px 10px;text-align:left;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Sub-Team</th>
          <th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Riders</th>
          <th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Chall</th>
          <th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Vol</th>
          <th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">1st Yr</th>
          <th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Total</th>
          <th style="padding:8px 6px;text-align:right;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Raised</th>
          <th style="padding:8px 6px;text-align:right;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Goal</th>
          <th style="padding:8px 6px;text-align:right;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">Committed</th>
          <th style="padding:8px 6px;text-align:center;font-size:10px;text-transform:uppercase;color:#888;font-weight:600">% Goal</th>
        </tr>
        {team_rows_html}
      </table>
    </div>'''

    # Assemble full email
    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
  <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f4f5f7">
    <tr><td align="center" style="padding:24px 16px">
      <table cellpadding="0" cellspacing="0" border="0" width="640" style="max-width:640px">

        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#00471F,#0E1411);border-radius:12px 12px 0 0;padding:24px 28px;text-align:center">
          <div style="font-size:22px;font-weight:800;color:#44D62C;margin-bottom:4px">Team Huntington {report_type}</div>
          <div style="font-size:13px;color:rgba(255,255,255,0.6)">{data["date"]} &middot; Day {data["campaign_day"]} of Campaign</div>
        </td></tr>

        <!-- Summary bar -->
        <tr><td style="background:#00471F;padding:12px 28px">
          <table cellpadding="0" cellspacing="0" border="0" width="100%">
            <tr>
              <td align="center" style="padding:4px 8px">
                <div style="font-size:20px;font-weight:800;color:#44D62C">{money(data["raised"])}</div>
                <div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">Raised {delta_str(data["raised_delta"], is_money=True)}</div>
              </td>
              <td align="center" style="padding:4px 8px">
                <div style="font-size:20px;font-weight:800;color:rgba(255,255,255,0.8)">{money(data["goal"])}</div>
                <div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">Goal</div>
              </td>
              <td align="center" style="padding:4px 8px">
                <div style="font-size:20px;font-weight:800;color:#44D62C">{data["members_total"]:,}</div>
                <div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">Members {delta_str(data["members_delta"])}</div>
              </td>
              <td align="center" style="padding:4px 8px">
                <div style="font-size:20px;font-weight:800;color:#44D62C">{data["high_rollers"]}</div>
                <div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">High Rollers</div>
              </td>
              <td align="center" style="padding:4px 8px">
                <div style="font-size:20px;font-weight:800;color:#44D62C">{data["survivors"]}</div>
                <div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">Survivors</div>
              </td>
              <td align="center" style="padding:4px 8px">
                <div style="font-size:20px;font-weight:800;color:#44D62C">{data["first_year"]}</div>
                <div style="font-size:10px;color:rgba(255,255,255,0.5);text-transform:uppercase">1st Year</div>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Cards -->
        <tr><td style="background:#f4f5f7;padding:16px 12px 0">
          {cards_grid}
        </td></tr>

        <!-- Movers + Sub-team table -->
        <tr><td style="background:#f4f5f7;padding:0 16px 24px">
          {movers_html}
          {subteam_table}
        </td></tr>


      </table>
    </td></tr>
  </table>
</body>
</html>'''

    return html


# ---------------------------------------------------------------------------
# Image rendering (Pillow)
# ---------------------------------------------------------------------------

# Fonts
_FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Colors
C_GREEN = (68, 214, 44)
C_FOREST = (0, 71, 31)
C_BLACK = (14, 20, 17)
C_WHITE = (255, 255, 255)
C_GRAY = (244, 245, 247)
C_BORDER = (232, 236, 233)
C_LABEL = (136, 136, 136)
C_CHIP_BG = (247, 248, 249)
C_BAR_BG = (232, 236, 233)
C_TEXT = (51, 51, 51)


def _font(size, bold=False):
    return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, size)


def _round_rect(draw, xy, radius, fill=None, outline=None, width=1):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _draw_progress_bar(draw, x, y, w, h, pct_val, radius=5):
    """Draw a gradient-style progress bar."""
    _round_rect(draw, (x, y, x + w, y + h), radius, fill=C_BAR_BG)
    fill_w = max(int(w * min(pct_val, 100) / 100), 0)
    if fill_w > 0:
        _round_rect(draw, (x, y, x + fill_w, y + h), radius, fill=C_FOREST)
        # Green tip
        if fill_w > 4:
            tip_x = x + fill_w - min(fill_w // 2, 30)
            draw.rounded_rectangle((tip_x, y, x + fill_w, y + h), radius=radius, fill=C_GREEN)


def _draw_card(draw, x, y, w, h, card_data):
    """Draw a single infographic card at (x, y)."""
    # Card background
    _round_rect(draw, (x, y, x + w, y + h), 12, fill=C_WHITE, outline=C_BORDER)
    # Top accent bar
    draw.rectangle((x + 1, y + 1, x + w - 1, y + 4), fill=C_FOREST)
    # Green tip on right half of accent
    draw.rectangle((x + w // 2, y + 1, x + w - 1, y + 4), fill=C_GREEN)

    pad = 20
    cx, cy = x + pad, y + 16

    # Label + percentage
    f_label = _font(11, bold=True)
    draw.text((cx, cy), card_data["label"].upper(), fill=C_LABEL, font=f_label)

    pct_text = f"{card_data['pct']:.1f}%"
    f_pct = _font(13, bold=True)
    pct_w = draw.textlength(pct_text, font=f_pct)
    pct_x = x + w - pad - pct_w - 12
    _round_rect(draw, (pct_x, cy - 2, pct_x + pct_w + 12, cy + 18), 10, fill=(235, 245, 235))
    draw.text((pct_x + 6, cy), pct_text, fill=C_FOREST, font=f_pct)

    cy += 30

    # Big number
    f_big = _font(34, bold=True)
    draw.text((cx, cy), card_data["current"], fill=C_FOREST, font=f_big)
    cy += 42

    # Goal text
    f_goal = _font(12)
    f_goal_b = _font(12, bold=True)
    draw.text((cx, cy), "of ", fill=C_LABEL, font=f_goal)
    of_w = draw.textlength("of ", font=f_goal)
    draw.text((cx + of_w, cy), card_data["goal"], fill=C_TEXT, font=f_goal_b)
    goal_w = draw.textlength(card_data["goal"], font=f_goal_b)
    draw.text((cx + of_w + goal_w, cy), " goal", fill=C_LABEL, font=f_goal)

    # Delta (if present)
    if card_data.get("delta_text"):
        delta_x = cx + of_w + goal_w + draw.textlength(" goal ", font=f_goal)
        delta_color = C_GREEN if card_data.get("delta_positive", True) else (231, 76, 60)
        draw.text((delta_x, cy), card_data["delta_text"], fill=delta_color, font=_font(12, bold=True))
    cy += 22

    # Progress bar
    bar_w = w - 2 * pad
    _draw_progress_bar(draw, cx, cy, bar_w, 10, card_data["pct"])
    cy += 22

    # Chips
    chip_w = (bar_w - 8) // 3
    for i, (label, val) in enumerate(card_data["chips"]):
        chip_x = cx + i * (chip_w + 4)
        _round_rect(draw, (chip_x, cy, chip_x + chip_w, cy + 36), 6, fill=C_CHIP_BG)
        f_cv = _font(13, bold=True)
        f_cl = _font(8, bold=True)
        # Center value
        vw = draw.textlength(val, font=f_cv)
        draw.text((chip_x + (chip_w - vw) / 2, cy + 4), val, fill=C_FOREST, font=f_cv)
        # Center label
        lw = draw.textlength(label.upper(), font=f_cl)
        draw.text((chip_x + (chip_w - lw) / 2, cy + 22), label.upper(), fill=C_LABEL, font=f_cl)


def _draw_subteam_table(draw, x, y, w, teams, short_name_fn):
    """Draw the participation by sub-team table. Returns height used."""
    f_title = _font(15, bold=True)
    draw.text((x, y), "Participation by Sub-Team", fill=C_FOREST, font=f_title)
    y += 26

    # Column widths — table_w is ~640px (680 - 2*20 pad)
    col_name = 185
    col_num = 38
    col_money = 52
    col_pct = 42
    cols = [col_name, col_num, col_num, col_num, col_num, col_num, col_money, col_money, col_money, col_pct]
    headers = ["SUB-TEAM", "RIDERS", "CHALL", "VOL", "1ST YR", "TOTAL", "RAISED", "GOAL", "COMMIT", "% GOAL"]

    row_h = 24
    f_hdr = _font(9, bold=True)
    f_cell = _font(10)
    f_cell_b = _font(10, bold=True)

    # Header row
    _round_rect(draw, (x, y, x + w, y + row_h), 0, fill=C_CHIP_BG)
    cx = x + 8
    for i, hdr in enumerate(headers):
        draw.text((cx, y + 6), hdr, fill=C_LABEL, font=f_hdr)
        cx += cols[i]
    y += row_h

    # Data rows
    for t in teams:
        sn = short_name_fn(t["name"])
        goals = GOALS_SUBTEAMS.get(sn, {})
        fund_goal = goals.get("funds", 0)
        fund_pct = f"{t['total_raised']/fund_goal*100:.0f}%" if fund_goal else "—"

        fund_goal_str = money_short(fund_goal) if fund_goal else "—"
        first_yr = str(t.get("first_year", 0))

        # Alternating bg
        row_vals = [sn, str(t["riders"]), str(t["challengers"]), str(t["volunteers"]),
                    first_yr, str(t["total"]), money_short(t["total_raised"]),
                    fund_goal_str, money_short(t["total_committed"]), fund_pct]

        cx = x + 8
        for i, val in enumerate(row_vals):
            font = f_cell_b if i in (5, 6, 8) else f_cell
            color = C_FOREST if i in (6, 8) else (C_LABEL if i in (4, 7) else C_TEXT)
            # Truncate name column if it overflows
            if i == 0:
                max_w = cols[0] - 6
                while draw.textlength(val, font=font) > max_w and len(val) > 4:
                    val = val[:-1]
                if val != row_vals[0]:
                    val = val.rstrip() + "…"
            draw.text((cx, y + 5), val, fill=color, font=font)
            cx += cols[i]

        # Row separator
        draw.line((x, y + row_h - 1, x + w, y + row_h - 1), fill=C_BORDER, width=1)
        y += row_h

    return y


def _draw_movers(draw, x, y, w, subteam_deltas, short_name_fn, weekly=False):
    """Draw top movers table. Returns new y."""
    top_movers = sorted(
        [(name, d) for name, d in subteam_deltas.items() if d["raised_delta"] > 0],
        key=lambda x_: x_[1]["raised_delta"], reverse=True
    )[:5 if weekly else 3]
    if not top_movers:
        return y

    label = "Top Movers This Week" if weekly else "Top Movers Today"
    f_title = _font(15, bold=True)
    draw.text((x, y), label, fill=C_FOREST, font=f_title)
    y += 26

    f_hdr = _font(9, bold=True)
    f_cell = _font(11)
    f_cell_b = _font(11, bold=True)
    row_h = 26

    # Header
    _round_rect(draw, (x, y, x + w, y + row_h), 0, fill=C_CHIP_BG)
    draw.text((x + 8, y + 6), "SUB-TEAM", fill=C_LABEL, font=f_hdr)
    draw.text((x + 300, y + 6), "RAISED", fill=C_LABEL, font=f_hdr)
    draw.text((x + 420, y + 6), "MEMBERS", fill=C_LABEL, font=f_hdr)
    y += row_h

    for name, d in top_movers:
        sn = short_name_fn(name)
        raised_txt = f"+{money_short(d['raised_delta'])}"
        members_txt = f"+{d['members_delta']}" if d["members_delta"] > 0 else str(d["members_delta"])

        draw.text((x + 8, y + 5), sn, fill=C_TEXT, font=f_cell)
        draw.text((x + 300, y + 5), raised_txt, fill=C_GREEN, font=f_cell_b)
        draw.text((x + 420, y + 5), members_txt, fill=C_TEXT, font=f_cell)
        draw.line((x, y + row_h - 1, x + w, y + row_h - 1), fill=C_BORDER, width=1)
        y += row_h

    return y + 16


def build_image(data):
    """Render the report as a JPEG image using Pillow."""

    def short_name(name):
        return name.replace("Team Huntington Bank - ", "").replace("Credit, Collections, and Financial Recovery Group", "Credit, Collections, and FRG")

    # Prepare card data
    def _delta_text(val, is_money=False):
        if val > 0:
            return ("+" + (money_short(val) if is_money else f"{val:,}"), True)
        elif val < 0:
            return ("-" + (money_short(abs(val)) if is_money else f"{abs(val):,}"), False)
        return ("", True)

    dt_raised = _delta_text(data["raised_delta"], is_money=True)
    dt_riders = _delta_text(data["riders_delta"])
    dt_challengers = _delta_text(data["challengers_delta"])
    dt_volunteers = _delta_text(data["volunteers_delta"])

    cards = [
        {
            "label": "Funds Raised",
            "current": money(data["raised"]),
            "goal": money(data["goal"]),
            "pct": pct(data["raised"], data["goal"]),
            "delta_text": dt_raised[0], "delta_positive": dt_raised[1],
            "chips": [("Committed", money_short(data["committed"])),
                      ("High Rollers", money_short(data["hr_committed"])),
                      ("Standard", money_short(data["std_committed"]))],
        },
        {
            "label": "Riders",
            "current": f"{data['riders']:,}",
            "goal": f"{GOALS['riders']:,}",
            "pct": pct(data["riders"], GOALS["riders"]),
            "delta_text": dt_riders[0], "delta_positive": dt_riders[1],
            "chips": [("Day", str(data["campaign_day"])),
                      ("To Ride", f"{data['days_to_ride']}d"),
                      ("1st Year", f"{data['first_year']:,}")],
        },
        {
            "label": "Challengers",
            "current": f"{data['challengers']:,}",
            "goal": f"{GOALS['challengers']:,}",
            "pct": pct(data["challengers"], GOALS["challengers"]),
            "delta_text": dt_challengers[0], "delta_positive": dt_challengers[1],
            "chips": [("Day", str(data["campaign_day"])),
                      ("To Ride", f"{data['days_to_ride']}d"),
                      ("Total", f"{data['members_total']:,}")],
        },
        {
            "label": "Volunteers",
            "current": f"{data['volunteers']:,}",
            "goal": f"{GOALS['volunteers']:,}",
            "pct": pct(data["volunteers"], GOALS["volunteers"]),
            "delta_text": dt_volunteers[0], "delta_positive": dt_volunteers[1],
            "chips": [("Day", str(data["campaign_day"])),
                      ("To Ride", f"{data['days_to_ride']}d"),
                      ("Total", f"{data['members_total']:,}")],
        },
    ]

    # Layout
    IMG_W = 680
    CARD_W = 310
    CARD_H = 180
    GAP = 12
    PAD = 20

    # Calculate total height
    # Header: 70, summary bar: 50, cards: 2 rows, movers: ~120, subteam table: ~400
    is_weekly_img = data.get("period") == "weekly"
    n_movers = min(5 if is_weekly_img else 3, sum(1 for d in data["subteam_deltas"].values() if d["raised_delta"] > 0))
    n_teams = len(data["teams"])
    table_h = 26 + 24 + n_teams * 24 + 20
    movers_h = 26 + 26 + n_movers * 26 + 16 if n_movers > 0 else 0
    IMG_H = 70 + 50 + PAD + (CARD_H + GAP) * 2 + movers_h + table_h + PAD * 2

    img = Image.new("RGB", (IMG_W, IMG_H), C_GRAY)
    draw = ImageDraw.Draw(img)

    # Header background
    draw.rectangle((0, 0, IMG_W, 70), fill=C_BLACK)
    f_header = _font(20, bold=True)
    f_sub = _font(12)
    report_type = "Weekly Report" if data.get("period") == "weekly" else "Daily Report"
    title = f"Team Huntington {report_type}"
    tw = draw.textlength(title, font=f_header)
    draw.text(((IMG_W - tw) / 2, 14), title, fill=C_GREEN, font=f_header)
    sub = f"{data['date']}  ·  Day {data['campaign_day']} of Campaign"
    sw = draw.textlength(sub, font=f_sub)
    draw.text(((IMG_W - sw) / 2, 42), sub, fill=(255, 255, 255, 150), font=f_sub)

    # Summary bar
    bar_y = 70
    draw.rectangle((0, bar_y, IMG_W, bar_y + 50), fill=C_FOREST)
    f_sv = _font(18, bold=True)
    f_sl = _font(9, bold=True)
    summary_items = [
        (money(data["raised"]), "RAISED"),
        (money(data["goal"]), "GOAL"),
        (f"{data['members_total']:,}", "MEMBERS"),
        (str(data["high_rollers"]), "HIGH ROLLERS"),
        (str(data["survivors"]), "SURVIVORS"),
        (str(data["first_year"]), "1ST YEAR"),
    ]
    col_w = IMG_W // len(summary_items)
    for i, (val, label) in enumerate(summary_items):
        cx = i * col_w + col_w // 2
        vw = draw.textlength(val, font=f_sv)
        draw.text((cx - vw / 2, bar_y + 6), val, fill=C_GREEN, font=f_sv)
        lw = draw.textlength(label, font=f_sl)
        draw.text((cx - lw / 2, bar_y + 30), label, fill=(255, 255, 255, 130), font=f_sl)

    # Cards 2x2
    cards_y = bar_y + 50 + PAD
    card_x0 = (IMG_W - CARD_W * 2 - GAP) // 2
    positions = [
        (card_x0, cards_y),
        (card_x0 + CARD_W + GAP, cards_y),
        (card_x0, cards_y + CARD_H + GAP),
        (card_x0 + CARD_W + GAP, cards_y + CARD_H + GAP),
    ]
    for pos, card in zip(positions, cards):
        _draw_card(draw, pos[0], pos[1], CARD_W, CARD_H, card)

    # Movers + Table
    content_y = cards_y + (CARD_H + GAP) * 2 + 8
    table_w = IMG_W - PAD * 2
    is_weekly = data.get("period") == "weekly"

    content_y = _draw_movers(draw, PAD, content_y, table_w, data["subteam_deltas"], short_name, weekly=is_weekly)
    _draw_subteam_table(draw, PAD, content_y, table_w, data["teams"], short_name)

    # Save as PNG (lossless, sharp text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def send_email(html, to_addr, image_bytes=None, weekly=False):
    """Send the HTML email via Gmail SMTP."""
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        print("ERROR: GMAIL_APP_PASSWORD not set.")
        print("Set it: export GMAIL_APP_PASSWORD=<your-app-password>")
        sys.exit(1)

    today_str = datetime.now().strftime("%b %-d")
    if weekly:
        week_start = (datetime.now() - timedelta(days=7)).strftime("%b %-d")
        subject = f"Pelotonia Weekly Report — {week_start} to {today_str}"
    else:
        subject = f"Pelotonia Daily Report — {today_str}"

    msg = MIMEMultipart("mixed")
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Reply-To"] = SENDER_EMAIL

    # HTML + plain text alternative part
    alt = MIMEMultipart("alternative")
    plain = (
        f"Team Huntington Dashboard — {today_str}\n\n"
        f"View full dashboard: {os.environ.get('DASHBOARD_URL', '')}\n"
    )
    alt.attach(MIMEText(plain, "plain", "utf-8"))
    alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)

    # Attach JPEG image
    if image_bytes:
        today_file = datetime.now().strftime("%Y-%m-%d")
        img_part = MIMEImage(image_bytes, _subtype="png")
        img_part.add_header(
            "Content-Disposition", "attachment",
            filename=f"pelotonia-dashboard-{today_file}.png",
        )
        msg.attach(img_part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, password)
        server.sendmail(SENDER_EMAIL, [to_addr], msg.as_string())

    print(f"Sent to {to_addr}")


def main():
    parser = argparse.ArgumentParser(description="Pelotonia daily/weekly email report")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true", help="Preview HTML (don't send)")
    mode.add_argument("--send", action="store_true", help="Send the email")
    parser.add_argument("--weekly", action="store_true", help="Weekly report (7-day deltas instead of daily)")
    parser.add_argument("--to", default=DEFAULT_TO, help=f"Recipient (default: {DEFAULT_TO})")
    parser.add_argument("--output", "-o", help="Save HTML to file (with --preview)")
    args = parser.parse_args()

    label = "weekly" if args.weekly else "daily"
    print(f"Gathering {label} data...")
    data = gather_data(weekly=args.weekly)
    html = build_html(data)
    print("Rendering image...")
    image_bytes = build_image(data)

    if args.preview:
        if args.output:
            Path(args.output).write_text(html, encoding="utf-8")
            img_path = Path(args.output).with_suffix(".png")
            img_path.write_bytes(image_bytes)
            print(f"Saved to {args.output} + {img_path}")
        else:
            print(html)
    elif args.send:
        send_email(html, args.to, image_bytes, weekly=args.weekly)


if __name__ == "__main__":
    main()
