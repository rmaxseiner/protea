# Enhanced Semantic Search

## Overview

Improve Protea's search functionality with better semantic understanding through larger embedding models and category-aware query expansion. This enables users to find items using abstract terms like "fastener" to locate bolts, screws, and nails.

## Current State

Protea uses a hybrid search combining:
- **FTS5 full-text search** for keyword matching
- **Vector similarity** using `all-MiniLM-L6-v2` (22.7M parameters, 384 dimensions)

### Current Limitations

The all-MiniLM-L6-v2 model produces relatively low similarity scores for conceptually related but lexically different terms:

| Query | Item | Similarity |
|-------|------|------------|
| "fastener" | "M6 Hex Bolts" | 0.35 |
| "fastener" | "Wood Screws" | 0.34 |
| "electronic component" | "10K Ohm Resistors" | 0.21 |
| "electronic component" | "Arduino Uno" | 0.21 |

With the 0.2 similarity threshold (lowered from 0.3 in Jan 2026), these items are now included but may rank lower than expected.

---

## Feature 1: Larger Embedding Model Option

### Proposal

Add support for `all-mpnet-base-v2` as an optional higher-quality embedding model.

### Model Comparison

| Model | Parameters | Disk Size | Dimensions | Quality |
|-------|------------|-----------|------------|---------|
| all-MiniLM-L6-v2 (current) | 22.7M | ~90MB | 384 | Good |
| all-mpnet-base-v2 | 109.5M | ~420MB | 768 | Better |

### Similarity Improvement

| Query | Item | MiniLM | MPNet | Improvement |
|-------|------|--------|-------|-------------|
| "fastener" | "M6 Hex Bolts" | 0.35 | 0.35 | - |
| "fastener" | "Wood Screws" | 0.34 | 0.55 | +62% |
| "electronic component" | "10K Ohm Resistors" | 0.21 | 0.26 | +24% |
| "power tool" | "Cordless Drill" | 0.44 | 0.48 | +9% |

### Configuration

Add environment variable to select model:

```bash
# Default (smaller, faster)
INVENTORY_EMBEDDING_MODEL=all-MiniLM-L6-v2

# Optional (larger, better semantic understanding)
INVENTORY_EMBEDDING_MODEL=all-mpnet-base-v2
```

### Implementation Steps

1. **Update config.py**
   - Add model choice validation
   - Add embedding dimension auto-detection based on model

2. **Update embedding_service.py**
   - Handle different embedding dimensions
   - Add model info logging on startup

3. **Database migration**
   - Embeddings are stored as BLOBs, so dimension change requires re-embedding
   - Add `backfill_embeddings.py` script to regenerate embeddings
   - Store model name in metadata table for tracking

4. **Update Docker image**
   - Consider separate image tags for mini vs full model
   - Or download model on first run

### Trade-offs

| Aspect | MiniLM (current) | MPNet |
|--------|------------------|-------|
| Docker image size | ~800MB | ~1.2GB |
| RAM usage | ~500MB | ~1GB |
| Embedding speed | ~5ms/item | ~15ms/item |
| Semantic quality | Good | Better |
| Startup time | ~2s | ~5s |

### Recommendation

Keep MiniLM as default for resource-constrained deployments. Offer MPNet as opt-in for users who prioritize search quality over resource usage.

---

## Feature 2: Category-Aware Query Expansion

### Proposal

Automatically expand search queries using the category hierarchy to improve recall for abstract searches.

### How It Works

When a user searches for "fastener":

1. **Check if query matches a category name or alias**
   - Look up categories table for "fastener"
   - Find "Hardware > Fasteners" category

2. **Get items in that category**
   - Query items in "Fasteners" and child categories
   - Extract common terms: "bolt", "screw", "nail", "washer", "rivet"

3. **Expand the query**
   - Original: `"fastener"`
   - Expanded: `"fastener bolt screw nail washer"`

4. **Run hybrid search with expanded query**
   - FTS now matches "bolt" directly
   - Vector search has more context

### Example Expansions

| Original Query | Category Match | Expanded Query |
|----------------|----------------|----------------|
| "fastener" | Hardware > Fasteners | "fastener bolt screw nail washer nut" |
| "electronic component" | Electronics > Components | "electronic component resistor capacitor transistor diode" |
| "power tool" | Tools > Power Tools | "power tool drill saw sander grinder" |
| "storage" | Supplies > Storage | "storage container box bin organizer" |

### Implementation Steps

