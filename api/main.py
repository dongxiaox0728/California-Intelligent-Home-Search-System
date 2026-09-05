from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from scripts.query_parser import QueryParser
from scripts.entity_extractor import EntityExtractor
from scripts.semantic_searcher import SemanticSearcher
from scripts.extractive_listing_summarizer import ListingSummarizer
from scripts.compliance_checker import ComplianceChecker
from scripts.query_intent_classifier import predict_intent
from scripts.signal_extractor import SignalExtractor

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Real Estate NLP API",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

parser = QueryParser()
entity_extractor = EntityExtractor(
    "taxonomy/taxonomy_week1.json"
)
semantic_searcher = SemanticSearcher()
semantic_searcher.load()
listing_summarizer = ListingSummarizer()
compliance_checker = ComplianceChecker()
signal_extractor = SignalExtractor(
    taxonomy_path="taxonomy/taxonomy_week1.json"
)

class ParseQueryRequest(BaseModel):
    query:str

class ExtractEntitiesRequest(BaseModel):
    text: str

class SearchRequest(BaseModel):
    query:str
    top_k: int = 5

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



@app.post("/parse-query")
@limiter.limit("10/second")
async def parse_query(request: Request, body: ParseQueryRequest):
    try:
        filters = parser.parse(body.query)
        return {
            "query": body.query,
            "filters": filters
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
        entities = entity_extractor.extract_all(body.text)

        return {
            "text": body.text,
            "entities": entities
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

import json
import hashlib
from api.redis_client import redis_client


@app.post("/search")
@limiter.limit("10/second")
async def search_listings(request: Request, body: SearchRequest):
    try:
        cache_input = f"{body.query}:{body.top_k}"

        cache_key = "search:" + hashlib.sha256(
            cache_input.encode()
        ).hexdigest()

        cached = redis_client.get(cache_key)

        if cached:
            print("CACHE HIT")
            return json.loads(cached)

        print("CACHE MISS")

        # Your original semantic search only
        results = semantic_searcher.search(
            query=body.query,
            top_k=body.top_k
        )

        response = {
            "query": body.query,
            "count": len(results),
            "results": results
        }

        # Store for 5 minutes
        redis_client.setex(
            cache_key,
            300,
            json.dumps(response)
        )

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
        summary = listing_summarizer.extractive_summary(
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
        result = compliance_checker.check_listing(body.text)

        return result

    except TypeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.post("/classify-intent")
@limiter.limit("10/second")
async def classify_intent(request: Request, body: IntentRequest):
    try:
        result = predict_intent(body.query)

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

@app.post("/extract-signals")
@limiter.limit("10/second")
async def extract_signals(request: Request, body: SignalRequest):
    try:
        listing_record = {
            "L_ListingID": body.L_ListingID,
            "L_Remarks": body.L_Remarks
        }

        result = signal_extractor.extract_signals(listing_record)

        return result

    except TypeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )