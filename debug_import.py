import sys
import os

# Add current directory to path so we can import our own modules
sys.path.insert(0, os.getcwd())

try:
    print("Current working directory:", os.getcwd())
    print("Python path:", sys.path[:3])
    
    # Import and see what's in handlers
    import actions.handlers
    print("handlers module imported successfully")
    print("handlers module contents:", dir(actions.handlers))
    
    # Try to import the handler module specifically  
    from actions.handlers import second_trip_meeting
    print("second_trip_meeting imported successfully")
    
except Exception as e:
    print("Error:", str(e))
    import traceback
    traceback.print_exc()
