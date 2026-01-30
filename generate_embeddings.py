#!/usr/bin/env python3
"""
Generate embeddings for all insights in braingym.db.
Run once (or when you add lots of new content) to enable semantic search and query interface.

Usage:
  export OPENAI_API_KEY="sk-..."
  python3 generate_embeddings.py

Takes ~10-15 minutes for 2,000+ insights (~$2 cost with text-embedding-3-small).
"""
import os
import sys


def main():
    print("🚀 Generating embeddings for all insights...")
    print("This will take ~10-15 minutes for 2,000+ insights")
    print()

    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set!")
        print("Set it with: export OPENAI_API_KEY='sk-...'")
        sys.exit(1)

    try:
        from embeddings import EmbeddingEngine
    except ImportError as e:
        print(f"❌ Could not import embeddings: {e}")
        print("Install openai: pip install openai")
        sys.exit(1)

    engine = EmbeddingEngine()

    if not engine.client:
        print("❌ OpenAI client not initialized. Check OPENAI_API_KEY.")
        sys.exit(1)

    try:
        engine.embed_all_insights()
        print()
        print("✅ All embeddings generated!")
        print("You can now use semantic search and the query interface at /query")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
