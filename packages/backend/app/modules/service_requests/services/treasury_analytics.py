"""
Treasury Analytics Service
Statistical analysis using pandas, scipy, and sklearn

Author: Claude Code
Date: 2026-01-08
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression
from loguru import logger
import asyncpg

from app.modules.service_requests.models.analytics_models import (
    DescriptiveStats,
    StatisticsResponse,
    CorrelationResult,
    CorrelationStrength,
    CorrelationMatrix,
    TrendAnalysis,
    TrendDirection,
    TrendsResponse,
    AnomalyPoint,
    AnomaliesResponse,
    PredictionPoint,
    PredictionsResponse,
    ReportFinding,
    FindingSeverity,
    FindingCategory,
    AnalyticsReport,
)


class TreasuryAnalyticsService:
    """
    Service for treasury analytics using pandas/scipy/sklearn

    Provides:
    - Descriptive statistics
    - Correlation analysis
    - Trend analysis with linear regression
    - Anomaly detection using Z-score
    - Time series predictions
    - Automated report generation with recommendations
    """

    # =========================================================================
    # CONFIGURATION: Thresholds for analysis and recommendations
    # =========================================================================

    THRESHOLDS = {
        "correlation": {
            "weak": 0.3,
            "moderate": 0.5,
            "strong": 0.7,
        },
        "trend": {
            "declining": -0.05,  # -5% slope
            "stable_upper": 0.05,  # +5% slope
        },
        "anomaly": {
            "z_score": 2.0,  # Standard deviations
            "max_count": 5,  # Alert threshold
        },
        "sla": {
            "critical": 80,
            "warning": 90,
            "good": 95,
        },
        "prediction": {
            "low_confidence": 0.7,  # R-squared threshold
            "high_confidence": 0.85,
        },
        "processing": {
            "high_time_minutes": 60,
        },
    }

    # Recommendations by language
    RECOMMENDATIONS = {
        "weak_correlation": {
            "es": "La correlación entre {var1} y {var2} es débil ({coef:.2f}). No hay relación significativa.",
            "fr": "La corrélation entre {var1} et {var2} est faible ({coef:.2f}). Pas de relation significative.",
            "en": "Correlation between {var1} and {var2} is weak ({coef:.2f}). No significant relationship.",
        },
        "strong_correlation": {
            "es": "Correlación fuerte detectada entre {var1} y {var2} ({coef:.2f}). Considere optimizar {var1}.",
            "fr": "Forte corrélation détectée entre {var1} et {var2} ({coef:.2f}). Envisagez d'optimiser {var1}.",
            "en": "Strong correlation detected between {var1} and {var2} ({coef:.2f}). Consider optimizing {var1}.",
        },
        "declining_trend": {
            "es": "Tendencia decreciente detectada en {metric} ({slope:.1f}%). Analice: estacionalidad, cambios regulatorios, problemas operativos.",
            "fr": "Tendance décroissante détectée pour {metric} ({slope:.1f}%). Analysez : saisonnalité, changements réglementaires, problèmes opérationnels.",
            "en": "Declining trend detected in {metric} ({slope:.1f}%). Analyze: seasonality, regulatory changes, operational issues.",
        },
        "growing_trend": {
            "es": "Tendencia creciente en {metric} ({slope:.1f}%). Buen rendimiento, mantenga las estrategias actuales.",
            "fr": "Tendance croissante pour {metric} ({slope:.1f}%). Bonne performance, maintenez les stratégies actuelles.",
            "en": "Growing trend in {metric} ({slope:.1f}%). Good performance, maintain current strategies.",
        },
        "high_anomalies": {
            "es": "Se detectaron {count} anomalías. Verifique los procesos de validación y los datos de entrada.",
            "fr": "{count} anomalies détectées. Vérifiez les processus de validation et les données d'entrée.",
            "en": "{count} anomalies detected. Check validation processes and input data.",
        },
        "critical_sla": {
            "es": "Tasa SLA crítica ({rate:.1f}%). Refuerce el equipo o revise los plazos objetivo.",
            "fr": "Taux SLA critique ({rate:.1f}%). Renforcez l'équipe ou révisez les délais cibles.",
            "en": "Critical SLA rate ({rate:.1f}%). Reinforce the team or revise target deadlines.",
        },
        "low_prediction_confidence": {
            "es": "Predicciones poco confiables (R²={r2:.2f}). Datos insuficientes o alta volatilidad.",
            "fr": "Prédictions peu fiables (R²={r2:.2f}). Données insuffisantes ou forte volatilité.",
            "en": "Unreliable predictions (R²={r2:.2f}). Insufficient data or high volatility.",
        },
        "high_processing_time": {
            "es": "Tiempo de procesamiento elevado ({time:.0f} min). Identifique los cuellos de botella.",
            "fr": "Temps de traitement élevé ({time:.0f} min). Identifiez les goulots d'étranglement.",
            "en": "High processing time ({time:.0f} min). Identify bottlenecks.",
        },
    }

    # =========================================================================
    # JSON-SAFE NUMERIC HELPER
    # =========================================================================

    @staticmethod
    def _safe_float(x: Any, default: float = 0.0) -> float:
        """Convert numpy/scipy/pandas value to JSON-safe float.

        scipy.stats.pearsonr returns NaN for constant series, LinearRegression
        can produce Inf on pathological fits, and numpy.std can return 0.0
        triggering NaN downstream. Starlette's JSON encoder rejects NaN/Inf
        with `Out of range float values are not JSON compliant` (HTTP 500).

        This helper normalizes any non-finite numeric to `default` (0.0 by
        default) so the entire analytics report can serialize safely.
        """
        try:
            v = float(x)
            return v if np.isfinite(v) else default
        except (TypeError, ValueError):
            return default

    # =========================================================================
    # DATA EXTRACTION
    # =========================================================================

    async def get_kpi_data(
        self,
        db: asyncpg.Connection,
        period: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        entity_code: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Extract KPI data from materialized view

        Args:
            db: Database connection
            period: Period type (day, week, month, year)
            date_from: Start date
            date_to: End date
            entity_code: Optional entity scope filter. If None, no entity
                filter is applied (admin global view). Otherwise filters
                rows by the supplied entity_code.

        Returns:
            DataFrame with KPI data
        """
        # Calculate date range if not provided
        if not date_to:
            date_to = datetime.now().strftime("%Y-%m-%d")

        if not date_from:
            days_map = {"day": 1, "week": 7, "month": 30, "year": 365}
            days = days_map.get(period, 30)
            date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # asyncpg requires datetime.date objects for date columns (not strings)
        date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
        date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()

        # Bug 1 fix dynamic (2026-05-06): mv_treasury_daily_kpis aggregates
        # payments for ALL entities (TESORO + AYUNTAMIENTO + CAMARA + ...).
        # The entity filter is now parameterized so admin global scope sees
        # everything while entity-scoped supervisors see only their own
        # entity. None = no clause (global admin).
        query_params: list = [date_from_obj, date_to_obj]
        entity_clause = ""
        if entity_code:
            query_params.append(entity_code)
            entity_clause = f"AND entity_code = ${len(query_params)}"
        query = f"""
            SELECT
                report_date,
                payment_method,
                entity_code,
                entity_name,
                service_code,
                workflow_code,
                total_amount,
                payment_count AS transaction_count,
                completed_count AS success_count,
                rejected_count AS failed_count,
                avg_processing_minutes
            FROM mv_treasury_daily_kpis
            WHERE report_date BETWEEN $1 AND $2
              {entity_clause}
            ORDER BY report_date
        """

        try:
            rows = await db.fetch(query, *query_params)
            if not rows:
                logger.warning(f"No KPI data found for period {date_from} to {date_to}")
                return pd.DataFrame()

            # Convert to DataFrame and fix types.
            # asyncpg returns decimal.Decimal for numeric/money columns;
            # pandas/numpy cannot do quantile/corr interpolation on Decimal.
            # Also fill NaN for numeric columns (NULL from FILTER clauses).
            df = pd.DataFrame([dict(row) for row in rows])
            df["report_date"] = pd.to_datetime(df["report_date"])
            numeric_cols = ["total_amount", "transaction_count", "success_count",
                            "failed_count", "avg_processing_minutes"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            return df

        except Exception as e:
            logger.error(f"Error fetching KPI data: {e}")
            return pd.DataFrame()

    async def get_agent_performance_data(
        self,
        db: asyncpg.Connection,
        date_from: str,
        date_to: str,
        entity_code: Optional[str] = None,
    ) -> pd.DataFrame:
        """Extract agent performance data from payment_validation_audit.

        Uses actual audit trail (not the empty agent_performance_stats table)
        to provide monthly agent metrics for cross-correlation with treasury KPIs.

        Args:
            entity_code: Optional entity scope filter. If None, no entity
                filter (admin global view). Otherwise filters by EXISTS
                join on agent_profiles → entities.code.
        """
        # Bug 1 fix dynamic (2026-05-06): entity filter is now parameterized.
        # None = global admin (no clause), explicit entity_code restricts via
        # EXISTS join on agent_profiles → entities.
        # asyncpg requires datetime.date objects for date columns
        df_obj = datetime.strptime(date_from, "%Y-%m-%d").date() if isinstance(date_from, str) else date_from
        dt_obj = datetime.strptime(date_to, "%Y-%m-%d").date() if isinstance(date_to, str) else date_to
        query_params: list = [df_obj, dt_obj]
        entity_clause = ""
        if entity_code:
            query_params.append(entity_code)
            entity_clause = f"""AND EXISTS (
                SELECT 1 FROM agent_profiles ap2
                JOIN entities e2 ON e2.id = ap2.entity_id
                WHERE ap2.id = pva.agent_profile_id
                  AND e2.code = ${len(query_params)}
                  AND ap2.is_active = true
            )"""
        query = f"""
            SELECT
                pva.agent_profile_id::text AS agent_id,
                to_char(date_trunc('month', pva.created_at), 'YYYY-MM') AS month_year,
                COUNT(*) AS validations_count,
                COUNT(*) FILTER (WHERE pva.action = 'reject') AS rejections_count,
                COALESCE(AVG(pva.action_duration_seconds) / 60.0, 0) AS avg_processing_minutes,
                CASE WHEN COUNT(*) > 0
                    THEN ROUND(
                        COUNT(*) FILTER (WHERE pva.action = 'approve')::numeric
                        / COUNT(*)::numeric * 100, 2
                    )
                    ELSE 0
                END AS sla_respect_rate,
                COUNT(DISTINCT pva.payment_id) AS unique_payments
            FROM payment_validation_audit pva
            WHERE pva.agent_profile_id IS NOT NULL
            AND pva.created_at >= $1::date
            AND pva.created_at < ($2::date + INTERVAL '1 month')
            {entity_clause}
            GROUP BY pva.agent_profile_id, date_trunc('month', pva.created_at)
            ORDER BY month_year, validations_count DESC
        """

        try:
            rows = await db.fetch(query, *query_params)
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame([dict(row) for row in rows])
            # Convert Decimal → float for numeric columns (asyncpg returns Decimal)
            for col in ["validations_count", "rejections_count", "avg_processing_minutes",
                         "sla_respect_rate", "unique_payments"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            return df
        except Exception as e:
            logger.error(f"Error fetching agent performance data: {e}")
            return pd.DataFrame()

    # =========================================================================
    # DESCRIPTIVE STATISTICS
    # =========================================================================

    def calculate_descriptive_stats(
        self,
        df: pd.DataFrame,
        columns: List[str],
    ) -> List[DescriptiveStats]:
        """
        Calculate descriptive statistics for specified columns

        Args:
            df: Input DataFrame
            columns: Columns to analyze

        Returns:
            List of DescriptiveStats objects
        """
        results = []

        for col in columns:
            if col not in df.columns:
                continue

            data = df[col].dropna()
            if len(data) == 0:
                continue

            # asyncpg returns decimal.Decimal for numeric columns;
            # pandas/numpy quantile cannot interpolate Decimal * float.
            data = data.astype(float)

            desc = data.describe()
            q1, q3 = data.quantile([0.25, 0.75])

            results.append(
                DescriptiveStats(
                    metric_name=col,
                    count=int(desc["count"]),
                    mean=self._safe_float(desc["mean"]),
                    median=self._safe_float(data.median()),
                    std=self._safe_float(desc["std"]),
                    min=self._safe_float(desc["min"]),
                    max=self._safe_float(desc["max"]),
                    q1=self._safe_float(q1),
                    q3=self._safe_float(q3),
                    iqr=self._safe_float(q3 - q1),
                )
            )

        return results

    async def get_statistics(
        self,
        db: asyncpg.Connection,
        period: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        entity_code: Optional[str] = None,
    ) -> StatisticsResponse:
        """Get descriptive statistics for treasury data"""
        df = await self.get_kpi_data(db, period, date_from, date_to, entity_code=entity_code)

        if df.empty:
            return StatisticsResponse(
                period=period,
                date_from=date_from or "",
                date_to=date_to or "",
                total_records=0,
                metrics=[],
            )

        columns = ["total_amount", "transaction_count", "avg_processing_minutes"]
        stats = self.calculate_descriptive_stats(df, columns)

        return StatisticsResponse(
            period=period,
            date_from=date_from or df["report_date"].min().strftime("%Y-%m-%d"),
            date_to=date_to or df["report_date"].max().strftime("%Y-%m-%d"),
            total_records=len(df),
            metrics=stats,
        )

    # =========================================================================
    # CORRELATION ANALYSIS
    # =========================================================================

    def _interpret_correlation(self, coefficient: float) -> CorrelationStrength:
        """Interpret correlation coefficient strength"""
        abs_coef = abs(coefficient)
        if abs_coef < self.THRESHOLDS["correlation"]["weak"]:
            return CorrelationStrength.WEAK
        elif abs_coef < self.THRESHOLDS["correlation"]["strong"]:
            return CorrelationStrength.MODERATE
        else:
            return CorrelationStrength.STRONG

    def calculate_correlations(
        self,
        df: pd.DataFrame,
        columns: List[str],
    ) -> List[CorrelationResult]:
        """
        Calculate Pearson correlations between columns

        Args:
            df: Input DataFrame
            columns: Columns to correlate

        Returns:
            List of CorrelationResult objects
        """
        results = []

        # Filter to available columns
        available_cols = [c for c in columns if c in df.columns]
        if len(available_cols) < 2:
            return results

        for i, col1 in enumerate(available_cols):
            for col2 in available_cols[i + 1 :]:
                # Get paired data without NaN
                data1 = df[col1]
                data2 = df[col2]
                mask = ~(data1.isna() | data2.isna())

                if mask.sum() < 3:  # Need at least 3 points
                    continue

                v1 = data1[mask].astype(float).values
                v2 = data2[mask].astype(float).values

                # pearsonr returns NaN when either series has zero variance
                # (constant input). NaN cannot be JSON-serialized, so skip.
                if np.std(v1) == 0 or np.std(v2) == 0:
                    logger.debug(
                        f"Skipping correlation {col1}/{col2}: constant series"
                    )
                    continue

                try:
                    coefficient, p_value = stats.pearsonr(v1, v2)
                    coef = self._safe_float(coefficient, 0.0)
                    p = self._safe_float(p_value, 1.0)

                    results.append(
                        CorrelationResult(
                            variable_1=col1,
                            variable_2=col2,
                            coefficient=coef,
                            p_value=p,
                            strength=self._interpret_correlation(coef),
                            is_significant=(p < 0.05 and coef != 0.0),
                        )
                    )
                except Exception as e:
                    logger.warning(f"Correlation error for {col1}/{col2}: {e}")

        return results

    async def get_correlations(
        self,
        db: asyncpg.Connection,
        period: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        entity_code: Optional[str] = None,
    ) -> CorrelationMatrix:
        """Get correlation matrix for treasury metrics"""
        df = await self.get_kpi_data(db, period, date_from, date_to, entity_code=entity_code)

        columns = [
            "total_amount",
            "transaction_count",
            "success_count",
            "avg_processing_minutes",
        ]

        correlations = self.calculate_correlations(df, columns) if not df.empty else []

        return CorrelationMatrix(
            period=period,
            date_from=date_from or "",
            date_to=date_to or "",
            correlations=correlations,
            variables_analyzed=columns,
        )

    # =========================================================================
    # TREND ANALYSIS
    # =========================================================================

    def _interpret_trend(self, slope_pct: float) -> TrendDirection:
        """Interpret trend direction from slope percentage"""
        if slope_pct < self.THRESHOLDS["trend"]["declining"]:
            return TrendDirection.DECLINING
        elif slope_pct > self.THRESHOLDS["trend"]["stable_upper"]:
            return TrendDirection.GROWING
        else:
            return TrendDirection.STABLE

    def analyze_trend(
        self,
        df: pd.DataFrame,
        date_col: str,
        value_col: str,
    ) -> Optional[TrendAnalysis]:
        """
        Analyze trend using linear regression

        Args:
            df: Input DataFrame
            date_col: Date column name
            value_col: Value column name

        Returns:
            TrendAnalysis object or None
        """
        if df.empty or value_col not in df.columns:
            return None

        # Aggregate by date
        daily = df.groupby(date_col)[value_col].sum().reset_index()
        daily = daily.sort_values(date_col)

        if len(daily) < 3:
            return None

        # Convert dates to numeric (days from start)
        daily["day_num"] = (daily[date_col] - daily[date_col].min()).dt.days

        X = daily["day_num"].values.reshape(-1, 1)
        y = daily[value_col].values

        try:
            # Linear regression
            model = LinearRegression()
            model.fit(X, y)

            slope = model.coef_[0]
            intercept = model.intercept_

            # R-squared
            y_pred = model.predict(X)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            # Slope as percentage of mean
            mean_value = np.mean(y)
            slope_pct = (slope / mean_value * 100) if mean_value > 0 else 0

            # Confidence level
            if r_squared >= self.THRESHOLDS["prediction"]["high_confidence"]:
                confidence = "high"
            elif r_squared >= self.THRESHOLDS["prediction"]["low_confidence"]:
                confidence = "medium"
            else:
                confidence = "low"

            # Projections — only reliable if N >= 14 and R² >= 0.5
            last_day = daily["day_num"].max()
            n_days = len(daily)
            is_reliable = n_days >= 14 and r_squared >= 0.5

            proj_7d = self._safe_float(model.predict([[last_day + 7]])[0])
            proj_30d = self._safe_float(model.predict([[last_day + 30]])[0])

            return TrendAnalysis(
                metric_name=value_col,
                slope=self._safe_float(slope),
                intercept=self._safe_float(intercept),
                r_squared=self._safe_float(r_squared),
                direction=self._interpret_trend(slope_pct),
                slope_percentage=self._safe_float(slope_pct),
                confidence_level=confidence,
                projection_7d=max(0.0, proj_7d) if is_reliable else None,
                projection_30d=max(0.0, proj_30d) if is_reliable else None,
                data_points=n_days,
                is_reliable=is_reliable,
            )

        except Exception as e:
            logger.error(f"Trend analysis error for {value_col}: {e}")
            return None

    async def get_trends(
        self,
        db: asyncpg.Connection,
        period: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        entity_code: Optional[str] = None,
    ) -> TrendsResponse:
        """Get trend analysis for treasury metrics"""
        df = await self.get_kpi_data(db, period, date_from, date_to, entity_code=entity_code)

        trends = []
        if not df.empty:
            for col in ["total_amount", "transaction_count"]:
                trend = self.analyze_trend(df, "report_date", col)
                if trend:
                    trends.append(trend)

        return TrendsResponse(
            period=period,
            date_from=date_from or "",
            date_to=date_to or "",
            trends=trends,
        )

    # =========================================================================
    # ANOMALY DETECTION
    # =========================================================================

    def detect_anomalies(
        self,
        df: pd.DataFrame,
        date_col: str,
        value_col: str,
        z_threshold: float = 2.0,
    ) -> List[AnomalyPoint]:
        """
        Detect anomalies using Z-score method

        Args:
            df: Input DataFrame
            date_col: Date column name
            value_col: Value column name
            z_threshold: Z-score threshold for anomaly detection

        Returns:
            List of AnomalyPoint objects
        """
        if df.empty or value_col not in df.columns:
            return []

        # Aggregate by date
        daily = df.groupby(date_col)[value_col].sum().reset_index()

        if len(daily) < 3:
            return []

        values = daily[value_col].values
        mean_val = np.mean(values)
        std_val = np.std(values)

        if std_val == 0:
            return []

        z_scores = (values - mean_val) / std_val

        anomalies = []
        for i, z in enumerate(z_scores):
            if abs(z) > z_threshold:
                value = self._safe_float(values[i])
                expected = self._safe_float(mean_val)
                deviation = (
                    self._safe_float((value - expected) / expected * 100)
                    if expected > 0
                    else 0.0
                )
                anomalies.append(
                    AnomalyPoint(
                        date=daily.iloc[i][date_col].strftime("%Y-%m-%d"),
                        metric_name=value_col,
                        value=value,
                        expected_value=expected,
                        z_score=self._safe_float(z),
                        deviation_percentage=deviation,
                        anomaly_type="high" if z > 0 else "low",
                    )
                )

        return anomalies

    async def get_anomalies(
        self,
        db: asyncpg.Connection,
        period: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        entity_code: Optional[str] = None,
    ) -> AnomaliesResponse:
        """Get detected anomalies for treasury data"""
        df = await self.get_kpi_data(db, period, date_from, date_to, entity_code=entity_code)

        all_anomalies = []
        by_metric: Dict[str, int] = {}

        if not df.empty:
            z_threshold = self.THRESHOLDS["anomaly"]["z_score"]
            for col in ["total_amount", "transaction_count"]:
                anomalies = self.detect_anomalies(df, "report_date", col, z_threshold)
                all_anomalies.extend(anomalies)
                by_metric[col] = len(anomalies)

        return AnomaliesResponse(
            period=period,
            date_from=date_from or "",
            date_to=date_to or "",
            total_anomalies=len(all_anomalies),
            anomalies=all_anomalies,
            anomalies_by_metric=by_metric,
        )

    # =========================================================================
    # PREDICTIONS
    # =========================================================================

    def generate_predictions(
        self,
        df: pd.DataFrame,
        date_col: str,
        value_col: str,
        horizon_days: int = 7,
        confidence_level: float = 0.95,
    ) -> Tuple[List[PredictionPoint], float]:
        """
        Generate predictions using linear regression

        Args:
            df: Input DataFrame
            date_col: Date column name
            value_col: Value column name
            horizon_days: Days to predict
            confidence_level: Confidence level for intervals

        Returns:
            Tuple of (predictions list, r_squared)
        """
        if df.empty or value_col not in df.columns:
            return [], 0.0

        # Aggregate by date
        daily = df.groupby(date_col)[value_col].sum().reset_index()
        daily = daily.sort_values(date_col)

        if len(daily) < 7:
            return [], 0.0

        # Convert to numeric
        daily["day_num"] = (daily[date_col] - daily[date_col].min()).dt.days

        X = daily["day_num"].values.reshape(-1, 1)
        y = daily[value_col].values

        # Fit model
        model = LinearRegression()
        model.fit(X, y)

        # R-squared
        y_pred_train = model.predict(X)
        ss_res = np.sum((y - y_pred_train) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Standard error for prediction intervals
        n = len(y)
        se = np.sqrt(ss_res / (n - 2)) if n > 2 else 0
        t_value = stats.t.ppf((1 + confidence_level) / 2, n - 2) if n > 2 else 1.96

        # Generate predictions
        last_date = daily[date_col].max()
        last_day = daily["day_num"].max()

        predictions = []
        for i in range(1, horizon_days + 1):
            pred_day = last_day + i
            pred_date = last_date + timedelta(days=i)
            pred_value = self._safe_float(model.predict([[pred_day]])[0])

            # Prediction interval
            margin = self._safe_float(t_value * se * np.sqrt(1 + 1 / n))

            predictions.append(
                PredictionPoint(
                    date=pred_date.strftime("%Y-%m-%d"),
                    predicted_value=max(0.0, pred_value),  # No negative predictions
                    lower_bound=max(0.0, pred_value - margin),
                    upper_bound=self._safe_float(pred_value + margin),
                    confidence_level=confidence_level,
                )
            )

        return predictions, self._safe_float(r_squared)

    async def get_predictions(
        self,
        db: asyncpg.Connection,
        period: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        horizon_days: int = 7,
        entity_code: Optional[str] = None,
    ) -> PredictionsResponse:
        """Get predictions for treasury revenue"""
        df = await self.get_kpi_data(db, period, date_from, date_to, entity_code=entity_code)

        predictions, r_squared = (
            self.generate_predictions(
                df, "report_date", "total_amount", horizon_days
            )
            if not df.empty
            else ([], 0.0)
        )

        warning = None
        if r_squared < self.THRESHOLDS["prediction"]["low_confidence"]:
            warning = f"Low confidence predictions (R²={r_squared:.2f}). Results should be interpreted with caution."

        return PredictionsResponse(
            metric_name="total_amount",
            period=period,
            date_from=date_from or "",
            date_to=date_to or "",
            horizon_days=horizon_days,
            model_type="linear_regression",
            r_squared=r_squared,
            predictions=predictions,
            warning=warning,
        )

    # =========================================================================
    # NL SUMMARY GENERATORS
    # =========================================================================

    VARIABLE_LABELS = {
        "es": {
            "total_amount": "ingresos",
            "transaction_count": "volumen de transacciones",
            "avg_processing_minutes": "tiempo de procesamiento",
            "success_count": "transacciones exitosas",
            "failed_count": "transacciones fallidas",
        },
        "fr": {
            "total_amount": "revenus",
            "transaction_count": "volume de transactions",
            "avg_processing_minutes": "temps de traitement",
            "success_count": "transactions reussies",
            "failed_count": "transactions echouees",
        },
        "en": {
            "total_amount": "revenue",
            "transaction_count": "transaction volume",
            "avg_processing_minutes": "processing time",
            "success_count": "successful transactions",
            "failed_count": "failed transactions",
        },
    }

    def _var_label(self, var: str, lang: str) -> str:
        return self.VARIABLE_LABELS.get(lang, self.VARIABLE_LABELS["es"]).get(var, var)

    def _generate_trend_summary(
        self, trends: List[TrendAnalysis], data_days: int, language: str
    ) -> str:
        """Generate NL summary for trend analysis section."""
        lang = language if language in ("es", "fr", "en") else "es"

        if data_days < 3:
            return {
                "es": f"Datos insuficientes ({data_days} dias). Se necesitan al menos 14 dias para un analisis de tendencias fiable.",
                "fr": f"Donnees insuffisantes ({data_days} jours). Au moins 14 jours sont necessaires pour une analyse de tendances fiable.",
                "en": f"Insufficient data ({data_days} days). At least 14 days are needed for reliable trend analysis.",
            }[lang]

        if not trends:
            return {
                "es": "No se detectaron tendencias significativas en el periodo seleccionado.",
                "fr": "Aucune tendance significative detectee pour la periode selectionnee.",
                "en": "No significant trends detected for the selected period.",
            }[lang]

        parts = []
        for t in trends:
            name = self._var_label(t.metric_name, lang)
            pct = abs(t.slope_percentage)

            if not t.is_reliable:
                reliability = {
                    "es": f" (exploratorio: {t.data_points} dias, R²={t.r_squared:.2f})",
                    "fr": f" (exploratoire : {t.data_points} jours, R²={t.r_squared:.2f})",
                    "en": f" (exploratory: {t.data_points} days, R²={t.r_squared:.2f})",
                }[lang]
            else:
                reliability = ""

            if t.direction == TrendDirection.GROWING:
                parts.append({
                    "es": f"Los {name} muestran una tendencia creciente (+{pct:.1f}% por dia){reliability}.",
                    "fr": f"Les {name} montrent une tendance croissante (+{pct:.1f}% par jour){reliability}.",
                    "en": f"{name.capitalize()} shows a growing trend (+{pct:.1f}% per day){reliability}.",
                }[lang])
            elif t.direction == TrendDirection.DECLINING:
                parts.append({
                    "es": f"Los {name} muestran una tendencia decreciente (-{pct:.1f}% por dia){reliability}. Verifique posibles causas estacionales o operativas.",
                    "fr": f"Les {name} montrent une tendance decroissante (-{pct:.1f}% par jour){reliability}. Verifiez les causes saisonnieres ou operationnelles.",
                    "en": f"{name.capitalize()} shows a declining trend (-{pct:.1f}% per day){reliability}. Check for seasonal or operational causes.",
                }[lang])
            else:
                parts.append({
                    "es": f"Los {name} se mantienen estables{reliability}.",
                    "fr": f"Les {name} restent stables{reliability}.",
                    "en": f"{name.capitalize()} remains stable{reliability}.",
                }[lang])

        if data_days < 14:
            caveat = {
                "es": f" Nota: este analisis se basa en solo {data_days} dias de datos — las conclusiones son exploratorias.",
                "fr": f" Note : cette analyse se base sur seulement {data_days} jours de donnees — les conclusions sont exploratoires.",
                "en": f" Note: this analysis is based on only {data_days} days of data — conclusions are exploratory.",
            }[lang]
            parts.append(caveat)

        return " ".join(parts)

    def _generate_correlation_summary(
        self, correlations: List[CorrelationResult], data_days: int, language: str
    ) -> str:
        """Generate NL summary for correlation analysis section."""
        lang = language if language in ("es", "fr", "en") else "es"

        if data_days < 14:
            return {
                "es": f"Correlaciones exploratorias ({data_days} dias de datos). Se necesitan al menos 14 dias para resultados estadisticamente fiables.",
                "fr": f"Correlations exploratoires ({data_days} jours de donnees). Au moins 14 jours sont necessaires pour des resultats statistiquement fiables.",
                "en": f"Exploratory correlations ({data_days} days of data). At least 14 days are needed for statistically reliable results.",
            }[lang]

        if not correlations:
            return {
                "es": "No se detectaron correlaciones entre las variables analizadas.",
                "fr": "Aucune correlation detectee entre les variables analysees.",
                "en": "No correlations detected between analyzed variables.",
            }[lang]

        significant = [c for c in correlations if c.is_significant]
        strong = [c for c in significant if c.strength == CorrelationStrength.STRONG]

        parts = []
        if strong:
            for c in strong:
                v1 = self._var_label(c.variable_1, lang)
                v2 = self._var_label(c.variable_2, lang)
                sign = {
                    "es": "positiva" if c.coefficient > 0 else "negativa",
                    "fr": "positive" if c.coefficient > 0 else "negative",
                    "en": "positive" if c.coefficient > 0 else "negative",
                }[lang]
                parts.append({
                    "es": f"Correlacion fuerte {sign} entre {v1} y {v2} (r={c.coefficient:.2f}, p={c.p_value:.3f}).",
                    "fr": f"Forte correlation {sign} entre {v1} et {v2} (r={c.coefficient:.2f}, p={c.p_value:.3f}).",
                    "en": f"Strong {sign} correlation between {v1} and {v2} (r={c.coefficient:.2f}, p={c.p_value:.3f}).",
                }[lang])
        elif significant:
            parts.append({
                "es": f"{len(significant)} correlacion(es) moderada(s) significativa(s) detectada(s).",
                "fr": f"{len(significant)} correlation(s) moderee(s) significative(s) detectee(s).",
                "en": f"{len(significant)} significant moderate correlation(s) detected.",
            }[lang])
        else:
            parts.append({
                "es": "Las correlaciones detectadas no son estadisticamente significativas (p > 0.05).",
                "fr": "Les correlations detectees ne sont pas statistiquement significatives (p > 0.05).",
                "en": "Detected correlations are not statistically significant (p > 0.05).",
            }[lang])

        return " ".join(parts)

    def _generate_explore_summary(
        self,
        primary: str,
        trend: Optional[TrendAnalysis],
        correlation: Optional['CorrelationResult'],
        anomalies: List[AnomalyPoint],
        data_days: int,
        language: str,
    ) -> str:
        """Generate NL summary for explore tab."""
        lang = language if language in ("es", "fr", "en") else "es"
        name = self._var_label(primary, lang)
        parts = []

        if data_days < 3:
            return {
                "es": f"Datos insuficientes para analizar {name} ({data_days} dias).",
                "fr": f"Donnees insuffisantes pour analyser {name} ({data_days} jours).",
                "en": f"Insufficient data to analyze {name} ({data_days} days).",
            }[lang]

        if trend:
            pct = abs(trend.slope_percentage)
            if trend.direction == TrendDirection.GROWING:
                parts.append({
                    "es": f"{name.capitalize()} muestra una tendencia al alza (+{pct:.1f}%/dia, R²={trend.r_squared:.2f}).",
                    "fr": f"{name.capitalize()} montre une tendance a la hausse (+{pct:.1f}%/jour, R²={trend.r_squared:.2f}).",
                    "en": f"{name.capitalize()} shows an upward trend (+{pct:.1f}%/day, R²={trend.r_squared:.2f}).",
                }[lang])
            elif trend.direction == TrendDirection.DECLINING:
                parts.append({
                    "es": f"{name.capitalize()} muestra una tendencia a la baja (-{pct:.1f}%/dia, R²={trend.r_squared:.2f}). Investigue las posibles causas.",
                    "fr": f"{name.capitalize()} montre une tendance a la baisse (-{pct:.1f}%/jour, R²={trend.r_squared:.2f}). Investiguez les causes possibles.",
                    "en": f"{name.capitalize()} shows a downward trend (-{pct:.1f}%/day, R²={trend.r_squared:.2f}). Investigate possible causes.",
                }[lang])
            else:
                parts.append({
                    "es": f"{name.capitalize()} se mantiene estable (variacion {pct:.1f}%/dia, R²={trend.r_squared:.2f}).",
                    "fr": f"{name.capitalize()} reste stable (variation {pct:.1f}%/jour, R²={trend.r_squared:.2f}).",
                    "en": f"{name.capitalize()} remains stable (variation {pct:.1f}%/day, R²={trend.r_squared:.2f}).",
                }[lang])

        if correlation:
            v2 = self._var_label(correlation.variable_2, lang)
            if correlation.is_significant and correlation.strength == CorrelationStrength.STRONG:
                parts.append({
                    "es": f"Correlacion fuerte con {v2} (r={correlation.coefficient:.2f}).",
                    "fr": f"Forte correlation avec {v2} (r={correlation.coefficient:.2f}).",
                    "en": f"Strong correlation with {v2} (r={correlation.coefficient:.2f}).",
                }[lang])

        if anomalies:
            n = len(anomalies)
            parts.append({
                "es": f"Se detectaron {n} anomalia(s) en el periodo.",
                "fr": f"{n} anomalie(s) detectee(s) sur la periode.",
                "en": f"{n} anomaly(ies) detected in the period.",
            }[lang])

        if data_days < 14:
            parts.append({
                "es": f"Advertencia: solo {data_days} dias de datos — resultados exploratorios.",
                "fr": f"Attention : seulement {data_days} jours de donnees — resultats exploratoires.",
                "en": f"Warning: only {data_days} days of data — exploratory results.",
            }[lang])

        return " ".join(parts) if parts else {
            "es": f"Analisis de {name} completado. Sin hallazgos destacables.",
            "fr": f"Analyse de {name} terminee. Aucune observation notable.",
            "en": f"Analysis of {name} completed. No notable findings.",
        }[lang]

    # =========================================================================
    # REPORT GENERATION
    # =========================================================================

    def _get_recommendation(
        self,
        key: str,
        language: str,
        **kwargs,
    ) -> str:
        """Get localized recommendation text"""
        template = self.RECOMMENDATIONS.get(key, {}).get(language, "")
        return template.format(**kwargs) if template else ""

    async def generate_report(
        self,
        db: asyncpg.Connection,
        period: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        language: str = "es",
        entity_code: Optional[str] = None,
    ) -> AnalyticsReport:
        """
        Generate comprehensive analytics report

        Args:
            db: Database connection
            period: Period type
            date_from: Start date
            date_to: End date
            language: Report language (es, fr, en)
            entity_code: Optional entity scope filter. None = global admin
                view (all entities). Otherwise restricts the report to the
                supplied entity_code.

        Returns:
            Complete AnalyticsReport
        """
        # Get all data
        df = await self.get_kpi_data(db, period, date_from, date_to, entity_code=entity_code)

        if df.empty:
            return AnalyticsReport(
                period=period,
                date_from=date_from or "",
                date_to=date_to or "",
                generated_at=datetime.now().isoformat(),
                language=language,
                total_records=0,
                total_amount=0,
                total_transactions=0,
                avg_transaction_amount=0,
                statistics=[],
                correlations=[],
                trends=[],
                predictions=[],
                anomalies=[],
                findings=[],
                alerts_count=0,
                warnings_count=0,
                health_score=100,
                health_status="good",
            )

        # Calculate all analyses
        stats_cols = ["total_amount", "transaction_count", "avg_processing_minutes"]
        statistics = self.calculate_descriptive_stats(df, stats_cols)

        corr_cols = ["total_amount", "transaction_count", "avg_processing_minutes"]
        correlations = self.calculate_correlations(df, corr_cols)

        trends = []
        for col in ["total_amount", "transaction_count"]:
            trend = self.analyze_trend(df, "report_date", col)
            if trend:
                trends.append(trend)

        predictions, r_squared = self.generate_predictions(
            df, "report_date", "total_amount", horizon_days=7
        )

        anomalies = []
        for col in ["total_amount", "transaction_count"]:
            anomalies.extend(
                self.detect_anomalies(
                    df, "report_date", col, self.THRESHOLDS["anomaly"]["z_score"]
                )
            )

        # Generate findings
        findings = []
        alerts_count = 0
        warnings_count = 0

        # Check correlations
        for corr in correlations:
            if corr.is_significant:
                if corr.strength == CorrelationStrength.STRONG:
                    findings.append(
                        ReportFinding(
                            category=FindingCategory.CORRELATION,
                            severity=FindingSeverity.INFO,
                            title=f"Strong correlation: {corr.variable_1}/{corr.variable_2}",
                            message=self._get_recommendation(
                                "strong_correlation",
                                language,
                                var1=corr.variable_1,
                                var2=corr.variable_2,
                                coef=corr.coefficient,
                            ),
                            metric_value=corr.coefficient,
                            threshold=self.THRESHOLDS["correlation"]["strong"],
                        )
                    )

        # Check trends
        for trend in trends:
            if trend.direction == TrendDirection.DECLINING:
                findings.append(
                    ReportFinding(
                        category=FindingCategory.TREND,
                        severity=FindingSeverity.WARNING,
                        title=f"Declining trend: {trend.metric_name}",
                        message=self._get_recommendation(
                            "declining_trend",
                            language,
                            metric=trend.metric_name,
                            slope=trend.slope_percentage,
                        ),
                        metric_value=trend.slope_percentage,
                        threshold=self.THRESHOLDS["trend"]["declining"] * 100,
                    )
                )
                warnings_count += 1
            elif trend.direction == TrendDirection.GROWING:
                findings.append(
                    ReportFinding(
                        category=FindingCategory.TREND,
                        severity=FindingSeverity.INFO,
                        title=f"Growing trend: {trend.metric_name}",
                        message=self._get_recommendation(
                            "growing_trend",
                            language,
                            metric=trend.metric_name,
                            slope=trend.slope_percentage,
                        ),
                        metric_value=trend.slope_percentage,
                    )
                )

        # Check anomalies
        if len(anomalies) > self.THRESHOLDS["anomaly"]["max_count"]:
            findings.append(
                ReportFinding(
                    category=FindingCategory.ANOMALY,
                    severity=FindingSeverity.WARNING,
                    title="High number of anomalies",
                    message=self._get_recommendation(
                        "high_anomalies", language, count=len(anomalies)
                    ),
                    metric_value=len(anomalies),
                    threshold=self.THRESHOLDS["anomaly"]["max_count"],
                )
            )
            warnings_count += 1

        # Check prediction confidence
        if r_squared < self.THRESHOLDS["prediction"]["low_confidence"]:
            findings.append(
                ReportFinding(
                    category=FindingCategory.PREDICTION,
                    severity=FindingSeverity.WARNING,
                    title="Low prediction confidence",
                    message=self._get_recommendation(
                        "low_prediction_confidence", language, r2=r_squared
                    ),
                    metric_value=r_squared,
                    threshold=self.THRESHOLDS["prediction"]["low_confidence"],
                )
            )
            warnings_count += 1

        # Calculate health score
        health_score = 100
        health_score -= alerts_count * 20
        health_score -= warnings_count * 10
        health_score -= min(len(anomalies), 10) * 2
        health_score = max(0, min(100, health_score))

        if health_score >= 80:
            health_status = "good"
        elif health_score >= 50:
            health_status = "warning"
        else:
            health_status = "critical"

        # Summary metrics
        total_amount = self._safe_float(df["total_amount"].sum())
        total_transactions = int(df["transaction_count"].sum())

        # Data quality
        data_days = int(df["report_date"].nunique())
        data_sufficient = data_days >= 14

        # NL summaries
        trend_summary = self._generate_trend_summary(trends, data_days, language)
        correlation_summary = self._generate_correlation_summary(correlations, data_days, language)

        return AnalyticsReport(
            period=period,
            date_from=date_from or df["report_date"].min().strftime("%Y-%m-%d"),
            date_to=date_to or df["report_date"].max().strftime("%Y-%m-%d"),
            generated_at=datetime.now().isoformat(),
            language=language,
            total_records=len(df),
            total_amount=total_amount,
            total_transactions=total_transactions,
            avg_transaction_amount=self._safe_float(
                total_amount / total_transactions
            ) if total_transactions > 0 else 0.0,
            statistics=statistics,
            correlations=correlations,
            trends=trends,
            predictions=predictions,
            anomalies=anomalies,
            findings=findings,
            alerts_count=alerts_count,
            warnings_count=warnings_count,
            health_score=health_score,
            health_status=health_status,
            data_days=data_days,
            data_sufficient=data_sufficient,
            trend_summary=trend_summary,
            correlation_summary=correlation_summary,
        )


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

treasury_analytics_service = TreasuryAnalyticsService()
