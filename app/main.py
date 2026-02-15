import os
import uuid
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, init_db, SessionLocal
from app.models import Brand, StoreMapping, SkuRule, Admin
from app.services.auth import (
    authenticate_admin, create_session, get_session, destroy_session,
    seed_admin, seed_brands, hash_password,
)
from app.brands import get_processor
from app.services.external_db import fetch_order_statuses, fetch_order_items

app = FastAPI(title=settings.APP_NAME)

# Mount static files
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

# Templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


# ── Startup ──────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    init_db()
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_brands(db)
    finally:
        db.close()


# ── Helpers ──────────────────────────────────────────────────
def get_admin_session(request: Request) -> Optional[dict]:
    token = request.cookies.get("session_token")
    if token:
        return get_session(token)
    return None


# ══════════════════════════════════════════════════════════════
#  PUBLIC PAGES
# ══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    admin = get_admin_session(request)
    return templates.TemplateResponse("landing.html", {
        "request": request, "admin": admin,
    })


@app.get("/analysis", response_class=HTMLResponse)
def analysis_home(request: Request, db: Session = Depends(get_db)):
    brands = db.query(Brand).filter(Brand.is_active == True).all()
    admin = get_admin_session(request)
    return templates.TemplateResponse("home.html", {
        "request": request, "brands": brands, "admin": admin,
    })


@app.get("/operations", response_class=HTMLResponse)
def operations_page(request: Request):
    admin = get_admin_session(request)
    return templates.TemplateResponse("operations.html", {
        "request": request, "admin": admin,
    })


@app.get("/dashboard/{brand_key}", response_class=HTMLResponse)
def dashboard_page(brand_key: str, request: Request, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.processor_key == brand_key).first()
    if not brand:
        raise HTTPException(404, "العلامة التجارية غير موجودة")
    admin = get_admin_session(request)
    # Fetch statuses from external DB for this brand
    try:
        statuses = fetch_order_statuses(brand_key)
    except Exception:
        statuses = []
    return templates.TemplateResponse("dashboard.html", {
        "request": request, "brand": brand, "admin": admin, "statuses": statuses,
    })


# ── Fetch from DB ────────────────────────────────────────────
@app.post("/api/fetch-db")
async def fetch_from_database(
    brand_key: str = Form(...),
    status_values: str = Form(""),
    date_from: str = Form(""),
    date_to: str = Form(""),
):
    try:
        statuses = [v.strip() for v in status_values.split(",") if v.strip()] if status_values else None
        result = fetch_order_items(
            brand_key=brand_key,
            status_values=statuses,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
        )
        processor = get_processor(brand_key)
        tables = processor.compute_from_sku_list(result["items"])
        # Inject order counts into summary
        tables["summary"]["total_orders"] = result["total_orders"]

        return JSONResponse({
            "success": True,
            "tables": tables,
            "total_rows": result["total_orders"],
            "filtered_rows": result["filtered_orders"],
        })
    except Exception as e:
        return JSONResponse({"error": f"خطأ: {str(e)}"}, status_code=500)


# ── Upload & Process ─────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(
    brand_key: str = Form(...),
    file: UploadFile = File(...),
    status_values: str = Form(""),
    date_from: str = Form(""),
    date_to: str = Form(""),
    status_column: str = Form("حالة الطلب"),
    date_column: str = Form("تاريخ الطلب"),
):
    # Save uploaded file
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.xlsx', '.xls', '.csv']:
        return JSONResponse({"error": "صيغة الملف غير مدعومة"}, status_code=400)

    file_id = str(uuid.uuid4())
    save_path = settings.UPLOAD_DIR / f"{file_id}{ext}"
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    try:
        processor = get_processor(brand_key)
        df = processor.read_input_file(str(save_path))

        # Get available status options and date columns BEFORE filtering
        status_options = processor.get_status_options(df)
        date_columns = processor.get_date_columns(df)

        # Apply filters
        filters = {
            "status_column": status_column,
            "date_column": date_column,
        }
        if status_values:
            filters["status_values"] = [v.strip() for v in status_values.split(",") if v.strip()]
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to

        filtered_df = processor.apply_filters(df, filters)
        tables = processor.compute_tables(filtered_df)

        return JSONResponse({
            "success": True,
            "file_id": file_id,
            "tables": tables,
            "status_options": status_options,
            "date_columns": date_columns,
            "total_rows": len(df),
            "filtered_rows": len(filtered_df),
        })

    except KeyError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"خطأ في المعالجة: {str(e)}"}, status_code=500)


