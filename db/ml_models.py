"""
ML-specific database models for training data collection
These tables store structured data optimized for machine learning
"""

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, JSON, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class MLTrainingData(Base):
    """
    ML training dataset - records token outcomes for supervised learning
    Each row represents a complete token lifecycle with labeled outcome
    """
    __tablename__ = 'ml_training_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    mint_address = Column(String, index=True, unique=True)

    # ===== INITIAL STATE (at detection) =====
    # These are features for ML model input
    initial_liquidity_usd = Column(Float)
    initial_market_cap = Column(Float)
    initial_price_usd = Column(Float)
    initial_holder_count = Column(Integer)
    initial_top_holder_pct = Column(Float)
    initial_volume_24h = Column(Float)

    # Authority flags
    mint_authority_revoked = Column(Boolean)
    freeze_authority_revoked = Column(Boolean)
    lp_locked = Column(Boolean)
    lp_burn_pct = Column(Float)

    # Trading metrics at detection
    initial_buy_count = Column(Integer)
    initial_sell_count = Column(Integer)
    initial_buy_sell_ratio = Column(Float)
    initial_trade_volume = Column(Float)

    # Social/metadata indicators
    has_website = Column(Boolean)
    has_twitter = Column(Boolean)
    has_telegram = Column(Boolean)
    description_length = Column(Integer)

    # ===== OUTCOME LABELS (after time periods) =====
    # What actually happened to this token?

    # 5-minute outcome
    price_change_5m = Column(Float)  # % change after 5 minutes
    volume_5m = Column(Float)  # Trading volume in first 5 minutes
    holders_change_5m = Column(Integer)  # New holders gained
    outcome_5m = Column(String)  # MOON | RUG | STABLE | DEAD
    max_profit_5m = Column(Float)  # Maximum achievable profit % in 5m

    # 1-hour outcome
    price_change_1h = Column(Float)
    volume_1h = Column(Float)
    holders_change_1h = Column(Integer)
    outcome_1h = Column(String)
    max_profit_1h = Column(Float)

    # 24-hour outcome
    price_change_24h = Column(Float)
    volume_24h = Column(Float)
    holders_change_24h = Column(Integer)
    outcome_24h = Column(String)
    max_profit_24h = Column(Float)

    # Final classification
    is_rug_pull = Column(Boolean)  # Did it rug?
    is_quick_profit_rug = Column(Boolean)  # Pumped then rugged quickly?
    is_slow_rug = Column(Boolean)  # Slow bleed out?
    is_legitimate = Column(Boolean)  # Real project?
    is_moon = Column(Boolean)  # Went to the moon?

    # Rug detection metrics
    rug_timestamp = Column(DateTime, nullable=True)  # When did it rug?
    time_to_rug_minutes = Column(Float, nullable=True)  # How long until rug?
    max_liquidity_usd = Column(Float)  # Peak liquidity before rug
    liquidity_removed_pct = Column(Float)  # % liquidity removed during rug

    # Profitability for quick traders
    best_entry_price = Column(Float)  # Best entry point
    best_exit_price = Column(Float)  # Best exit point
    max_achievable_profit_pct = Column(Float)  # Perfect trade profit
    safe_exit_window_minutes = Column(Float)  # How long until unsafe?

    # Metadata
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    data_complete = Column(Boolean, default=False)  # Has all time periods been observed?

    # Raw data for debugging
    raw_features = Column(JSON)  # All initial features as JSON
    raw_outcome_data = Column(JSON)  # All outcome data as JSON

    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_ml_outcome_5m', 'outcome_5m'),
        Index('idx_ml_outcome_1h', 'outcome_1h'),
        Index('idx_ml_outcome_24h', 'outcome_24h'),
        Index('idx_ml_is_rug', 'is_rug_pull'),
        Index('idx_ml_quick_profit', 'is_quick_profit_rug'),
    )


class TokenBehaviorPattern(Base):
    """
    Stores detected behavioral patterns for pattern matching
    Used to identify similar tokens and predict outcomes
    """
    __tablename__ = 'token_behavior_patterns'

    id = Column(Integer, primary_key=True, autoincrement=True)
    mint_address = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Pattern detection
    pattern_type = Column(String, index=True)  # PUMP_AND_DUMP | SLOW_RUG | MOON | STABLE
    confidence = Column(Float)  # 0-1 confidence score

    # Pattern characteristics
    liquidity_pattern = Column(JSON)  # Time series of liquidity changes
    price_pattern = Column(JSON)  # Time series of price changes
    holder_pattern = Column(JSON)  # Time series of holder changes
    trade_pattern = Column(JSON)  # Buy/sell ratio over time

    # Similar tokens (for pattern matching)
    similar_tokens = Column(JSON)  # List of similar mint addresses
    similarity_score = Column(Float)  # How similar to historical patterns

    # Predictions based on pattern
    predicted_outcome = Column(String)  # RUG | MOON | STABLE | DEAD
    predicted_time_to_outcome_minutes = Column(Float)  # When will it happen?
    predicted_max_profit_pct = Column(Float)  # Expected max profit
    risk_score = Column(Float)  # 0-100 risk assessment

    # Pattern metadata
    pattern_data = Column(JSON)  # Complete pattern details


class MLPrediction(Base):
    """
    Stores ML model predictions for real-time tracking
    Tracks accuracy and improves over time
    """
    __tablename__ = 'ml_predictions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    mint_address = Column(String, index=True)
    prediction_timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Model information
    model_version = Column(String)  # Which ML model made this prediction
    model_type = Column(String)  # GPT | LOCAL_ML | ENSEMBLE

    # Predictions
    predicted_outcome = Column(String)  # RUG | MOON | STABLE
    confidence = Column(Float)  # 0-1 confidence
    risk_score = Column(Float)  # 0-100 overall risk
    opportunity_score = Column(Float)  # 0-100 profit opportunity

    # Specific predictions
    predicted_price_5m = Column(Float)
    predicted_price_1h = Column(Float)
    predicted_price_24h = Column(Float)
    predicted_max_profit = Column(Float)
    predicted_rug_probability = Column(Float)  # 0-1 probability of rug
    predicted_time_to_rug = Column(Float, nullable=True)  # Minutes until rug

    # Recommended actions
    recommended_action = Column(String)  # BUY | AVOID | WATCH | SELL
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    time_horizon_minutes = Column(Float)  # How long to hold

    # Actual outcomes (filled in later for accuracy tracking)
    actual_outcome = Column(String, nullable=True)
    actual_price_5m = Column(Float, nullable=True)
    actual_price_1h = Column(Float, nullable=True)
    actual_price_24h = Column(Float, nullable=True)
    actual_max_profit = Column(Float, nullable=True)

    # Accuracy metrics
    prediction_accurate = Column(Boolean, nullable=True)
    prediction_error = Column(Float, nullable=True)  # How far off was it?

    # Full prediction data
    prediction_data = Column(JSON)  # Complete prediction details
    feature_importance = Column(JSON)  # Which features influenced prediction

    __table_args__ = (
        Index('idx_pred_timestamp', 'prediction_timestamp'),
        Index('idx_pred_outcome', 'predicted_outcome'),
    )


class MLModelPerformance(Base):
    """
    Tracks ML model performance over time
    Helps identify which models work best
    """
    __tablename__ = 'ml_model_performance'

    id = Column(Integer, primary_key=True, autoincrement=True)
    model_version = Column(String, index=True)
    evaluation_timestamp = Column(DateTime, default=datetime.utcnow)

    # Dataset info
    total_predictions = Column(Integer)
    evaluation_period_hours = Column(Float)

    # Accuracy metrics
    overall_accuracy = Column(Float)  # % correct predictions
    rug_detection_accuracy = Column(Float)  # % rugs correctly identified
    false_positive_rate = Column(Float)  # % safe tokens marked as risky
    false_negative_rate = Column(Float)  # % rugs marked as safe

    # Performance by outcome type
    moon_detection_accuracy = Column(Float)
    rug_detection_precision = Column(Float)
    rug_detection_recall = Column(Float)

    # Profit metrics
    avg_predicted_profit = Column(Float)
    avg_actual_profit = Column(Float)
    profit_prediction_error = Column(Float)

    # Timing accuracy
    avg_time_prediction_error_minutes = Column(Float)

    # Full performance data
    performance_data = Column(JSON)
    confusion_matrix = Column(JSON)  # Detailed classification results


class QuickProfitOpportunity(Base):
    """
    Tracks tokens identified as quick profit opportunities
    Even if they might rug, can we profit in the first few minutes?
    """
    __tablename__ = 'quick_profit_opportunities'

    id = Column(Integer, primary_key=True, autoincrement=True)
    mint_address = Column(String, index=True)
    detected_timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Opportunity assessment
    opportunity_score = Column(Float)  # 0-100 how good is this opportunity
    risk_score = Column(Float)  # 0-100 overall risk
    confidence = Column(Float)  # 0-1 confidence in assessment

    # Expected outcome
    expected_max_profit_pct = Column(Float)  # Expected max profit %
    expected_time_to_peak_minutes = Column(Float)  # When to exit
    expected_rug_time_minutes = Column(Float, nullable=True)  # When will it rug?

    # Entry/Exit strategy
    recommended_entry_price = Column(Float)
    recommended_exit_price = Column(Float)
    stop_loss_price = Column(Float)
    max_hold_time_minutes = Column(Float)

    # Why is this an opportunity?
    opportunity_reasons = Column(JSON)  # List of positive signals
    risk_reasons = Column(JSON)  # List of risk factors

    # Pattern matching
    similar_past_tokens = Column(JSON)  # Similar tokens that worked
    pattern_type = Column(String)  # Type of pattern detected

    # Actual results (filled in later)
    actual_max_profit_pct = Column(Float, nullable=True)
    actual_time_to_peak_minutes = Column(Float, nullable=True)
    did_rug = Column(Boolean, nullable=True)
    time_to_rug_minutes = Column(Float, nullable=True)

    # Success tracking
    was_profitable = Column(Boolean, nullable=True)
    actual_profit_if_followed = Column(Float, nullable=True)
    opportunity_accurate = Column(Boolean, nullable=True)

    # Full opportunity data
    opportunity_data = Column(JSON)

    __table_args__ = (
        Index('idx_opportunity_score', 'opportunity_score'),
        Index('idx_opportunity_detected', 'detected_timestamp'),
    )
