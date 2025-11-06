#!/usr/bin/env python3
"""
Format utilities for NetLogo to PlantUML pipeline.

Provides centralized formatting functions for various data types,
including duration formatting, text formatting, and other display utilities.
"""

from typing import Union


class FormatUtils:
    """Utility class for formatting various data types."""
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """
        Format duration in seconds to human-readable format.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted string with seconds and human-readable format if > 60 seconds
        """
        if seconds < 60:
            return f"{seconds:.2f}s"
        else:
            minutes = int(seconds // 60)
            remaining_seconds = seconds % 60
            
            if minutes == 1:
                if remaining_seconds == 0:
                    return f"{seconds:.2f}s (1 minute)"
                else:
                    return f"{seconds:.2f}s (1 minute and {remaining_seconds:.0f} seconds)"
            else:
                if remaining_seconds == 0:
                    return f"{seconds:.2f}s ({minutes} minutes)"
                else:
                    return f"{seconds:.2f}s ({minutes} minutes and {remaining_seconds:.0f} seconds)"
    
    @staticmethod
    def format_bytes(bytes_value: int) -> str:
        """
        Format bytes to human-readable format.
        
        Args:
            bytes_value: Number of bytes
            
        Returns:
            Formatted string (e.g., "1.5 MB", "2.3 GB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    @staticmethod
    def format_number(number: Union[int, float], precision: int = 2) -> str:
        """
        Format number with appropriate precision and separators.
        
        Args:
            number: Number to format
            precision: Number of decimal places
            
        Returns:
            Formatted number string
        """
        if isinstance(number, int):
            return f"{number:,}"
        else:
            return f"{number:,.{precision}f}"

    @staticmethod
    def to_identifier(value: Union[str, int, float]) -> str:
        """Convert arbitrary input into a valid Python identifier.

        - Replace any non [A-Za-z0-9_] char by '_'
        - Collapse consecutive underscores
        - Prefix with '_' if it starts with a digit or becomes empty
        - Ensure final string satisfies str.isidentifier()
        """
        import re

        if value is None:
            return "_unnamed"

        text = str(value)
        ident = re.sub(r"\W", "_", text)
        ident = re.sub(r"_+", "_", ident)
        ident = ident.strip("_")
        if not ident or ident[0].isdigit():
            ident = f"_{ident}" if ident else "_unnamed"
        if not ident.isidentifier():
            ident = "_" + "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in ident)
            ident = re.sub(r"_+", "_", ident)
            if not ident or (not ident[0].isalpha() and ident[0] != "_"):
                ident = f"_{ident}"

        return ident
