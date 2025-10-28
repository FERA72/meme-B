"""
Database models for storing memecoin data
This file defines the structure of our PostgreSQL tables
"""

from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, JSON, Text, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

# Base class for all our database models
Base = declarative_base()


class Token(Base):
    """
    Main table storing all detected tokens (memecoins)
    Each row represents one unique token on Solana
    """
    __tablename__ = 'tokens'
    
    # Primary identifier - the token's mint address (unique on Solana)
    mint_address = Column(String, primary_key=True)
    
    # Basic token information
    name = Column(String)  # Token name (e.g., "Pepe Coin")
    symbol = Column(String)  # Token symbol (e.g., "PEPE")
    decimals = Column(Integer)  # Number of decimal places (usually 6 or 9)
    supply = Column(Float)  # Total token supply
    
    # Creator and authority information
    creator = Column(String)  # Wallet address of token creator
    mint_authority = Column(String, nullable=True)  # If not None, creator can mint more tokens (RED FLAG)
    freeze_authority = Column(String, nullable=True)  # If not None, creator can freeze wallets (RED FLAG)
    
    # Liquidity and market data
    liquidity_usd = Column(Float, default=0.0)  # Total liquidity in USD
    market_cap = Column(Float, default=0.0)  # Market capitalization
    price_usd = Column(Float, default=0.0)  # Current price per token
    volume_24h = Column(Float, default=0.0)  # 24-hour trading volume
    price_change_24h = Column(Float, default=0.0)  # 24-hour price change percentage
    dex_name = Column(String, nullable=True)  # Which DEX the token trades on (e.g., "raydium", "orca")
    
    # Holder information
    holder_count = Column(Integer, default=0)  # Number of unique wallets holding the token
    top_holder_percentage = Column(Float, default=0.0)  # % of supply held by largest holder
    
    # Liquidity pool information
    lp_locked = Column(Boolean, default=False)  # Is liquidity pool locked? (GOOD if True)
    lp_burn_percentage = Column(Float, default=0.0)  # % of LP tokens burned
    pool_address = Column(String, nullable=True)  # Address of the liquidity pool
    
    # Safety and filtering
    is_safe = Column(Boolean, default=False)  # Passed our anti-rug filters?
    is_graduated = Column(Boolean, default=False)  # Has it grown enough to graduate?
    risk_flags = Column(JSON, default=list)  # List of detected risks (e.g., ["high_tax", "no_lp_lock"])
    
    # Metadata and tracking
    token_metadata = Column(JSON, default=dict)  # Additional data (description, website, social links)
    first_seen = Column(DateTime, default=datetime.utcnow)  # When we first detected this token
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Last data refresh
    
    # Performance tracking
    initial_liquidity = Column(Float, default=0.0)  # Liquidity when first detected
    initial_holders = Column(Integer, default=0)  # Holder count when first detected
    growth_rate = Column(Float, default=0.0)  # % growth in market cap since detection

    # Watchlist entries (whitelist/blacklist)
    watchlist_entries = relationship(
        "TokenWatchlist",
        back_populates="token",
        cascade="all, delete-orphan",
        lazy="joined"
    )


class TokenSnapshot(Base):
    """
    Historical snapshots of token data
    Used to track changes over time and train ML models
    """
    __tablename__ = 'token_snapshots'
    
    # Composite primary key (token + timestamp)
    id = Column(Integer, primary_key=True, autoincrement=True)
    mint_address = Column(String, index=True)  # Which token this snapshot is for
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)  # When snapshot was taken
    
    # Snapshot of market data at this point in time
    liquidity_usd = Column(Float)
    market_cap = Column(Float)
    price_usd = Column(Float)
    holder_count = Column(Integer)
    volume_24h = Column(Float)
    
    # Store complete state for historical analysis
    full_data = Column(JSON)  # Complete token state at this timestamp


class FilterLog(Base):
    """
    Logs of all filtering decisions
    Helps us understand what tokens are being rejected and why
    """
    __tablename__ = 'filter_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    mint_address = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Filter results
    passed = Column(Boolean)  # Did it pass all filters?
    failed_filters = Column(JSON)  # List of filters it failed (e.g., ["liquidity_too_low", "mint_authority_not_revoked"])
    
    # Data at time of filtering
    liquidity_at_check = Column(Float)
    holder_count_at_check = Column(Integer)
    filter_details = Column(JSON)  # Complete filter analysis


class TokenWatchlist(Base):
    """
    Tracks whitelist/blacklist status for tokens.
    """
    __tablename__ = 'token_watchlist'

    id = Column(Integer, primary_key=True, autoincrement=True)
    mint_address = Column(String, ForeignKey('tokens.mint_address'), nullable=False, index=True)
    list_type = Column(String, nullable=False)  # whitelist | blacklist
    reason = Column(Text, nullable=True)
    details = Column('details', JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    token = relationship("Token", back_populates="watchlist_entries")

    __table_args__ = (
        UniqueConstraint('mint_address', 'list_type', name='uq_watchlist_mint_type'),
    )
