"""
Treasury Analytics Models
Pydantic models for statistical analysis results

Author: Claude Code
Date: 2026-01-08
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class CorrelationStrength(str, Enum):
    """Strength interpretation of correlation coefficient"""
    WEAK = "weak"           # |r| < 0.3
    MODERATE = "moderate"   # 0.3 <= |r| < 0.7
    STRONG = "strong"       # |r| >= 0.7


class TrendDirection(str, Enum):
    """Direction of trend based on slope"""
    DECLINING = "declining"  # slope < -5%
    STABLE = "stable"        # -5% <= slope <= 5%
    GROWING = "growing"      # slope > 5%


class FindingSeverity(str, Enum):
    """Severity level for report findings"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class FindingCategory(str, Enum):
    """Category of report finding"""
    CORRELATION = "correlation"
    TREND = "trend"
    ANOMALY = "anomaly"
    SLA = "sla"
    PREDICTION = "prediction"
    PERFORMANCE = "performance"


# =============================================================================
# DESCRIPTIVE STATISTICS
# =============================================================================

class DescriptiveStats(BaseModel):
    """Descriptive statistics for a metric"""
    metric_name: str = Field(..., description="Name of the metric")
    count: int = Field(..., description="Number of observations")
    mean: float = Field(..., description="Arithmetic mean")
    median: float = Field(..., description="Median (50th percentile)")
    std: float = Field(..., description="Standard deviation")
    min: float = Field(..., description="Minimum value")
    max: float = Field(..., description="Maximum value")
    q1: float = Field(..., description="First quartile (25th percentile)")
    q3: float = Field(..., description="Third quartile (75th percentile)")
    iqr: float = Field(..., description="Interquartile range (Q3 - Q1)")

    class Config:
        json_schema_extra = {
            "example": {
                "metric_name": "transaction_amount",
                "count": 1250,
                "mean": 125000.50,
                "median": 95000.00,
                "std": 45000.25,
                "min": 5000.00,
                "max": 500000.00,
                "q1": 75000.00,
                "q3": 150000.00,
                "iqr": 75000.00
            }
        }


class StatisticsResponse(BaseModel):
    """Response for statistics endpoint"""
    period: str
    date_from: str
    date_to: str
    total_records: int
    metrics: List[DescriptiveStats]


# =============================================================================
# CORRELATIONS
# =============================================================================

class CorrelationResult(BaseModel):
    """Result of correlation analysis between two variables"""
    variable_1: str = Field(..., description="First variable name")
    variable_2: str = Field(..., description="Second variable name")
    coefficient: float = Field(..., description="Pearson correlation coefficient (-1 to 1)")
    p_value: float = Field(..., description="Statistical significance p-value")
    strength: CorrelationStrength = Field(..., description="Interpretation of correlation strength")
    is_significant: bool = Field(..., description="Whether p-value < 0.05")

    class Config:
        json_schema_extra = {
            "example": {
                "variable_1": "workload",
                "variable_2": "processing_time",
                "coefficient": 0.72,
                "p_value": 0.001,
                "strength": "strong",
                "is_significant": True
            }
        }


class CorrelationMatrix(BaseModel):
    """Full correlation matrix response"""
    period: str
    date_from: str
    date_to: str
    correlations: List[CorrelationResult]
    variables_analyzed: List[str]


# =============================================================================
# TREND ANALYSIS
# =============================================================================

class TrendAnalysis(BaseModel):
    """Result of trend analysis using linear regression"""
    metric_name: str = Field(..., description="Metric being analyzed")
    slope: float = Field(..., description="Slope of the trend line")
    intercept: float = Field(..., description="Y-intercept of the trend line")
    r_squared: float = Field(..., description="Coefficient of determination (0 to 1)")
    direction: TrendDirection = Field(..., description="Trend direction interpretation")
    slope_percentage: float = Field(..., description="Slope as percentage change")
    confidence_level: str = Field(..., description="Confidence level based on R-squared")
    projection_7d: Optional[float] = Field(None, description="Projected value in 7 days")
    projection_30d: Optional[float] = Field(None, description="Projected value in 30 days")
    data_points: int = Field(0, description="Number of data points used for analysis")
    is_reliable: bool = Field(True, description="True if N >= 14 and R² >= 0.5")

    class Config:
        json_schema_extra = {
            "example": {
                "metric_name": "daily_revenue",
                "slope": 2500.50,
                "intercept": 100000.00,
                "r_squared": 0.85,
                "direction": "growing",
                "slope_percentage": 2.5,
                "confidence_level": "high",
                "projection_7d": 117503.50,
                "projection_30d": 175015.00
            }
        }


class TrendsResponse(BaseModel):
    """Response for trends endpoint"""
    period: str
    date_from: str
    date_to: str
    trends: List[TrendAnalysis]


# =============================================================================
# ANOMALY DETECTION
# =============================================================================

class AnomalyPoint(BaseModel):
    """A detected anomaly point"""
    date: str = Field(..., description="Date of the anomaly")
    metric_name: str = Field(..., description="Metric where anomaly was detected")
    value: float = Field(..., description="Actual value")
    expected_value: float = Field(..., description="Expected/mean value")
    z_score: float = Field(..., description="Z-score (standard deviations from mean)")
    deviation_percentage: float = Field(..., description="Percentage deviation from expected")
    anomaly_type: str = Field(..., description="Type: 'high' or 'low'")

    class Config:
        json_schema_extra = {
            "example": {
                "date": "2026-01-05",
                "metric_name": "transaction_count",
                "value": 250,
                "expected_value": 100,
                "z_score": 3.2,
                "deviation_percentage": 150.0,
                "anomaly_type": "high"
            }
        }


class AnomaliesResponse(BaseModel):
    """Response for anomalies endpoint"""
    period: str
    date_from: str
    date_to: str
    total_anomalies: int
    anomalies: List[AnomalyPoint]
    anomalies_by_metric: Dict[str, int]


# =============================================================================
# PREDICTIONS
# =============================================================================

class PredictionPoint(BaseModel):
    """A prediction point with confidence interval"""
    date: str = Field(..., description="Predicted date")
    predicted_value: float = Field(..., description="Predicted value")
    lower_bound: float = Field(..., description="Lower bound of confidence interval")
    upper_bound: float = Field(..., description="Upper bound of confidence interval")
    confidence_level: float = Field(0.95, description="Confidence level (default 95%)")


class PredictionsResponse(BaseModel):
    """Response for predictions endpoint"""
    metric_name: str
    period: str
    date_from: str
    date_to: str
    horizon_days: int
    model_type: str = Field("linear_regression", description="Model used for prediction")
    r_squared: float = Field(..., description="Model fit quality")
    predictions: List[PredictionPoint]
    warning: Optional[str] = Field(None, description="Warning if R-squared is low")


# =============================================================================
# REPORT FINDINGS & RECOMMENDATIONS
# =============================================================================

class ReportFinding(BaseModel):
    """A finding in the analytics report"""
    category: FindingCategory
    severity: FindingSeverity
    title: str = Field(..., description="Short title of the finding")
    message: str = Field(..., description="Detailed message")
    metric_value: Optional[float] = Field(None, description="Related metric value")
    threshold: Optional[float] = Field(None, description="Threshold that triggered this finding")
    recommendation: Optional[str] = Field(None, description="Recommended action")


class AnalyticsReport(BaseModel):
    """Complete analytics report with all analyses"""
    period: str
    date_from: str
    date_to: str
    generated_at: str
    language: str

    # Summary metrics
    total_records: int
    total_amount: float
    total_transactions: int
    avg_transaction_amount: float

    # Detailed analyses
    statistics: List[DescriptiveStats]
    correlations: List[CorrelationResult]
    trends: List[TrendAnalysis]
    predictions: List[PredictionPoint]
    anomalies: List[AnomalyPoint]

    # Report section
    findings: List[ReportFinding]
    alerts_count: int = Field(..., description="Number of critical findings")
    warnings_count: int = Field(..., description="Number of warning findings")

    # Overall health score (0-100)
    health_score: int = Field(..., description="Overall health score based on findings")
    health_status: str = Field(..., description="Status: good, warning, critical")

    # Data quality indicators
    data_days: int = Field(0, description="Number of distinct days with data")
    data_sufficient: bool = Field(True, description="True if data_days >= 14")

    # NL summaries for sections
    trend_summary: Optional[str] = Field(None, description="NL summary of trend analysis")
    correlation_summary: Optional[str] = Field(None, description="NL summary of correlation analysis")

    class Config:
        json_schema_extra = {
            "example": {
                "period": "month",
                "date_from": "2025-12-01",
                "date_to": "2025-12-31",
                "generated_at": "2026-01-08T10:30:00Z",
                "language": "fr",
                "total_records": 1250,
                "total_amount": 156250000,
                "total_transactions": 1250,
                "avg_transaction_amount": 125000,
                "statistics": [],
                "correlations": [],
                "trends": [],
                "predictions": [],
                "anomalies": [],
                "findings": [],
                "alerts_count": 1,
                "warnings_count": 3,
                "health_score": 75,
                "health_status": "warning"
            }
        }


# =============================================================================
# REQUEST MODELS
# =============================================================================

class AnalyticsParams(BaseModel):
    """Query parameters for analytics endpoints"""
    period: str = Field("month", description="Period: day, week, month, year")
    date_from: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")


class PredictionParams(AnalyticsParams):
    """Parameters for prediction endpoint"""
    horizon_days: int = Field(7, description="Number of days to predict", ge=1, le=90)


class ReportParams(AnalyticsParams):
    """Parameters for report endpoint"""
    language: str = Field("es", description="Report language: es, fr, en")
