#!/usr/bin/env python3
"""
Brain Gym - Main CLI
Processes WhatsApp exports and builds your insight database
"""
import sys
import argparse
from pathlib import Path
from typing import List

from parser import WhatsAppParser
from database import BrainGymDB
from classifier import InsightClassifier


class BrainGym:
    """Main Brain Gym application"""
    
    def __init__(self, db_path: str = "braingym.db"):
        self.db = BrainGymDB(db_path)
        self.parser = WhatsAppParser()
        self.classifier = InsightClassifier()
    
    def process_whatsapp_file(self, file_path: str) -> dict:
        """Process a WhatsApp export file"""
        print(f"\n📱 Processing WhatsApp export: {file_path}")
        
        # Parse the file
        messages = self.parser.parse_file(file_path)
        print(f"✓ Parsed {len(messages)} messages")
        
        # Extract insights
        insights = self.parser.extract_insights()
        print(f"✓ Extracted {len(insights)} insights")
        
        # Classify and store
        stored_count = 0
        duplicate_count = 0
        
        for insight in insights:
            # Classify and tag
            tags = self.classifier.classify(
                insight['content'],
                insight.get('context_message', '')
            )
            
            # Add source-specific tags
            if insight.get('source_type') and insight.get('source_url'):
                tags = self.classifier.add_source_tags(
                    tags,
                    insight['source_type'],
                    insight['source_url']
                )
            
            # Enhance tags
            tags = self.classifier.enhance_tags(tags)
            
            # Check if high value
            if self.classifier.is_high_value(insight['content'], insight.get('context_message', '')):
                tags.append('high_value')
            
            # Store in database
            result = self.db.insert_insight(
                content=insight['content'],
                source_url=insight.get('source_url'),
                source_type=insight.get('source_type'),
                shared_by=insight.get('shared_by'),
                shared_date=insight.get('shared_date'),
                context_message=insight.get('context_message'),
                tags=tags
            )
            
            if result:
                stored_count += 1
            else:
                duplicate_count += 1
        
        print(f"✓ Stored {stored_count} new insights")
        if duplicate_count > 0:
            print(f"⚠ Skipped {duplicate_count} duplicates")
        
        return {
            'messages': len(messages),
            'insights': len(insights),
            'stored': stored_count,
            'duplicates': duplicate_count
        }
    
    def process_multiple_files(self, file_paths: List[str]) -> dict:
        """Process multiple WhatsApp export files"""
        total_results = {
            'messages': 0,
            'insights': 0,
            'stored': 0,
            'duplicates': 0
        }
        
        for file_path in file_paths:
            if not Path(file_path).exists():
                print(f"❌ File not found: {file_path}")
                continue
            
            results = self.process_whatsapp_file(file_path)
            
            for key in total_results:
                total_results[key] += results[key]
        
        return total_results
    
    def show_stats(self):
        """Display database statistics"""
        stats = self.db.get_stats()
        
        print("\n" + "="*60)
        print("📊 BRAIN GYM STATISTICS")
        print("="*60)
        
        print(f"\n📚 Total Insights: {stats['total_insights']}")
        
        if stats.get('by_status'):
            print(f"\n📋 By Status:")
            for status, count in stats['by_status'].items():
                print(f"   {status.capitalize()}: {count}")
        
        if stats.get('by_type'):
            print(f"\n🔗 By Type:")
            for source_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
                print(f"   {source_type.capitalize()}: {count}")
        
        if stats.get('top_sharers'):
            print(f"\n👥 Top Sharers:")
            for i, (sharer, count) in enumerate(stats['top_sharers'].items(), 1):
                print(f"   {i}. {sharer}: {count} insights")
        
        print("\n" + "="*60)
    
    def show_recent_insights(self, limit: int = 10):
        """Display recent insights"""
        insights = self.db.get_insights(limit=limit)
        
        print("\n" + "="*60)
        print(f"🧠 RECENT INSIGHTS (showing {len(insights)} of {limit})")
        print("="*60)
        
        for i, insight in enumerate(insights, 1):
            print(f"\n[{i}] ID: {insight['id']}")
            print(f"👤 Shared by: {insight['shared_by']}")
            print(f"📅 Date: {insight['shared_date']}")
            print(f"🔖 Type: {insight['source_type'] or 'N/A'}")
            
            if insight['tags']:
                tags = insight['tags'].split(',')
                print(f"🏷️  Tags: {', '.join(tags)}")
            
            # Truncate long content
            content = insight['content']
            if len(content) > 150:
                content = content[:150] + "..."
            print(f"💭 Content: {content}")
            
            if insight['source_url']:
                print(f"🔗 URL: {insight['source_url']}")
            
            print("-" * 60)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Brain Gym - Ferment ideas into original thinking"
    )
    
    parser.add_argument(
        'files',
        nargs='*',
        help='WhatsApp export files to process'
    )
    
    parser.add_argument(
        '--db',
        default='braingym.db',
        help='Database file path (default: braingym.db)'
    )
    
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics'
    )
    
    parser.add_argument(
        '--show',
        type=int,
        metavar='N',
        help='Show N recent insights'
    )
    
    args = parser.parse_args()
    
    # Initialize Brain Gym
    brain_gym = BrainGym(db_path=args.db)
    
    # Process files if provided
    if args.files:
        print("🧠 Brain Gym - Processing WhatsApp Exports")
        print("="*60)
        
        results = brain_gym.process_multiple_files(args.files)
        
        print("\n" + "="*60)
        print("✅ PROCESSING COMPLETE")
        print("="*60)
        print(f"Total messages parsed: {results['messages']}")
        print(f"Total insights extracted: {results['insights']}")
        print(f"New insights stored: {results['stored']}")
        if results['duplicates'] > 0:
            print(f"Duplicates skipped: {results['duplicates']}")
        
        # Auto-show stats after processing
        brain_gym.show_stats()
        
        # Auto-show first 10 insights
        brain_gym.show_recent_insights(limit=10)
    
    # Show stats if requested
    elif args.stats:
        brain_gym.show_stats()
    
    # Show recent insights if requested
    elif args.show:
        brain_gym.show_recent_insights(limit=args.show)
    
    else:
        parser.print_help()
        print("\n💡 Example usage:")
        print("  python main.py chat1.txt chat2.txt chat3.txt")
        print("  python main.py --stats")
        print("  python main.py --show 20")


if __name__ == "__main__":
    main()
