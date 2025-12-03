from typing import Dict, Tuple, Optional
import time
import threading

class LoginAttemptTracker:
    def __init__(self, max_attempts: int = 3, lockout_duration: int = 900):  # 15 minutes = 900 seconds
        self.failed_attempts: Dict[str, Tuple[int, float]] = {}  # username -> (count, timestamp)
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration
        self.lock = threading.Lock()
        
        # Start a background thread to clean up expired entries
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """Start a background thread to periodically clean up expired lockouts"""
        def cleanup():
            while True:
                time.sleep(300)  # Check every 5 minutes
                self._cleanup_expired_lockouts()
                
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()
    
    def _cleanup_expired_lockouts(self):
        """Remove expired lockout entries"""
        current_time = time.time()
        with self.lock:
            to_remove = []
            for username, (attempts, timestamp) in self.failed_attempts.items():
                if current_time - timestamp > self.lockout_duration:
                    to_remove.append(username)
            
            for username in to_remove:
                del self.failed_attempts[username]
    
    def record_failed_attempt(self, username: str) -> None:
        """Record a failed login attempt for a username"""
        current_time = time.time()
        
        with self.lock:
            if username not in self.failed_attempts:
                self.failed_attempts[username] = (1, current_time)
            else:
                attempts, _ = self.failed_attempts[username]
                self.failed_attempts[username] = (attempts + 1, current_time)
    
    def is_locked_out(self, username: str) -> Tuple[bool, Optional[int]]:
        """
        Check if a username is locked out
        Returns: (is_locked, seconds_remaining)
        """
        current_time = time.time()
        
        with self.lock:
            if username in self.failed_attempts:
                attempts, timestamp = self.failed_attempts[username]
                
                # Check if max attempts reached and still in lockout period
                if attempts >= self.max_attempts:
                    time_elapsed = current_time - timestamp
                    if time_elapsed < self.lockout_duration:
                        remaining = int(self.lockout_duration - time_elapsed)
                        return True, remaining
                    else:
                        # Lockout period expired, reset attempts
                        del self.failed_attempts[username]
            
            return False, None
    
    def reset_attempts(self, username: str) -> None:
        """Reset failed attempts after successful login"""
        with self.lock:
            if username in self.failed_attempts:
                del self.failed_attempts[username]


# Create a global instance
login_tracker = LoginAttemptTracker()
