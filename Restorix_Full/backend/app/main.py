from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.config import get_settings
from app.api.v1.router import router as v1_router
from app.core.rate_limit import limiter

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version='1.0.0',
    docs_url='/api/docs' if settings.app_env != 'production' else None,
    redoc_url=None,
    openapi_url='/openapi.json' if settings.app_env != 'production' else None,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={'detail': 'Troppe richieste, riprova tra poco.'},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(v1_router, prefix='/api/v1')


@app.get('/api/health')
async def health():
    return {'status': 'ok', 'app': settings.app_name}
