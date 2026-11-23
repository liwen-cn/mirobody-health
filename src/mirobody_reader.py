"""Read standardized health observations directly from Mirobody's PostgreSQL view `v_observation`.

Zero extra Python dependencies: executes read-only SQL via `docker exec <container> psql`
(default for local MacBook / Mac mini OrbStack/Docker deployment) or host `psql` if configured.
"""

import json
import os
import re
import subprocess
from datetime import datetime


DEFAULT_PG_CONTAINER = os.environ.get("MIROBODY_PG_CONTAINER", "mirobody-pg-1")
DEFAULT_PG_USER = os.environ.get("MIROBODY_PG_USER", "holistic_user")
DEFAULT_PG_DB = os.environ.get("MIROBODY_PG_DB", "holistic_db")


def _run_psql_json(sql_query, pg_container=DEFAULT_PG_CONTAINER):
    """Execute a SQL query that returns a single JSON array string and parse it."""
    wrapped_sql = (
        "SET search_path TO theta_ai, public; "
        f"SELECT COALESCE(json_agg(t), '[]'::json) FROM ({sql_query}) t;"
    )
    cmd = [
        "docker", "exec", "-i", pg_container,
        "psql", "-U", DEFAULT_PG_USER, "-d", DEFAULT_PG_DB,
        "-t", "-A", "-q", "-c", wrapped_sql,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    # psql may output "SET\n[...]" because of SET search_path
    lines = [line.strip() for line in res.stdout.splitlines() if line.strip() and line.strip() != "SET"]
    raw_json = "\n".join(lines).strip()
    if not raw_json:
        return []
    return json.loads(raw_json)


def format_display_name(raw_name, fallback_uid=""):
    """Normalize Mirobody account names (e.g. '三 张' -> '张三') for display."""
    s = str(raw_name or "").strip()
    if not s:
        return f"用户 #{fallback_uid}" if fallback_uid else "健康档案"
    m = re.fullmatch(r"([\u4e00-\u9fff]{1,3})\s+([\u4e00-\u9fff]{1,2})", s)
    if m:
        return m.group(2) + m.group(1) if len(m.group(1)) >= len(m.group(2)) else m.group(1) + m.group(2)
    return s


def _calc_age(birth_str):
    """Compute integer age in years from a YYYY-MM-DD birth string, or None."""
    s = str(birth_str or "").strip()[:10]
    if not s:
        return None
    try:
        dob = datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None
    today = datetime.now().date()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age if 1 <= age <= 120 else None


def list_users_with_uploads(pg_container=DEFAULT_PG_CONTAINER, include_demo=False):
    """List users in Mirobody who have file-based observations, enriched with name, gender, and age."""
    where_extra = "" if include_demo else "AND o.source_ref LIKE 'th_files:web_uploads/%'"
    sql = f"""
        SELECT o.user_id,
               COALESCE(NULLIF(TRIM(c.nickname), ''), NULLIF(TRIM(u.name), ''), SPLIT_PART(u.email, '@', 1), '') AS raw_name,
               COALESCE(u.gender, 0) AS gender_code,
               COALESCE(u.birth, '') AS birth,
               COUNT(*) AS obs_count,
               COUNT(DISTINCT o.source_ref) AS file_count,
               MIN(o.local_date)::text AS first_date,
               MAX(o.local_date)::text AS last_date
          FROM v_observation o
          LEFT JOIN health_app_user u ON u.id::text = o.user_id
          LEFT JOIN LATERAL (
              SELECT nickname
                FROM care_circle_members
               WHERE user_id = u.id
                 AND deleted_at IS NULL
                 AND nickname IS NOT NULL
                 AND TRIM(nickname) <> ''
               ORDER BY id ASC
               LIMIT 1
          ) c ON TRUE
         WHERE o.source_kind = 'file'
           {where_extra}
         GROUP BY o.user_id, c.nickname, u.name, u.email, u.gender, u.birth
         ORDER BY o.user_id
    """
    rows = _run_psql_json(sql, pg_container=pg_container)
    for row in rows:
        uid = str(row.get("user_id") or "")
        g_code = row.get("gender_code")
        row["display_name"] = format_display_name(row.get("raw_name"), fallback_uid=uid)
        row["gender"] = "男" if g_code == 1 else ("女" if g_code == 2 else "")
        row["age"] = _calc_age(row.get("birth"))
    return rows


def fetch_user_observations(user_id="1", include_demo=False, pg_container=DEFAULT_PG_CONTAINER):
    """Fetch all standardized file-based observations for a user from `v_observation`.

    Note: strips any PII; only returns de-identified clinical observations and source file refs.
    """
    uid = str(user_id).replace("'", "''")
    where_extra = "" if include_demo else "AND source_ref LIKE 'th_files:web_uploads/%'"
    sql = f"""
        SELECT id,
               local_date::text AS report_date,
               name_text,
               COALESCE(display_zh, '') AS display_zh,
               COALESCE(display, '') AS display_en,
               value_text,
               value_num,
               COALESCE(value_canonical::text, '') AS value_canonical,
               COALESCE(unit_text, '') AS unit_text,
               COALESCE(unit_canonical, '') AS unit_canonical,
               COALESCE(ref_text, '') AS ref_text,
               ref_low,
               ref_high,
               COALESCE(flag_text, '') AS flag_text,
               COALESCE(code, '') AS loinc_code,
               COALESCE(panel_text, '') AS panel_text,
               COALESCE(specimen_text, '') AS specimen_text,
               kind,
               value_kind,
               source_ref
          FROM v_observation
         WHERE user_id = '{uid}'
           AND source_kind = 'file'
           {where_extra}
         ORDER BY local_date ASC, id ASC
    """
    return _run_psql_json(sql, pg_container=pg_container)


def fetch_user_medications(user_id="1", pg_container=DEFAULT_PG_CONTAINER):
    """Fetch any logged medications/interventions from Mirobody (if present)."""
    uid = str(user_id).replace("'", "''")
    sql = f"""
        SELECT name_text,
               COALESCE(dose_text, '') AS dose_text,
               COALESCE(frequency_text, '') AS frequency_text,
               COALESCE(status, '') AS status,
               COALESCE(start_date::text, '') AS start_date,
               COALESCE(end_date::text, '') AS end_date
          FROM th_medication
         WHERE user_id = '{uid}'
         ORDER BY start_date DESC NULLS LAST
    """
    try:
        return _run_psql_json(sql, pg_container=pg_container)
    except Exception:
        return []


# Core Apple Watch / wearable daily summary metrics (prefix before '.apple_health*')
WEARABLE_METRICS = [
    ("dailyTotalSteps", "日均步数", "步", 1.0, 0),
    ("dailyTotalActiveCalories", "日均活动消耗", "kcal", 1.0, 0),
    ("dailyTotalExerciseMinutes", "日均锻炼时长", "分钟", 1.0, 1),
    ("dailyAvgRestingHeartRates", "日均静息心率", "bpm", 1.0, 1),
    ("dailyNighttimeRestingHrHeartRates", "夜间静息心率", "bpm", 1.0, 1),
    ("dailyAvgHrvSDNN", "心率变异性 HRV", "ms", 1.0, 1),
    ("dailyTotalSleepAnalysis_Asleep(Total)", "日均总睡眠", "小时", 1.0 / 3600000.0, 2),
    ("dailyTotalSleepAnalysis_Asleep(Deep)", "日均深睡", "分钟", 1.0 / 60000.0, 0),
    ("dailyTotalSleepAnalysis_Asleep(REM)", "日均 REM 睡眠", "分钟", 1.0 / 60000.0, 0),
    ("dailyAvgOxygenSaturations", "日均血氧饱和度", "%", 1.0, 1),
    ("dailyAvgRespiratoryRates", "日均呼吸频率", "次/分", 1.0, 1),
    ("dailyLastBodyMasss", "体重", "kg", 1.0, 1),
    ("dailyLastBmis", "BMI", "", 1.0, 1),
]


def fetch_wearable_summary(user_id="1", pg_container=DEFAULT_PG_CONTAINER):
    """Aggregate Apple Watch / wearable daily summaries across 30d, 90d, 1y, 3y and yearly trends."""
    uid = str(user_id).replace("'", "''")
    metric_keys = ", ".join(f"'{m[0]}'" for m in WEARABLE_METRICS)

    # 1. Windowed averages anchored to the user's latest device date (not wall-clock today)
    sql_windows = f"""
        WITH base AS (
            SELECT SPLIT_PART(name_text, '.', 1) AS metric,
                   local_date,
                   value_num
              FROM v_observation
             WHERE user_id = '{uid}'
               AND source_kind = 'device'
               AND value_num IS NOT NULL
               AND SPLIT_PART(name_text, '.', 1) IN ({metric_keys})
        ),
        anchor AS (
            SELECT MAX(local_date) AS max_d,
                   MIN(local_date) AS min_d,
                   COUNT(DISTINCT local_date) AS total_days
              FROM base
        )
        SELECT b.metric,
               a.min_d::text AS overall_first_day,
               a.max_d::text AS overall_last_day,
               a.total_days AS overall_total_days,
               COUNT(*) FILTER (WHERE b.local_date > a.max_d - INTERVAL '30 days') AS days_30d,
               AVG(b.value_num) FILTER (WHERE b.local_date > a.max_d - INTERVAL '30 days') AS avg_30d,
               COUNT(*) FILTER (WHERE b.local_date > a.max_d - INTERVAL '90 days') AS days_90d,
               AVG(b.value_num) FILTER (WHERE b.local_date > a.max_d - INTERVAL '90 days') AS avg_90d,
               COUNT(*) FILTER (WHERE b.local_date > a.max_d - INTERVAL '365 days') AS days_1y,
               AVG(b.value_num) FILTER (WHERE b.local_date > a.max_d - INTERVAL '365 days') AS avg_1y,
               COUNT(*) FILTER (WHERE b.local_date > a.max_d - INTERVAL '1095 days') AS days_3y,
               AVG(b.value_num) FILTER (WHERE b.local_date > a.max_d - INTERVAL '1095 days') AS avg_3y,
               (ARRAY_AGG(b.value_num ORDER BY b.local_date DESC))[1] AS latest_val,
               MAX(b.local_date)::text AS latest_date
          FROM base b
         CROSS JOIN anchor a
         GROUP BY b.metric, a.min_d, a.max_d, a.total_days
    """

    # 2. Yearly trend over the last 4 calendar years for key longevity/fitness metrics
    sql_yearly = f"""
        WITH base AS (
            SELECT SPLIT_PART(name_text, '.', 1) AS metric,
                   EXTRACT(YEAR FROM local_date)::int AS yr,
                   value_num
              FROM v_observation
             WHERE user_id = '{uid}'
               AND source_kind = 'device'
               AND value_num IS NOT NULL
               AND SPLIT_PART(name_text, '.', 1) IN (
                   'dailyTotalSteps',
                   'dailyTotalExerciseMinutes',
                   'dailyAvgRestingHeartRates',
                   'dailyAvgHrvSDNN',
                   'dailyTotalSleepAnalysis_Asleep(Total)',
                   'dailyLastBodyMasss'
               )
        ),
        max_yr AS (SELECT MAX(yr) AS y FROM base)
        SELECT b.yr,
               b.metric,
               COUNT(*) AS days,
               AVG(b.value_num) AS avg_val
          FROM base b
         CROSS JOIN max_yr m
         WHERE b.yr >= m.y - 3
         GROUP BY b.yr, b.metric
         ORDER BY b.yr ASC, b.metric ASC
    """

    try:
        rows = _run_psql_json(sql_windows, pg_container=pg_container)
        yearly_rows = _run_psql_json(sql_yearly, pg_container=pg_container)
    except Exception:
        return {"has_data": False}

    if not rows:
        return {"has_data": False}

    meta_map = {m[0]: m for m in WEARABLE_METRICS}
    by_metric = {r["metric"]: r for r in rows}

    def _fmt(val, scale, digits):
        if val is None:
            return None
        v = float(val) * scale
        return int(round(v)) if digits == 0 else round(v, digits)

    metrics_out = []
    for key, label, unit, scale, digits in WEARABLE_METRICS:
        r = by_metric.get(key)
        if not r:
            continue
        metrics_out.append({
            "key": key,
            "label": label,
            "unit": unit,
            "latest_val": _fmt(r.get("latest_val"), scale, digits),
            "latest_date": r.get("latest_date", ""),
            "d30": {"avg": _fmt(r.get("avg_30d"), scale, digits), "days": r.get("days_30d", 0)},
            "d90": {"avg": _fmt(r.get("avg_90d"), scale, digits), "days": r.get("days_90d", 0)},
            "y1": {"avg": _fmt(r.get("avg_1y"), scale, digits), "days": r.get("days_1y", 0)},
            "y3": {"avg": _fmt(r.get("avg_3y"), scale, digits), "days": r.get("days_3y", 0)},
        })

    yearly_map = {}
    for yr_row in yearly_rows:
        yr = str(yr_row["yr"])
        mkey = yr_row["metric"]
        if mkey not in meta_map:
            continue
        _, label, unit, scale, digits = meta_map[mkey]
        yearly_map.setdefault(yr, {})[label] = {
            "avg": _fmt(yr_row.get("avg_val"), scale, digits),
            "unit": unit,
            "days": yr_row.get("days", 0),
        }

    first_row = rows[0]
    return {
        "has_data": True,
        "source": "Apple Watch / Apple Health",
        "date_span": {
            "first_day": first_row.get("overall_first_day", ""),
            "last_day": first_row.get("overall_last_day", ""),
            "total_days": first_row.get("overall_total_days", 0),
        },
        "metrics": metrics_out,
        "yearly_trend": yearly_map,
    }
