from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from scripts.query_parser import QueryParser
from scripts.entity_extractor import EntityExtractor
from scripts.semantic_searcher import SemanticSearcher
from scripts.extractive_listing_summarizer import ListingSummarizer
from scripts.compliance_checker import ComplianceChecker
from scripts.query_intent_classifier import predict_intent
from scripts.signal_extractor import SignalExtractor

app = FastAPI(
    title="Real Estate NLP API",
    version="1.0.0"
)

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

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "Real Estate NLP is running"
    }



@app.post("/parse-query")
async def parse_query(request: ParseQueryRequest):
    try:
        filters = parser.parse(request.query)
        return {
            "query": request.query,
            "filters": filters
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.post("/extract-entities")
async def extract_entities(request: ExtractEntitiesRequest):
    try:
        entities = entity_extractor.extract_all(request.text)

        return {
            "text": request.text,
            "entities": entities
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/search")
async def search_listings(request: SearchRequest):
    try:
        results = semantic_searcher.search(
            query=request.query,
            top_k=request.top_k
        )

        return {
            "query": request.query,
            "count": len(results),
            "results": results
        }

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
async def summarize_listing(request: SummarizeRequest):
    try:
        summary = listing_summarizer.extractive_summary(
            remarks=request.remarks,
            num_sentences=request.num_sentences
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
async def check_compliance(request: ComplianceRequest):
    try:
        result = compliance_checker.check_listing(request.text)

        return result

    except TypeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.post("/classify-intent")
async def classify_intent(request: IntentRequest):
    try:
        result = predict_intent(request.query)

        return {
            "query": request.query,
            "intent": result["intent"],
            "confidence": result["confidence"]
        }

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.post("/extract-signals")
async def extract_signals(request: SignalRequest):
    try:
        listing_record = {
            "L_ListingID": request.L_ListingID,
            "L_Remarks": request.L_Remarks
        }

        result = signal_extractor.extract_signals(listing_record)

        return result

    except TypeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )