"""
Database operations and connection management.
Extends core persistence with whitelist/blacklist tracking for tokens.
"""

from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import os
from core.logger import get_logger
from db.models import Base, Token, TokenSnapshot, FilterLog, TokenWatchlist
from datetime import datetime
from typing import List, Optional, Dict


class Database:
    """
    Main database handler
    Manages connection pool and provides methods for all database operations
    """
    
    def __init__(self, connection_string: str):
        """
        Initialize database connection
        
        Args:
            connection_string: PostgreSQL connection URL
                             Format: postgresql://username:password@host:port/database
        """
        # Create database engine with connection pooling for better performance
        self.engine = create_engine(
            connection_string,
            poolclass=QueuePool,  # Reuse database connections
            pool_size=10,  # Keep 10 connections ready
            max_overflow=20,  # Allow up to 20 extra connections if needed
            echo=False  # Set to True to see all SQL queries (useful for debugging)
        )
        
        # Session factory - creates new database sessions when needed
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.log = get_logger("database")
        
    def create_tables(self):
        """
        Create all database tables if they don't exist
        Call this once when setting up the system
        """
        Base.metadata.create_all(bind=self.engine)
        
    @contextmanager
    def get_session(self):
        """
        Context manager for database sessions
        Automatically handles commit/rollback and closing
        
        Usage:
            with db.get_session() as session:
                session.add(token)
                # Automatically commits and closes when done
        """
        session = self.SessionLocal()
        try:
            yield session  # Give the session to the caller
            session.commit()  # Save all changes
        except Exception as e:
            session.rollback()  # Undo changes if error occurs
            raise e  # Re-raise the error so caller knows something went wrong
        finally:
            session.close()  # Always close the connection
    
    def save_token(self, token_data: Dict) -> Token:
        """
        Save or update a token in the database
        
        Args:
            token_data: Dictionary with token information
        
        Returns:
            Token object that was saved
        """
        with self.get_session() as session:
            # Check if token already exists
            existing = session.query(Token).filter_by(
                mint_address=token_data['mint_address']
            ).first()
            
            if existing:
                # Update existing token with new data
                for key, value in token_data.items():
                    setattr(existing, key, value)
                existing.last_updated = datetime.utcnow()
                return existing
            else:
                # Create new token entry
                token = Token(**token_data)
                session.add(token)
                return token
    
    def get_token(self, mint_address: str) -> Optional[Token]:
        """
        Retrieve a single token by its mint address
        
        Args:
            mint_address: The token's unique mint address
        
        Returns:
            Token object or None if not found
        """
        with self.get_session() as session:
            return session.query(Token).filter_by(mint_address=mint_address).first()
    
    def get_all_tokens(self, limit: int = 100, include_blacklisted: bool = False) -> List[Token]:
        """
        Get all tokens, ordered by most recently discovered
        
        Args:
            limit: Maximum number of tokens to return
        
        Returns:
            List of Token objects
        """
        with self.get_session() as session:
            query = session.query(Token)
            if not include_blacklisted:
                query = query.filter(
                    ~Token.watchlist_entries.any(TokenWatchlist.list_type == 'blacklist')
                )
            return query.order_by(Token.first_seen.desc()).limit(limit).all()
    
    def get_safe_tokens(self, limit: int = 100) -> List[Token]:
        """
        Get tokens that passed safety filters
        
        Args:
            limit: Maximum number of tokens to return
        
        Returns:
            List of safe Token objects
        """
        with self.get_session() as session:
            query = session.query(Token).filter(
                Token.is_safe.is_(True),
                ~Token.watchlist_entries.any(TokenWatchlist.list_type == 'blacklist')
            )
            return query.order_by(Token.last_updated.desc()).limit(limit).all()
    
    def get_graduated_tokens(self) -> List[Token]:
        """
        Get tokens that have graduated (met growth thresholds)
        
        Returns:
            List of graduated Token objects
        """
        with self.get_session() as session:
            return session.query(Token).filter_by(
                is_graduated=True
            ).order_by(Token.market_cap.desc()).all()
    
    def get_top_tokens(self, limit: int = 20) -> List[Token]:
        """
        Get top tokens by market cap (for dashboard display)
        
        Args:
            limit: Number of top tokens to return
        
        Returns:
            List of Token objects ordered by market cap
        """
        with self.get_session() as session:
            query = session.query(Token).filter(
                Token.is_safe.is_(True),
                Token.symbol.isnot(None),
                Token.symbol != '',
                Token.symbol != 'UNK',
                ~Token.watchlist_entries.any(TokenWatchlist.list_type == 'blacklist')
            )
            return query.order_by(Token.growth_rate.desc(), Token.market_cap.desc()).limit(limit).all()
    
    def save_snapshot(self, mint_address: str, data: Dict):
        """
        Save a historical snapshot of a token's data
        Used for tracking changes over time
        
        Args:
            mint_address: Token to snapshot
            data: Current token data to save
        """
        with self.get_session() as session:
            # Convert datetime objects to strings for JSON serialization
            import json
            from datetime import datetime
            
            def json_serial(obj):
                """JSON serializer for objects not serializable by default json code"""
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            # Create a copy and clean it for JSON
            clean_data = json.loads(json.dumps(data, default=json_serial))
            
            snapshot = TokenSnapshot(
                mint_address=mint_address,
                liquidity_usd=data.get('liquidity_usd', 0),
                market_cap=data.get('market_cap', 0),
                price_usd=data.get('price_usd', 0),
                holder_count=data.get('holder_count', 0),
                volume_24h=data.get('volume_24h', 0),
                full_data=clean_data
            )
            session.add(snapshot)
    
    def log_filter_result(self, mint_address: str, passed: bool, 
                         failed_filters: List[str], details: Dict):
        """
        Log the result of running filters on a token
        
        Args:
            mint_address: Token that was filtered
            passed: Whether it passed all filters
            failed_filters: List of filter names it failed
            details: Complete filter analysis data
        """
        with self.get_session() as session:
            # Convert datetime objects to strings for JSON serialization
            import json
            from datetime import datetime
            
            def json_serial(obj):
                """JSON serializer for objects not serializable by default json code"""
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            # Create a copy and clean it for JSON
            clean_details = json.loads(json.dumps(details, default=json_serial))
            
            log = FilterLog(
                mint_address=mint_address,
                passed=passed,
                failed_filters=failed_filters,
                liquidity_at_check=details.get('liquidity_usd', 0),
                holder_count_at_check=details.get('holder_count', 0),
                filter_details=clean_details
            )
            session.add(log)
    
    def get_recent_mints(self, minutes: int = 10) -> List[Token]:
        """
        Get tokens discovered in the last N minutes
        Used for "Recent Mints" dashboard section
        
        Args:
            minutes: How many minutes back to look
        
        Returns:
            List of recently discovered tokens
        """
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        with self.get_session() as session:
            return session.query(Token).filter(
                Token.first_seen >= cutoff
            ).order_by(Token.first_seen.desc()).all()

    def get_tokens_by_mints(self, mint_addresses: List[str]) -> Dict[str, Token]:
        """
        Fetch tokens for a list of mint addresses.
        """
        if not mint_addresses:
            return {}

        with self.get_session() as session:
            rows = session.query(Token).filter(Token.mint_address.in_(mint_addresses)).all()
            return {row.mint_address: row for row in rows}
    
    def get_recent_tokens(self, limit: int = 50) -> List[Token]:
        with self.get_session() as session:
            return session.query(Token).order_by(Token.first_seen.desc()).limit(limit).all()

    def mark_as_graduated(self, mint_address: str):
        """
        Mark a token as graduated
        
        Args:
            mint_address: Token to graduate
        """
        with self.get_session() as session:
            token = session.query(Token).filter_by(mint_address=mint_address).first()
            if token:
                token.is_graduated = True
                token.last_updated = datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Watchlist helpers
    # ------------------------------------------------------------------ #
    def add_to_watchlist(self, mint_address: str, list_type: str,
                         reason: Optional[str] = None, details: Optional[Dict] = None):
        """
        Add or update an entry on the watchlist.
        """
        details = details or {}
        list_type = list_type.lower()

        with self.get_session() as session:
            entry = session.query(TokenWatchlist).filter_by(
                mint_address=mint_address, list_type=list_type
            ).first()

            if entry:
                existing_details = entry.details or {}
                if details:
                    existing_details.update(details)
                entry.details = existing_details
                if reason is not None:
                    entry.reason = reason
                entry.updated_at = datetime.utcnow()
            else:
                entry = TokenWatchlist(
                    mint_address=mint_address,
                    list_type=list_type,
                    reason=reason,
                    details=details
                )
                session.add(entry)

            # Ensure opposing list entry is removed to keep state consistent
            opposite = "blacklist" if list_type == "whitelist" else "whitelist"
            session.query(TokenWatchlist).filter_by(
                mint_address=mint_address,
                list_type=opposite
            ).delete(synchronize_session=False)

    def update_watchlist_details(self, mint_address: str, updates: Dict):
        """
        Merge updates into existing watchlist entries (both whitelist/blacklist).
        """
        if not updates:
            return

        with self.get_session() as session:
            entries = session.query(TokenWatchlist).filter_by(mint_address=mint_address).all()
            for entry in entries:
                merged = entry.details or {}
                merged.update(updates)
                entry.details = merged
                entry.updated_at = datetime.utcnow()

    def remove_from_watchlist(self, mint_address: str, list_type: Optional[str] = None):
        """
        Remove a token from watchlists.
        """
        with self.get_session() as session:
            query = session.query(TokenWatchlist).filter_by(mint_address=mint_address)
            if list_type:
                query = query.filter_by(list_type=list_type.lower())
            query.delete(synchronize_session=False)

    def is_on_watchlist(self, mint_address: str, list_type: str) -> bool:
        with self.get_session() as session:
            return session.query(TokenWatchlist).filter_by(
                mint_address=mint_address,
                list_type=list_type.lower()
            ).first() is not None

    def is_blacklisted(self, mint_address: str) -> bool:
        return self.is_on_watchlist(mint_address, "blacklist")

    def is_whitelisted(self, mint_address: str) -> bool:
        return self.is_on_watchlist(mint_address, "whitelist")

    def get_watchlist(self, list_type: str) -> List[TokenWatchlist]:
        with self.get_session() as session:
            return session.query(TokenWatchlist).filter_by(
                list_type=list_type.lower()
            ).order_by(TokenWatchlist.updated_at.desc()).all()

    def get_watchlist_counts(self) -> Dict[str, int]:
        with self.get_session() as session:
            whitelist_count = session.query(TokenWatchlist).filter_by(list_type="whitelist").count()
            blacklist_count = session.query(TokenWatchlist).filter_by(list_type="blacklist").count()
            return {
                "whitelist": whitelist_count,
                "blacklist": blacklist_count,
            }

    def prune_placeholder_tokens(self) -> int:
        """
        Remove tokens with placeholder metadata (UNK/Unknown) from active tables.

        Returns:
            Number of tokens removed
        """
        removed = 0

        with self.get_session() as session:
            placeholder_filter = or_(
                Token.symbol.is_(None),
                Token.symbol == '',
                Token.symbol == 'UNK',
                Token.name.is_(None),
                Token.name == '',
                Token.name == 'Unknown'
            )
            tokens = session.query(Token).filter(placeholder_filter).all()

            for token in tokens:
                session.query(TokenWatchlist).filter_by(
                    mint_address=token.mint_address
                ).delete()
                session.query(TokenSnapshot).filter_by(
                    mint_address=token.mint_address
                ).delete()
                session.query(FilterLog).filter_by(
                    mint_address=token.mint_address
                ).delete()
                session.delete(token)
                removed += 1

        if removed:
            self.log.info("Pruned %s placeholder tokens", removed)
        return removed

    def reset_data(self):
        """
        Wipe all token-related tables (tokens, snapshots, filter logs, watchlist).
        Use with caution.
        """
        with self.get_session() as session:
            session.query(TokenWatchlist).delete()
            session.query(TokenSnapshot).delete()
            session.query(FilterLog).delete()
            session.query(Token).delete()
        self.log.info("Database reset: cleared tokens, snapshots, filter logs, and watchlists")


# Global database instance (initialized in main.py)
db: Optional[Database] = None


def init_database(connection_string: str):
    """
    Initialize the global database instance
    
    Args:
        connection_string: PostgreSQL connection URL
    """
    global db
    db = Database(connection_string)
    db.create_tables()
    return db


