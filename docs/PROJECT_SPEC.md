# DELHI METRO APP - COMPLETE PROJECT SPECIFICATION

## PROJECT OVERVIEW

**Name:** Delhi Metro Navigator Pro
**Version:** 1.0
**Status:** Development (for placement portfolio)
**Estimated Timeline:** 8 weeks
**Target Companies:** Google, Amazon, Microsoft, Flipkart, Ola, Swiggy

---

## EXECUTIVE SUMMARY

A real-time Delhi Metro navigation app combining:
- ✅ **Dijkstra's shortest path algorithm** with real-time constraints
- ✅ **NVIDIA RAG** for natural language understanding (Hindi/English)
- ✅ **Offline-first** architecture with SQLite caching
- ✅ **Live tracking** with GPS + real-time metro positions
- ✅ **Disruption alerts** (closed lines, delays, platform changes)
- ✅ **Platform-specific** directions (which platform, exit, escalators)
- ✅ **Voice input** for hands-free navigation

---

## TECH STACK

### Backend
- **Language:** Python 3.9+
- **Framework:** Flask + FastAPI
- **Database:** PostgreSQL (production), SQLite (offline)
- **Cache:** Redis (real-time line status)
- **Vector Store:** FAISS (station embeddings)
- **Message Queue:** RabbitMQ (disruption broadcasts)
- **LLM:** NVIDIA NeMo (via Hugging Face)

### Frontend
- **Mobile:** Flutter (iOS + Android)
- **Web:** React.js (optional, for desktop)
- **Maps:** Google Maps API + custom overlay
- **Location:** Native GPS + background location tracking

### Real-time
- **WebSocket:** Socket.io (live disruptions)
- **Message Broker:** Redis Pub/Sub (line status)
- **Push Notifications:** Firebase Cloud Messaging

### Deployment
- **Backend:** Docker + Kubernetes
- **Database:** PostgreSQL on AWS RDS
- **Cache:** Redis on AWS ElastiCache
- **Storage:** AWS S3 (metro data files)
- **Monitoring:** Prometheus + Grafana

---

## ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                     MOBILE APP (Flutter)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Voice Input  │  │ GPS Location │  │ Route Screen │      │
│  │ (Hindi/Eng)  │  │ Tracking     │  │ + Live Track │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼──────────────────┼──────────────────┼──────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                    ┌────────▼────────┐
                    │  API Gateway    │
                    │  (FastAPI)      │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼─────┐      ┌──────▼──────┐      ┌─────▼───────┐
   │   RAG     │      │   Dijkstra  │      │ Disruptions │
   │  Engine   │      │   Engine    │      │   Service   │
   │ (NeMo)    │      │  (Graph)    │      │ (WebSocket) │
   └────┬─────┘      └──────┬──────┘      └─────┬───────┘
        │                   │                    │
   ┌────▼─────────────┬─────▼──────────────┬────▼───────────┐
   │                  │                    │                │
┌──▼────────┐  ┌─────▼──────────┐  ┌──────▼──────┐  ┌──────▼──────┐
│  FAISS    │  │   PostgreSQL   │  │    Redis    │  │  RabbitMQ   │
│Embeddings │  │   (Stations,   │  │  (Real-time)│  │(Event Queue)│
│           │  │   Routes)      │  │             │  │             │
└───────────┘  └────────────────┘  └─────────────┘  └─────────────┘

                  ┌──────────────────────┐
                  │  SQLite (Offline DB) │
                  │ (Cached metro data)  │
                  └──────────────────────┘
```

---

## DATABASE SCHEMA

### PostgreSQL (Main Database)

#### 1. STATIONS TABLE
```sql
CREATE TABLE stations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    hindi_name VARCHAR(100),
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    line_ids TEXT[] (e.g., ARRAY[1, 3, 5]),
    is_interchange BOOLEAN DEFAULT FALSE,
    opening_year INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Example
