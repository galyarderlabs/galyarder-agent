"""
Session Insights Engine for G-Agent.

Analyzes historical session data from the SQLite state database to produce
comprehensive usage insights — token consumption, cost estimates, tool usage
patterns, activity trends, model/platform breakdowns, and session metrics.
"""

import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from g_agent.session.sqlite_store import SessionSQLiteStore


def _parse_iso_timestamp(value: str | None) -> float | None:
    """Parse an ISO timestamp into epoch seconds."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _provider_from_model(model: str | None) -> str:
    """Infer a provider bucket from a recorded model name."""
    text = str(model or "").strip()
    if not text:
        return "unknown"
    if "/" in text:
        provider = text.split("/", 1)[0].strip()
        return provider or "unknown"
    if ":" in text:
        provider = text.split(":", 1)[0].strip()
        return provider or "unknown"
    return text


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    hours = seconds / 3600
    return f"{hours:.1f}h"


def _bar_chart(values: list[int], max_width: int = 20) -> list[str]:
    """Create simple horizontal bar chart strings from values."""
    peak = max(values) if values else 1
    if peak == 0:
        return ["" for _ in values]
    return ["█" * max(1, int(v / peak * max_width)) if v > 0 else "" for v in values]


class InsightsEngine:
    """
    Analyzes session history and produces usage insights.

    Works directly with a SessionSQLiteStore instance to query session and message data,
    and parses metrics/events.jsonl for advanced provider/failed call insights.
    """

    def __init__(self, db: SessionSQLiteStore, workspace: Path | None = None):
        """
        Initialize with a SessionSQLiteStore instance.

        Args:
            db: A SessionSQLiteStore instance
            workspace: The path to the G-Agent workspace directory
        """
        self.db = db
        self._conn = db._conn
        self.workspace = workspace

    def generate(self, days: int = 30, source: str | None = None) -> dict[str, Any]:
        """
        Generate a complete insights report.

        Args:
            days: Number of days to look back (default: 30)
            source: Optional filter by source channel

        Returns:
            Report with all computed insights.
        """
        cutoff = time.time() - (days * 86400)

        # Gather raw data
        sessions = self._get_sessions(cutoff, source)
        tool_usage, skill_usage = self._get_tool_and_skill_usage(cutoff, source)
        message_stats = self._get_message_stats(cutoff, source)
        provider_stats, failed_calls = self._get_metrics_events(days, source)

        if not sessions:
            return {
                "days": days,
                "source_filter": source,
                "empty": True,
                "overview": {},
                "models": [],
                "platforms": [],
                "tools": [],
                "skills": {},
                "providers": [],
                "failed_calls": [],
                "activity": {},
                "top_sessions": [],
            }

        # Compute insights
        overview = self._compute_overview(sessions, message_stats)
        models = self._compute_model_breakdown(sessions)
        platforms = self._compute_platform_breakdown(sessions)
        tools = self._compute_tool_breakdown(tool_usage)
        skills = self._compute_skill_breakdown(skill_usage)
        activity = self._compute_activity_patterns(sessions)
        top_sessions = self._compute_top_sessions(sessions)

        return {
            "days": days,
            "source_filter": source,
            "empty": False,
            "generated_at": time.time(),
            "overview": overview,
            "models": models,
            "platforms": platforms,
            "tools": tools,
            "skills": skills,
            "providers": provider_stats,
            "failed_calls": failed_calls,
            "activity": activity,
            "top_sessions": top_sessions,
        }

    _SESSION_COLS = (
        "s.id, s.channel, "
        "COALESCE((SELECT m.model FROM messages m "
        "WHERE m.session_id = s.id AND m.model IS NOT NULL AND m.model != '' "
        "ORDER BY m.created_at DESC, m.id DESC LIMIT 1), 'unknown') AS model, "
        "s.created_at, s.updated_at, s.message_count, s.tool_call_count, "
        "s.input_tokens, s.output_tokens, s.input_cost, s.output_cost, s.total_cost"
    )

    _GET_SESSIONS_WITH_SOURCE = (
        f"SELECT {_SESSION_COLS} FROM sessions s"
        " WHERE s.created_at >= ? AND s.channel = ?"
        " ORDER BY s.created_at DESC"
    )
    _GET_SESSIONS_ALL = (
        f"SELECT {_SESSION_COLS} FROM sessions s"
        " WHERE s.created_at >= ?"
        " ORDER BY s.created_at DESC"
    )

    def _get_sessions(self, cutoff: float, source: str | None = None) -> list[dict[str, Any]]:
        """Fetch sessions within the time window."""
        try:
            if source:
                cursor = self._conn.execute(self._GET_SESSIONS_WITH_SOURCE, (cutoff, source))
            else:
                cursor = self._conn.execute(self._GET_SESSIONS_ALL, (cutoff,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception:
            return []

    def _get_metrics_events(
        self, days: int, source: str | None = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Parse events.jsonl to extract provider stats and failed calls."""
        if not self.workspace:
            return [], []

        events_path = self.workspace / "state" / "metrics" / "events.jsonl"
        if not events_path.exists():
            return [], []

        provider_data: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"calls": 0, "errors": 0, "latency_sum": 0.0}
        )
        failed_calls: list[dict[str, Any]] = []
        cutoff_ts = datetime.now(timezone.utc).timestamp() - (days * 86400)

        try:
            with events_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(record, dict):
                        continue

                    ts_str = str(record.get("ts") or "")
                    ts = _parse_iso_timestamp(ts_str)
                    if ts is None or ts < cutoff_ts:
                        continue

                    event_type = record.get("type")
                    if event_type == "llm_call":
                        model = str(record.get("model") or "unknown")
                        provider = _provider_from_model(model)
                        stats = provider_data[provider]
                        stats["calls"] = int(stats["calls"]) + 1
                        stats["latency_sum"] = float(stats["latency_sum"]) + float(
                            record.get("latency_ms") or 0.0
                        )

                        if not record.get("success", True):
                            stats["errors"] = int(stats["errors"]) + 1
                            failed_calls.append(
                                {
                                    "time": ts_str,
                                    "type": "llm",
                                    "target": model,
                                    "error": str(record.get("error") or "Unknown error"),
                                }
                            )
                    elif event_type == "tool_call" and not record.get("success", True):
                        failed_calls.append(
                            {
                                "time": ts_str,
                                "type": "tool",
                                "target": str(record.get("tool") or "unknown"),
                                "error": str(record.get("error") or "Unknown error"),
                            }
                        )

            provider_list: list[dict[str, Any]] = []
            for name, stats in provider_data.items():
                calls = int(stats["calls"])
                avg_latency = (float(stats["latency_sum"]) / calls) if calls else 0.0
                provider_list.append(
                    {
                        "provider": name,
                        "calls": calls,
                        "errors": int(stats["errors"]),
                        "avg_latency_ms": avg_latency,
                    }
                )

            provider_list.sort(key=lambda x: x["calls"], reverse=True)
            failed_calls = list(reversed(failed_calls))[:10]

            return provider_list, failed_calls
        except Exception:
            return [], []

    def _get_tool_and_skill_usage(
        self, cutoff: float, source: str | None = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Get tool call counts and skill usage from messages."""
        tool_calls_counts = Counter()
        skill_counts: dict[str, dict[str, Any]] = {}
        found_structured_tool_rows = False

        def _track_skill(name: str, args: Any, ts: float | None) -> None:
            if name not in {"skill_view", "skill_manage"}:
                return
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    return
            if not isinstance(args, dict):
                return

            skill_name = args.get("name")
            if not isinstance(skill_name, str) or not skill_name.strip():
                return

            skill_key = skill_name.strip()
            entry = skill_counts.setdefault(
                skill_key,
                {
                    "skill": skill_key,
                    "view_count": 0,
                    "manage_count": 0,
                    "last_used_at": None,
                },
            )
            if name == "skill_view":
                entry["view_count"] += 1
            else:
                entry["manage_count"] += 1

            if ts is not None and (entry["last_used_at"] is None or ts > entry["last_used_at"]):
                entry["last_used_at"] = ts

        try:
            if source:
                cursor = self._conn.execute(
                    """SELECT t.tool_name, t.arguments_json, t.created_at
                       FROM tool_calls t
                       JOIN sessions s ON s.id = t.session_id
                       WHERE s.created_at >= ? AND s.channel = ?""",
                    (cutoff, source),
                )
            else:
                cursor = self._conn.execute(
                    """SELECT t.tool_name, t.arguments_json, t.created_at
                       FROM tool_calls t
                       JOIN sessions s ON s.id = t.session_id
                       WHERE s.created_at >= ?""",
                    (cutoff,),
                )

            rows = cursor.fetchall()
            if rows:
                for row in rows:
                    name = str(row["tool_name"] or "").strip()
                    if not name or name == "unknown":
                        continue
                    found_structured_tool_rows = True
                    tool_calls_counts[name] += 1
                    _track_skill(name, row["arguments_json"], row["created_at"])
        except Exception:
            pass

        if found_structured_tool_rows:
            tool_res = [
                {"tool_name": name, "count": count}
                for name, count in tool_calls_counts.most_common()
            ]
            return tool_res, list(skill_counts.values())

        # Fallback to messages metadata
        try:
            if source:
                cursor = self._conn.execute(
                    """SELECT m.metadata_json, m.created_at
                       FROM messages m
                       JOIN sessions s ON s.id = m.session_id
                       WHERE s.created_at >= ? AND s.channel = ?
                         AND m.role = 'assistant' AND m.metadata_json IS NOT NULL""",
                    (cutoff, source),
                )
            else:
                cursor = self._conn.execute(
                    """SELECT m.metadata_json, m.created_at
                       FROM messages m
                       JOIN sessions s ON s.id = m.session_id
                       WHERE s.created_at >= ?
                         AND m.role = 'assistant' AND m.metadata_json IS NOT NULL""",
                    (cutoff,),
                )

            for row in cursor.fetchall():
                try:
                    meta = json.loads(row["metadata_json"])
                    if not isinstance(meta, dict):
                        continue
                    calls = meta.get("tool_calls")
                    if isinstance(calls, list):
                        for call in calls:
                            if not isinstance(call, dict):
                                continue
                            name = call.get("tool_name")
                            args = call.get("arguments_json") or call.get("arguments")
                            if not name:
                                func = call.get("function")
                                if isinstance(func, dict):
                                    name = func.get("name")
                                    if not args:
                                        args = func.get("arguments")
                            if name:
                                tool_name = str(name).strip()
                                if tool_name and tool_name != "unknown":
                                    tool_calls_counts[tool_name] += 1
                                    _track_skill(tool_name, args, row["created_at"])
                except (json.JSONDecodeError, TypeError, AttributeError):
                    continue
        except Exception:
            pass

        tool_res = [
            {"tool_name": name, "count": count}
            for name, count in tool_calls_counts.most_common()
        ]
        return tool_res, list(skill_counts.values())

    def _get_message_stats(self, cutoff: float, source: str | None = None) -> dict[str, Any]:
        """Get aggregate message statistics."""
        try:
            if source:
                cursor = self._conn.execute(
                    """SELECT
                         COUNT(*) as total_messages,
                         SUM(CASE WHEN m.role = 'user' THEN 1 ELSE 0 END) as user_messages,
                         SUM(CASE WHEN m.role = 'assistant' THEN 1 ELSE 0 END) as assistant_messages,
                         SUM(CASE WHEN m.role = 'tool' THEN 1 ELSE 0 END) as tool_messages
                       FROM messages m
                       JOIN sessions s ON s.id = m.session_id
                       WHERE s.created_at >= ? AND s.channel = ?""",
                    (cutoff, source),
                )
            else:
                cursor = self._conn.execute(
                    """SELECT
                         COUNT(*) as total_messages,
                         SUM(CASE WHEN m.role = 'user' THEN 1 ELSE 0 END) as user_messages,
                         SUM(CASE WHEN m.role = 'assistant' THEN 1 ELSE 0 END) as assistant_messages,
                         SUM(CASE WHEN m.role = 'tool' THEN 1 ELSE 0 END) as tool_messages
                       FROM messages m
                       JOIN sessions s ON s.id = m.session_id
                       WHERE s.created_at >= ?""",
                    (cutoff,),
                )
            row = cursor.fetchone()
            return dict(row) if row else {
                "total_messages": 0, "user_messages": 0,
                "assistant_messages": 0, "tool_messages": 0,
            }
        except Exception:
            return {
                "total_messages": 0, "user_messages": 0,
                "assistant_messages": 0, "tool_messages": 0,
            }

    def _compute_overview(
        self, sessions: list[dict[str, Any]], message_stats: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute high-level overview statistics."""
        total_input = sum(s.get("input_tokens") or 0 for s in sessions)
        total_output = sum(s.get("output_tokens") or 0 for s in sessions)
        total_tokens = total_input + total_output
        total_tool_calls = sum(s.get("tool_call_count") or 0 for s in sessions)
        total_messages = sum(s.get("message_count") or 0 for s in sessions)
        total_cost = sum(s.get("total_cost") or 0.0 for s in sessions)

        durations = []
        for s in sessions:
            start = s.get("created_at")
            end = s.get("updated_at")
            if start and end and end > start:
                durations.append(end - start)

        total_hours = sum(durations) / 3600 if durations else 0
        avg_duration = sum(durations) / len(durations) if durations else 0

        started_timestamps = [s["created_at"] for s in sessions if s.get("created_at")]
        date_range_start = min(started_timestamps) if started_timestamps else None
        date_range_end = max(started_timestamps) if started_timestamps else None

        return {
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "total_tool_calls": total_tool_calls,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_tokens,
            "estimated_cost": total_cost,
            "total_hours": total_hours,
            "avg_session_duration": avg_duration,
            "avg_messages_per_session": total_messages / len(sessions) if sessions else 0,
            "avg_tokens_per_session": total_tokens / len(sessions) if sessions else 0,
            "user_messages": message_stats.get("user_messages") or 0,
            "assistant_messages": message_stats.get("assistant_messages") or 0,
            "tool_messages": message_stats.get("tool_messages") or 0,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
        }

    def _compute_model_breakdown(self, sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Break down usage by model."""
        model_data = defaultdict(lambda: {
            "sessions": 0, "input_tokens": 0, "output_tokens": 0,
            "total_tokens": 0, "tool_calls": 0, "cost": 0.0,
        })

        for s in sessions:
            model = s.get("model") or "unknown"
            display_model = model.split("/")[-1] if "/" in model else model
            d = model_data[display_model]
            d["sessions"] += 1
            inp = s.get("input_tokens") or 0
            out = s.get("output_tokens") or 0
            d["input_tokens"] += inp
            d["output_tokens"] += out
            d["total_tokens"] += inp + out
            d["tool_calls"] += s.get("tool_call_count") or 0
            d["cost"] += s.get("total_cost") or 0.0

        result = [
            {"model": model, **data}
            for model, data in model_data.items()
        ]
        result.sort(key=lambda x: (x["total_tokens"], x["sessions"]), reverse=True)
        return result

    def _compute_platform_breakdown(
        self, sessions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Break down usage by platform/source channel."""
        platform_data = defaultdict(lambda: {
            "sessions": 0, "messages": 0, "input_tokens": 0,
            "output_tokens": 0, "total_tokens": 0, "tool_calls": 0,
        })

        for s in sessions:
            source = s.get("channel") or "unknown"
            d = platform_data[source]
            d["sessions"] += 1
            d["messages"] += s.get("message_count") or 0
            inp = s.get("input_tokens") or 0
            out = s.get("output_tokens") or 0
            d["input_tokens"] += inp
            d["output_tokens"] += out
            d["total_tokens"] += inp + out
            d["tool_calls"] += s.get("tool_call_count") or 0

        result = [
            {"platform": platform, **data}
            for platform, data in platform_data.items()
        ]
        result.sort(key=lambda x: x["sessions"], reverse=True)
        return result

    def _compute_tool_breakdown(
        self, tool_usage: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Process tool usage data into a ranked list with percentages."""
        total_calls = sum(t["count"] for t in tool_usage) if tool_usage else 0
        result = []
        for t in tool_usage:
            pct = (t["count"] / total_calls * 100) if total_calls else 0
            result.append({
                "tool": t["tool_name"],
                "count": t["count"],
                "percentage": pct,
            })
        return result

    def _compute_skill_breakdown(self, skill_usage: list[dict[str, Any]]) -> dict[str, Any]:
        """Process per-skill usage into summary + ranked list."""
        total_skill_loads = sum(s["view_count"] for s in skill_usage) if skill_usage else 0
        total_skill_edits = sum(s["manage_count"] for s in skill_usage) if skill_usage else 0
        total_skill_actions = total_skill_loads + total_skill_edits

        top_skills = []
        for skill in skill_usage:
            total_count = skill["view_count"] + skill["manage_count"]
            percentage = (total_count / total_skill_actions * 100) if total_skill_actions else 0
            top_skills.append({
                "skill": skill["skill"],
                "view_count": skill["view_count"],
                "manage_count": skill["manage_count"],
                "total_count": total_count,
                "percentage": percentage,
                "last_used_at": skill.get("last_used_at"),
            })

        top_skills.sort(
            key=lambda s: (
                s["total_count"],
                s["view_count"],
                s["manage_count"],
                s["last_used_at"] or 0,
                s["skill"],
            ),
            reverse=True,
        )

        return {
            "summary": {
                "total_skill_loads": total_skill_loads,
                "total_skill_edits": total_skill_edits,
                "total_skill_actions": total_skill_actions,
                "distinct_skills_used": len(skill_usage),
            },
            "top_skills": top_skills,
        }

    def _compute_activity_patterns(self, sessions: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze activity patterns by day of week and hour."""
        day_counts = Counter()
        hour_counts = Counter()
        daily_counts = Counter()

        for s in sessions:
            ts = s.get("created_at")
            if not ts:
                continue
            dt = datetime.fromtimestamp(ts)
            day_counts[dt.weekday()] += 1
            hour_counts[dt.hour] += 1
            daily_counts[dt.strftime("%Y-%m-%d")] += 1

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_breakdown = [
            {"day": day_names[i], "count": day_counts.get(i, 0)}
            for i in range(7)
        ]

        hour_breakdown = [
            {"hour": i, "count": hour_counts.get(i, 0)}
            for i in range(24)
        ]

        busiest_day = max(day_breakdown, key=lambda x: x["count"]) if day_breakdown else None
        busiest_hour = max(hour_breakdown, key=lambda x: x["count"]) if hour_breakdown else None
        active_days = len(daily_counts)

        if daily_counts:
            all_dates = sorted(daily_counts.keys())
            current_streak = 1
            max_streak = 1
            for i in range(1, len(all_dates)):
                d1 = datetime.strptime(all_dates[i - 1], "%Y-%m-%d")
                d2 = datetime.strptime(all_dates[i], "%Y-%m-%d")
                if (d2 - d1).days == 1:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 1
        else:
            max_streak = 0

        return {
            "by_day": day_breakdown,
            "by_hour": hour_breakdown,
            "busiest_day": busiest_day,
            "busiest_hour": busiest_hour,
            "active_days": active_days,
            "max_streak": max_streak,
        }

    def _compute_top_sessions(self, sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find notable sessions (longest, most messages, most tokens)."""
        top = []

        sessions_with_duration = [
            s for s in sessions
            if s.get("created_at") and s.get("updated_at")
        ]
        if sessions_with_duration:
            longest = max(
                sessions_with_duration,
                key=lambda s: (s["updated_at"] - s["created_at"]),
            )
            dur = longest["updated_at"] - longest["created_at"]
            top.append({
                "label": "Longest session",
                "session_id": longest["id"][:16] if longest.get("id") else "?",
                "value": _format_duration(dur),
                "date": datetime.fromtimestamp(longest["created_at"]).strftime("%b %d"),
            })

        if sessions:
            most_msgs = max(sessions, key=lambda s: s.get("message_count") or 0)
            if (most_msgs.get("message_count") or 0) > 0:
                top.append({
                    "label": "Most messages",
                    "session_id": most_msgs["id"][:16] if most_msgs.get("id") else "?",
                    "value": f"{most_msgs['message_count']} msgs",
                    "date": datetime.fromtimestamp(most_msgs["created_at"]).strftime("%b %d") if most_msgs.get("created_at") else "?",
                })

            most_tokens = max(
                sessions,
                key=lambda s: (s.get("input_tokens") or 0) + (s.get("output_tokens") or 0),
            )
            token_total = (most_tokens.get("input_tokens") or 0) + (most_tokens.get("output_tokens") or 0)
            if token_total > 0:
                top.append({
                    "label": "Most tokens",
                    "session_id": most_tokens["id"][:16] if most_tokens.get("id") else "?",
                    "value": f"{token_total:,} tokens",
                    "date": datetime.fromtimestamp(most_tokens["created_at"]).strftime("%b %d") if most_tokens.get("created_at") else "?",
                })

        return top

    def format_gateway(self, report: dict[str, Any]) -> str:
        """Format the insights report for messaging (markdown)."""
        if report.get("empty"):
            days = report.get("days", 30)
            return f"No sessions found in the last {days} days."

        lines = []
        o = report["overview"]
        days = report["days"]

        lines.append(f"📊 <b>G-Agent Insights</b> — Last {days} days\n")

        lines.append(f"<b>Sessions:</b> {o['total_sessions']} | <b>Messages:</b> {o['total_messages']:,} | <b>Tool calls:</b> {o['total_tool_calls']:,}")
        lines.append(f"<b>Tokens:</b> {o['total_tokens']:,} (in: {o['total_input_tokens']:,} / out: {o['total_output_tokens']:,})")
        if o["total_hours"] > 0:
            lines.append(f"<b>Active time:</b> ~{_format_duration(o['total_hours'] * 3600)} | <b>Avg session:</b> ~{_format_duration(o['avg_session_duration'])}")
        lines.append("")

        if report["models"]:
            lines.append("<b>🤖 Models:</b>")
            for m in report["models"][:5]:
                lines.append(f"  {m['model'][:25]} — {m['sessions']} sessions, {m['total_tokens']:,} tokens")
            lines.append("")

        if report.get("providers"):
            lines.append("<b>🏢 Providers:</b>")
            for p in report["providers"][:5]:
                err_str = f", {p['errors']} errs" if p['errors'] > 0 else ""
                lines.append(f"  {p['provider']} — {p['calls']:,} calls ({p['avg_latency_ms']:.0f}ms avg{err_str})")
            lines.append("")

        if len(report["platforms"]) > 1:
            lines.append("<b>📱 Channels:</b>")
            for p in report["platforms"]:
                lines.append(f"  {p['platform']} — {p['sessions']} sessions, {p['messages']:,} msgs")
            lines.append("")

        if report["tools"]:
            lines.append("<b>🔧 Top Tools:</b>")
            for t in report["tools"][:8]:
                lines.append(f"  {t['tool']} — {t['count']:,} calls ({t['percentage']:.1f}%)")
            lines.append("")

        skills = report.get("skills", {})
        if skills.get("top_skills"):
            lines.append("<b>🧠 Top Skills:</b>")
            for skill in skills["top_skills"][:5]:
                suffix = ""
                if skill.get("last_used_at"):
                    suffix = f" (used {datetime.fromtimestamp(skill['last_used_at']).strftime('%b %d')})"
                lines.append(f"  {skill['skill']} — {skill['view_count']:,} reads, {skill['manage_count']:,} edits{suffix}")
            lines.append("")

        if report.get("failed_calls"):
            lines.append("<b>⚠️ Recent Failed Calls:</b>")
            for f in report["failed_calls"][:3]:
                err = str(f["error"])[:60]
                dt = datetime.fromisoformat(f["time"].replace("Z", "+00:00")).strftime('%b %d %H:%M')
                lines.append(f"  [{dt}] {f['type'].upper()} {f['target']} - {err}")
            lines.append("")

        act = report.get("activity", {})
        if act.get("busiest_day") and act.get("busiest_hour"):
            hr = act["busiest_hour"]["hour"]
            ampm = "AM" if hr < 12 else "PM"
            display_hr = hr % 12 or 12
            lines.append(f"<b>📅 Busiest:</b> {act['busiest_day']['day']}s ({act['busiest_day']['count']} sessions), {display_hr}{ampm} ({act['busiest_hour']['count']} sessions)")
            if act.get("active_days"):
                lines.append(f"<b>Active days:</b> {act['active_days']}")
            if act.get("max_streak", 0) > 1:
                lines.append(f"<b>Best streak:</b> {act['max_streak']} consecutive days")

        return "\n".join(lines)