# ── Re-process with filters (no re-upload) ───────────────────
@app.post("/api/reprocess")
async def reprocess(
    brand_key: str = Form(...),
    file_id: str = Form(...),
    status_values: str = Form(""),
    date_from: str = Form(""),
    date_to: str = Form(""),
    status_column: str = Form("حالة الطلب"),
    date_column: str = Form("تاريخ الطلب"),
):
    # Find saved file
    found = None
    for ext in ['.xlsx', '.xls', '.csv']:
        path = settings.UPLOAD_DIR / f"{file_id}{ext}"
        if path.exists():
            found = path
            break

    if not found:
        return JSONResponse({"error": "الملف غير موجود. يرجى إعادة الرفع."}, status_code=404)

    try:
        processor = get_processor(brand_key)
        df = processor.read_input_file(str(found))

        filters = {
            "status_column": status_column,
            "date_column": date_column,
        }
        if status_values:
            filters["status_values"] = [v.strip() for v in status_values.split(",") if v.strip()]
        if date_from:
            filters["date_from"] = date_from
        if date_to:
            filters["date_to"] = date_to

        filtered_df = processor.apply_filters(df, filters)
        tables = processor.compute_tables(filtered_df)

        return JSONResponse({
            "success": True,
            "tables": tables,
            "total_rows": len(df),
            "filtered_rows": len(filtered_df),
        })

    except Exception as e:
        return JSONResponse({"error": f"خطأ في المعالجة: {str(e)}"}, status_code=500)


# ── Export Excel ─────────────────────────────────────────────
@app.post("/api/export")
async def export_excel(request: Request):
    body = await request.json()
    brand_key = body.get("brand_key")
    tables = body.get("tables")

    if not brand_key or not tables:
        return JSONResponse({"error": "بيانات ناقصة"}, status_code=400)

    try:
        processor = get_processor(brand_key)
        file_id = str(uuid.uuid4())
        output_path = str(settings.EXPORT_DIR / f"{file_id}.xlsx")
        processor.export_excel(tables, output_path)

        return JSONResponse({
            "success": True,
            "download_url": f"/api/download/{file_id}",
        })
    except Exception as e:
        return JSONResponse({"error": f"خطأ في التصدير: {str(e)}"}, status_code=500)


@app.get("/api/download/{file_id}")
def download_file(file_id: str):
    path = settings.EXPORT_DIR / f"{file_id}.xlsx"
    if not path.exists():
        raise HTTPException(404, "الملف غير موجود")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"report_{file_id[:8]}.xlsx",
    )


# ══════════════════════════════════════════════════════════════
#  ADMIN AUTH
# ══════════════════════════════════════════════════════════════

@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    admin = get_admin_session(request)
    if admin:
        return RedirectResponse("/admin", status_code=302)
    return templates.TemplateResponse("admin_login.html", {"request": request})


@app.post("/admin/login")
def admin_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    admin = authenticate_admin(db, email, password)
    if not admin:
        return templates.TemplateResponse("admin_login.html", {
            "request": request, "error": "البريد الإلكتروني أو كلمة المرور غير صحيحة",
        })
    token = create_session(admin)
    response = RedirectResponse("/admin", status_code=302)
    response.set_cookie("session_token", token, httponly=True, max_age=settings.SESSION_EXPIRE_HOURS * 3600)
    return response


@app.get("/admin/logout")
def admin_logout(request: Request):
    token = request.cookies.get("session_token")
    if token:
        destroy_session(token)
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("session_token")
    return response


# ══════════════════════════════════════════════════════════════
#  ADMIN PAGES
# ══════════════════════════════════════════════════════════════

def require_admin(request: Request):
    admin = get_admin_session(request)
    if not admin:
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
    return admin


@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db)):
    admin = get_admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    brands = db.query(Brand).all()
    return templates.TemplateResponse("admin_home.html", {
        "request": request, "admin": admin, "brands": brands,
    })


# ── Change Password ──────────────────────────────────────────
@app.get("/admin/password", response_class=HTMLResponse)
def change_password_page(request: Request):
    admin = get_admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    return templates.TemplateResponse("admin_password.html", {
        "request": request, "admin": admin,
    })


