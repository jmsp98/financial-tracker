#!/usr/bin/env python3
"""
Dashboard runner script for the Financial Tracker.
Starts the interactive Dash web dashboard for data visualization and analysis.
"""

import os
import sys
import logging

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def main():
    """Run the financial dashboard."""
    
    # Setup logging
    logging.basicConfig(
        level=logging.WARNING,  # Reduced verbosity - only show warnings and errors
        format='%(levelname)s: %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        # Import dashboard
        from src.dashboard import dashboard
        
        if dashboard is None:
            print("❌ Dashboard dependencies not installed!")
            print("\nInstall required packages:")
            print("  pip install dash plotly dash-bootstrap-components")
            sys.exit(1)
        
        # Try different ports if default is in use
        import socket
        port = 8050
        for attempt_port in [8050, 8051, 8052, 8053, 8054]:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', attempt_port))
                    port = attempt_port
                    break
            except OSError:
                continue
        
        print("🚀 Starting Financial Tracker Dashboard...")
        print("📊 Pure ML categorization enabled")
        print("\n" + "="*50)
        print(f"Dashboard will open at: http://127.0.0.1:{port}")
        print("Press Ctrl+C to stop the server")
        print("="*50 + "\n")
        
        # Run dashboard
        dashboard.run(debug=False, port=port)
        
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\nMake sure you're in the financial-tracker directory and have installed dependencies:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Error starting dashboard: {e}")
        logger.error(f"Dashboard startup failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()