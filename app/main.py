import logging
import os
import secrets
import time
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import select, text

from app.db import Label, Message, Order, session_factory
from app.schemas import LabelInput, MessageInput, OrderView
from app.service import Conflict, recompute, view


logger = logging.getLogger("sellershield")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
security = HTTPBasic()


def create_app(factory=None, username=None, password=None):
    @asynccontextmanager
    async def lifespan(app):
        if not app.state.username or not app.state.password:
            raise RuntimeError("MERCHANT_USERNAME and MERCHANT_PASSWORD must be set")
        if app.state.sessions is None:
            app.state.sessions = session_factory()
        yield

    app = FastAPI(title="SellerShield Backend", version="0.1.0", description="Single-merchant sandbox demo. PROTECTED is a local rule result, not a PayPal guarantee.", lifespan=lifespan)
    app.state.sessions = factory
    app.state.username = username if username is not None else os.getenv("MERCHANT_USERNAME")
    app.state.password = password if password is not None else os.getenv("MERCHANT_PASSWORD")
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(static_dir / "index.html")

    def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
        user_ok = secrets.compare_digest(credentials.username.encode(), (app.state.username or "").encode())
        password_ok = secrets.compare_digest(credentials.password.encode(), (app.state.password or "").encode())
        if not app.state.username or not app.state.password or not (user_ok and password_ok):
            raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Basic"})

    def session():
        with app.state.sessions() as db:
            with db.begin():
                yield db

    def locked_order(db, order_id):
        order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
        if order is None:
            raise HTTPException(404, "Order not found")
        return order

    origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if value.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            # Log no exception text: database errors can contain bound address/message values.
            logger.error("request failed method=%s", request.method)
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        if request.url.path == '/' or request.url.path.startswith('/static/'):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'; object-src 'none'"
        route = request.scope.get("route")
        logger.info("method=%s route=%s status=%s duration_ms=%.1f", request.method, getattr(route, "path", "unmatched"), response.status_code, (time.monotonic() - started) * 1000)
        return response

    @app.exception_handler(Conflict)
    async def conflict_handler(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        # FastAPI's default includes rejected input; omit buyer data from errors.
        return JSONResponse(status_code=422, content={"detail": [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]})

    @app.get("/health/ready")
    def ready():
        try:
            with app.state.sessions() as db:
                db.execute(text("SELECT 1"))
        except Exception:
            raise HTTPException(503, "Database unavailable") from None
        return {"status": "ready"}

    @app.get("/orders", response_model=list[OrderView], dependencies=[Depends(authenticate)])
    def orders(db=Depends(session, scope="function")):
        return [view(db, order) for order in db.scalars(select(Order).order_by(Order.created_at.desc(), Order.id.desc()))]

    @app.get("/orders/{order_id}", response_model=OrderView, dependencies=[Depends(authenticate)])
    def detail(order_id: str, db=Depends(session, scope="function")):
        order = db.get(Order, order_id)
        if order is None:
            raise HTTPException(404, "Order not found")
        return view(db, order)

    @app.post("/messages", response_model=OrderView, dependencies=[Depends(authenticate)])
    def message(body: MessageInput, db=Depends(session, scope="function")):
        order = locked_order(db, body.order_id)
        if body.ai_analysis and body.ai_analysis.quote not in body.text:
            raise HTTPException(422, "Analysis quote must occur in the original message")
        existing = db.scalar(select(Message).where(Message.order_id == order.id, Message.external_id == body.id))
        analysis = body.ai_analysis.model_dump() if body.ai_analysis else None
        if existing:
            if existing.text != body.text or (existing.analysis is not None and existing.analysis != analysis):
                raise Conflict("Message identifier already exists with different data")
            if existing.analysis == analysis:
                return view(db, order)
            existing.analysis = analysis
        else:
            db.add(Message(order_id=order.id, external_id=body.id, text=body.text, analysis=analysis))
        db.flush()
        recompute(db, order)
        return view(db, order)

    @app.post("/labels", response_model=OrderView, dependencies=[Depends(authenticate)])
    def label(body: LabelInput, db=Depends(session, scope="function")):
        order = locked_order(db, body.order_id)
        db.add(Label(order_id=order.id, data=body.model_dump(exclude={"order_id"})))
        db.flush()
        recompute(db, order)
        return view(db, order)

    return app


app = create_app()
