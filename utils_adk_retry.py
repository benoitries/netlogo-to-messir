#!/usr/bin/env python3
"""
ADK Retry Mechanisms for Persona V3 Orchestrator
Provides retry utilities with exponential backoff for ADK workflows.
"""

import time
import asyncio
import logging
from typing import Callable, Any, Optional, Type, Tuple, List
from functools import wraps

logger = logging.getLogger(__name__)

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 1.5
DEFAULT_INITIAL_DELAY = 1.0
DEFAULT_MAX_DELAY = 60.0


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        initial_delay: float = DEFAULT_INITIAL_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
            backoff_factor: Factor for exponential backoff (e.g., 1.5 means 1s, 1.5s, 2.25s, ...)
            initial_delay: Initial delay in seconds before first retry
            max_delay: Maximum delay between retries in seconds
            retryable_exceptions: Tuple of exception types that should trigger retries
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.retryable_exceptions = retryable_exceptions or (Exception,)


def with_adk_retry(
    func: Optional[Callable] = None,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
):
    """
    Decorator to add retry logic with exponential backoff to a function.
    
    Can be used as a decorator:
        @with_adk_retry(max_retries=3)
        async def my_function():
            ...
    
    Or called directly:
        result = await with_adk_retry(my_function, max_retries=3)()
    
    Args:
        func: Function to wrap (if used as decorator without parameters)
        max_retries: Maximum number of retry attempts
        backoff_factor: Factor for exponential backoff
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        retryable_exceptions: Tuple of exception types that should trigger retries
        on_retry: Optional callback function called on each retry (attempt, exception)
    
    Returns:
        Wrapped function with retry logic
    """
    config = RetryConfig(
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        initial_delay=initial_delay,
        max_delay=max_delay,
        retryable_exceptions=retryable_exceptions,
    )
    
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        async def async_wrapper(*args, **kwargs) -> Any:
            attempt = 0
            last_exception = None
            func_name = f.__name__
            
            logger.info(
                f"[ADK] Retry configuration for {func_name}: "
                f"max_retries={config.max_retries}, "
                f"initial_delay={config.initial_delay}s, "
                f"backoff_factor={config.backoff_factor}, "
                f"max_delay={config.max_delay}s"
            )
            
            while attempt <= config.max_retries:
                try:
                    # Log attempt number
                    if attempt == 0:
                        logger.info(f"[ADK] Executing {func_name} (initial attempt)")
                    else:
                        logger.info(
                            f"[ADK] Executing {func_name} (retry attempt {attempt}/{config.max_retries})"
                        )
                    
                    # Execute the function
                    if hasattr(f, '__await__') or callable(f) and hasattr(f, '__call__'):
                        # Check if it's a coroutine function
                        import inspect
                        if inspect.iscoroutinefunction(f):
                            result = await f(*args, **kwargs)
                        else:
                            result = f(*args, **kwargs)
                    else:
                        result = await f(*args, **kwargs) if hasattr(f, '__await__') else f(*args, **kwargs)
                    
                    # Success - return result
                    if attempt > 0:
                        logger.info(
                            f"[ADK] ✓ {func_name} succeeded after {attempt} retry attempt(s) "
                            f"(total attempts: {attempt + 1})"
                        )
                    else:
                        logger.debug(f"[ADK] ✓ {func_name} succeeded on first attempt")
                    return result
                    
                except config.retryable_exceptions as e:
                    attempt += 1
                    last_exception = e
                    exception_type = type(e).__name__
                    exception_msg = str(e)
                    
                    logger.warning(
                        f"[ADK] ✗ {func_name} failed on attempt {attempt}/{config.max_retries + 1}: "
                        f"{exception_type}: {exception_msg}"
                    )
                    
                    # Check if we should retry
                    if attempt > config.max_retries:
                        logger.error(
                            f"[ADK] ✗✗ {func_name} exhausted all {config.max_retries} retry attempts. "
                            f"Total attempts: {config.max_retries + 1}. "
                            f"Last error: {exception_type}: {exception_msg}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        config.initial_delay * (config.backoff_factor ** (attempt - 1)),
                        config.max_delay
                    )
                    
                    # Log retry attempt with details
                    logger.warning(
                        f"[ADK] ⟳ Retrying {func_name} in {delay:.2f}s "
                        f"(attempt {attempt + 1}/{config.max_retries + 1} will be made). "
                        f"Backoff calculation: {config.initial_delay}s * {config.backoff_factor}^{attempt - 1} = {delay:.2f}s"
                    )
                    
                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(attempt, e)
                        except Exception as callback_error:
                            logger.warning(f"[ADK] Retry callback failed: {callback_error}")
                    
                    # Wait before retry (always use asyncio for async wrapper)
                    await asyncio.sleep(delay)
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Function {f.__name__} failed after {attempt} attempts")
        
        @wraps(f)
        def sync_wrapper(*args, **kwargs) -> Any:
            attempt = 0
            last_exception = None
            func_name = f.__name__
            
            logger.info(
                f"[ADK] Retry configuration for {func_name}: "
                f"max_retries={config.max_retries}, "
                f"initial_delay={config.initial_delay}s, "
                f"backoff_factor={config.backoff_factor}, "
                f"max_delay={config.max_delay}s"
            )
            
            while attempt <= config.max_retries:
                try:
                    # Log attempt number
                    if attempt == 0:
                        logger.info(f"[ADK] Executing {func_name} (initial attempt)")
                    else:
                        logger.info(
                            f"[ADK] Executing {func_name} (retry attempt {attempt}/{config.max_retries})"
                        )
                    
                    result = f(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(
                            f"[ADK] ✓ {func_name} succeeded after {attempt} retry attempt(s) "
                            f"(total attempts: {attempt + 1})"
                        )
                    else:
                        logger.debug(f"[ADK] ✓ {func_name} succeeded on first attempt")
                    return result
                    
                except config.retryable_exceptions as e:
                    attempt += 1
                    last_exception = e
                    exception_type = type(e).__name__
                    exception_msg = str(e)
                    
                    logger.warning(
                        f"[ADK] ✗ {func_name} failed on attempt {attempt}/{config.max_retries + 1}: "
                        f"{exception_type}: {exception_msg}"
                    )
                    
                    if attempt > config.max_retries:
                        logger.error(
                            f"[ADK] ✗✗ {func_name} exhausted all {config.max_retries} retry attempts. "
                            f"Total attempts: {config.max_retries + 1}. "
                            f"Last error: {exception_type}: {exception_msg}"
                        )
                        raise
                    
                    delay = min(
                        config.initial_delay * (config.backoff_factor ** (attempt - 1)),
                        config.max_delay
                    )
                    
                    logger.warning(
                        f"[ADK] ⟳ Retrying {func_name} in {delay:.2f}s "
                        f"(attempt {attempt + 1}/{config.max_retries + 1} will be made). "
                        f"Backoff calculation: {config.initial_delay}s * {config.backoff_factor}^{attempt - 1} = {delay:.2f}s"
                    )
                    
                    if on_retry:
                        try:
                            on_retry(attempt, e)
                        except Exception as callback_error:
                            logger.warning(f"[ADK] Retry callback failed: {callback_error}")
                    
                    time.sleep(delay)
            
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Function {f.__name__} failed after {attempt} attempts")
        
        # Determine if function is async
        import inspect
        if inspect.iscoroutinefunction(f):
            return async_wrapper
        else:
            return sync_wrapper
    
    # Handle both @with_adk_retry and @with_adk_retry(...) usage
    if func is None:
        return decorator
    else:
        return decorator(func)


async def execute_with_retry(
    func: Callable,
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    initial_delay: float = DEFAULT_INITIAL_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    external_logger: Optional[logging.Logger] = None,
    **kwargs
) -> Any:
    """
    Execute a function with retry logic and exponential backoff.
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        max_retries: Maximum number of retry attempts
        backoff_factor: Factor for exponential backoff
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        retryable_exceptions: Tuple of exception types that should trigger retries
        on_retry: Optional callback function called on each retry
        **kwargs: Keyword arguments for the function
    
    Returns:
        Result of the function execution
    
    Raises:
        Last exception encountered if all retries are exhausted
    """
    config = RetryConfig(
        max_retries=max_retries,
        backoff_factor=backoff_factor,
        initial_delay=initial_delay,
        max_delay=max_delay,
        retryable_exceptions=retryable_exceptions or (Exception,),
    )
    
    attempt = 0
    last_exception = None
    func_name = func.__name__ if hasattr(func, '__name__') else 'unknown'
    retry_logger = external_logger or logger
    
    retry_logger.info(
        f"[ADK] Retry configuration for {func_name}: "
        f"max_retries={config.max_retries}, "
        f"initial_delay={config.initial_delay}s, "
        f"backoff_factor={config.backoff_factor}, "
        f"max_delay={config.max_delay}s"
    )
    
    while attempt <= config.max_retries:
        try:
            import inspect
            if attempt == 0:
                retry_logger.info(f"[ADK] Executing {func_name} (initial attempt)")
            else:
                retry_logger.info(
                    f"[ADK] Executing {func_name} (retry attempt {attempt}/{config.max_retries})"
                )
            
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            if attempt > 0:
                retry_logger.info(
                    f"[ADK] ✓ {func_name} succeeded after {attempt} retry attempt(s) "
                    f"(total attempts: {attempt + 1})"
                )
            else:
                retry_logger.debug(f"[ADK] ✓ {func_name} succeeded on first attempt")
            return result
            
        except config.retryable_exceptions as e:
            attempt += 1
            last_exception = e
            exception_type = type(e).__name__
            exception_msg = str(e)
            
            retry_logger.warning(
                f"[ADK] ✗ {func_name} failed on attempt {attempt}/{config.max_retries + 1}: "
                f"{exception_type}: {exception_msg}"
            )
            
            if attempt > config.max_retries:
                retry_logger.error(
                    f"[ADK] ✗✗ {func_name} exhausted all {config.max_retries} retry attempts. "
                    f"Total attempts: {config.max_retries + 1}. "
                    f"Last error: {exception_type}: {exception_msg}"
                )
                raise
            
            # Calculate delay with exponential backoff
            delay = min(
                config.initial_delay * (config.backoff_factor ** (attempt - 1)),
                config.max_delay
            )
            
            retry_logger.warning(
                f"[ADK] ⟳ Retrying {func_name} in {delay:.2f}s "
                f"(attempt {attempt + 1}/{config.max_retries + 1} will be made). "
                f"Backoff calculation: {config.initial_delay}s * {config.backoff_factor}^{attempt - 1} = {delay:.2f}s"
            )
            
            if on_retry:
                try:
                    on_retry(attempt, e)
                except Exception as callback_error:
                    retry_logger.warning(f"[ADK] Retry callback failed: {callback_error}")
            
            import asyncio
            await asyncio.sleep(delay)
    
    if last_exception:
        raise last_exception
    raise RuntimeError(f"Function failed after {attempt} attempts")

