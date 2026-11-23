from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from functools import lru_cache
import hashlib
import json
import logging
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator
from redis.exceptions import RedisError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.redis_client import redis_client
from backend.search_service import SearchService, json_safe

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Real Estate NLP API",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

search_service = SearchService()


@lru_cache(maxsize=None)
def component(name):
    """Load optional endpoint components only when that endpoint is requested."""
    if name == "entities":
        from scripts.entity_extractor import EntityExtractor
        return EntityExtractor(str(ROOT / "taxonomy/taxonomy_week1.json"))
    if name == "summary":
        from scripts.extractive_listing_summarizer import ListingSummarizer
        return ListingSummarizer(listings_path=ROOT / "data/processed/listing_sample_cleaned.csv")
    if name == "compliance":
        from scripts.compliance_checker import ComplianceChecker
        return ComplianceChecker()
    if name == "signals":
        from scripts.signal_extractor import SignalExtractor
        return SignalExtractor(taxonomy_path=str(ROOT / "taxonomy/taxonomy_week1.json"))
    if name == "bm25":
        from scripts.bm25_search import BM25Searcher
        searcher = BM25Searcher(data_path=ROOT / "data/processed/listing_full_cleaned.csv")
        searcher.load()
        return searcher
    if name == "intent":
        if not (ROOT / "data/models/intent_classifier").is_dir():
            raise RuntimeError(
                "Intent classification is unavailable: the trained model is missing "
                "from data/models/intent_classifier. Property search can still run."
            )
        from scripts.query_intent_classifier import predict_intent
        return predict_intent
    raise ValueError(f"Unknown component: {name}")


def cached_response(key):
    try:
        cached = redis_client.get(key)
        return json.loads(cached) if cached else None
    except (RedisError, ValueError):
        logger.warning("Search cache unavailable; continuing without cached results.")
        return None


def cache_response(key, response):
    try:
        redis_client.setex(key, 300, json.dumps(response, allow_nan=False))
    except RedisError:
        logger.warning("Search results returned without caching; Redis unavailable.")

class ParseQueryRequest(BaseModel):
    query: str = Field(min_length=1)

    @field_validator("query")
    @classmethod
    def nonempty_query(cls, value):
        if not value.strip():
            raise ValueError("Search query cannot be empty.")
        return value.strip()

class ExtractEntitiesRequest(BaseModel):
    text: str

class SearchRequest(ParseQueryRequest):
    top_k: int = Field(default=5, ge=1, le=100, strict=True)


class NumericRefinement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    min: int | float | None = None
    max: int | float | None = None
    preferred: int | float | None = None


class SearchRefinements(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    city: str | None = None
    price: NumericRefinement | None = None
    bedrooms: NumericRefinement | None = None
    bathrooms: NumericRefinement | None = None


class RefinedQueryRequest(ParseQueryRequest):
    refinements: SearchRefinements | None = None

    def refinement_args(self):
        edits = self.refinements.model_dump(exclude_unset=True) if self.refinements else {}
        return {"refinements": edits} if edits else {}


class RefinedSearchRequest(RefinedQueryRequest):
    top_k: int = Field(default=5, ge=1, le=100, strict=True)

class SummarizeRequest(BaseModel):
    remarks: str
    num_sentences: int = 3

class ComplianceRequest(BaseModel):
    text:str

class IntentRequest(BaseModel):
    query:str

class SignalRequest(BaseModel):
    L_ListingID: str | None = None
    L_Remarks: str

class SearchResponse(BaseModel):
    query: str
    results: list
    count: int

@app.get("/health")
@limiter.limit("10/second")
async def health_check(request: Request):
    return {
        "status": "ok",
        "message": "Real Estate NLP is running"
    }



@app.get("/search-options")
@limiter.limit("10/second")
def search_options(request: Request):
    cache_key = "search-options:v1"
    cached = cached_response(cache_key)
    if cached is not None:
        return cached
    try:
        options = search_service.search_options()
    except Exception:
        logger.exception("Unable to load search options.")
        raise HTTPException(status_code=503, detail="Search options are temporarily unavailable.")
    cache_response(cache_key, options)
    return options


@app.post("/parse-query")
@limiter.limit("10/second")
def parse_query(request: Request, body: RefinedQueryRequest):
    try:
        parsed = search_service.parse(body.query, **body.refinement_args())
        return {
            "query": body.query,
            "filters": parsed["structured_filters"]["conditions"],
            "parsed_query": parsed,
            "structured_filters": parsed["structured_filters"],
            "semantic_words": parsed["semantic_words"],
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.post("/extract-entities")
@limiter.limit("10/second")
async def extract_entities(request: Request, body: ExtractEntitiesRequest):
    try:
        entities = component("entities").extract_all(body.text)

        return {
            "text": body.text,
            "entities": entities
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/search")
@limiter.limit("10/second")
def search_listings(request: Request, body: RefinedSearchRequest):
    try:
        refinement_args = body.refinement_args()
        cache_input = json.dumps([body.query, body.top_k, refinement_args], sort_keys=True)

        cache_key = "search:hybrid:v2:" + hashlib.sha256(
            cache_input.encode()
        ).hexdigest()

        cached = cached_response(cache_key)

        if cached is not None:
            return cached

        response = search_service.search(
            query=body.query,
            top_k=body.top_k,
            **refinement_args,
        )

        cache_response(cache_key, response)

        return response

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e)
        )
    except Exception:
        logger.exception("Hybrid search failed.")
        raise HTTPException(status_code=503, detail="Search is temporarily unavailable. Check the database and search artifacts.")

@app.post("/bm25-search")
@limiter.limit("10/second")
def bm25_search_listings(request: Request, body: SearchRequest):
    try:
        cache_input = f"{body.query}:{body.top_k}"

        cache_key = "bm25_search:v2:" + hashlib.sha256(
            cache_input.encode()
        ).hexdigest()

        cached = cached_response(cache_key)

        if cached is not None:
            return cached

        results = component("bm25").search(
            query=body.query,
            top_k=body.top_k
        )

        response = json_safe({
            "query": body.query,
            "count": len(results),
            "results": results
        })

        cache_response(cache_key, response)

        return response

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/summarize")
@limiter.limit("10/second")
async def summarize_listing(request: Request, body: SummarizeRequest):
    try:
        summary = component("summary").extractive_summary(
            remarks=body.remarks,
            num_sentences=body.num_sentences
        )

        return {
            "summary": summary
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/check-compliance")
@limiter.limit("10/second")
async def check_compliance(request: Request, body: ComplianceRequest):
    try:
        result = component("compliance").check_listing(body.text)

        return result

    except TypeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.post("/classify-intent")
@limiter.limit("10/second")
def classify_intent(request: Request, body: IntentRequest):
    try:
        result = component("intent")(body.query)

        return {
            "query": body.query,
            "intent": result["intent"],
            "confidence": result["confidence"]
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except (RuntimeError, OSError):
        raise HTTPException(
            status_code=503,
            detail="Intent classification is unavailable. Restore the trained model "
                   "in data/models/intent_classifier. Property search can still run."
        )

@app.post("/extract-signals")
@limiter.limit("10/second")
async def extract_signals(request: Request, body: SignalRequest):
    try:
        listing_record = {
            "L_ListingID": body.L_ListingID,
            "L_Remarks": body.L_Remarks
        }

        result = component("signals").extract_signals(listing_record)

        return result

    except TypeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
