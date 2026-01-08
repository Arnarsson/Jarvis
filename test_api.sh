#!/bin/bash

echo "2. Creating test entity (JARVIS)..."
curl -s -X POST http://localhost:8000/memory/entity \
  -H "Content-Type: application/json" \
  -d '{"name":"JARVIS System","type":"project","metadata":{"status":"operational"}}' | python3 -m json.tool

echo -e "\n3. Adding observation..."
curl -s -X POST http://localhost:8000/memory/observation \
  -H "Content-Type: application/json" \
  -d '{"entity_name":"JARVIS System","content":"Successfully deployed Memory API on port 8000. All core endpoints operational including search, entities, observations.","source":"system_test"}' | python3 -m json.tool

echo -e "\n4. Searching for JARVIS..."
curl -s "http://localhost:8000/memory/search?q=JARVIS&limit=5" | python3 -m json.tool

echo -e "\n5. Getting system stats..."
curl -s http://localhost:8000/memory/stats | python3 -m json.tool

echo -e "\n✅ API Test Complete!"
