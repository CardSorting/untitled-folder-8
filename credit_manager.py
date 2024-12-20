import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from redis import Redis

class CreditManager:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        
    def _get_user_key(self, user_id: str) -> str:
        """Get Redis key for user's credit balance."""
        return f"credits:balance:{user_id}"
        
    def _get_transactions_key(self, user_id: str) -> str:
        """Get Redis key for user's transaction history."""
        return f"credits:transactions:{user_id}"
        
    def get_balance(self, user_id: str) -> int:
        """Get user's current credit balance."""
        balance = self.redis.get(self._get_user_key(user_id))
        return int(balance) if balance else 0
        
    def add_credits(self, user_id: str, amount: int, description: str, transaction_type: str) -> bool:
        """Add credits to user's balance."""
        key = self._get_user_key(user_id)
        tx_key = self._get_transactions_key(user_id)
        
        # Use Redis transaction to update balance and add transaction atomically
        with self.redis.pipeline() as pipe:
            try:
                # Watch the balance key for changes
                pipe.watch(key)
                
                # Get current balance
                current_balance = int(pipe.get(key) or 0)
                new_balance = current_balance + amount
                
                # Start transaction
                pipe.multi()
                
                # Update balance
                pipe.set(key, new_balance)
                
                # Record transaction
                transaction = {
                    "amount": amount,
                    "description": description,
                    "type": transaction_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "balance_after": new_balance
                }
                pipe.lpush(tx_key, json.dumps(transaction))
                
                # Execute transaction
                pipe.execute()
                return True
                
            except Exception:
                return False
            finally:
                pipe.reset()
    
    def spend_credits(self, user_id: str, amount: int, description: str, transaction_type: str) -> bool:
        """Spend credits from user's balance."""
        key = self._get_user_key(user_id)
        tx_key = self._get_transactions_key(user_id)
        
        # Use Redis transaction to update balance and add transaction atomically
        with self.redis.pipeline() as pipe:
            try:
                # Watch the balance key for changes
                pipe.watch(key)
                
                # Get current balance
                current_balance = int(pipe.get(key) or 0)
                
                # Check if user has enough credits
                if current_balance < amount:
                    return False
                    
                new_balance = current_balance - amount
                
                # Start transaction
                pipe.multi()
                
                # Update balance
                pipe.set(key, new_balance)
                
                # Record transaction
                transaction = {
                    "amount": -amount,
                    "description": description,
                    "type": transaction_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "balance_after": new_balance
                }
                pipe.lpush(tx_key, json.dumps(transaction))
                
                # Execute transaction
                pipe.execute()
                return True
                
            except Exception:
                return False
            finally:
                pipe.reset()
    
    def get_transaction_history(self, user_id: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
        """Get paginated transaction history for a user."""
        tx_key = self._get_transactions_key(user_id)
        
        # Get total number of transactions
        total = self.redis.llen(tx_key)
        
        # Calculate start and end indices for pagination
        start = (page - 1) * per_page
        end = start + per_page - 1
        
        # Get transactions for current page
        transactions_raw = self.redis.lrange(tx_key, start, end)
        transactions = [json.loads(tx) for tx in transactions_raw]
        
        return {
            "transactions": transactions,
            "total": total,
            "page": page,
            "per_page": per_page
        }

# Create Redis client with Upstash configuration
redis_client = Redis(
    host='adapting-panther-46467.upstash.io',
    port=6379,
    password='AbWDAAIjcDFkZTYzZmU4NzZhNjg0YTNhYjkwMzk2NTNiNTQ5YjE1MHAxMA',
    ssl=True
)

# Create global credit manager instance
credit_manager = CreditManager(redis_client)