1. **Add category aliases table**
   ```sql
   CREATE TABLE category_aliases (
       id TEXT PRIMARY KEY,
       category_id TEXT NOT NULL REFERENCES categories(id),
       alias TEXT NOT NULL,
       created_at TEXT NOT NULL
   );

   -- Seed with common aliases
   INSERT INTO category_aliases (id, category_id, alias) VALUES
       (uuid(), 'fasteners-cat-id', 'fastener'),
       (uuid(), 'fasteners-cat-id', 'hardware'),
       (uuid(), 'electronics-cat-id', 'electronic component'),
       (uuid(), 'electronics-cat-id', 'electronics');
   ```

2. **Create expansion service** (`src/protea/services/query_expansion.py`)
   ```python
   def expand_query(db: Database, query: str) -> str:
       """Expand query using category knowledge."""
       # Check for category alias match
       category = find_category_by_alias(db, query)
       if not category:
           return query

       # Get sample item names from category
       items = get_items_in_category(db, category.id, limit=10)
       terms = extract_key_terms(items)

       # Combine original query with category terms
       return f"{query} {' '.join(terms)}"
   ```

3. **Integrate into search_items()**
   ```python
   def search_items(db, query, ...):
       # Expand query before searching
       expanded_query = expand_query(db, query)

       # Run FTS with expanded query
       fts_results = _fts_search(db, expanded_query, ...)

       # Run vector search with expanded query
       vector_results = _vector_search(db, expanded_query, ...)
   ```

4. **Add configuration toggle**
   ```bash
   INVENTORY_QUERY_EXPANSION_ENABLED=true  # default
   ```

### Term Extraction Strategy

Extract key terms from item names in the matched category:

```python
def extract_key_terms(items: list[Item]) -> list[str]:
    """Extract distinctive terms from item names."""
    # Tokenize all item names
    all_words = []
    for item in items:
        words = item.name.lower().split()
        all_words.extend(words)

    # Count frequency
    word_counts = Counter(all_words)

    # Filter stop words and very common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'of', 'for', 'with', 'in'}

    # Return top distinctive terms
    terms = [
        word for word, count in word_counts.most_common(10)
        if word not in stop_words and len(word) > 2
    ]

    return terms[:5]  # Limit expansion to 5 terms
```

### Search Flow Diagram

```
User Query: "fastener"
         │
         ▼
┌─────────────────────┐
│ Category Lookup     │
│ "fastener" → Found  │
│ Hardware > Fasteners│
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Get Category Items  │
│ • M6 Hex Bolts      │
│ • Wood Screws       │
│ • Finishing Nails   │
│ • Lock Washers      │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Extract Terms       │
│ bolt, screw, nail,  │
│ washer, hex         │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Expanded Query      │
│ "fastener bolt      │
│  screw nail washer" │
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│ Hybrid Search       │
│ • FTS: matches bolt │
│ • Vector: semantic  │
└─────────────────────┘
         │
         ▼
Results: Bolts, Screws, Nails ranked by relevance
```

### Trade-offs

| Aspect | Without Expansion | With Expansion |
|--------|-------------------|----------------|
| Search latency | ~50ms | ~70ms (+1 category lookup) |
| Abstract query recall | Low | High |
| Precision | High | Slightly lower (more results) |
| Requires setup | No | Category aliases needed |

---

## Implementation Priority

### Phase 1: Quick Wins (Completed)
- [x] Lower similarity threshold from 0.3 to 0.2 (inclusion in vector results)
- [x] Lower vector-only threshold from 0.4 to 0.25 (for items only found via vector)
- [x] Add comprehensive vector search tests (50 tests in test_embedding_service.py and test_vector_search.py)

### Phase 2: Larger Model (Completed)
- [x] Upgrade default model from all-MiniLM-L6-v2 to all-mpnet-base-v2
- [x] Update embedding dimension from 384 to 768
- [x] Update tests to use config-based dimensions
- [x] Backfill script regenerates embeddings with new model

### Phase 3: Category-Aware Expansion (Future)
1. Add category_aliases migration
2. Seed common category aliases
3. Implement query expansion service
4. Integrate into search_items()
5. Add tests for expansion

### Phase 3: Larger Model Option
1. Update config for model selection
2. Handle different embedding dimensions
3. Add backfill script for model migration
4. Update Docker build for optional model
5. Document resource requirements

---

## Testing Strategy

### Unit Tests
- Query expansion with known categories
- Term extraction from item names
- Category alias matching

### Integration Tests
- Search "fastener" finds bolts/screws with expansion
- Search "electronic component" finds resistors
- Expansion disabled returns original behavior

### Performance Tests
- Measure search latency with/without expansion
- Compare result quality metrics

---

## Resources

- [Sentence Transformers Models](https://www.sbert.net/docs/pretrained_models.html)
- [all-mpnet-base-v2 on HuggingFace](https://huggingface.co/sentence-transformers/all-mpnet-base-v2)
- [SQLite FTS5 Documentation](https://www.sqlite.org/fts5.html)