-- id: 1, name: 'Dwarka', hindi_name: 'द्वारका', latitude: 28.5921,
-- longitude: 77.0460, line_ids: [1] (Blue Line), is_interchange: false
```

#### 2. LINES TABLE
```sql
CREATE TABLE lines (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    color VARCHAR(20),
    total_stations INTEGER,
    operational_status VARCHAR(20) DEFAULT 'OPERATIONAL',
    status_updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Lines: Blue, Yellow, Red, Green, Pink, Purple, Orange, Silver,
-- Gold, Magenta, Rapid Metro, Airport Express
```

#### 3. LINE_STATUS (Real-time) TABLE
```sql
CREATE TABLE line_status (
    id SERIAL PRIMARY KEY,
    line_id INTEGER REFERENCES lines(id),
    status VARCHAR(50), -- 'OPERATIONAL', 'DELAYED', 'CLOSED', 'PARTIAL'
    affected_stations TEXT[], -- JSON array of station names
    reason VARCHAR(500),
    delay_minutes INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by VARCHAR(100) DEFAULT 'SYSTEM',
    UNIQUE(line_id, updated_at)
);
```

#### 4. ROUTES TABLE (Station connections)
```sql
CREATE TABLE routes (
    id SERIAL PRIMARY KEY,
    from_station_id INTEGER REFERENCES stations(id),
    to_station_id INTEGER REFERENCES stations(id),
    line_id INTEGER REFERENCES lines(id),
    distance_km DECIMAL(5, 2),
    travel_time_seconds INTEGER,
    sequence_order INTEGER, -- Order in line
    is_direct BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(from_station_id, to_station_id, line_id)
);
```

#### 5. PLATFORMS TABLE
```sql
CREATE TABLE platforms (
    id SERIAL PRIMARY KEY,
    station_id INTEGER REFERENCES stations(id),
    line_id INTEGER REFERENCES lines(id),
    platform_number INTEGER,
    direction VARCHAR(100), -- 'Towards X' or 'Towards Y'
    platform_type VARCHAR(20), -- 'ISLAND', 'SIDE', 'SPLIT'
    escalators BOOLEAN,
    elevators BOOLEAN,
    exits TEXT[], -- JSON array of exit names
    amenities TEXT[], -- JSON: ['wifi', 'toilet', 'shop', 'atm']
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(station_id, line_id, platform_number)
);
```

#### 6. DISRUPTIONS TABLE (Historical)
```sql
CREATE TABLE disruptions (
    id SERIAL PRIMARY KEY,
    line_id INTEGER REFERENCES lines(id),
    station_ids INTEGER[],
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    reason VARCHAR(500),
    severity VARCHAR(20), -- 'MINOR', 'MAJOR', 'CRITICAL'
    type VARCHAR(50), -- 'CLOSURE', 'DELAY', 'PLATFORM_CHANGE'
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 7. USER_ROUTES (Save favorite routes)
```sql
CREATE TABLE user_routes (
    id SERIAL PRIMARY KEY,
    user_id UUID,
    from_station_id INTEGER REFERENCES stations(id),
    to_station_id INTEGER REFERENCES stations(id),
    saved_at TIMESTAMP DEFAULT NOW(),
    frequency_count INTEGER DEFAULT 1
);
```

#### 8. METRO_POSITIONS (Live train positions)
```sql
CREATE TABLE metro_positions (
    id SERIAL PRIMARY KEY,
    line_id INTEGER REFERENCES lines(id),
    train_id VARCHAR(50),
    current_station_id INTEGER REFERENCES stations(id),
    direction VARCHAR(100), -- 'towards X'
    speed_kmh DECIMAL(5, 2),
    next_station_id INTEGER,
    eta_next_seconds INTEGER,
    passenger_count INTEGER,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Auto-purge old records (keep last 24 hours)
CREATE INDEX idx_metro_positions_updated ON metro_positions(updated_at);
```

---

### SQLite (Offline Database)

```sql
-- Minimal copy for offline use
CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY,
    name TEXT,
    hindi_name TEXT,
    latitude REAL,
    longitude REAL,
    lines TEXT
);

CREATE TABLE IF NOT EXISTS routes (
    from_station TEXT,
    to_station TEXT,
    line TEXT,
    distance REAL,
    duration INTEGER
);

CREATE TABLE IF NOT EXISTS line_status (
    line TEXT PRIMARY KEY,
    status TEXT,
    last_updated TIMESTAMP
);
```

---

## API ENDPOINTS

### 1. Route Finding
```
POST /api/v1/routes/find
{
    "from_station": "Dwarka",
    "to_station": "India Gate",
    "user_location": {"lat": 28.5921, "lng": 77.0460},
    "preferences": {
        "max_transfers": 2,
        "avoid_lines": ["Yellow"],
        "accessibility": true
    },
    "language": "hi"
}

Response:
{
    "routes": [
        {
            "id": "route_123",
            "segments": [
                {
                    "from": "Dwarka",
                    "to": "Rajiv Chowk",
                    "line": "Blue",
                    "line_color": "#0066CC",
                    "platform": "Platform 1",
                    "direction": "Towards Noida",
                    "stops_count": 5,
                    "duration_seconds": 600,
                    "distance_km": 8.5,
                    "platforms": [
                        {
                            "number": 1,
                            "type": "ISLAND",
                            "exit": "Exit A - Towards IGI Airport"
                        }
                    ]
                },
                {
                    "from": "Rajiv Chowk",
                    "to": "India Gate",
                    "line": "Red",
                    "line_color": "#FF0000",
                    "platform": "Platform 2",
                    "transfer_time_seconds": 300,
                    "duration_seconds": 480
                }
            ],
            "total_duration_seconds": 1380,
            "total_transfers": 1,
            "eta_minutes": 23,
            "distance_km": 15.2,
            "alerts": [
                {
                    "type": "DELAY",
                    "line": "Red",
                    "message": "Red Line experiencing 2-3 min delay"
                }
            ]
        }
    ]
}
```

### 2. Natural Language Query (RAG)
```
POST /api/v1/query/natural
{
    "query": "Mujhe Dwarka se India Gate jana hai, Yellow Line se mat nikalna",
    "language": "hi",
    "user_location": {"lat": 28.5921, "lng": 77.0460}
}

Response:
{
    "understood_intent": {
        "from": "Dwarka",
        "to": "India Gate",
        "constraints": ["avoid_yellow_line"],
        "language_detected": "hi"
    },
    "routes": [...] (same as above)
}
```

### 3. Live Disruptions (WebSocket)
```
WS /api/v1/disruptions/live

Events:
{
    "type": "LINE_STATUS_UPDATE",
    "line": "Yellow",
    "status": "PARTIAL_CLOSURE",
    "affected_stations": ["Jantar Mantar", "Central Secretariat"],
    "reason": "Signal failure",
    "eta_resumption": "14:30"
}
```

### 4. Station Details
```
GET /api/v1/stations/{station_id}

Response:
{
    "id": 1,
    "name": "Dwarka",
    "hindi_name": "द्वारका",
    "location": {"lat": 28.5921, "lng": 77.0460},
    "lines": [
        {
            "id": 1,
            "name": "Blue Line",
            "status": "OPERATIONAL",
            "platforms": [
                {
                    "number": 1,
                    "direction": "Towards Noida",
                    "amenities": ["wifi", "atm", "shop"],
                    "accessibility": true
                }
            ]
        }
    ]
}
```

### 5. Metro Positions (Real-time)
```
GET /api/v1/lines/{line_id}/trains

Response:
{
    "line": "Blue",
    "trains": [
        {
            "id": "BL_001",
            "current_station": "Dwarka",
            "next_station": "Dwarka Mor",
            "eta_next_seconds": 120,
            "passenger_percentage": 65
        },
        {
            "id": "BL_002",
            "current_station": "Rajiv Chowk",
            "next_station": "Yamuna Bank",
            "eta_next_seconds": 90,
            "passenger_percentage": 45
        }
    ]
}
```

---

## CORE ALGORITHMS & IMPLEMENTATIONS

### 1. DIJKSTRA'S WITH REAL-TIME CONSTRAINTS

```python
# pseudo-code
def dijkstra_metro_routing(graph, start, end, constraints, real_time_data):
    """
    find_route(from_station, to_station, preferences)

    Constraints Applied:
    - Skip closed lines (from real_time_data)
    - Add delay penalty for delayed lines
    - Add transfer penalty
    - Add accessibility preference (elevators, etc.)

    Time Complexity: O(E log V)
    Space Complexity: O(V + E)
    """

    # 1. Build dynamic graph with real-time weights
    graph = build_weighted_graph(all_routes, line_status)

    # 2. Apply constraints
    if "avoid_lines" in constraints:
        for line in constraints["avoid_lines"]:
            remove_line_from_graph(graph, line)

    # 3. Dijkstra with multi-objective
    # Minimize: time + transfers + accessibility penalties
    distances = dijkstra(graph, start, end)

    # 4. Extract K best routes
    top_routes = extract_k_best_routes(distances, k=3)

    return top_routes
```

### 2. NVIDIA RAG (Natural Language Understanding)

```python
# pseudo-code
class MetroRAG:
    def __init__(self):
        self.llm = HuggingFaceLLM("nvidia/nemotron-3-8b-instruct")
        self.vector_store = FAISS(station_embeddings)
        self.retriever = VectorStoreRetriever(self.vector_store)

    def process_query(self, user_query_in_hindi):
        """
        Process: "Mujhe Dwarka se India Gate jana hai, Yellow Line mat use karna"

        Pipeline:
        1. Retrieve relevant context (stations, line status)
        2. Run LLM to extract intent
        3. Parse constraints
        4. Call Dijkstra with constraints
        5. Generate human-readable response
        """

        # Step 1: Retrieval
        context = self.retriever.retrieve(user_query_in_hindi)
        # Retrieved: Similar stations, line closures, platforms

        # Step 2: LLM Processing
        prompt = f"""
        User Query (Hindi): {user_query_in_hindi}

        Available Context:
        - Stations: {context['stations']}
        - Line Status: {context['line_status']}
        - Current Time: {context['time']}

        Extract:
        1. From station
        2. To station
        3. Constraints/preferences
        4. Language preference

        Output JSON format:
        {{
            "from": "...",
            "to": "...",
            "constraints": [...],
            "response_language": "hi"
        }}
        """

        parsed_intent = self.llm(prompt)

        # Step 3: Call Dijkstra
        routes = dijkstra_metro_routing(
            from_station=parsed_intent['from'],
            to_station=parsed_intent['to'],
            constraints=parsed_intent['constraints']
        )

        # Step 4: Generate response in Hindi
        response = generate_hindi_response(routes)

        return response
```

### 3. OFFLINE MODE WITH SYNC

```python
# pseudo-code
class OfflineMetroEngine:
    def __init__(self):
        self.sqlite_db = sqlite3.connect("metro_offline.db")
        self.is_online = check_internet()

    def initialize_offline(self):
        """
        When app first opens (online):
        1. Download entire metro graph
        2. Compress and store in SQLite
        3. Cache embeddings locally
        4. Store last line status

        Size: ~50MB (manageable)
        """

        if self.is_online:
            # Download from API
            all_stations = fetch_all_stations()
            all_routes = fetch_all_routes()
            line_status = fetch_line_status()

            # Store in SQLite
            self.store_offline(all_stations, all_routes)

            # Also cache disruption history
            self.cache_disruption_history()

    def get_route_offline(self, from_st, to_st):
        """
        Use Dijkstra on cached SQLite data
        No internet needed for basic routing
        """

        cursor = self.sqlite_db.cursor()

        # Load from SQLite
        cursor.execute("""
            SELECT * FROM routes
            WHERE from_station = ? OR to_station = ?
        """, (from_st, to_st))

        local_graph = cursor.fetchall()

        # Run Dijkstra on local graph
        route = dijkstra_on_local(local_graph, from_st, to_st)

        return route

    def sync_when_online(self):
        """
        When connection restored:
        1. Upload user's saved routes
        2. Download new disruptions
        3. Update line status
        4. Notify of changes
        """

        if self.is_online:
            # Pull latest changes
            latest_disruptions = fetch_recent_disruptions()
            latest_status = fetch_line_status()

            # Update local DB
            self.update_offline_db(latest_disruptions, latest_status)

            # Notify user
            self.notify_route_changes()
```

### 4. REAL-TIME DISRUPTION DETECTION

```python
# pseudo-code
class DisruptionService:
    def __init__(self):
        self.redis = redis.Redis()
        self.ws = WebSocketServer()
        self.db = PostgreSQL()

    def listen_disruptions(self):
        """
        Real-time monitoring of:
        - Official DMRC announcements (API)
        - Twitter mentions (pattern matching)
        - User reports (crowdsourced)
        - Sensor data (platform capacity, delays)
        """

        # 1. DMRC API polling
        def poll_dmrc_api():
            while True:
                status = fetch_dmrc_api()
                if status_changed(status, self.redis.get('last_status')):
                    self.broadcast_update(status)
                time.sleep(30)  # Poll every 30 seconds

        # 2. Twitter API (crowdsource)
        def monitor_twitter():
            for tweet in twitter_stream("#DelhiMetro"):
                if contains_disruption_keyword(tweet):
                    self.analyze_and_broadcast(tweet)

        # 3. User reports
        def accept_user_reports():
            # Endpoint: POST /api/v1/report/disruption
            # Requires: authentication, location verification
            pass

    def broadcast_update(self, disruption_data):
        """
        Send to:
        1. Active users via WebSocket
        2. Affected route users (filtered)
        3. Store in DB (history)
        """

        # Redis Pub/Sub for real-time
        self.redis.publish(
            f"disruption:{disruption_data['line']}",
            json.dumps(disruption_data)
        )

        # Notify users with active routes
        affected_users = self.find_affected_users(disruption_data)
        for user_id in affected_users:
            self.ws.emit_to_user(user_id, 'disruption_alert',
                                disruption_data)

        # Store in DB (historical tracking)
        self.db.insert_disruption(disruption_data)
```

---

## PROJECT STRUCTURE

```
DelhiMetroApp/
│
├── backend/
│   ├── main.py                    # FastAPI server
│   ├── requirements.txt           # Dependencies
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── config.py         # Configuration (API keys, DB URLs)
│   │   │   ├── security.py       # Auth tokens, JWT
│   │   │   └── constants.py      # Metro lines, station colors
│   │   │
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── routes.py     # Route finding endpoints
│   │   │   │   ├── stations.py   # Station info endpoints
│   │   │   │   ├── query.py      # Natural language query
│   │   │   │   ├── disruptions.py # Disruption endpoints
│   │   │   │   └── user.py       # User preferences
│   │   │   └── websocket.py      # WebSocket handlers
│   │   │
│   │   ├── services/
│   │   │   ├── routing_engine.py  # Dijkstra implementation
│   │   │   ├── rag_engine.py      # NVIDIA RAG
│   │   │   ├── disruption_service.py  # Real-time updates
│   │   │   ├── offline_sync.py    # Offline DB sync
│   │   │   └── platform_finder.py # Platform-specific info
│   │   │
│   │   ├── models/
│   │   │   ├── station.py         # SQLAlchemy models
│   │   │   ├── line.py
│   │   │   ├── route.py
│   │   │   ├── platform.py
│   │   │   └── disruption.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── route_request.py   # Pydantic models
│   │   │   ├── route_response.py
│   │   │   └── query_schema.py
│   │   │
│   │   └── utils/
│   │       ├── graph_builder.py    # Build metro graph
│   │       ├── gps_utils.py        # Location calculations
│   │       ├── hindi_processor.py  # Hindi text processing
│   │       ├── db_utils.py         # Database helpers
│   │       └── cache_manager.py    # Redis operations
│   │
│   ├── data/
│   │   ├── metro_data.json         # All 12 lines + 256 stations
│   │   ├── platforms_data.json     # Platform info
│   │   └── embeddings/             # FAISS vector store
│   │
│   ├── ml/
│   │   ├── embeddings.py           # Generate station embeddings
│   │   ├── rag_retriever.py        # RAG retriever
│   │   └── models/
│   │       └── nemo_model.py       # NVIDIA NeMo wrapper
│   │
│   ├── tests/
│   │   ├── test_routing_engine.py
│   │   ├── test_rag_engine.py
│   │   ├── test_disruptions.py
│   │   └── test_offline.py
│   │
│   └── migrations/
│       └── versions/               # Alembic DB migrations
│
├── mobile/
│   ├── flutter_app/
│   │   ├── lib/
│   │   │   ├── main.dart
│   │   │   │
│   │   │   ├── screens/
│   │   │   │   ├── home_screen.dart
│   │   │   │   ├── route_screen.dart
│   │   │   │   ├── tracking_screen.dart
│   │   │   │   └── settings_screen.dart
│   │   │   │
│   │   │   ├── services/
│   │   │   │   ├── api_service.dart      # Backend API calls
│   │   │   │   ├── location_service.dart # GPS tracking
│   │   │   │   ├── voice_service.dart    # Voice input (STT)
│   │   │   │   ├── offline_db_service.dart
│   │   │   │   └── websocket_service.dart
│   │   │   │
│   │   │   ├── widgets/
│   │   │   │   ├── route_card.dart
│   │   │   │   ├── platform_info_widget.dart
│   │   │   │   ├── disruption_alert.dart
│   │   │   │   └── live_tracker.dart
│   │   │   │
│   │   │   └── models/
│   │   │       ├── route_model.dart
│   │   │       ├── station_model.dart
│   │   │       └── user_model.dart
│   │   │
│   │   ├── pubspec.yaml             # Dependencies
│   │   └── assets/
│   │       ├── images/              # Metro line icons, colors
│   │       └── metro_data.db        # Offline SQLite
│   │
│   └── web/  (Optional React)
│       ├── src/
│       │   ├── components/
│       │   ├── pages/
│       │   └── services/
│       └── package.json
│
├── docker/
│   ├── Dockerfile                   # Python backend
│   ├── docker-compose.yml           # PostgreSQL + Redis + Backend
│   └── nginx.conf                   # Reverse proxy
│
├── kubernetes/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── secrets.yaml
│
├── docs/
│   ├── API_DOCUMENTATION.md
│   ├── ARCHITECTURE.md
│   ├── SETUP_GUIDE.md
│   └── DEPLOYMENT.md
│
└── README.md
```

---

## IMPLEMENTATION ROADMAP

### Phase 1: Backend Foundation (Week 1-2)
- [ ] Setup FastAPI + PostgreSQL + Redis
- [ ] Create database schema (stations, lines, routes)
- [ ] Implement basic Graph class
- [ ] Implement Dijkstra's algorithm
- [ ] Create API endpoints for route finding
- [ ] Setup Docker environment

### Phase 2: Advanced Routing (Week 2-3)
- [ ] Add real-time constraints (closed lines, delays)
- [ ] Implement platform-specific routing
- [ ] Add transfer penalty logic
- [ ] Create static test data for 12 lines
- [ ] Benchmark routing speed

### Phase 3: RAG Integration (Week 3-4)
- [ ] Setup NVIDIA NeMo LLM
- [ ] Create FAISS vector store for stations
- [ ] Implement RAG retriever
- [ ] Build natural language query parser
- [ ] Support Hindi + English queries
- [ ] Add intent extraction

### Phase 4: Real-time System (Week 4-5)
- [ ] Setup WebSocket server
- [ ] Implement Redis Pub/Sub for disruptions
- [ ] Create disruption data structure
- [ ] Build DMRC API integration (mock)
- [ ] Implement user notifications
- [ ] Setup message queue (RabbitMQ optional)

### Phase 5: Offline Mode (Week 5-6)
- [ ] Create SQLite schema
- [ ] Implement data compression
- [ ] Build sync logic (online ↔ offline)
- [ ] Test offline routing
- [ ] Implement conflict resolution

### Phase 6: Mobile App (Week 6-7)
- [ ] Setup Flutter project
- [ ] Build home screen
- [ ] Implement route search UI
- [ ] Add GPS tracking
- [ ] Build live tracking screen
- [ ] Implement voice input (STT)
- [ ] Add offline mode toggle

### Phase 7: Testing & Optimization (Week 7-8)
- [ ] Unit tests (routing, RAG, sync)
- [ ] Integration tests (API + DB)
- [ ] Load testing (1000s concurrent users)
- [ ] Performance optimization
- [ ] Documentation
- [ ] Prepare for deployment

---

## KEY FEATURES IMPLEMENTATION DETAIL

### 1. PLATFORM-SPECIFIC ROUTING
```
Route Response should include for each segment:
{
    "from": "Dwarka",
    "to": "Rajiv Chowk",
    "line": "Blue",
    "platform": {
        "number": 1,
        "type": "ISLAND",
        "direction": "Towards Noida City Centre",
        "amenities": ["escalator", "toilet", "atm"],
        "exit": "Exit A1 (towards IGI Airport exit)",
        "accessibility": true
    }
}
```

### 2. REAL-TIME ETA PREDICTION
```
Algorithm:
1. Get current train positions (from metro_positions table)
2. Current user location (GPS)
3. Calculate:
   - Time to reach starting station
   - Waiting time for next train
   - Travel time (based on current train speed)
   - Platform transfer time
   - Estimated arrival

Update: Every 10 seconds
Accuracy: ±2 minutes
```

### 3. VOICE INPUT INTEGRATION
```
User says: "Mujhe India Gate jana hai"
→ Google Speech-to-Text API (mobile)
→ Extract intent: to_station = "India Gate"
→ If from_station not known: prompt user
→ Call /api/v1/query/natural
→ Text-to-Speech response in Hindi

Requirements:
- Internet connection (or offline STT fallback)
- Microphone permission
- Language selection (Hindi, English, etc.)
```

### 4. DISRUPTION ALERTS LOGIC
```
User has saved route: Dwarka → India Gate (Blue Line + Red Line)

Scenario: Yellow Line closes at Jantar Mantar
→ Disruption service broadcasts update
→ Check if user's route affected: NO
→ No alert

Scenario: Red Line delays 3 minutes
→ Disruption service broadcasts delay
→ Check if user's route affected: YES (Red Line used)
→ Alert: "Red Line experiencing delays. ETA revised to 35 min (was 32 min)"
→ Offer: "View alternative routes?"
```

---

## TESTING STRATEGY

### Unit Tests
```python
# test_routing_engine.py
def test_dijkstra_simple_path():
    graph = build_test_graph()
    path = dijkstra(graph, 'A', 'D')
    assert path == ['A', 'B', 'D']

def test_dijkstra_with_constraints():
    graph = build_test_graph()
    constraints = {"avoid_lines": ["Yellow"]}
    path = dijkstra(graph, 'Dwarka', 'India Gate', constraints)
    assert 'Yellow' not in get_lines_in_path(path)

def test_rag_hindi_query():
    rag = MetroRAG()
    result = rag.process_query("Mujhe Dwarka se India Gate jana hai")
    assert result['from'] == 'Dwarka'
    assert result['to'] == 'India Gate'

def test_offline_sync():
    offline_db = OfflineMetro()
    offline_db.get_route_offline('Dwarka', 'Rajiv Chowk')
    # Should work without internet
```

### Integration Tests
```python
# test_api_integration.py
def test_full_route_finding_flow():
    # 1. Send request to API
    # 2. Check database queries
    # 3. Verify response format
    # 4. Check cache hit

def test_disruption_broadcast():
    # 1. Trigger disruption
    # 2. Check Redis Pub/Sub
    # 3. Verify WebSocket broadcast
    # 4. Check database insert
```

### Load Testing
```bash
# k6 load testing script
100 virtual users
10 requests per second
Duration: 5 minutes
Target endpoints:
- /api/v1/routes/find (40%)
- /api/v1/query/natural (30%)
- /api/v1/stations/{id} (20%)
- /api/v1/lines/{id}/trains (10%)

Expected: <100ms latency @ p95
```

---

## DEPLOYMENT

### Docker Setup
```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/metro
      - REDIS_URL=redis://cache:6379
    depends_on:
      - db
      - cache

  db:
    image: postgres:14
    environment:
      POSTGRES_DB: metro
      POSTGRES_PASSWORD: password

  cache:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

### Cloud Deployment (AWS)
- **Backend:** EC2 + Docker + Auto-scaling
- **Database:** RDS PostgreSQL (Multi-AZ)
- **Cache:** ElastiCache Redis
- **Storage:** S3 (metro data)
- **CDN:** CloudFront (maps, images)
- **Monitoring:** CloudWatch + Datadog

---

## SUCCESS CRITERIA FOR PLACEMENT

✅ **Routing Algorithm:** Dijkstra working, <50ms response time
✅ **RAG Integration:** Hindi queries understood correctly, >90% accuracy
✅ **Offline Mode:** Works without internet, auto-syncs when online
✅ **Real-time Updates:** Disruptions broadcast <1 second
✅ **Platform Details:** Correct platforms shown for each transfer
✅ **Code Quality:** 80%+ test coverage, clean architecture
✅ **Documentation:** API docs, setup guide, deployment guide
✅ **GitHub:** 50+ commits, meaningful messages, clean repo

---

## INTERVIEW TALKING POINTS

**Q: How does your routing handle 1M stations?**
> "Dijkstra's O(E log V) scales well. For production, I'd shard the graph by geographic region and use microservices. Each shard handles routing independently, then merge results."

**Q: How does RAG improve over traditional search?**
> "Traditional: User types exact station names. RAG: Understands natural language, handles misspellings, context-aware (remembers recent routes), multi-language support."

**Q: How do you ensure 99.9% uptime for live disruptions?**
> "Multi-region deployment, database replication, Redis cache (fallback to DB), redundant WebSocket servers, circuit breaker pattern."

**Q: How would you scale this to 100 Indian cities?**
> "Generalized graph schema (any city can use same code), separate DB per city, federated search across cities, central user auth."

---

## NEXT STEPS

1. **Start with Claude Code:** Provide this document to Claude Code
2. **Build incrementally:** Week 1-2 backend, Week 3-4 RAG, etc.
3. **Test thoroughly:** Unit + integration tests for each module
4. **Deploy to GitHub:** Regular commits with good messages
5. **By Month 2:** Production-ready system with documentation
6. **Interview prep:** Practice explaining architecture, trade-offs, scalability

---

## ESTIMATED EFFORT

- **Backend:** 40 hours
- **RAG Integration:** 15 hours
- **Mobile App:** 30 hours
- **Testing:** 10 hours
- **Documentation:** 5 hours
- **Total:** ~100 hours (~2-3 weeks full-time)

**Perfect for placement portfolio!**

---

**This is enterprise-grade architecture. Build it well, and you're ready for Google/Amazon/Microsoft interviews.**
