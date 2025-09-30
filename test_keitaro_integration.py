#!/usr/bin/env python3
"""
Test script to verify Keitaro integration is working correctly
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database.models import Database
from database.keitaro_models import KeitaroProfile

async def test_keitaro_integration():
    """Test that Keitaro integration is working correctly"""
    
    print("🔧 Testing Keitaro Integration")
    print("=" * 50)
    
    try:
        # Initialize database connection
        import config
        db = Database(config.DATABASE_URL)
        
        # Test 1: Check if keitaro_profiles table exists and is accessible
        print("📊 Test 1: Database table accessibility")
        query = "SELECT COUNT(*) AS count FROM keitaro_profiles"
        result = await db.execute(query, fetch=True)
        count = result[0]['count'] if result and result[0] else 0
        print(f"   ✅ keitaro_profiles table accessible - count: {count}")
        
        # Test 2: Check if keitaro_routes table exists
        print("📊 Test 2: Routes table accessibility")
        query = "SELECT COUNT(*) AS count FROM keitaro_routes"
        result = await db.execute(query, fetch=True)
        count = result[0]['count'] if result and result[0] else 0
        print(f"   ✅ keitaro_routes table accessible - count: {count}")
        
        # Test 3: Check if keitaro_events table exists
        print("📊 Test 3: Events table accessibility")
        query = "SELECT COUNT(*) AS count FROM keitaro_events"
        result = await db.execute(query, fetch=True)
        count = result[0]['count'] if result and result[0] else 0
        print(f"   ✅ keitaro_events table accessible - count: {count}")
        
        print("\n🎉 All Keitaro integration tests passed!")
        print("✅ Database tables are properly created and accessible")
        print("✅ No more 'UndefinedTable' errors should occur")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    finally:
        # Database class doesn't need explicit closing
        pass

if __name__ == "__main__":
    success = asyncio.run(test_keitaro_integration())
    sys.exit(0 if success else 1)