@app.post("/admin/password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    session = get_admin_session(request)
    if not session:
        return RedirectResponse("/admin/login", status_code=302)

    admin = db.query(Admin).get(session["admin_id"])
    from app.services.auth import verify_password
    if not verify_password(admin.password_hash, current_password):
        return templates.TemplateResponse("admin_password.html", {
            "request": request, "admin": session, "error": "كلمة المرور الحالية غير صحيحة",
        })

    admin.password_hash = hash_password(new_password)
    db.commit()
    return templates.TemplateResponse("admin_password.html", {
        "request": request, "admin": session, "success": "تم تغيير كلمة المرور بنجاح",
    })


# ══════════════════════════════════════════════════════════════
#  STORE MAPPINGS CRUD
# ══════════════════════════════════════════════════════════════

@app.get("/admin/stores", response_class=HTMLResponse)
def stores_page(request: Request, db: Session = Depends(get_db)):
    admin = get_admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    mappings = db.query(StoreMapping).all()
    brands = db.query(Brand).all()
    return templates.TemplateResponse("admin_stores.html", {
        "request": request, "admin": admin, "mappings": mappings, "brands": brands,
    })


@app.post("/admin/stores/add")
def add_store_mapping(
    request: Request,
    brand_id: int = Form(...),
    crm_store_name: str = Form(...),
    external_postgres_id: int = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = get_admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)

    mapping = StoreMapping(
        brand_id=brand_id,
        crm_store_name=crm_store_name,
        external_postgres_id=external_postgres_id,
        notes=notes,
    )
    db.add(mapping)
    db.commit()
    return RedirectResponse("/admin/stores", status_code=302)


@app.post("/admin/stores/delete/{mapping_id}")
def delete_store_mapping(mapping_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    mapping = db.query(StoreMapping).get(mapping_id)
    if mapping:
        db.delete(mapping)
        db.commit()
    return RedirectResponse("/admin/stores", status_code=302)


@app.post("/admin/stores/edit/{mapping_id}")
def edit_store_mapping(
    mapping_id: int,
    request: Request,
    crm_store_name: str = Form(...),
    external_postgres_id: int = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = get_admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    mapping = db.query(StoreMapping).get(mapping_id)
    if mapping:
        mapping.crm_store_name = crm_store_name
        mapping.external_postgres_id = external_postgres_id
        mapping.notes = notes
        db.commit()
    return RedirectResponse("/admin/stores", status_code=302)


# ══════════════════════════════════════════════════════════════
#  SKU RULES CRUD
# ══════════════════════════════════════════════════════════════

@app.get("/admin/sku-rules", response_class=HTMLResponse)
def sku_rules_page(request: Request, db: Session = Depends(get_db)):
    admin = get_admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    rules = db.query(SkuRule).all()
    brands = db.query(Brand).all()
    return templates.TemplateResponse("admin_sku_rules.html", {
        "request": request, "admin": admin, "rules": rules, "brands": brands,
    })


@app.post("/admin/sku-rules/add")
def add_sku_rule(
    request: Request,
    brand_id: int = Form(...),
    sku_pattern: str = Form(...),
    target_field: str = Form(...),
    multiplier: int = Form(1),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    admin = get_admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    rule = SkuRule(
        brand_id=brand_id,
        sku_pattern=sku_pattern,
        target_field=target_field,
        multiplier=multiplier,
        description=description,
    )
    db.add(rule)
    db.commit()
    return RedirectResponse("/admin/sku-rules", status_code=302)


@app.post("/admin/sku-rules/delete/{rule_id}")
def delete_sku_rule(rule_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    rule = db.query(SkuRule).get(rule_id)
    if rule:
        db.delete(rule)
        db.commit()
    return RedirectResponse("/admin/sku-rules", status_code=302)


@app.post("/admin/sku-rules/edit/{rule_id}")
def edit_sku_rule(
    rule_id: int,
    request: Request,
    sku_pattern: str = Form(...),
    target_field: str = Form(...),
    multiplier: int = Form(1),
    description: str = Form(""),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
):
    admin = get_admin_session(request)
    if not admin:
        return RedirectResponse("/admin/login", status_code=302)
    rule = db.query(SkuRule).get(rule_id)
    if rule:
        rule.sku_pattern = sku_pattern
        rule.target_field = target_field
        rule.multiplier = multiplier
        rule.description = description
        rule.is_active = is_active
        db.commit()
    return RedirectResponse("/admin/sku-rules", status_code=302)
