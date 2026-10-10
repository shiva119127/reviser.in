from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from ..models.schema import IngestRequest, IngestJobResponse
from ..services.ingestion_engine import IngestionEngine

router = APIRouter(prefix="/api/ingest", tags=["Ingestion Pipeline"])

@router.post("", response_model=IngestJobResponse)
def create_ingest_job(request: IngestRequest):
    url = request.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL must not be empty.")
    
    engine = IngestionEngine.get_instance()
    job_id = engine.create_job(url=url, force_reprocess=request.force_reprocess)
    job_status = engine.get_job_status(job_id)
    if not job_status:
        raise HTTPException(status_code=500, detail="Failed to initialize ingestion job.")
    return job_status

@router.get("/{job_id}", response_model=IngestJobResponse)
def get_job_status(job_id: str):
    engine = IngestionEngine.get_instance()
    job_status = engine.get_job_status(job_id)
    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job ID '{job_id}' not found.")
    return job_status

@router.post("/{job_id}/retry", response_model=IngestJobResponse)
def retry_job(job_id: str):
    engine = IngestionEngine.get_instance()
    job = engine.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job ID '{job_id}' not found.")
    
    url = job["url"]
    new_job_id = engine.create_job(url=url, force_reprocess=False)
    new_job_status = engine.get_job_status(new_job_id)
    return new_job_status

@router.get("", response_model=List[IngestJobResponse])
def list_jobs():
    engine = IngestionEngine.get_instance()
    return [IngestJobResponse(**j) for j in reversed(list(engine.jobs.values()))]
