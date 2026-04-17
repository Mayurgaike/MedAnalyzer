"""
Trend Detector — analyzes lab value trends over time.

For each numeric lab metric across time:
  - Calculate % change (first → last)
  - Run simple linear regression 
  - Classify: RISING / FALLING / STABLE / CRITICAL / INSUFFICIENT_DATA
  - Check medical thresholds
"""

import logging
import math
from enum import Enum

logger = logging.getLogger(__name__)


class TrendDirection(str, Enum):
    RISING = "RISING"
    FALLING = "FALLING"
    STABLE = "STABLE"
    CRITICAL = "CRITICAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# Medical thresholds — used for critical classification
# ---------------------------------------------------------------------------
MEDICAL_THRESHOLDS = {
    "HbA1c": {"critical_high": 6.5, "warning_high": 5.7, "label_high": "Diabetic range", "label_warn": "Pre-diabetic"},
    "Blood Sugar": {"critical_high": 126, "warning_high": 100, "label_high": "Diabetic (fasting)", "label_warn": "Pre-diabetic"},
    "BP Systolic": {"critical_high": 140, "warning_high": 130, "label_high": "Hypertensive", "label_warn": "Elevated"},
    "BP Diastolic": {"critical_high": 90, "warning_high": 85, "label_high": "Hypertensive", "label_warn": "Elevated"},
    "Hemoglobin": {"critical_low": 10.0, "warning_low": 12.0, "label_low": "Anemic", "label_warn": "Low"},
    "Creatinine": {"critical_high": 2.0, "warning_high": 1.3, "label_high": "Kidney concern", "label_warn": "Elevated"},
    "Cholesterol": {"critical_high": 240, "warning_high": 200, "label_high": "High cholesterol", "label_warn": "Borderline"},
    "LDL Cholesterol": {"critical_high": 160, "warning_high": 130, "label_high": "High LDL", "label_warn": "Borderline"},
    "Triglycerides": {"critical_high": 200, "warning_high": 150, "label_high": "High triglycerides", "label_warn": "Borderline"},
    "BMI": {"critical_high": 30.0, "warning_high": 25.0, "label_high": "Obese", "label_warn": "Overweight"},
    "TSH": {"critical_high": 10.0, "warning_high": 4.5, "label_high": "Hypothyroid", "label_warn": "Borderline"},
}


def analyze_trends(lab_time_series: dict[str, list[dict]]) -> list[dict]:
    """
    Analyze trends for all lab metrics.
    
    Args:
        lab_time_series: {metric_name: [{date, value, unit, ...}]}
    
    Returns:
        List of trend objects.
    """
    trends = []

    for metric, data_points in lab_time_series.items():
        trend = analyze_single_metric(metric, data_points)
        trends.append(trend)

    # Sort: critical first, then rising, then others
    priority = {
        TrendDirection.CRITICAL: 0,
        TrendDirection.RISING: 1,
        TrendDirection.FALLING: 2,
        TrendDirection.STABLE: 3,
        TrendDirection.INSUFFICIENT_DATA: 4,
    }
    trends.sort(key=lambda t: priority.get(TrendDirection(t["trend"]), 5))

    return trends


def analyze_single_metric(metric: str, data_points: list[dict]) -> dict:
    """
    Analyze trend for a single lab metric.
    
    Returns:
        {
            metric, trend, change_percent, current_value, first_value,
            threshold_status, threshold_label, data_points, slope,
            unit, reference_min, reference_max
        }
    """
    # Minimum data point check (user feedback: guard against noisy trends)
    if len(data_points) < 2:
        current = data_points[0] if data_points else {}
        threshold_info = _check_threshold(metric, current.get("value", 0))
        
        # Even with insufficient trend data, we can still flag critical values
        trend_dir = TrendDirection.INSUFFICIENT_DATA
        if threshold_info["status"] == "critical":
            trend_dir = TrendDirection.CRITICAL

        return {
            "metric": metric,
            "trend": trend_dir.value,
            "change_percent": 0.0,
            "current_value": current.get("value", 0),
            "first_value": current.get("value", 0),
            "threshold_status": threshold_info["status"],
            "threshold_label": threshold_info["label"],
            "data_points": data_points,
            "data_point_count": len(data_points),
            "slope": 0.0,
            "unit": current.get("unit", ""),
            "reference_min": current.get("reference_min"),
            "reference_max": current.get("reference_max"),
            "message": "Insufficient data — need at least 2 readings for trend analysis",
        }

    # Extract values
    values = [dp["value"] for dp in data_points]
    first_value = values[0]
    current_value = values[-1]

    # Percent change
    if first_value != 0:
        change_percent = ((current_value - first_value) / abs(first_value)) * 100
    else:
        change_percent = 0.0 if current_value == 0 else 100.0

    # Linear regression slope
    slope = _linear_regression_slope(values)

    # Threshold check on current value
    threshold_info = _check_threshold(metric, current_value)

    # Classify trend direction
    trend_dir = _classify_trend(change_percent, slope, threshold_info["status"])

    # Build message
    message = _build_trend_message(metric, trend_dir, change_percent, current_value, threshold_info)

    return {
        "metric": metric,
        "trend": trend_dir.value,
        "change_percent": round(change_percent, 1),
        "current_value": current_value,
        "first_value": first_value,
        "threshold_status": threshold_info["status"],
        "threshold_label": threshold_info["label"],
        "data_points": data_points,
        "data_point_count": len(data_points),
        "slope": round(slope, 4),
        "unit": data_points[-1].get("unit", ""),
        "reference_min": data_points[-1].get("reference_min"),
        "reference_max": data_points[-1].get("reference_max"),
        "message": message,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _linear_regression_slope(values: list[float]) -> float:
    """
    Calculate the slope of simple linear regression.
    x-axis = index (0, 1, 2, ...), y-axis = values.
    """
    n = len(values)
    if n < 2:
        return 0.0

    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n

    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0

    return numerator / denominator


def _check_threshold(metric: str, value: float) -> dict:
    """Check if a value crosses medical thresholds."""
    thresholds = MEDICAL_THRESHOLDS.get(metric)
    if not thresholds:
        return {"status": "normal", "label": "Within expected range"}

    # Check critical high
    if "critical_high" in thresholds and value >= thresholds["critical_high"]:
        return {"status": "critical", "label": thresholds.get("label_high", "Critical")}

    # Check warning high
    if "warning_high" in thresholds and value >= thresholds["warning_high"]:
        return {"status": "warning", "label": thresholds.get("label_warn", "Elevated")}

    # Check critical low
    if "critical_low" in thresholds and value <= thresholds["critical_low"]:
        return {"status": "critical", "label": thresholds.get("label_low", "Critical low")}

    # Check warning low
    if "warning_low" in thresholds and value <= thresholds["warning_low"]:
        return {"status": "warning", "label": thresholds.get("label_warn", "Low")}

    return {"status": "normal", "label": "Within normal range"}


def _classify_trend(
    change_percent: float, slope: float, threshold_status: str
) -> TrendDirection:
    """Classify the trend direction based on change, slope, and threshold."""
    # If current value is critical, always flag as CRITICAL
    if threshold_status == "critical":
        return TrendDirection.CRITICAL

    # Based on percentage change
    if change_percent > 10:
        return TrendDirection.RISING
    elif change_percent < -10:
        return TrendDirection.FALLING
    else:
        return TrendDirection.STABLE


def _build_trend_message(
    metric: str,
    trend: TrendDirection,
    change_percent: float,
    current_value: float,
    threshold_info: dict,
) -> str:
    """Build a human-readable trend message."""
    direction = ""
    if trend == TrendDirection.RISING:
        direction = f"increasing (↑{abs(change_percent):.1f}%)"
    elif trend == TrendDirection.FALLING:
        direction = f"decreasing (↓{abs(change_percent):.1f}%)"
    elif trend == TrendDirection.STABLE:
        direction = "stable"
    elif trend == TrendDirection.CRITICAL:
        direction = f"at critical level — {threshold_info['label']}"
    else:
        direction = "data pending"

    return f"{metric} is {direction}. Current: {current_value}. {threshold_info['label']}."
