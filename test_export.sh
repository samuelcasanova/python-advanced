#!/bin/bash

# Configuration
API_URL="http://localhost:8080"

echo "Step 1: Triggering CSV export..."
RESPONSE=$(curl -s -X POST "$API_URL/export")
TASK_ID=$(echo $RESPONSE | grep -oP '(?<="task_id":")[^"]+')

if [ -z "$TASK_ID" ]; then
    echo "Error: Failed to trigger export."
    echo "Response: $RESPONSE"
    exit 1
fi

echo "Export triggered. Task ID: $TASK_ID"

echo "Step 2: Polling for task completion..."
MAX_RETRIES=10
RETRY_COUNT=0
STATUS="PENDING"

while [[ "$STATUS" != "SUCCESS" && "$STATUS" != "FAILURE" && $RETRY_COUNT -lt $MAX_RETRIES ]]; do
    sleep 2
    RESPONSE=$(curl -s -X GET "$API_URL/export/$TASK_ID")
    STATUS=$(echo $RESPONSE | grep -oP '(?<="status":")[^"]+')
    echo "Current Status: $STATUS"
    ((RETRY_COUNT++))
done

if [ "$STATUS" == "SUCCESS" ]; then
    DOWNLOAD_PATH=$(echo $RESPONSE | grep -oP '(?<="result":")[^"]+')
    echo "Export successful! Download link: $DOWNLOAD_PATH"
    
    echo "Step 3: Downloading the CSV file..."
    curl -s -o "exported_todos.csv" "$API_URL$DOWNLOAD_PATH"
    
    if [ -f "exported_todos.csv" ]; then
        echo "File downloaded successfully: exported_todos.csv"
        echo "--- File Content Preview ---"
        head -n 5 exported_todos.csv
        echo "----------------------------"
    else
        echo "Error: Failed to download the file."
    fi
else
    echo "Error: Task failed or timed out. Final Status: $STATUS"
    exit 1
fi
