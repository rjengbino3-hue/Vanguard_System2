# test_db.py
from src.database import save_violation, get_recent_violations

print("🚀 Step 1: Sending a test violation payload to Supabase...")
event_id = save_violation(
    device_id="LAPTOP-TEST-ENVIRONMENT",
    violation_type="helmet_violation_per_motorcycle",
    class_name="motorcycle_with_no_or_invalid_helmet",
    confidence=0.92,
    location="Ramon Magsaysay Ave Station",
    latitude=6.7483,
    longitude=125.3571
)

if event_id:
    print(f"✅ Success! Data sent. Generated Event ID: {event_id}")
    
    print("\n🔍 Step 2: Querying the cloud database to confirm row existence...")
    records = get_recent_violations(limit=1)
    
    if records:
        print("🎉 Verification complete! Here is the data pulled from the cloud:")
        print(records[0])
    else:
        print("❌ Sent successfully, but failed to retrieve the log.")
else:
    print("❌ Connection test failed. Check your URL, Key, or network path.")