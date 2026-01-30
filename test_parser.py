#!/usr/bin/env python3
"""
Test script to verify the Brain Gym parser works correctly
"""
from parser import WhatsAppParser
from database import BrainGymDB
from classifier import InsightClassifier


def test_parser():
    """Test the WhatsApp parser with sample data"""
    print("🧪 Testing WhatsApp Parser")
    print("="*60)
    
    parser = WhatsAppParser()
    
    # Parse the sample file
    messages = parser.parse_file('sample_whatsapp_export.txt')
    
    print(f"\n✓ Parsed {len(messages)} messages")
    
    # Show first 3 messages
    print("\n📱 Sample Messages:")
    for i, msg in enumerate(messages[:3], 1):
        print(f"\n[{i}] {msg.sender} at {msg.datetime_str}")
        print(f"    Content: {msg.content[:80]}...")
        if msg.urls:
            print(f"    URLs: {msg.urls}")
    
    # Get statistics
    stats = parser.get_statistics()
    print("\n📊 Parsing Stats:")
    print(f"   Total messages: {stats['total_messages']}")
    print(f"   Messages with URLs: {stats['messages_with_urls']}")
    print(f"   Total URLs: {stats['total_urls']}")
    print(f"   Unique senders: {stats['unique_senders']}")
    
    # Extract insights
    insights = parser.extract_insights()
    print(f"\n✓ Extracted {len(insights)} insights")
    
    # Show first 2 insights
    print("\n💡 Sample Insights:")
    for i, insight in enumerate(insights[:2], 1):
        print(f"\n[{i}] Type: {insight['source_type']}")
        print(f"    Shared by: {insight['shared_by']}")
        print(f"    Content: {insight['content'][:80]}...")
        if insight['source_url']:
            print(f"    URL: {insight['source_url']}")


def test_classifier():
    """Test the content classifier"""
    print("\n\n🧪 Testing Content Classifier")
    print("="*60)
    
    classifier = InsightClassifier()
    
    test_content = [
        ("This framework on first principles thinking changed how I solve problems", "philosophy"),
        ("How to validate your startup idea in 48 hours", "startups, tactical"),
        ("The biggest mistake founders make is building before talking to users", "startups, cautionary"),
    ]
    
    for content, expected_themes in test_content:
        tags = classifier.classify(content)
        tags = classifier.enhance_tags(tags)
        
        print(f"\nContent: {content[:60]}...")
        print(f"Tags: {', '.join(tags)}")
        print(f"High Value: {classifier.is_high_value(content)}")


def test_database():
    """Test database operations"""
    print("\n\n🧪 Testing Database")
    print("="*60)
    
    # Use a test database
    db = BrainGymDB("test_braingym.db")
    
    # Insert a test insight
    insight_id = db.insert_insight(
        content="Test insight about mental models",
        source_url="https://example.com/test",
        source_type="article",
        shared_by="Test User",
        shared_date="30/01/2026, 10:00",
        context_message="This is a test message",
        tags=["mental_models", "learning", "test"]
    )
    
    print(f"\n✓ Inserted insight with ID: {insight_id}")
    
    # Get stats
    stats = db.get_stats()
    print(f"\nDatabase Stats:")
    print(f"   Total insights: {stats['total_insights']}")
    
    # Get insights
    insights = db.get_insights(limit=1)
    if insights:
        print(f"\n✓ Retrieved insight:")
        print(f"   Content: {insights[0]['content']}")
        print(f"   Tags: {insights[0]['tags']}")
    
    print("\n⚠ Note: Test database saved as 'test_braingym.db'")


if __name__ == "__main__":
    print("\n🧠 Brain Gym Test Suite")
    print("="*60)
    
    try:
        test_parser()
        test_classifier()
        test_database()
        
        print("\n\n✅ All tests passed!")
        print("\n💡 Next steps:")
        print("   1. Try: python main.py sample_whatsapp_export.txt")
        print("   2. Export your real WhatsApp chats")
        print("   3. Process them: python main.py chat1.txt chat2.txt chat3.txt")
        
    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}")
        print("Make sure 'sample_whatsapp_export.txt' exists in the same directory")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
