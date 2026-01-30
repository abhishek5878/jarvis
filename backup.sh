#!/bin/bash
# Brain Gym Database Backup Utility

DB_FILE="braingym.db"
BACKUP_DIR="backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/braingym_${DATE}.db"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Check if database exists
if [ ! -f "$DB_FILE" ]; then
    echo "❌ Error: Database file '$DB_FILE' not found"
    exit 1
fi

# Create backup
cp "$DB_FILE" "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    # Get file size
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    
    echo "✅ Backup created successfully!"
    echo "📁 File: $BACKUP_FILE"
    echo "💾 Size: $SIZE"
    
    # Count total backups
    BACKUP_COUNT=$(ls -1 "$BACKUP_DIR" | wc -l | tr -d ' ')
    echo "📊 Total backups: $BACKUP_COUNT"
    
    # Show oldest and newest
    OLDEST=$(ls -1t "$BACKUP_DIR" | tail -1)
    echo "🕐 Oldest: $OLDEST"
    echo "🕑 Newest: $(basename $BACKUP_FILE)"
else
    echo "❌ Backup failed"
    exit 1
fi
